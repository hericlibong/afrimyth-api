# Rapport — Phase 2, incrément 2 : référentiels métier

- **Date :** 16 octobre 2026
- **Dépôt :** `afrimyth-api`
- **Branche :** `main`
- **Statut :** revue validée, corrections intégrées, clôture documentaire préparée ; non committé

## 1. Objectif et périmètre

Ajouter les quatre référentiels validés par l'ADR 0002 — `CulturalArea`,
`Country`, `Ethnicity`, `Domain` — les relier à `Entity`, et les rendre
administrables et visibles dans l'API de détail.

Hors périmètre, conformément au prompt :

- import du corpus V2, même pilote ;
- `variant_of`, `EntityRelation`, `Source` ;
- workflow de modération, propriété, champs de suppression logique ;
- endpoints autonomes de référentiel ;
- CRUD : l'API reste publique et strictement en lecture seule.

Aucune décision métier n'a été rouverte, aucune nouvelle ADR créée, aucune
tâche de roadmap cochée.

## 2. État Git

### Initial

```
# afrimyth-api
## main...origin/main
(arbre propre)

# django-portfolio
## main...origin/main
?? docs/prompts/phase-2-increment-2-referentiels.md
```

### Final

```
# afrimyth-api
 M mythology/admin.py
 M mythology/models.py
 M mythology/serializers.py
 M mythology/tests/factories.py
 M mythology/tests/test_api.py
 M mythology/views.py
?? docs/reports/phase-2-increment-2-referentiels.md
?? mythology/migrations/0003_domain_country_entity_primary_country_and_more.py
?? mythology/tests/test_reference.py

# django-portfolio
?? docs/prompts/phase-2-increment-2-referentiels.md
```

Aucun commit, aucun push, aucun `git add` : l'index est vide, vérifié par
`git diff --cached --name-only`. L'historique publié n'a pas été touché.

`git check-ignore` confirme que `.env`, `.venv/`, `.pytest_cache/`,
`.mypy_cache/` et `.ruff_cache/` sont ignorés. `_audit/` et `.claude/` sont
couverts par le `.gitignore` de `django-portfolio` et n'apparaissent pas.

## 3. Fichiers créés ou modifiés

**Créés**

- `mythology/migrations/0003_domain_country_entity_primary_country_and_more.py`
  — générée par `makemigrations`
- `mythology/tests/test_reference.py` — 25 tests
- `docs/reports/phase-2-increment-2-referentiels.md` — ce rapport

**Modifiés**

- `mythology/models.py` — `CulturalAreaKind`, `CulturalArea`, `Country`,
  `Ethnicity`, `Domain`, et les sept relations de `Entity`
- `mythology/admin.py` — quatre admins de référentiel, `EntityAdmin` enrichi
- `mythology/serializers.py` — quatre serializers de référence, détail élargi
- `mythology/views.py` — `select_related` et `prefetch_related` du `retrieve`
- `mythology/tests/factories.py` — quatre constructeurs de référentiel
- `mythology/tests/test_api.py` — tests des référentiels dans l'API, et mise
  à jour du test de requêtes existant (voir section 9)

Aucun fichier hors périmètre touché. Aucun package ni app supplémentaire :
les quatre modèles vivent dans `mythology`, et aucun modèle abstrait n'a été
introduit pour factoriser `name` et `slug`.

## 4. Schéma retenu

### `CulturalArea`

| Champ | Type |
|---|---|
| `name` | `CharField(max_length=255, unique=True)` |
| `slug` | `SlugField(max_length=255, unique=True)` |
| `kind` | `CharField(max_length=20, choices=CulturalAreaKind.choices)` |
| `parent` | `ForeignKey("self", PROTECT, related_name="children", null=True, blank=True)` |

`CulturalAreaKind` porte les valeurs techniques anglaises et leurs libellés
publics : `african_region` / `African region`, `transregional` /
`Transregional`, `diasporic` / `Diasporic`.

Deux barrières contre l'auto-parentage, de portées différentes :

- `CheckConstraint(condition=~Q(parent=F("id")), name="cultural_area_parent_is_not_self")`
  — **garantie en base**, s'applique même à un `save()` direct ;
- `clean()` — produit un message lisible dans un formulaire plutôt qu'une
  `IntegrityError`. À lui seul, il ne garantirait rien.

Les cycles indirects — A → B → A — ne sont **pas** détectés : ce serait un
moteur d'arbre, hors périmètre.

### `Country`

| Champ | Type |
|---|---|
| `name` | `CharField(max_length=255, unique=True)` |
| `slug` | `SlugField(max_length=255, unique=True)` |
| `iso_code` | `CharField(max_length=2, blank=True)` |

**Représentation du code facultatif.** Le code absent est la chaîne vide, pas
`NULL`. L'unicité « lorsqu'il est renseigné » est donc portée par
`UniqueConstraint(fields=["iso_code"], condition=~Q(iso_code=""),
name="unique_country_iso_code_when_set")`. Autant de pays sans code peuvent
coexister, et il n'y a qu'une seule représentation de l'absence — ce qui évite
le problème relevé sur `CreatureProfile.threat_level` à l'incrément précédent,
où `NULL` et `""` restent tous deux possibles.

**Normalisation et validation, de portées différentes :**

- la normalisation — `strip()` puis `upper()` — est faite dans `save()`, donc
  elle s'applique à `save()` et `objects.create(iso_code="ng")` ;
  `QuerySet.update()`, `bulk_create()` et `bulk_update()` contournent `save()` ;
- le contrôle de format — exactement deux lettres ASCII de A à Z — n'est appliqué que
  par `clean()`, donc par `full_clean()`, les formulaires et l'administration.
  `objects.create(iso_code="N1")` passerait : la seule barrière de base est la
  longueur maximale de deux caractères. Ce point est signalé dans la docstring
  et dans le test correspondant.

Aucune dépendance externe n'a été ajoutée : pas de liste ISO embarquée. Le
modèle ne garantit donc pas que le code existe réellement, seulement qu'il a
la forme attendue. `Country` ne doit contenir que de véritables pays —
`Pan-African`, `Congo Basin` et `Diaspora` relèvent de `CulturalArea` — mais
c'est une règle éditoriale, non contrainte par le schéma.

### `Ethnicity`

| Champ | Type |
|---|---|
| `name` | `CharField(max_length=255, unique=True)` |
| `slug` | `SlugField(max_length=255, unique=True)` |
| `primary_cultural_area` | `ForeignKey(CulturalArea, PROTECT, related_name="ethnicities", null=True, blank=True)` |

### `Domain`

| Champ | Type |
|---|---|
| `name` | `CharField(max_length=255, unique=True)` |
| `slug` | `SlugField(max_length=255, unique=True)` |

Les quatre modèles ont `ordering = ["name"]`, un `__str__` renvoyant le nom, et
des `verbose_name` français — la normalisation en anglais des libellés publics
est une tâche de roadmap, inscrite au titre de l'ADR 0003.

### Relations ajoutées à `Entity`

| Champ | Type | `related_name` |
|---|---|---|
| `primary_country` | `FK(Country, PROTECT, null, blank)` | `entities_as_primary_country` |
| `secondary_countries` | `M2M(Country, blank)` | `entities_as_secondary_country` |
| `primary_ethnicity` | `FK(Ethnicity, PROTECT, null, blank)` | `entities_as_primary_ethnicity` |
| `secondary_ethnicities` | `M2M(Ethnicity, blank)` | `entities_as_secondary_ethnicity` |
| `primary_cultural_area` | `FK(CulturalArea, PROTECT, null, blank)` | `entities_as_primary_area` |
| `secondary_cultural_areas` | `M2M(CulturalArea, blank)` | `entities_as_secondary_area` |
| `domains` | `M2M(Domain, blank)` | `entities` |

Les `related_name` distinguent explicitement l'ancrage du rattachement
secondaire, ce qu'un test vérifie : un même pays peut être l'ancrage d'une
entité et le rattachement secondaire d'une autre sans ambiguïté.

Aucun index manuel sur les trois `primary_*` — Django indexe déjà les clés
étrangères — et aucune table de liaison explicite, les relations multiples ne
portant aucune donnée propre.

### Règle non appliquée, et pourquoi

L'ADR 0002 veut qu'une même valeur ne soit pas simultanément ancrage principal
et rattachement secondaire. **Cette règle n'est imposée nulle part dans cet
incrément.** Un `Model.clean()` ne la couvrirait pas : les sélections
plusieurs-à-plusieurs de l'administration sont enregistrées après la
validation de l'instance, si bien qu'une valeur secondaire nouvellement
cochée échapperait au contrôle. Prétendre la garantir avec une validation
incomplète serait trompeur, et aucun signal global n'a été ajouté pour autant.

Son application appartiendra aux services d'import et d'écriture, avant
l'ouverture du CRUD. Un test — `test_meme_valeur_principale_et_secondaire_n_est_pas_bloquee`
— fixe le comportement réel, afin que la situation soit constatée dès
maintenant plutôt que découverte plus tard.

## 5. Migration et base de développement

Une seule migration pour cet incrément :
`0003_domain_country_entity_primary_country_and_more`, générée par Django.

```
+ Create model Domain
+ Create model Country
+ Add field primary_country to entity
+ Add field secondary_countries to entity
+ Create model CulturalArea
+ Add field primary_cultural_area to entity
+ Add field secondary_cultural_areas to entity
+ Add field domains to entity
+ Create model Ethnicity
+ Add field primary_ethnicity to entity
+ Add field secondary_ethnicities to entity
+ Create constraint cultural_area_parent_is_not_self on model culturalarea
```

Tous les nouveaux champs de `Entity` sont facultatifs — `null=True` sur les
trois clés étrangères, `blank=True` sur les quatre relations multiples — donc
aucune migration de données n'a été nécessaire.

Appliquée sur PostgreSQL 16, puis vérifiée :

- `shango` existe toujours : `Shango`, type `divinity`, genre `male` ;
- ses données sont intactes, dont `symbols = ['Hache à double tranchant', 'Foudre']` ;
- ses horodatages sont restés au **13 octobre 2026**, preuve que la ligne n'a
  pas été réécrite par la migration ;
- ses sept nouveaux champs sont vides : trois ancrages `None`, quatre
  collections vides ;
- une seule entité en base, et les quatre tables de référentiel sont **vides** :
  aucune donnée de démonstration n'a été créée dans la base de développement.

La capture du JSON de la section 6 a été obtenue dans une **base de test
jetable**, créée puis détruite par le script, afin de ne rien écrire en
développement.

## 6. Forme exacte du JSON de détail

`GET /api/entities/shango/` pour une entité entièrement rattachée :

```json
{
  "id": "8a71ca00-f976-4d34-82b1-9b8a327e2ca6",
  "slug": "shango",
  "name": "Shango",
  "entity_type": "divinity",
  "category": "Orisha of Lightning",
  "gender": "male",
  "cultural_role": "Thunder deity",
  "alignment": "",
  "story_description": "Récit du dieu du tonnerre.",
  "characteristics": [],
  "physical_signs": [],
  "symbols": ["Double-headed axe"],
  "power_objects": [],
  "symbolic_animals": [],
  "manifestations": "",
  "primary_country": {
    "id": 1, "slug": "nigeria", "name": "Nigeria", "iso_code": "NG"
  },
  "secondary_countries": [
    { "id": 2, "slug": "benin", "name": "Benin", "iso_code": "BJ" }
  ],
  "primary_ethnicity": { "id": 1, "slug": "yoruba", "name": "Yoruba" },
  "secondary_ethnicities": [{ "id": 2, "slug": "fon", "name": "Fon" }],
  "primary_cultural_area": {
    "id": 1, "slug": "west-africa", "name": "West Africa",
    "kind": "african_region"
  },
  "secondary_cultural_areas": [
    {
      "id": 2, "slug": "caribbean-diaspora", "name": "Caribbean diaspora",
      "kind": "diasporic"
    }
  ],
  "domains": [
    { "id": 2, "slug": "justice", "name": "Justice" },
    { "id": 1, "slug": "thunder", "name": "Thunder" }
  ],
  "created_at": "2026-10-16T12:43:54.719095Z",
  "updated_at": "2026-10-16T12:43:54.719095Z",
  "divinity_profile": {
    "cult_offerings": ["Yam"],
    "cult_taboos": ["Lying"],
    "cult_rituals": [],
    "cult_places": [],
    "cult_festivals": []
  },
  "hero_profile": null,
  "creature_profile": null
}
```

Sans aucun rattachement, les trois ancrages valent `null` et les quatre
collections sont des listes vides ; les clés sont toujours présentes.

**Représentations de référence.** Socle commun `id`, `slug`, `name` ;
`Country` ajoute `iso_code` ; `CulturalArea` ajoute `kind`. `Ethnicity` et
`Domain` restent sur le socle. Ni `parent`, ni `children`, ni le
`primary_cultural_area` d'une ethnie ne sont imbriqués — un test le vérifie,
pour éviter les cascades de sérialisation.

**Liste inchangée.** `GET /api/entities/` conserve exactement son contrat :
`id`, `slug`, `name`, `entity_type`, `category`. Un test de non-régression le
confirme sur une entité entièrement rattachée.

## 7. Nombre de requêtes

`retrieve` applique `select_related` sur les trois profils et les trois
ancrages principaux, puis `prefetch_related` sur les quatre collections. Le
queryset de la liste n'a pas été modifié.

| Cas | Attendu | Mesuré |
|---|---|---|
| Détail d'une entité entièrement rattachée, profil inclus | 5 | 5 |
| Détail d'une entité sans aucun rattachement, par type | 5 | 5 |

Décompte : **1** requête pour l'entité, qui ramène par jointure les trois
profils et les trois ancrages, puis **4** requêtes, une par collection
préchargée.

Le comptage global fixe un budget de cinq requêtes. Sur une seule entité,
retirer le préchargement d'une collection ne change pas nécessairement ce
budget : la lecture de cette collection demande aussi une seule requête,
quel que soit son nombre d'éléments. Un test complémentaire évalue le queryset
réel de la vue puis vérifie que le serializer ne déclenche aucune requête.
Ce test détecte un préchargement manquant. Ces contrôles ne constituent pas
une promesse générale de performance.

## 8. Tests

73 cas de test dans le dépôt après correction, dont 34 ajoutés par cet incrément.

**`mythology/tests/test_reference.py` — 29 cas exécutés après correction**

- création et représentation des quatre référentiels, accès inverse
  `area.ethnicities` ;
- hiérarchie `parent` / `children` d'une aire ;
- unicité du nom et du slug d'un pays, en deux cas paramétrés ;
- unicité du nom des trois autres référentiels ;
- les trois valeurs de `CulturalArea.kind` acceptées par `full_clean()` ;
- une valeur de `kind` inconnue rejetée par `full_clean()` ;
- auto-parentage refusé par `full_clean()` **et** par la contrainte de base,
  en deux tests distincts, parce que les deux portées diffèrent ;
- normalisation de `iso_code` en majuscules, vérifiée après
  `refresh_from_db()` donc sur la valeur réellement stockée ;
- format de `iso_code` rejeté par `full_clean()`, avec la portée exacte dans
  la docstring ;
- plusieurs pays sans code ISO acceptés ; code renseigné unique ;
- `ProtectedError` à la suppression d'un pays, d'une ethnie ou d'une aire
  servant d'ancrage principal, d'une aire parente, et de l'aire principale
  d'une ethnie ;
- un domaine seulement rattaché en secondaire reste supprimable, le lien
  disparaissant — `ManyToManyField` n'accepte pas `on_delete` ;
- coexistence des trois ancrages et des quatre collections ;
- plusieurs valeurs par collection ;
- `related_name` distinguant ancrage et rattachement secondaire ;
- entité sans aucun rattachement ;
- règle « principal ≠ secondaire » non bloquée, comportement documenté.

**`mythology/tests/test_api.py` — 5 tests ajoutés après correction**

- liste n'exposant aucun référentiel, sur une entité entièrement rattachée ;
- détail exposant les sept clés, avec le jeu de clés exact de chaque
  représentation de référence et l'ordre des collections ;
- détail sans rattachement : ancrages `null`, collections vides ;
- détail n'imbriquant ni `parent`, ni `children`, ni l'aire d'une ethnie ;
- plus le test de requêtes de la section 7.

**Non-régression** — les 39 tests antérieurs passent sans modification, à
l'exception du seul test de comptage de requêtes, dont le nombre attendu a
changé pour une raison expliquée en section 9. Les profils de divinité, de
héros et de créature conservent leur comportement.

## 9. Divergences avec le prompt

Une seule, assumée et nécessaire.

**Le test de requêtes de l'incrément précédent a été modifié.**
`test_detail_charge_les_trois_profils_en_une_requete` attendait **1** requête.
L'ajout de quatre `prefetch_related` en porte le total à **5**, car Django les
exécute même lorsque les collections sont vides. Le test a donc été renommé
`test_detail_a_un_cout_constant_quel_que_soit_le_type` et son attente portée à
5, avec une docstring expliquant le décompte.

Le détail d'une entité sans rattachement coûte désormais cinq requêtes,
car il expose quatre nouvelles collections. Pour cette unique entité,
précharger ces collections ne réduit pas nécessairement le total par rapport
à leur chargement à la demande. Le préchargement les rend disponibles avant
la sérialisation ; son intérêt pour éviter un N+1 se manifeste lorsqu'on
sérialise plusieurs entités avec leurs collections. La liste actuelle reste
compacte et n'expose pas ces collections.

Aucune autre divergence : les sept relations demandées sont exactement celles
implémentées, aucune app ni modèle abstrait n'a été ajouté, aucun endpoint de
référentiel n'a été créé, et la tâche de roadmap n'a pas été cochée.

## 10. Commandes de contrôle

| Commande | Sortie | Code |
|---|---|---|
| `python manage.py check` | `System check identified no issues (0 silenced).` | 0 |
| `python manage.py makemigrations --check --dry-run` | `No changes detected` | 0 |
| `python manage.py showmigrations mythology` | `[X] 0001_initial`, `[X] 0002_creatureprofile_heroprofile`, `[X] 0003_domain_country_entity_primary_country_and_more` | 0 |
| `pytest` | `73 passed in 3.31s` après correction Codex | 0 |
| `ruff check .` | `All checks passed!` | 0 |
| `ruff format --check .` | `28 files already formatted` | 0 |
| `mypy .` | `Success: no issues found in 28 source files` | 0 |

Trois avertissements de Ruff ont été traités en cours de route, aucun n'étant
laissé en suspens : `DJ012` sur l'ordre des méthodes de `Country` — `save()`
doit précéder les méthodes personnalisées, dont `clean()` — un faux positif
`SIM300` sur une comparaison d'ensembles, réécrite dans l'autre sens, et un
import devenu inutile. `ruff format` a été appliqué sur deux fichiers de test
avant de relancer les contrôles.

## 11. Administration

Les quatre référentiels sont enregistrés, avec recherche sur `name` et `slug`,
`prepopulated_fields` du slug depuis le nom, et les relations utiles en
colonne : `kind` et `parent` pour `CulturalArea`, `iso_code` pour `Country`,
`primary_cultural_area` pour `Ethnicity`. Filtres sur `kind` pour les aires et
sur `primary_cultural_area__kind` pour les ethnies. `parent` et
`primary_cultural_area` passent par `autocomplete_fields`.

`EntityAdmin` affiche `primary_country` et `primary_ethnicity` en colonnes,
filtre sur `primary_cultural_area__kind`, place les trois ancrages en
`autocomplete_fields` et les quatre collections en `filter_horizontal`. Le
formulaire reste celui de Django, sans personnalisation.

## 12. Limites volontairement reportées

- **Règle « principal ≠ secondaire »** — non imposée, voir section 4. Reviendra
  avec les services d'import et d'écriture, avant le CRUD.
- **Cohérence `entity_type` / profil** — toujours non garantie : `clean()`
  empêche un mauvais rattachement, `objects.create()` ne le déclenche pas.
- **Validité réelle des codes ISO** — seul le format est contrôlé, et seulement
  par `full_clean()`. Aucune liste de référence n'est embarquée.
- **Cycles indirects d'aires culturelles** — non détectés.
- **Contenu éditorial de `Country`** — l'exclusion des pseudo-pays est une
  règle de l'ADR 0002, appliquée à la saisie et à l'import, pas par le schéma.
- **Endpoints de référentiel** — aucun, en attente d'un besoin client confirmé
  lors de la stabilisation de l'API publique.
- **`variant_of`, `EntityRelation`, `Source`, workflow, suppression logique** —
  incréments suivants de la phase 2.
- **Import du corpus V2** — phases 2 et 5.
- **Libellés publics en français** — `verbose_name` et libellés de choix des
  modèles peuvent rester en français ; `CulturalAreaKind` a déjà ses libellés
  en anglais. Leur
  normalisation en anglais est une tâche de roadmap inscrite au titre de
  l'ADR 0003, à traiter avant la stabilisation du contrat public. Les valeurs
  techniques exposées par l'API, elles, sont bien en anglais.

## 13. Petites corrections de revue appliquées par Codex

Corrections réalisées directement avec l'autorisation de l'auteur :

- `Country.clean_fields()` normalise le code avant le contrôle de longueur :
  `full_clean()` accepte désormais `" ng "` et conserve `"NG"`.
- `Country.clean()` exige deux lettres ASCII de A à Z. Les codes accentués,
  numériques, trop courts ou trop longs sont couverts par les tests.
- La documentation limite la garantie de normalisation aux écritures passant
  par `save()` ; les opérations en masse et `QuerySet.update()` le contournent.
- Le test de budget de cinq requêtes est conservé. Un nouveau test utilise
  le queryset réel de la vue et impose zéro requête pendant la sérialisation
  de l'entité préchargée. L'explication erronée du gain de requêtes sur une
  seule entité est corrigée dans les tests et les sections 7 et 9.

Vérifications après correction : 73 tests réussis ; Ruff, formatage et mypy
validés ; contrôle Django sans problème ; aucune migration supplémentaire
détectée. L'exécution Python a nécessité une sortie du bac à sable pour
accéder à l'interpréteur Windows existant, sans modifier l'environnement.

Les fichiers supplémentaires modifiés par la revue sont `mythology/models.py`,
`mythology/tests/test_reference.py`, `mythology/tests/test_api.py` et ce rapport,
tous déjà dans le périmètre de l'incrément. Aucun commit ni push réalisé.

## 14. Clôture de revue — géographie et répartition du travail

La revue pédagogique a précisé l'usage de `CulturalArea` : `kind` distingue
la nature de l'aire et `parent` porte sa hiérarchie. Les quatre régions
continentales du périmètre sont `West Africa`, `Central Africa`, `East Africa`
et `Southern Africa`, toutes de type `african_region`, sans parent. Le Nord
reste hors périmètre actuel, sans être interdit par le schéma.

`Congo Basin` est une sous-région de `Central Africa`, avec le même `kind`.
`Diaspora` est une entrée `diasporic` distincte des régions continentales ;
des destinations comme `Caribbean diaspora` peuvent lui être rattachées.
`Pan-African` reste `transregional`, sans rattachement arbitraire à une région.
Ces noms sont des données de référence, pas des valeurs de choix codées en dur.
Leur création est prévue à l'import pilote et le regroupement pour la carte
à l'intégration V2. Aucun de ces traitements n'a été exécuté pendant la clôture.

La précision est consignée dans l'ADR 0002, section 3, du dépôt de pilotage.
La tâche des référentiels est cochée dans la roadmap ; le reste de la phase 2
reste ouvert. `django-portfolio/AGENTS.md` consigne la répartition validée :
Codex évalue et applique les petites corrections ; Claude CLI réalise les
tâches complètes et les corrections importantes à partir d'un prompt revu.

Fichiers de pilotage ajoutés ou modifiés pour cette clôture : `AGENTS.md`,
`docs/adr/0002-decisions-structurantes-phase-0.md`, `docs/roadmap-projet-1.md`,
et `docs/prompts/phase-2-increment-2-cloture.md`. Le prompt initial
`docs/prompts/phase-2-increment-2-referentiels.md` reste également à committer.
La section 2 conserve la capture Git de fin d'implémentation par Claude ;
elle précède ces ajouts de revue et de clôture. Le rapport temporaire de
clôture consignera l'état Git réel après les commits.

Ces ajouts sont documentaires. Ils ne changent ni le code validé ni le schéma.
Aucun commit ni push effectué par Codex.
