# Phase 4 — Incrément 2 : groupes et lecture privée

Rapport d'intervention de Claude CLI, le 24 octobre 2026.
Prompt : `docs/prompts/phase-4-increment-2-private-read.md` du dépôt de
pilotage `django-portfolio`. Décisions de référence : ADR 0002 (matrice de
permissions, décision 7), ADR 0003 (langue) et ADR 0004 (conventions de rôles).

## 1. Objectif et périmètre

Créer les trois groupes Django `contributor`, `reviewer` et `administrator`
par migration de données, et ouvrir deux routes de **lecture privée** dont la
sélection dépend du rôle de l'appelant et de la propriété des fiches. La
lecture publique et ses protections restent inchangées.

**Hors périmètre, non implémenté :** CRUD, transitions de statut,
suppression et restauration, inscription en libre-service, nouvelle durée de
jeton, champ `role` sur le compte, moteur générique de permissions ou de
workflow.

## 2. Fichiers touchés

### Ajoutés

| Fichier | Rôle |
| --- | --- |
| `accounts/migrations/0002_business_role_groups.py` | Migration de données créant les trois groupes ; inverse sans effet |
| `accounts/roles.py` | D'où viennent les rôles : groupes lus en base à chaque appel |
| `mythology/permissions.py` | `HasBusinessRole` : le contrôle de rôle sur la route |
| `mythology/tests/test_private_read.py` | 79 cas sur les deux routes privées |
| `tests/test_role_groups.py` | 15 cas sur la migration et la lecture des rôles |
| `docs/guide-groupes-lecture-privee.md` | Guide pédagogique et exercices manuels proposés |

### Modifiés

| Fichier | Nature du changement |
| --- | --- |
| `mythology/selectors.py` | Politique privée (`private_filter`, `private_entities`, `private_relations`, `private_entity_detail`, `is_privately_readable`), jointures du détail factorisées, `filter_public_entities` renommée `filter_entities` |
| `mythology/serializers.py` | `PrivateEntityListSerializer` et `PrivateEntityDetailSerializer`, par héritage ; `account_identifier_field()` |
| `mythology/views.py` | `EntityNavigationViewSet` extrait, `PrivateEntityViewSet` ajoutée |
| `mythology/urls.py` | Enregistrement de `manage/entities` |
| `mythology/schema.py` | Textes publics, réponses 401/403/404 et exemples des routes privées |
| `config/settings.py` | Description globale réécrite, tag `management`, `EntityStatusEnum` |
| `mythology/tests/test_openapi.py` | Chemins attendus, exigence de sécurité, nouveaux contrôles de composants et d'exemples |
| `README.md` | Sections *Two read contracts*, *Private editorial read API*, *Authentication*, *Project status* |
| `CLAUDE.md` | Section authentification réécrite : un jeton ouvre désormais les routes privées, selon le groupe |

Aucun modèle n'a changé : `makemigrations --check --dry-run` ne détecte aucune
migration de schéma manquante.

## 3. Contrat livré

### Routes

| Route | Méthode | Accès |
| --- | --- | --- |
| `GET /api/manage/entities/` | lecture seule | jeton d'accès **et** rôle métier |
| `GET /api/manage/entities/{slug}/` | lecture seule | idem |

Seule l'authentification JWT est acceptée sur ces routes, comme sur `me` : une
session d'administration ouverte ne suffit pas.

### Qui lit quoi

| Appelant | Réponse |
| --- | --- |
| Anonyme, jeton absent, malformé, expiré, mal signé, ou jeton de renouvellement | `401` |
| Authentifié sans rôle métier (y compris `is_staff` seul ou groupe étranger) | `403`, même sur une fiche publiée |
| Contributeur | Toutes les publiées, plus ses propres `draft`, `submitted`, `rejected` |
| Relecteur, administrateur, superutilisateur actif | Toutes les fiches non supprimées |

Les suppressions logiques sont exclues pour tous. Un propriétaire nul
n'appartient à aucun contributeur ; relecteurs et administrateurs lisent ces
fiches. Dans le détail, une fiche interdite, une fiche supprimée et un slug
inexistant renvoient le **même** `404`, au corps identique. La liste et son
`count` ne portent que les fiches autorisées.

### Champs ajoutés

- **Liste privée :** les cinq champs compacts, plus `status` et `created_by`.
- **Détail privé :** tous les champs métier du détail public, plus `status`,
  `created_by`, `submitted_at`, `reviewed_at`, `reviewed_by`, `review_notes`.

`created_by` et `reviewed_by` sont des **identifiants**. Aucun compte n'est
sérialisé : ni nom d'utilisateur, ni adresse, ni empreinte, ni groupe, ni
permission. `deleted_at` et `deleted_by` restent hors contrat, privé compris.

Les réponses publiques n'acquièrent aucun de ces champs, et leur sélection ne
change pas selon l'appelant : un jeton de relecteur ou de superutilisateur ne
révèle aucun brouillon en public.

### Références imbriquées

Sur le détail privé, `variant_of` n'est exposé que si la cible est lisible par
l'appelant, sinon `null` — sans fuite d'identifiant, de slug, de nom ni de
type. Une relation résolue vers une cible interdite est entièrement omise, et
le nom de la cible n'est pas recopié dans `to_name`. Les relations réellement
non résolues restent lisibles. Les cibles restent des références compactes de
quatre champs. Les fiches supprimées sont masquées aussi dans ces références.

La même fiche peut donc se rendre différemment selon le rôle de l'appelant :
c'est le comportement attendu, pas un défaut de cache.

### Navigation réutilisée

Les 20 éléments par page, l'ordre `name` puis `id`, les cinq paramètres
(`page`, `search`, `entity_type`, `country`, `cultural_area`) et leur
validation sont **les mêmes objets de code** que ceux de la collection
publique. Les tests comparent le bloc `parameters` du schéma et les corps de
`400` entre les deux routes. Un paramètre restreint une sélection déjà
politique ; aucun ne l'élargit.

### Écritures

`POST`, `PUT`, `PATCH`, `DELETE` renvoient `405` sur les deux routes privées,
pour tous les rôles, superutilisateur compris. Aucune action administrative
cachée n'a été ajoutée. Pour un appelant anonyme, le `401` précède le `405` :
DRF vérifie l'authentification avant de résoudre la méthode.

## 4. Décisions de conception

### Deux niveaux de contrôle, et pourquoi les deux

`HasBusinessRole` décide de l'accès à la route — c'est le `403`. La sélection
des fiches est faite dans le **queryset** — c'est le `404` et le `count`. Les
deux sont nécessaires : DRF ne consulte pas une permission d'objet pour les
fiches qu'une liste ne renvoie pas. Une permission objet seule aurait laissé
`count` et `results` divulguer des fiches interdites.

### Les rôles viennent de la base, une fois par requête

`accounts.roles.business_roles()` lit `user.groups` à chaque appel : aucun
claim JWT, aucun cache durable. `PrivateEntityViewSet.caller_roles` est un
`cached_property` sur l'instance de vue, qui ne vit qu'une requête : la
permission le calcule, puis le queryset et le contexte du serializer
réutilisent la même valeur. Une requête lit donc les groupes **une seule
fois**, et un changement de groupe agit sans réémettre le jeton.

`HasBusinessRole` lit `getattr(view, "caller_roles", frozenset())`. Le repli
est volontairement restrictif : une vue qui n'expose pas cet attribut est
refusée, jamais autorisée par défaut.

### Une politique, un préfixe, deux usages

`private_filter(roles=…, caller_id=…, prefix=…)` retourne un `Q`. Le `prefix`
— `"to_entity__"` — permet d'appliquer **la même** règle à la cible d'une
relation jointe, sans réécrire la politique une seconde fois. Un `caller_id`
nul fait disparaître la branche de propriété au lieu de comparer `created_by`
à `NULL` : sans cela, un appelant sans identité s'approprierait toutes les
fiches importées sans propriétaire.

`is_privately_readable()` est la même règle évaluée en Python, pour les
références déjà jointes, sans requête supplémentaire. Sans rôle, elle répond
toujours `False` : la représentation privée masque ses références plutôt que
de retomber sur la politique publique, plus permissive.

### Serializers privés par héritage

`PrivateEntityListSerializer` et `PrivateEntityDetailSerializer` héritent des
classes publiques et ne déclarent que ce qui diffère : les champs ajoutés et
la garde des références. Aucun champ métier n'est recopié. Le mode privé ne
se déclenche par aucun paramètre HTTP : ce sont deux classes distinctes,
choisies par la vue qui possède la route. La politique de l'appelant arrive
par le contexte du serializer, pas par la requête.

### Une base de navigation, pas de la vue publique

**Correction appliquée en cours de route.** `PrivateEntityViewSet` héritait
d'abord d'`EntityViewSet`. La génération du schéma a révélé deux effets
indésirables : drf-spectacular **cumule** les annotations le long de la chaîne
d'héritage, si bien que l'exemple du détail public apparaissait sous le
composant privé, et que l'`auth=[]` de la vue publique supprimait l'exigence
`Bearer` des routes privées.

La navigation réellement commune a donc été extraite dans
`EntityNavigationViewSet`, qui ne porte **aucune** annotation et ne décide
d'aucune visibilité. Les deux vues concrètes en héritent et décrivent chacune
son contrat. Un test de non-régression garde ce point
(`test_the_public_detail_example_stays_on_the_public_route`).

### `filter_public_entities` → `filter_entities`

La fonction restreint un queryset et ne décide d'aucune visibilité ; les deux
collections lui passent une sélection déjà filtrée par leur politique. Le nom
public devenait trompeur dès lors que la collection privée l'utilise aussi.
Seul le nom change ; le comportement et les tests de navigation existants sont
intacts.

### La migration ne détruit rien

`get_or_create` par nom réutilise un groupe déjà présent, sans toucher ses
membres. L'opération inverse est **volontairement sans effet** : les groupes
pouvaient préexister, et des personnes y ont peut-être été affectées depuis.
Un retour à `accounts 0001` ne doit pas supprimer silencieusement ces
affectations ; retirer un groupe reste un acte administratif explicite.

Aucune permission Django n'est attachée aux groupes : les droits de ce projet
sont les règles de l'ADR, évaluées côté serveur depuis l'appartenance aux
groupes. Attacher des permissions inutilisées suggérerait des droits qu'aucun
code ne lit. Aucune donnée ni compte de démonstration n'est créé par la
migration.

## 5. Vérifications réellement exécutées

Toutes les commandes ci-dessous ont été lancées dans
`C:\Users\heric\dev\afrimyth-api`, avec `.venv`, le 24 octobre 2026.

| Contrôle | Commande | Résultat |
| --- | --- | --- |
| Contrôles Django | `manage.py check` | `System check identified no issues (0 silenced).` |
| Migrations manquantes | `manage.py makemigrations --check --dry-run` | `No changes detected` |
| Schéma OpenAPI | `manage.py spectacular --file … --validate --fail-on-warn` | aucune sortie, donc aucun avertissement ni erreur de validation |
| Tests | `pytest -q` | **573 cas, tous passants**, en 5 min 12 s |
| Lint | `ruff check .` | `All checks passed!` |
| Format | `ruff format --check .` | `54 files already formatted` |
| Typage | `mypy .` | `Success: no issues found in 54 source files` |

Les 573 cas se décomposent en 463 cas préexistants — le total de la suite
complète relevé à l'incrément 1 — et **110 cas nouveaux**, vérifiés par
collecte :

| Fichier | Cas nouveaux |
| --- | --- |
| `mythology/tests/test_private_read.py` | 79 |
| `tests/test_role_groups.py` | 15 |
| `mythology/tests/test_openapi.py` | 16 (59 cas → 75) |

Deux corrections sont survenues pendant le travail, avant ce relevé : les
longueurs de ligne signalées par Ruff et les annotations de type des trois
champs d'identifiant de compte signalées par mypy. Les sept contrôles ci-dessus
ont été relancés après ces corrections ; les résultats du tableau sont ceux de
l'état final.

### Migration appliquée et vérifiée

```
manage.py migrate accounts
  Applying accounts.0002_business_role_groups... OK
manage.py showmigrations accounts
  [X] 0001_initial
  [X] 0002_business_role_groups
```

État de la base de développement relevé **après** application :

| Groupe | Membres | Permissions |
| --- | --- | --- |
| `administrator` | 0 | 0 |
| `contributor` | 0 | 0 |
| `reviewer` | 0 | 0 |

Comptes : 2, dont **0 avec un groupe**. Fiches : 4, toutes en `draft`, dont
**0 avec un propriétaire**. Autrement dit : les comptes existants conservent
leurs droits, et les propriétaires comme les statuts du corpus n'ont pas été
modifiés. Aucune donnée de démonstration n'a été créée.

### Requêtes mesurées

Relevé hors suite de tests, par `CaptureQueriesContext`, sur base de test :

| Scénario | Requêtes |
| --- | --- |
| Liste privée, 3 fiches | 4 |
| Liste privée, 30 fiches | **4** |
| Détail privé, 1 relation non résolue | 9 |
| Détail privé, variante + 3 cibles résolues + 1 non résolue | **9** |
| Liste publique anonyme (référence) | 2 |

Décomposition du détail privé : 1 compte (authentification JWT) + 1 groupes +
1 fiche, qui ramène par `select_related` les trois profils, les trois ancrages
et `variant_of` + 6 préchargements — quatre collections de référentiels, les
sources et les relations sortantes déjà filtrées, cibles jointes. Le détail
public coûte 7 requêtes, soit les deux mêmes requêtes d'appelant en moins.

Aucun budget n'a été fixé d'avance : les tests comparent deux tailles de
corpus et deux richesses de relations, et exigent l'égalité. Un test
complémentaire sérialise un détail préchargé en **0 requête**, ce qui prouve
la présence effective de chaque préchargement.

## 6. Limites connues

- **`submitted_at`, `reviewed_at` et `deleted_at` restent non saisissables**
  dans l'administration. Une fiche de démonstration passée en `submitted` à la
  main aura donc `submitted_at` à `null` sur le détail privé. Ces horodatages
  seront posés par les actions prévues : soumission en incrément 5, revue
  en incrément 6 et suppression en incrément 7.
- **Les quatre fiches de la base de développement sont des brouillons sans
  propriétaire.** Elles sont donc invisibles aux contributeurs sur la route
  privée, et visibles aux relecteurs. C'est la règle, pas un défaut, mais cela
  impose de créer des fiches neuves pour démontrer le cas du contributeur.
- **Les fiches supprimées logiquement ne sont lisibles par personne** sur ces
  routes, administrateur compris. Leur consultation et leur restauration
  relèvent de l'incrément 7.
- **Aucune révocation de jeton.** La limite de l'incrément 1 reste entière :
  un jeton signé reste valable jusqu'à son expiration. Un retrait de groupe,
  en revanche, agit immédiatement — c'est précisément pourquoi les rôles ne
  sont pas dans le jeton.
- **Aucune relation entrante, aucune variante inverse** n'est exposée, en
  privé comme en public.
- **La route racine `/api/`** de `DefaultRouter` liste désormais aussi
  `manage/entities`. Elle n'expose qu'une liste d'URL, exige une
  authentification par le défaut fermé du projet, et ne figure pas dans le
  schéma OpenAPI.
- **Le `403` nomme les trois groupes** dans son message. C'est délibéré — un
  appelant doit pouvoir comprendre ce qui lui manque — et ne révèle aucune
  donnée du corpus ni l'existence d'un compte.

## 7. Exercices manuels restant à faire

Rien n'a été exécuté dans un navigateur ni dans Postman. Le guide
`docs/guide-groupes-lecture-privee.md` propose, dans l'ordre : création des
trois comptes de démonstration et affectation manuelle de leurs groupes dans
l'administration, création de quatre fiches appartenant à deux contributeurs
distincts, puis dix vérifications Postman — refus `401` et `403`, les deux
listes de contributeurs, la vue du relecteur, le `404` indistinguable, une
référence imbriquée vue par deux rôles, les champs du détail privé,
l'invariance du contrat public, le changement de groupe avec le même jeton, le
refus des écritures et l'inefficacité d'un paramètre client.

Après revue Codex, le nettoyage cible les quatre slugs et les trois noms de
compte exacts proposés, pas tous les préfixes `demo-`. Le lien de variante
proposé est retiré avant la suppression, pour respecter `PROTECT` ; les
autres références restent protégées. Les trois groupes ne sont pas supprimés.

**Aucun secret n'a été lu ni affiché** : ni le contenu de `.env`, ni une valeur
de Postman, ni un jeton. Le guide renvoie au Local Vault et demande de relire
tout export avant partage.

## 8. État Git des deux dépôts

Rien n'est committé ni poussé, conformément au prompt. Les deux dépôts sont
sur `main`.

### `afrimyth-api` — HEAD `62b8610`

```
 M CLAUDE.md
 M README.md
 M config/settings.py
 M mythology/schema.py
 M mythology/selectors.py
 M mythology/serializers.py
 M mythology/tests/test_openapi.py
 M mythology/urls.py
 M mythology/views.py
?? accounts/migrations/0002_business_role_groups.py
?? accounts/roles.py
?? docs/guide-groupes-lecture-privee.md
?? mythology/permissions.py
?? docs/reports/phase-4-increment-2-private-read.md
?? mythology/tests/test_private_read.py
?? tests/test_role_groups.py
```

### `django-portfolio` — HEAD `f5d3046`

```
 M docs/roadmap-projet-1.md
?? Pipfile
?? docs/adr/0004-lecture-privee-et-roles.md
?? docs/prompts/phase-4-increment-2-private-read.md
```

Aucun de ces quatre éléments n'a été modifié par cette intervention : la
roadmap n'a **pas** été cochée, et le `Pipfile` non suivi était déjà présent
au début de la session. La clôture documentaire revient à Codex, après revue
et exercices.

## 9. Revue Codex — 24 octobre 2026

**Avis technique :** aucun défaut bloquant relevé dans les chemins examinés.
La migration, les rôles, les permissions, les sélections, les serializers,
les vues, les routes et les tests ont été confrontés aux ADR et au prompt.
La lecture publique reste séparée de la lecture privée ; les droits portent
sur les listes, leurs comptes et les références imbriquées, pas seulement
sur l'accès à une route.

**Sobriété :** pas de moteur générique de permissions, pas de validation JWT
réécrite. La base de navigation a deux consommateurs réels. Les gardes SQL et
Python ne sont pas supprimées : elles protègent respectivement la sélection
et les références sérialisées. Le volume vient aussi des tests, des textes
OpenAPI et d'explications souvent longues, pas seulement de logique ajoutée.

**Corrections légères appliquées directement, sans changement fonctionnel :**

- Traduction et raccourcissement des nouvelles docstrings françaises dans
  les vues, sélections, routes et deux nouveaux fichiers de tests. Les anciennes
  docstrings hors de ce périmètre restent pour la passe documentaire dédiée.
- Correction du commentaire de la fabrique de comptes de test : elle utilise
  bien `get_or_create`, et ne prouve donc pas à elle seule la migration.
  Les tests de migration dédiés restent en place.
- Nettoyage du guide limité aux quatre slugs et trois comptes exacts ; retrait
  préalable du seul lien de variante proposé, nécessaire avec `PROTECT`.
  Aucune de ces commandes de nettoyage n'a été exécutée.
- Précision du schéma : les différentes erreurs d'authentification partagent
  le code 401, pas forcément leur corps. Deux acteurs sont exposés sur le
  détail privé : propriétaire et relecteur, pas trois.
- Correction du calendrier des horodatages dans les limites du rapport :
  soumission en incrément 5, revue en 6 et suppression en 7.

**Vérifications Codex réellement exécutées :**

- `pytest -q mythology/tests/test_private_read.py tests/test_role_groups.py
  mythology/tests/test_openapi.py` : **169 tests passants**, en 235,90 secondes.
- `manage.py spectacular --file <fichier temporaire> --validate --fail-on-warn` :
  code de sortie 0, aucun avertissement.
- Ruff et vérification de format sur les sept fichiers Python corrigés :
  contrôles verts ; `git diff --check` sans erreur.

La suite complète de 573 cas reste le résultat rapporté par Claude ; Codex
ne l'a pas relancée intégralement. Aucun modèle, règle d'accès ou code
exécutable modifié par les corrections. Aucune donnée de développement
créée, corrigée ou supprimée par Codex. Rien committé ni poussé ; roadmap
non cochée. La revue pédagogique et les exercices Postman restent à faire
avant validation finale de l'incrément.

## 10. Colonne des groupes dans l'administration — 27 octobre 2026

À la demande de l'auteur, Codex ajoute directement une colonne **Groups**
dans la liste des utilisateurs. Modification locale d'affichage, sans changement
des permissions, du modèle ou des affectations de groupes.

- `accounts/admin.py` : sous-classe du `UserAdmin` standard ; ajout de
  `display_groups` à `list_display`, noms triés et séparés par des virgules,
  tiret lorsqu'aucun groupe n'est associé. Il s'agit des appartenances réelles,
  pas des rôles effectifs : un superutilisateur sans groupe affiche donc « — ».
- Préchargement de `groups` dans `get_queryset()` pour éviter une requête
  supplémentaire par utilisateur.
- `tests/test_user_admin.py` : quatre cas passants (aucun groupe, un groupe,
  plusieurs groupes et affichage sans requête après préchargement).
- Contrôles réellement exécutés : `manage.py check`, Ruff, vérification du
  format et mypy sur les deux fichiers, tous conformes. Tests finaux :
  **4 passed in 2.09s**. Ajustements intermédiaires limités à une ligne vide
  de format et à la déclaration explicite de `list_display` pour mypy.
- Aucun compte de développement modifié. Aucun commit ni push ; cette
  modification sera incluse dans la clôture de l'incrément après les exercices.

## 11. Validation pédagogique et clôture — 27 octobre 2026

L'auteur a validé la revue pédagogique et les essais suivants dans Postman :

| Compte / route | Résultat observé |
| --- | --- |
| `essai-postman`, liste privée, sans groupe métier | 403 |
| `demo-contrib-a`, liste privée après attribution d'Anansi | 200, `count: 1`, Anansi en draft, `created_by: 3` |
| `demo-contrib-a`, détail privé Anansi | 200 |
| `demo-contrib-a`, détail privé Oya | 404 |
| `demo-selecteur`, groupe reviewer, détail privé Oya | 200 |
| `demo-selecteur`, liste privée | 200, les quatre fiches |
| `demo-selecteur`, liste publique | 200, `count: 0` |
| `demo-selecteur`, POST liste privée avec jeton valide | 405, méthode POST non autorisée |

Les erreurs de jeton expiré et de mauvais type ont donné 401, avant le
contrôle du rôle ou de la méthode. Aucun secret ni jeton n'est recopié ici.

**Écart au guide initial :** les fiches fictives proposées n'ont pas été
créées. Les quatre fiches vues sont Anansi, Mokele-mbembe, Oya et Shango,
issues du corpus. Codex a confondu les fiches proposées avec celles présentes
pendant l'accompagnement ; l'erreur a été rectifiée sur la capture de l'admin.
L'auteur a affecté Anansi à `demo-contrib-a` ; elle reste draft. Les trois
autres restent draft sans propriétaire. Ne pas leur appliquer de nettoyage
destructif. Le compte reviewer créé s'appelle `demo-selecteur`, et non le
`demo-relecteur` proposé dans le guide.

Les comparaisons du second contributeur, le changement de groupe avec le même
jeton et les références imbriquées n'ont pas été validés manuellement : ils
restent couverts par les tests automatisés. Aucune publication de fiche n'a
été effectuée pour cet exercice. Les états des sections 5 et 8 sont les
relevés historiques de livraison, avant ces exercices et la clôture.

**Décision :** incrément 2 validé ; roadmap actualisée. Les contrôles acquis
sont réutilisés : 573 cas de la suite complète rapportés par Claude, 169 cas
ciblés exécutés par Codex, puis quatre tests de colonne admin passants après
son ajout. Aucun autre code modifié depuis ces contrôles. Clôture Git normale
autorisée par l'auteur ; les SHA et le résultat des pushes sont donnés dans
le message de clôture, sans auto-commit du rapport après chaque commande Git.
