# Rapport — Phase 3, incrément 1 : visibilité et contrat de lecture

- **Date :** 21 octobre 2026
- **Dépôt :** `afrimyth-api`
- **Branche :** `main`
- **Statut :** implémentation terminée, non committée, en attente de revue

## 1. Objectif et périmètre

Rendre l'API publique conforme à sa vocation : n'exposer que les fiches
publiées et non supprimées, ainsi que leurs références autorisées, avec des
réponses stables et des messages en anglais.

Hors périmètre : pagination, filtres et recherche (incrément 2), OpenAPI avec
Swagger ou ReDoc (incrément 3), CRUD et workflow (phase 4).

La roadmap n'a **pas** été cochée, rien n'a été committé ni poussé. Les
modifications documentaires présentes dans `django-portfolio` — roadmap et
`docs/notes/` — appartiennent à Codex et n'ont pas été touchées.

## 2. Fichiers modifiés

**Créés**

- `mythology/selectors.py` — la sélection publique centralisée
- `mythology/migrations/0007_alter_country_options_alter_creatureprofile_options_and_more.py`
  — migration de métadonnées, générée par Django
- `mythology/tests/test_public_visibility.py` — 22 cas
- `docs/reports/phase-3-increment-1-public-read-contract.md` — ce rapport

**Modifiés**

- `mythology/views.py` — branchement sur les sélecteurs, docstrings
  actualisées
- `mythology/serializers.py` — gardes de visibilité sur `variant_of` et
  `relations`, contrat d'utilisation documenté
- `mythology/models.py` — libellés publics en anglais : choix, `verbose_name`,
  `help_text`, `__str__` des profils, message de validation
- `config/settings.py` — `LANGUAGE_CODE = "en-us"`
- `README.md` — section « Public read API » en anglais
- `CLAUDE.md` — mention de `selectors.py` dans la règle de fonctions métier
- `mythology/tests/factories.py` — ajout de `create_published_entity()` et
  `publish()`
- `mythology/tests/test_api.py`, `test_models.py`, `test_profiles.py`,
  `test_pilot_import.py` — adaptation aux nouveaux comportements

Aucun manager n'a été modifié, aucune donnée de développement touchée.

## 3. La sélection publique et son contrat réutilisable

`mythology/selectors.py` regroupe la sélection et les gardes de visibilité :

```python
PUBLIC_FILTER = Q(status=EntityStatus.PUBLISHED, deleted_at__isnull=True)

def public_entities() -> QuerySet[Entity]: ...
def public_relations() -> QuerySet[EntityRelation]: ...
def public_entity_detail() -> QuerySet[Entity]: ...
def is_publicly_visible(entity: Entity | None) -> bool: ...
```

| Fonction | Rôle |
|---|---|
| `public_entities()` | fiches publiées et non supprimées — base de la liste |
| `public_relations()` | relations exposables : cible publique **ou** lien non résolu |
| `public_entity_detail()` | `public_entities()` + jointures + préchargements filtrés |
| `is_publicly_visible()` | même règle évaluée en Python, pour les gardes du serializer |

**Les deux conditions sont nécessaires.** Une fiche supprimée reste
`published` — c'est la décision 7 de l'ADR 0002, qui sépare état éditorial et
suppression logique. Filtrer sur le seul statut laisserait donc passer les
fiches supprimées.

**La règle ne dépend pas de l'appelant** : anonyme, connecté ou
superutilisateur obtiennent la même chose. Ces routes sont publiques, pas des
routes privées de gestion ; l'administration reste le chemin d'accès aux
fiches non publiées.

**Préparation de la phase 4.** La sélection privée pourra s'ajouter à côté de
`public_entities()`, en conservant la structure des représentations liste/détail.
La visibilité des références privées devra toutefois être définie explicitement
en phase 4 : les gardes actuelles du serializer appliquent toujours la règle
publique. Un simple changement du queryset ne suffit donc pas à exposer des
références privées à un relecteur habilité.

**Les managers conservent leur portée**, ce qu'un test vérifie explicitement
sur trois fiches — un brouillon, une publiée supprimée, une publiée :

| | Fiches vues |
|---|---|
| `Entity.objects` | 3 — toutes |
| `Entity.active` | 2 — hors suppression logique |
| `public_entities()` | 1 — règle publique |

La visibilité éditoriale n'a donc **pas** été poussée dans un manager, et
l'administration garde son queryset complet.

## 4. Règles appliquées aux références imbriquées

### `variant_of`

Objet synthétique à quatre champs si la référence est publique, `null`
sinon. Une référence masquée ne laisse filtrer ni identifiant, ni slug, ni
nom, ni type : trois tests le vérifient sur la charge utile **brute**, pour
les statuts `draft`, `submitted` et `rejected`, ainsi que pour une référence
supprimée.

### `relations`

| Cas | Comportement |
|---|---|
| cible résolue publique | lien conservé, cible en référence synthétique, `to_name=""` |
| lien déjà non résolu (`to_entity=null`) | conservé tel quel |
| cible résolue non publiée | lien **entièrement omis** |
| cible résolue supprimée | lien **entièrement omis** |

Un lien omis disparaît avec son `id`, son `kind` et ses `notes`. Son nom
n'est **pas** recopié dans `to_name` — ce qui reviendrait à republier la
cible masquée sous une autre forme. Un test vérifie que même le `kind` du
lien masqué n'apparaît pas dans la réponse.

Un `to_name` saisi comme cible absente n'est pas rapproché d'une fiche privée
homonyme : il reste exposé tel quel, et la fiche privée reste invisible. Un
test couvre ce cas, qui est exactement celui du lien `Shango` du pilote.

Aucune imbrication récursive : une cible publique n'est rendue que par la
référence à quatre champs existante.

### Choix technique retenu

**Filtrage en base pour le coût, garde en Python pour la sûreté.**

- `public_entity_detail()` précharge les relations sortantes avec le queryset
  **déjà filtré** de `public_relations()`, et joint `variant_of` ;
- `EntityDetailSerializer` applique en plus `is_publicly_visible()` sur
  `variant_of` et sur chaque cible de relation.

Cette redondance est volontaire. Le prompt demandait d'éviter « un chemin de
repli utilisant les relations non filtrées » : avec le seul filtrage de
queryset, un appel du serializer sur un queryset nu — test, futur appel
interne, oubli — aurait republié les liens masqués. La garde ferme ce chemin.
Un test le démontre : sur `Entity.objects.get(...)`, sans aucun préchargement,
`variant_of` vaut toujours `null` et le lien vers la cible privée reste omis.

Aucune instance n'est mutilée en base pour masquer une référence.

**Contrat d'utilisation**, documenté dans la docstring du serializer : il est
sûr quel que soit le queryset, mais **gratuit** seulement sur
`public_entity_detail()`. Sur un queryset nu, le filtrage reste correct au
prix d'une requête par référence consultée.

## 5. Contrat et langue publique

Les clés de la liste et du détail sont **inchangées**. Les trois clés de
profil restent présentes, `variant_of` reste objet ou `null`, les collections
restent des listes éventuellement vides, sources et référentiels gardent leur
forme. Les routes `/api/entities/` et `/api/entities/{slug}/`, leurs noms et
les UUID exposés sont conservés ; aucun slug n'a été renommé et aucun système
de routes n'a été ajouté.

Aucun compte, email, identité utilisateur, note de revue, statut interne ou
champ de suppression n'est exposé — les tests de non-divulgation de
l'incrément précédent sont conservés. Les écritures HTTP restent refusées.

### 404 indistinguable

Une fiche non publique et un slug inconnu renvoient le **même** statut et le
**même** corps :

```json
{"detail": "No Entity matches the given query."}
```

Un test compare les deux réponses et vérifie qu'aucun fragment — `draft`,
`status`, le slug ou le nom de la fiche masquée — n'apparaît.

### Normalisation en anglais

`LANGUAGE_CODE` passe de `fr-fr` à `en-us`. `TIME_ZONE` est inchangé, aucun
middleware de langue ni architecture i18n n'a été ajouté.

| Élément | Avant | Après |
|---|---|---|
| `EntityType` | Divinité, Héros, Créature | Divinity, Hero, Creature |
| `Gender` | Masculin, Féminin, Neutre, Androgyne, Fluide | Male, Female, Neutral, Androgynous, Fluid |
| `ThreatLevel` | Faible, Modéré, Élevé, Mythique | Low, Moderate, High, Mythic |
| `verbose_name` des 10 modèles | entité, pays, ethnie, profil de divinité… | entity, country, ethnicity, divinity profile… |
| `Entity.category.help_text` | « Sous-titre éditorial libre… » | "Free editorial subtitle…" |
| `__str__` des profils | « Profil de divinité — X » | "Divinity profile — X" |
| Erreur de rattachement de profil | « Un profil de divinité ne peut être rattaché… » | "A divinity profile can only be attached to an entity of type 'divinity'." |
| 404 / 405 de DRF | messages français | messages anglais |

`CulturalAreaKind`, `RelationKind`, `SourceKind` et `EntityStatus` étaient
déjà en anglais. Aucune valeur technique stockée n'a été renommée.

Les commentaires, docstrings internes, prompts et rapports restent en
français. Le corpus n'a été ni traduit ni reclassé.

## 6. Migration

`0007_alter_country_options_alter_creatureprofile_options_and_more`, générée
par Django et appliquée :

```
~ Change Meta options on country, creatureprofile, culturalarea,
  divinityprofile, domain, entity, entityrelation, ethnicity, heroprofile,
  source
~ Alter field threat_level on creatureprofile
~ Alter field category on entity
~ Alter field entity_type on entity
~ Alter field gender on entity
```

Ce sont uniquement des **métadonnées** : libellés de `Meta`, libellés de
choix et `help_text`. Aucune colonne, aucune contrainte, aucune valeur
stockée n'est modifiée. Aucune migration ancienne n'a été réécrite.

`showmigrations mythology` affiche les sept migrations en `[X]`, et
`makemigrations --check --dry-run` ne détecte plus aucun changement.

## 7. Tests

**286 cas exécutés**, soit une hausse nette de 29 par rapport aux 257 cas
précédents : 22 dans le nouveau module de visibilité et 7 supplémentaires
dans `test_api.py`. Les tests existants concernés sont également adaptés.

| Fichier | Cas |
|---|---|
| `mythology/tests/test_pilot_import.py` | 52 |
| `mythology/tests/test_api.py` | 50 |
| `mythology/tests/test_services.py` | 34 |
| `mythology/tests/test_relations.py` | 31 |
| `mythology/tests/test_reference.py` | 28 |
| `mythology/tests/test_sources.py` | 25 |
| `mythology/tests/test_editorial_fields.py` | 22 |
| `mythology/tests/test_public_visibility.py` | 22 |
| `mythology/tests/test_profiles.py` | 11 |
| `mythology/tests/test_models.py` | 7 |
| `tests/` (socle) | 4 |

### Comment les tests existants ont été adaptés

Le statut par défaut n'a **pas** été changé — ni dans les modèles, ni dans le
service, ni dans `create_entity()`, ni dans l'import. Deux outils ont été
ajoutés aux factories :

- `create_published_entity()` — crée une fiche publiée, pour les tests qui
  exercent la lecture publique ;
- `publish(entity)` — publie une fiche existante, utilisé après un import.

Les tests d'import continuent donc de vérifier la création en `draft`, puis
publient explicitement **dans la base de test** avant de lire l'API.

### Attentes obsolètes remplacées

| Ancien test | Devenu |
|---|---|
| `test_fiche_active_reste_accessible_quel_que_soit_son_statut` — tout statut lisible | `test_seule_une_fiche_publiee_est_visible` — seul `published` est lisible, 404 sinon |
| `test_cible_imbriquee_supprimee_reste_visible` — limite assumée | `test_cible_imbriquee_supprimee_est_masquee` — la limite est levée |
| 3 assertions de `__str__` en français | libellés anglais |

### Couverture ajoutée

Sélection centralisée : statuts non publiés exclus (paramétré), publiée
supprimée exclue, publiée active retenue, portée des trois managers,
filtrage de `public_relations()`, `is_publicly_visible()` sur les quatre cas.

Pas de contournement : utilisateur connecté, superutilisateur, administration
conservant ses accès.

404 indistinguable, messages anglais du 404 et des quatre 405, libellés de
choix et `verbose_name` anglais, message de validation anglais.

Références : variante non publiée (3 statuts), variante supprimée, variante
publiée exposée sans récursion, relations mélangées — publique, brouillon,
supprimée, non résolue — avec vérification du JSON brut, absence de
basculement en `to_name`, `to_name` homonyme d'une fiche privée conservé.

## 8. Budget de requêtes mesuré

Mesuré après coup, et non figé à l'avance, sur une entité entièrement reliée —
variante publique, trois relations dont une masquée et une non résolue, quatre
collections, profil, source :

| Cas | Mesuré |
|---|---|
| `GET /api/entities/{slug}/` | **7** requêtes |
| Sérialisation après évaluation de `public_entity_detail()` | **0** requête |
| `GET /api/entities/` | **1** requête |

Décompte du détail : 1 pour l'entité — qui ramène par jointure les trois
profils, les trois ancrages et `variant_of` — puis 6 préchargements : quatre
collections de référentiels, les relations filtrées et les sources.

Le budget est **inchangé** par rapport à l'incrément précédent : le filtrage
des relations est appliqué dans le queryset du `Prefetch`, donc sans requête
supplémentaire, et la garde du serializer travaille sur des objets déjà en
mémoire. Un test le vérifie explicitement : **masquer une référence ne coûte
aucune requête**, y compris quand la garde décide de masquer.

## 9. Données de développement — préservées

Relevé par lecture, sans aucune écriture :

```
anansi         hero      status=draft  deleted=None  created_by=None
mokele-mbembe  creature  status=draft  deleted=None  created_by=None
oya            divinity  status=draft  deleted=None  created_by=None
shango         divinity  status=draft  deleted=None  created_by=None

objects: 4   active: 4   public_entities(): 0
shango.symbols : ['Hache à double tranchant', 'Foudre']
oya.domains    : Cemeteries, Change, Storms, Transformation, Wind
relations: 3   country: 2  area: 6  ethnicity: 3  domain: 13
```

Aucune fiche n'a été publiée, aucun propriétaire attribué, aucune donnée
éditoriale modifiée. `shango` reste sans profil.

**Conséquence assumée et attendue** : la liste publique est vide et les URL du
pilote renvoient 404.

```
GET /api/entities/           → 200 []
GET /api/entities/oya/       → 404 {"detail": "No Entity matches the given query."}
GET /api/entities/anansi/    → 404 (idem)
GET /api/entities/mokele-mbembe/ → 404 (idem)
GET /api/entities/shango/    → 404 (idem)
POST / PUT / PATCH / DELETE  → 405 {"detail": "Method \"…\" not allowed."}
```

C'est le comportement correct d'une base ne contenant que des brouillons, et
non une régression. Le README le dit explicitement, afin qu'une collection
vide ne soit pas prise pour une panne.

## 10. Contrôles exécutés

| Commande | Sortie | Code |
|---|---|---|
| `python manage.py check` | `System check identified no issues (0 silenced).` | 0 |
| `python manage.py makemigrations --check --dry-run` | `No changes detected` | 0 |
| `pytest` | `286 passed in 25.40s` | 0 |
| `ruff check .` | `All checks passed!` | 0 |
| `ruff format --check .` | `39 files already formatted` | 0 |
| `mypy .` | `Success: no issues found in 39 source files` | 0 |

La migration générée a été appliquée, et `showmigrations mythology` la
confirme en `[X]`.

Une correction intermédiaire, suivie de la relance des seuls contrôles
affectés : cinq `E501` dans `test_api.py`, conséquence des remplacements
d'appels de factory, corrigés par `ruff format`. Aucune valeur du `.env`
n'est affichée.

## 11. Limites connues

- **Le texte public n'est pas censuré.** Les règles portent sur les
  références structurées. Un nom cité dans `story_description`, ou dans un
  `to_name` réellement saisi, reste visible : c'est un travail éditorial, pas
  un filtrage automatique. La note de revue du pilote le prévoit.
- **Le `to_name` n'est pas rapproché d'une fiche privée homonyme**, par
  choix : un lien non résolu reste non résolu, même si une fiche masquée
  porte ce nom.
- **Les relations entrantes et les variantes inverses** ne sont pas exposées,
  faute de besoin client établi.
- **La garde du serializer est correcte mais non gratuite** hors du queryset
  préparé : sur un queryset nu, elle coûte une requête par référence. La vue
  utilise toujours le queryset préparé.
- **Aucun cache**, aucune en-tête de cache HTTP : hors périmètre.

## 12. Travaux reportés

**Incrément 2 de la phase 3** — pagination, filtres et recherche. La note de
revue du pilote fixe déjà des contrats à préciser : portée du filtre pays
(principal et secondaires), prise en compte des sous-régions — `Congo Basin`
est enfant de `Central Africa` —, et absence de doublons dans les résultats
issus de relations multiples.

**Incrément 3 de la phase 3** — schéma OpenAPI, Swagger et ReDoc, avec
exemples de réponses et documentation des erreurs. Rien de tout cela n'existe
aujourd'hui.

**Phase 4** — JWT, groupes, permissions objet, CRUD, actions de transition,
attribution automatique du propriétaire, suppression logique et restauration.
La sélection privée s'ajoutera à côté de `public_entities()`, en conservant
la forme des réponses ; sa politique de références imbriquées devra être
explicitée, les gardes actuelles du serializer étant publiques.

**Travail éditorial, hors code** — publication des fiches du pilote, qui
restent en brouillon jusqu'à revue : classification d'Anansi, pays de
Mokele-mbembe, sources et corrections des trois fiches, selon
`docs/notes/revue-editoriale-corpus-pilote.md` du dépôt de pilotage.

## 13. État Git des deux dépôts

Aucun commit, aucun push, aucun `git add` : l'index est vide.

```
# afrimyth-api
## main...origin/main
 M CLAUDE.md
 M README.md
 M config/settings.py
 M mythology/models.py
 M mythology/serializers.py
 M mythology/views.py
 M mythology/tests/factories.py
 M mythology/tests/test_api.py
 M mythology/tests/test_models.py
 M mythology/tests/test_pilot_import.py
 M mythology/tests/test_profiles.py
?? docs/reports/phase-3-increment-1-public-read-contract.md
?? mythology/migrations/0007_alter_country_options_alter_creatureprofile_options_and_more.py
?? mythology/selectors.py
?? mythology/tests/test_public_visibility.py

# django-portfolio
## main...origin/main
 M docs/roadmap-projet-1.md
?? docs/notes/
?? docs/prompts/phase-3-increment-1-public-read-contract.md
```

Les trois entrées de `django-portfolio` sont les modifications documentaires
de Codex, **préservées sans y toucher**. Les deux branches sont `main` et
synchronisées avec `origin/main`. Après validation, Codex prendra en charge la
clôture documentaire et Git.

## 14. Relecture Codex

La lecture des sélecteurs, des serializers, de la vue, de la migration et
des tests n'a révélé aucun blocage fonctionnel par rapport au contrat public
demandé. Les copies du rapport sont identiques avant correction. Les
286 tests et les contrôles qualité sont les résultats exécutés par Claude ;
aucun changement de comportement n'est apporté pendant cette relecture.

Deux précisions documentaires : le total augmente de 29 cas (22 dans le
nouveau module, 7 dans le module API), et le futur accès privé de phase 4 ne
pourra pas se limiter à changer le queryset si ses références privées doivent
être rendues visibles. La structure de la réponse peut être conservée, mais
la politique des gardes de référence devra être explicite.

La liste publique vide et les 404 des brouillons sont attendus. Aucun statut
de développement n'est modifié pour la revue. La section 13 conserve l'état
antérieur aux ajouts de revue.

## 15. Validation et clôture — 21 octobre 2026

L'auteur confirme les vérifications pratiques : liste publique vide, détail
d'Oya en 404, fiche toujours visible dans l'administration. L'explication
pédagogique de la séparation entre base de travail et consultation publique
est validée. L'incrément est terminé ; la roadmap est actualisée et la
clôture comprend les commits et pushes normaux des deux dépôts.

Aucun changement fonctionnel depuis les 286 tests et contrôles de Claude :
ces résultats sont réutilisés. Le prochain incrément porte sur la pagination,
la recherche et les filtres, sans publication automatique du corpus pilote.
