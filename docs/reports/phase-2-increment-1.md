# Rapport — Phase 2, incrément 1 : `HeroProfile` et `CreatureProfile`

- **Date :** 15 octobre 2026
- **Dépôt :** `afrimyth-api`
- **Branche :** `main`
- **Statut :** incrément terminé, non committé

## 1. Objectif et périmètre

Compléter le modèle métier avec les deux profils manquants — héros et créature —
et les exposer en lecture, de sorte que les trois types d'entités disposent
d'un profil, d'une administration et d'une représentation détaillée.

Hors périmètre de cet incrément, et volontairement laissé aux suivants :

- référentiels `Country`, `Ethnicity`, `CulturalArea`, `Domain` et les
  relations `primary_*` / `secondary_*` de `Entity` ;
- `EntityRelation`, `variant_of` et `Source` ;
- service garantissant qu'une entité possède **exactement** un profil ;
- champs de propriété, de statut, de revue et de suppression logique ;
- `prefetch_related` : aucune relation multiple n'existe encore ;
- CRUD, authentification et permissions — l'API reste en lecture seule et
  `AllowAny` ;
- toute donnée de génération de médias (voir section 6).

## 2. Instructions du dépôt actualisées

`CLAUDE.md` décrivait encore le début de la phase 1 et interdisait l'existence
des modèles métier. Quatre passages devenus faux ont été corrigés :

| Passage | Avant | Après |
|---|---|---|
| Nature du projet | « le dépôt est au tout début de la phase 1 : seul le socle technique existe » | phase 1 terminée, `Entity` et `DivinityProfile` existent, la phase 2 complète le modèle incrément par incrément |
| Structure | « `mythology/` — aucun modèle pour l'instant » | « `Entity` et ses profils métier » |
| Règle de périmètre | « à ce stade, `Entity` et les profils métier ne doivent pas exister » | le modèle se complète un incrément à la fois, chaque incrément nommant ce qu'il laisse de côté |
| Hors périmètre | « génération d'images » en simple mot d'une liste | paragraphe dédié : les modèles ne portent que des faits mythologiques, aucun champ `prompt` sur `Entity` ni ses profils |

Les règles de simplicité, de tests, de migrations, de rapport, d'absence de
secrets et de langue sont conservées telles quelles.

## 3. Modèles ajoutés

### `HeroProfile`

`OneToOneField(Entity, on_delete=CASCADE, related_name="hero_profile")`.

| Champ | Type |
|---|---|
| `titles`, `achievements`, `quests`, `weapons_or_artifacts` | `string_array()` |
| `legacy`, `historical_context` | `TextField(blank=True)` |

Les alliés et les ennemis ne sont **pas** dans ce profil : ce sont des
relations entre entités, qui relèveront de `EntityRelation`. C'est noté dans la
docstring du modèle pour que la question ne se repose pas.

### `CreatureProfile`

`OneToOneField(Entity, on_delete=CASCADE, related_name="creature_profile")`.

| Champ | Type |
|---|---|
| `habitat`, `powers`, `strengths`, `weaknesses`, `encounter_omens`, `encounter_rules`, `known_sightings` | `string_array()` |
| `diet`, `size` | `CharField(max_length=255, blank=True)` |
| `appearance_notes` | `TextField(blank=True)` |
| `threat_level` | `CharField(max_length=10, choices=ThreatLevel.choices, blank=True, null=True)` |

`ThreatLevel` est une `models.TextChoices` — `low`, `medium`, `high`, `mythic` —
déclarée à côté de `EntityType` et `Gender`, avec des libellés français.

Chaque profil porte un `verbose_name` et un `verbose_name_plural` en français,
un `__str__` de la forme `Profil de héros — Soundiata`, et un `clean()` qui
refuse une entité dont `entity_type` ne correspond pas.

## 4. Décisions prises

### Le message de validation est factorisé, pas la validation

Les trois profils appliquent la même règle. Plutôt qu'un modèle abstrait ou un
mixin — explicitement exclus — seule la construction du message a été extraite
dans une fonction de module, `wrong_entity_type_error(profile_label, expected)`,
sur le modèle de `string_array()` qui existait déjà. Chaque profil conserve son
propre `clean()`, visible à l'endroit où la règle s'applique.

Conséquence assumée : le `clean()` de `DivinityProfile` a été réécrit pour
utiliser ce helper. Le comportement est inchangé, ce que vérifient les tests de
l'incrément précédent, conservés tels quels.

### Les trois clés de profil sont toujours présentes dans le détail

Le prompt laissait le choix entre « absentes » et « `null` ». Le contrat retenu
est : les trois clés `divinity_profile`, `hero_profile` et `creature_profile`
sont **toujours** présentes ; celle qui correspond au type porte l'objet, les
deux autres valent `null`. Un jeu de clés stable évite au client de tester
l'existence d'une clé en plus de sa valeur, et rend la réponse lisible quel que
soit le type. Trois tests couvrent les trois cas, plus un quatrième pour une
entité sans aucun profil.

### `threat_level` nullable — écart délibéré, borné mais réel

`ruff check` a signalé `DJ001 Avoid using null=True on string-based fields`.
L'avertissement est fondé : un champ textuel nullable ouvre deux
représentations de l'absence, `NULL` et `""`.

Le `null=True` est conservé, parce qu'il est demandé par le prompt et par
`docs/modele-donnees.md`. L'écart n'est pas pour autant sans effet — il est
seulement **borné** à ce stade, et il faut être précis sur ce qui est garanti.

**Ce qui est garanti.** Pour un champ à `choices` nullable,
`Field.formfield()` impose `empty_value=None`. Un choix laissé vide dans un
formulaire ou dans l'administration Django est donc enregistré `NULL`.

**Ce qui ne l'est pas.** Un appel ORM direct — `objects.create(threat_level="")`
— ou un futur serializer d'écriture peut toujours stocker `""`. Rien dans le
modèle ne l'empêche. L'API étant aujourd'hui en lecture seule, ce cas n'est
pas exposé : aucun client ne peut écrire dans ce champ.

**Ce qui est prévu.** La normalisation de `""` vers `None` sera imposée dans
les serializers ou les services d'écriture de la phase 4, au moment où
l'écriture deviendra possible. Aucune contrainte de base, aucun `clean()`
supplémentaire et aucune abstraction ne sont ajoutés maintenant : ce serait
traiter un cas qui n'existe pas encore.

Plutôt que de désactiver la règle globalement, l'écart est marqué par un
`# noqa: DJ001` local, commenté dans ces termes, et sa part vérifiable est
couverte par un test dont le nom délimite la portée :
`test_champ_de_formulaire_de_threat_level_utilise_none_comme_valeur_vide`
assère que le champ de formulaire est un `TypedChoiceField` dont `empty_value`
vaut `None`. Ce test ne prouve pas une garantie générale de la base, et sa
docstring le dit explicitement.

### `select_related` sur les trois relations

La vue de détail joint les trois profils dans la même requête. Une entité n'en
possède qu'un, mais le serializer interroge les trois pour produire le contrat
de clés stable décrit plus haut. Sans cette jointure, chaque détail coûterait
trois requêtes supplémentaires. La liste, qui n'expose aucun profil, ne joint
rien.

## 5. Fichiers touchés

**Créés**

- `mythology/migrations/0002_creatureprofile_heroprofile.py` — générée par `makemigrations`
- `mythology/tests/test_profiles.py` — 11 tests
- `docs/reports/phase-2-increment-1.md` — ce rapport
- `docs/prompts/phase-2-increment-1-profiles.md`, dans le dépôt
  `django-portfolio` — archive fidèle du prompt d'implémentation de cet
  incrément

**Modifiés**

- `mythology/models.py` — `ThreatLevel`, `wrong_entity_type_error()`, `HeroProfile`, `CreatureProfile`, `clean()` de `DivinityProfile` réécrit sans changement de comportement
- `mythology/admin.py` — `HeroProfileAdmin`, `CreatureProfileAdmin`
- `mythology/serializers.py` — `HeroProfileSerializer`, `CreatureProfileSerializer`, détail élargi aux trois profils
- `mythology/views.py` — `select_related` sur les trois relations
- `mythology/tests/factories.py` — `create_hero`, `create_creature`, `create_hero_profile`, `create_creature_profile`
- `mythology/tests/test_api.py` — tests des deux nouveaux profils et de la liste
- `CLAUDE.md` — voir section 2

Aucun fichier hors périmètre n'a été touché. `docs/reports/phase-1-push.md`
reste inchangé et non suivi : aucune erreur factuelle n'y a été constatée.

## 6. Administration et API

`HeroProfileAdmin` et `CreatureProfileAdmin` suivent `DivinityProfileAdmin` :
`list_display` minimal, `search_fields = ["entity__name"]`,
`autocomplete_fields = ["entity"]`. `CreatureProfileAdmin` ajoute
`threat_level` en colonne et en filtre, le champ étant le seul à valeurs
contrôlées.

Routes inchangées — `GET /api/entities/` et `GET /api/entities/{slug}/` — et
toujours en lecture seule sous `AllowAny`. Seule la charge utile du détail
s'élargit aux trois clés de profil. La collection reste strictement compacte,
ce qu'un test de non-régression vérifie pour les trois types.

## 7. Migration

`mythology/migrations/0002_creatureprofile_heroprofile.py`, générée par Django
et appliquée sur PostgreSQL 16 :

```
Migrations for 'mythology':
  mythology\migrations\0002_creatureprofile_heroprofile.py
    + Create model CreatureProfile
    + Create model HeroProfile

Applying mythology.0002_creatureprofile_heroprofile... OK
```

**Une seule migration, régénérée plutôt qu'empilée.** La correction du pluriel
`verbose_name_plural` de `CreatureProfile` porte sur une option suivie par
Django : la conserver en l'état aurait fait produire à `makemigrations` une
seconde migration `AlterModelOptions`, pour un simple libellé
d'administration. La migration `0002` n'étant ni committée ni poussée, et les
deux tables nouvelles étant vides — vérifié avant l'opération —, elle a été
dépilée (`migrate mythology 0001`), supprimée, puis **régénérée par
`makemigrations`** et réappliquée. Elle n'a donc jamais été éditée à la main,
conformément à la règle du dépôt, et l'historique reste à deux migrations pour
l'app `mythology`.

## 8. Tests

39 tests dans le dépôt, dont 15 ajoutés par cet incrément. Répartition réelle
obtenue par `pytest --collect-only` : 17 dans `test_api.py`, 11 dans
`test_profiles.py`, 7 dans `test_models.py`, 4 dans `tests/` à la racine.

**`mythology/tests/test_profiles.py`** — 11 tests

- création valide d'un profil de héros, relation vérifiée dans les deux sens ;
- création valide d'un profil de créature, idem ;
- valeurs par défaut des deux profils : listes vides, textes vides,
  `threat_level is None` à la création — ce qui ne dit rien d'un `""` fourni
  explicitement ;
- `empty_value is None` sur le champ de **formulaire** de `threat_level`,
  portée délimitée par le nom du test et par sa docstring ;
- refus d'un profil de héros sur une divinité, via `full_clean()` ;
- refus d'un profil de créature sur un héros, via `full_clean()` ;
- acceptation de chaque profil sur son propre type ;
- unicité `OneToOne` : un second profil de héros sur la même entité lève
  `IntegrityError` ;
- même test pour la créature ;
- suppression en cascade des deux profils avec leur entité.

**`mythology/tests/test_api.py`** — tests ajoutés ou élargis

- détail d'un héros : `hero_profile` imbriqué, les deux autres `null` ;
- détail d'une créature : `creature_profile` imbriqué, les deux autres `null` ;
- détail d'une divinité : comportement conservé, et vérification explicite que
  `hero_profile` et `creature_profile` valent `null` ;
- entité sans profil : les trois clés présentes, toutes `null` ;
- `threat_level` non renseigné sérialisé en `null` ;
- liste : compacte pour les trois types, aucune clé de profil ;
- détail chargé en **une seule requête** pour chacun des trois types
  (`django_assert_num_queries(1)`), ce qui teste l'effet du `select_related`
  sans mesurer de temps de réponse.

## 9. Résultats des six commandes

| Commande | Sortie | Code |
|---|---|---|
| `python manage.py check` | `System check identified no issues (0 silenced).` | 0 |
| `python manage.py makemigrations --check --dry-run` | `No changes detected` | 0 |
| `pytest` | `39 passed in 1.69s` | 0 |
| `ruff check .` | `All checks passed!` | 0 |
| `ruff format --check .` | `27 files already formatted` | 0 |
| `mypy .` | `Success: no issues found in 27 source files` | 0 |

## 10. Blocages rencontrés et résolution

Trois obstacles, tous résolus.

**`DJ001` sur `threat_level`.** Analysé plutôt que contourné : voir la décision
en section 4. Conservé avec un `noqa` local commenté et un test dont la portée
est explicitement limitée au champ de formulaire. L'incohérence `""` / `NULL`
reste possible par appel ORM direct ; elle sera traitée à l'écriture, en
phase 4.

**`SIM300` « Yoda condition ».** Faux positif de Ruff sur
`PROFILE_KEYS <= set(payload)`, qu'il lit comme une comparaison numérique
inversée. Réécrit en `set(payload) >= PROFILE_KEYS`, qui se lit aussi bien.

**`mypy` sur le champ de formulaire.** `Field.formfield()` est typé
`forms.Field`, qui n'expose pas `empty_value`. Résolu en resserrant le test
avec `isinstance(form_field, forms.TypedChoiceField)` — le test gagne en
précision au passage, puisqu'il vérifie aussi le type du champ produit.

Aucun blocage ouvert.

## 11. État Git

Rien n'est committé ni poussé.

```
 M CLAUDE.md
 M mythology/admin.py
 M mythology/models.py
 M mythology/serializers.py
 M mythology/tests/factories.py
 M mythology/tests/test_api.py
 M mythology/views.py
?? docs/reports/phase-1-push.md
?? docs/reports/phase-2-increment-1.md
?? mythology/migrations/0002_creatureprofile_heroprofile.py
?? mythology/tests/test_profiles.py
```

`docs/reports/phase-1-push.md` était déjà non suivi avant cet incrément et
n'a pas été modifié par celui-ci.

Côté `django-portfolio` :

```
 M docs/adr/0002-decisions-structurantes-phase-0.md
 M docs/roadmap-projet-1.md
?? .gitignore
?? docs/prompts/phase-2-increment-1-finalisation.md
?? docs/prompts/phase-2-increment-1-profiles.md
```

Les deux états ci-dessus sont ceux relevés **avant** les commits de
finalisation de cet incrément. Le détail de ces commits — identifiants,
messages et listes de fichiers — figure dans le rapport de finalisation
produit à cette occasion, et non ici.

### Répertoires exclusivement locaux

`_audit/` et `.claude/` sont désormais protégés par le `.gitignore` du dépôt
`django-portfolio`, qui les déclare tous les deux :

```gitignore
_audit/
.claude/
```

Quatre points sur cet état :

- la protection **appartient au dépôt** et ne dépend plus de la configuration
  Git globale de cette machine. Auparavant, `.claude/` n'échappait à
  l'indexation que parce que son unique fichier `settings.local.json` était
  couvert par `~/.config/git/ignore`, et `_audit/` que parce que chaque
  `git add` visait des chemins explicites. Le comportement est maintenant le
  même sur n'importe quel poste ;
- les deux répertoires n'ont été **ni supprimés ni indexés** ;
- ils **n'apparaissent plus dans `git status`** parce qu'ils sont ignorés, et
  non parce qu'ils auraient disparu. `_audit/` est toujours présent sur disque
  avec son contenu, `.claude/` avec ses réglages locaux ;
- aucun fichier déjà suivi n'est devenu ignoré par l'ajout de ce fichier,
  contrôlé par `git ls-files --cached --ignored --exclude-standard`, qui ne
  retourne rien.

## 12. Décision documentée côté pilotage

La frontière entre faits mythologiques et données de rendu est désormais
consignée à deux endroits du dépôt `django-portfolio` :

- **ADR 0002, section 8** — décision complète : aucun champ `prompt` sur
  `Entity` ni ses profils ; `prompt_canon`, prompt négatif, variantes, matrice
  de styles et métadonnées de médias rejoindront le module de rendu prévu
  après la V1 ; le corpus V2 reste la source conservée de ces données tant
  qu'elles ne sont pas importées, et l'API n'en deviendra la source de vérité
  qu'après cet import, par symétrie avec la décision 5 ; la phase 2 prépare en
  revanche les entrées du futur moteur — ethnie, signes physiques, symboles,
  objets de pouvoir — parce que ce sont elles-mêmes des faits mythologiques ;
- **roadmap, phase 2** — section « Frontière avec les données de rendu », qui
  renvoie à l'ADR et rappelle que la phase de rendu n'est pas déplacée dans la
  phase 2.

Seule la tâche « Ajouter `HeroProfile` et `CreatureProfile` » a été cochée.
Les neuf autres tâches de la phase 2 restent ouvertes.

## 13. Éléments volontairement reportés

**Incrément suivant de la phase 2** — référentiels `CulturalArea`, `Country`,
`Ethnicity` et `Domain`, puis les relations `primary_*` et `secondary_*` de
`Entity`, `variant_of`, `EntityRelation` et `Source`. C'est à ce moment que
`prefetch_related` deviendra pertinent, aucune relation multiple n'existant
aujourd'hui.

**Plus loin dans la phase 2** — cohérence stricte entre `entity_type` et le
profil associé. Aujourd'hui, `clean()` empêche un profil d'être rattaché au
mauvais type, mais rien n'impose qu'une entité possède un profil, ni qu'elle
n'en possède qu'un seul : `objects.create()` ne déclenche pas `clean()`. Cette
garantie passera par les services de création métier, comme le prévoit l'ADR
0002, et non par une abstraction polymorphe.

**Phases 3 et 4** — pagination, filtres, OpenAPI, visibilité restreinte aux
entités publiées, puis JWT, rôles, permissions objet, CRUD et modération.

**Après la V1** — module de rendu, conformément à la section 8 de l'ADR 0002.

**Dette technique inchangée** — aucun des deux dépôts n'a de `.gitattributes` ;
Git signale une conversion LF → CRLF à chaque ajout de fichier. À traiter avant
la CI de la phase 6.
