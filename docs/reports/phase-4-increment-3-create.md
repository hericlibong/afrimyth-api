# Phase 4 — Incrément 3 : création d'une entité et de son profil

Rapport d'intervention, en français, conformément à `CLAUDE.md`. Aucun secret,
aucune valeur de `.env`, aucun mot de passe et aucun jeton n'y figure.

Intervention : Claude CLI, 27 octobre 2026, sur demande du prompt
`docs/prompts/phase-4-increment-3-create.md` du dépôt de pilotage
`django-portfolio`.

## 1. Objectif et périmètre

Ouvrir **une seule** écriture : `POST /api/manage/entities/`, qui crée une
entité et le profil de son type, en brouillon, au nom du compte appelant.

Dans le périmètre : le contrat d'entrée explicite, la cohérence type/profil,
les rattachements aux référentiels existants, `variant_of` restreint à la
politique de lecture privée, le propriétaire et le statut imposés côté
serveur, l'atomicité, la documentation OpenAPI et le README.

Hors périmètre, et laissé tel quel : `PUT`, `PATCH`, `DELETE`, les transitions
de statut, la suppression et la restauration, l'inscription en libre-service,
les durées de jeton, la création imbriquée de `sources` et `relations`, et tout
nouveau CRUD de référentiels. Les lectures publiques et privées existantes sont
inchangées.

## 2. Fichiers touchés

### Ajoutés

| Fichier | Rôle |
| --- | --- |
| `mythology/tests/test_private_create.py` | 88 cas : permissions, contrat, refus, atomicité |
| `docs/guide-postman-creation.md` | Guide interne des exercices manuels |
| `docs/reports/phase-4-increment-3-create.md` | Ce rapport |

### Modifiés

| Fichier | Changement |
| --- | --- |
| `mythology/serializers.py` | `PrivateEntityCreateSerializer`, `CreatureProfileWriteSerializer`, `attach_collections()`, `caller_policy()` passé au niveau module |
| `mythology/views.py` | `PrivateEntityViewSet` gagne `CreateModelMixin`, le serializer de création et l'annotation OpenAPI `create` |
| `mythology/schema.py` | `CreationErrorSerializer`, description, exemples et réponse 400 de la création ; fin des descriptions privées corrigée |
| `config/settings.py` | Description OpenAPI globale : l'API n'est plus annoncée comme entièrement en lecture seule |
| `README.md` | Section *Create an entity and its profile*, tableaux et statut du projet |
| `mythology/tests/test_openapi.py` | Méthodes déclarées par chemin, et 24 cas supplémentaires sur l'opération de création |
| `mythology/tests/test_private_read.py` | Les refus `405` privés ne couvrent plus `POST` sur la collection |
| `tests/test_auth_does_not_change_reads.py` | Docstring précisée : les refus couverts sont ceux de `/api/entities/` |

Aucun modèle, aucune migration, aucun compte, aucune appartenance de groupe,
aucune donnée de développement n'a été touché. `makemigrations --check` ne
détecte aucun changement.

## 3. Contrat livré

### Route et accès

`POST /api/manage/entities/`, JWT uniquement, rôle métier obligatoire.
Contributeur, relecteur, administrateur et superutilisateur actif peuvent
créer. Sans jeton utilisable : `401`. Jeton valide sans rôle métier, `is_staff`
seul compris : `403`. Les règles sont celles de l'incrément 2, réutilisées
sans réécriture : `JWTAuthentication`, puis `IsAuthenticated`, puis
`HasBusinessRole`.

### Champs d'entrée

Corps JSON plat. Requis : `name`, `slug`, `entity_type`, `gender`. Le slug est
pris tel quel — ni génération depuis le nom, ni suffixe en cas de collision.

Facultatifs : `category`, `cultural_role`, `alignment`, `story_description`,
`manifestations`, et les cinq listes de chaînes `characteristics`,
`physical_signs`, `symbols`, `power_objects`, `symbolic_animals`.

Rattachements par identifiant de référentiel existant, sous les noms actuels :
`primary_country`, `secondary_countries`, `primary_ethnicity`,
`secondary_ethnicities`, `primary_cultural_area`, `secondary_cultural_areas`,
`domains`. Principaux facultatifs et nullables, collections facultatives et
vides par défaut. Aucun référentiel n'est créé au passage.

`variant_of` facultatif/nullable, par UUID.

### Profil

Sous la clé existante correspondant au type : `divinity_profile`,
`hero_profile` ou `creature_profile`. Clé absente ou `{}` : le profil est créé
avec ses valeurs par défaut — une entité n'existe jamais sans le profil de son
type. Refusés en `400` : une clé de profil d'un autre type, un profil `null`,
les clés `entity`, `entity_id`, `id`, `pk` dans un profil, et tout nom de
champ de profil inconnu.

### Ce qu'aucun client ne fournit

Refusés **explicitement**, nommés dans la réponse `400`, jamais ignorés :
`id`, `pk`, `status`, `created_by`, `created_by_id`, `submitted_at`,
`reviewed_at`, `reviewed_by`, `review_notes`, `deleted_at`, `deleted_by`,
`created_at`, `updated_at`, ainsi que `sources`, `relations`, `relations_from`
et `relations_to`, différés à l'incrément 4. Tout autre nom de champ inconnu
est refusé lui aussi, ce qui fait remonter une faute de frappe au lieu de la
laisser passer.

Le serveur impose `created_by` au compte authentifié et `status` à `draft`,
pour tous les rôles, administrateur compris.

### Refus propres au métier

- Nom déjà utilisé pour le même type, ou slug déjà utilisé : `400`.
- Référentiel inexistant : `400`, aucune création.
- Même valeur à la fois ancrage principal et rattachement secondaire d'une
  même dimension : `400`, selon les décisions 1, 2 et 3 de l'ADR 0002.
- `variant_of` visant une fiche non lisible par cet appelant, supprimée ou
  inexistante : `400`, avec **le même corps** dans les trois cas. La réponse
  ne révèle jamais l'existence d'une fiche.
- Mauvais type de données dans une liste de chaînes — chaîne, objet, liste
  imbriquée, nombre — : `400`, sans conversion silencieuse.

### Réponse

`201` avec la représentation du **détail privé** déjà existante, profil
inclus. La fiche est immédiatement lisible par son propriétaire sur les routes
privées et absente des routes publiques jusqu'à sa publication. Une création
invalide renvoie `400` et ne laisse aucune donnée partielle.

### Ce qui reste refusé

`PUT`, `PATCH` et `DELETE` : `405` sur les deux URL privées, pour tous les
rôles, superutilisateur compris. `POST` sur le détail privé : `405`. Les
routes publiques n'acquièrent aucune écriture : leurs quatre méthodes
d'écriture restent en `405`.

## 4. Décisions de conception

### `CreateModelMixin` sur une base en lecture seule

`PrivateEntityViewSet` hérite désormais de `mixins.CreateModelMixin` et de
`EntityNavigationViewSet`. Passer à un `ModelViewSet` complet aurait routé
`update`, `partial_update` et `destroy` d'un seul geste, c'est-à-dire ouvert
trois écritures non demandées. Un test de garde vérifie que la vue possède
`create` et **aucune** des trois autres actions, et qu'`EntityViewSet` n'en
acquiert aucune.

### Une liste explicite de champs, et le refus nommé du reste

`Meta.fields` énumère les 25 champs acceptés ; rien d'autre n'atteint le
modèle. Mais une liste explicite ne suffit pas : DRF laisse tomber
silencieusement une clé inconnue, si bien qu'un client envoyant
`"status": "published"` recevrait `201` et croirait avoir publié une fiche
restée en brouillon. `to_internal_value()` refuse donc ces clés **avant** toute
conversion, afin qu'un champ fautif soit toujours nommé, même quand un champ
requis manque dans la même requête.

Les mêmes vérifications sont appliquées à l'intérieur d'un profil, où un
serializer imbriqué aurait ignoré `entity` ou un nom mal orthographié.

Ce n'est pas un moteur de validation : deux petites méthodes, deux
dictionnaires de raisons, aucune introspection de modèle côté API.

### `variant_of` réutilise la politique privée, sans la réécrire

Le champ est déclaré `UUIDField` et résolu dans `validate_variant_of()` par
`private_entities(roles=…, caller_id=…)`, la sélection de l'incrément 2. Cette
résolution explicite permet d'uniformiser le refus. Un
`PrimaryKeyRelatedField` pourrait aussi utiliser un queryset dépendant du
contexte, sans imposer de duplication de politique ; il n'est pas utilisé ici.
Les trois cas — interdite, supprimée, inexistante —
produisent un message unique, ce qu'un test compare corps à corps.

### Le service garde son rôle, la transaction l'englobe

`create_entity_with_profile()` n'est pas modifié : il garantit toujours le
couple entité/profil, et l'import continue de l'appeler. Les relations
plusieurs-à-plusieurs exigent une fiche déjà enregistrée, donc elles sont
rattachées après, par `attach_collections()`, **dans la même transaction** que
le couple. Sans cette transaction englobante, un échec de rattachement
laisserait une fiche à moitié rattachée.

`attach_collections()` est une fonction nommée plutôt qu'une boucle dans
`create()` : c'est ce qui permet à un test de faire échouer le rattachement
*après* la création du couple et de vérifier qu'aucun objet partiel ne
subsiste.

### Conversion ciblée des erreurs Django

`create()` n'intercepte que `django.core.exceptions.ValidationError`, convertie
par `serializers.as_serializer_error()` en réponse `400` lisible. Aucune
capture générale : un `RuntimeError` reste une erreur serveur visible, ce qu'un
test vérifie explicitement, en contrôlant au passage que la transaction a bien
tout annulé.

### `threat_level` : une seule représentation de l'absence

Le commentaire du modèle `CreatureProfile` annonçait depuis la phase 2 que la
normalisation de `""` vers `None` serait imposée « dans les serializers ou
services d'écriture de la phase 4 ». C'est fait, au plus petit coût :
`CreatureProfileWriteSerializer` sous-classe la représentation de lecture et
n'ajoute qu'un `validate_threat_level()`. Les composants de lecture restent
inchangés.

### `caller_policy()` passé au niveau module

La méthode `PrivateEntityDetailSerializer.caller_policy()` est devenue une
fonction de module, appelée par le serializer de détail et par celui de
création. Même comportement, même défaut restrictif ; seule la place change,
parce que deux classes la partagent réellement maintenant.

## 5. Vérifications réellement exécutées

Toutes les commandes ci-dessous ont été lancées dans l'environnement virtuel
du dépôt, sur la base de test de pytest — jamais sur la base de développement.

| Commande | Résultat |
| --- | --- |
| `python manage.py check` | `System check identified no issues (0 silenced).` |
| `python manage.py makemigrations --check --dry-run` | `No changes detected`, sortie `0` |
| `python manage.py spectacular --validate --fail-on-warn` | sortie `0`, aucun avertissement |
| `pytest mythology/tests/test_private_create.py` | 88 passés |
| `pytest mythology/tests/test_openapi.py mythology/tests/test_private_read.py` | 180 passés |
| `pytest` | **691 passés** en 8 min 1 s, aucun échec, aucun test ignoré |
| `ruff check .` | `All checks passed!` |
| `ruff format --check .` | `56 files already formatted` |
| `mypy .` | `Success: no issues found in 56 source files` |

La suite comptait 577 cas à la clôture de l'incrément 2 : les 573 cas
rapportés par Claude, plus les quatre tests de colonne admin ajoutés par
Codex. La livraison initiale du présent incrément en compte 691, soit 114 de
plus — les 88 cas de création, les 24 cas OpenAPI de l'opération et les deux
cas nets supplémentaires issus du re-paramétrage des refus `405` privés.
Les ajouts de la revue Codex sont consignés séparément ci-dessous.

Le schéma a été écrit dans un fichier temporaire hors du dépôt : aucun schéma
généré n'est committé, conformément au README.

Trois corrections ont été nécessaires en cours de contrôle, suivies du seul
contrôle affecté à chaque fois :

1. `mypy` signalait un `Returning Any` sur `to_internal_value()`, dont la
   signature DRF retourne `Any` : l'annotation a été alignée.
2. `mypy` refusait un dépaquetage `**{champ: []}` dans un test paramétré, le
   dictionnaire étant typé `dict[str, list[Never]]` : le test construit
   maintenant son corps explicitement.
3. La docstring de `tests/test_auth_does_not_change_reads.py` annonçait encore
   un « contenu en lecture seule » sans distinguer les routes : elle précise
   désormais qu'elle couvre les refus de `/api/entities/`. Les 14 cas de ce
   fichier ont été relancés seuls, puis `ruff` et `ruff format`.

### Couverture des tests de création

Les 88 cas de `test_private_create.py` couvrent, dans cet ordre : les refus
`401` — anonyme et session seule — et `403` — sans groupe, `is_staff` seul,
groupe étranger ; les quatre rôles autorisés ; le propriétaire et le brouillon
imposés ; la lecture privée immédiate et l'absence en public ; les quatre
champs requis et le slug conservé tel quel ; les valeurs hors choix ; les trois
types et leur profil exact, avec le décompte des trois tables de profils ; les
valeurs par défaut d'un profil absent ou `{}` ; `threat_level` vide normalisé
en `null` ; les profils incohérents, `null`, nommant leur entité ou portant un
champ inconnu ; les treize champs serveur injectés ; les collections différées ;
un champ inconnu ; les champs métier simples ; quatre formes de tableau
invalide et un élément trop long ; les rattachements enregistrés, facultatifs,
inexistants et redondants ; `variant_of` lisible, nul, interdit, supprimé,
inexistant, mal formé, et vu différemment par un relecteur ; les doublons de
slug et de nom par type ; les trois cas d'atomicité ; les garde-fous de
configuration des vues.

## 6. Limites connues

- **La création est la seule écriture.** Aucune transition de statut n'est
  possible : une fiche créée reste en `draft` jusqu'à l'incrément 5, et n'est
  donc jamais visible publiquement par le seul effet de cet incrément.
- **`sources` et `relations` ne sont pas créés ici.** Leur présence est
  refusée, pas ignorée, mais aucun chemin ne permet encore de les attacher par
  l'API.
- **Les référentiels ne sont pas créables par l'API.** Ils restent créés par
  l'administration ou par l'import.
- **La règle principal/secondaire n'est imposée qu'ici.** Le commentaire de
  `Entity` reste exact : l'administration Django et un `objects.create()`
  direct peuvent toujours produire un recouvrement. L'ADR 0002 prévoyait
  justement cette application « par les services d'import et d'écriture ».
- **Les autres chemins d'écriture gardent leurs failles connues.**
  L'administration peut toujours créer une entité sans profil ou changer son
  `entity_type` après coup ; la garantie du service ne porte que sur ses propres
  appels réussis.
- **Le refus des champs inconnus est strict.** Un client qui envoie une clé
  supplémentaire — un champ de commentaire, un reste de formulaire — reçoit
  `400`. C'est délibéré, mais c'est un choix de contrat : il devra être tenu
  tel quel, ou assoupli explicitement, et non au cas par cas.
- **Aucune limitation de débit.** Le constat du README sur l'absence de
  throttling vaut désormais pour une route qui écrit, pas seulement pour
  l'obtention d'un jeton.
- **`pytest` exige PostgreSQL** dès lors que les tests touchent la base, ce
  qui est le cas de toute cette suite.

## 7. Exercices manuels restant à faire

Ils ne sont **pas** exécutés : le guide `docs/guide-postman-creation.md` les
propose, étape par étape, et rien n'a été créé automatiquement dans la base de
développement.

1. Obtenir un jeton d'accès pour `demo-contrib-a`.
2. Créer la fiche fictive au slug exact `demo-create-hero-a`, avec son profil
   de héros ; constater `201`, `status` à `draft`, `created_by` à l'identifiant
   du compte, et les deux autres clés de profil à `null`.
3. Relire la fiche en privé — réponse identique au `201` — puis constater le
   `404` avec le jeton de `demo-contrib-b`.
4. Constater son absence en public : détail `404`, collection à `count` zéro,
   avec et sans jeton.
5. Provoquer trois refus — statut imposé, mauvaise clé de profil, slug déjà
   pris — puis vérifier par la liste privée qu'aucune fiche partielle ne
   subsiste.
6. Confirmer que `PATCH`, `DELETE` et `POST` sur le détail répondent `405`, et
   que la création répond `401` sans jeton et `403` avec `essai-postman`.

Le nettoyage proposé ne cible que le slug exact `demo-create-hero-a`, jamais un
préfixe global. Les comptes `demo-contrib-a`, `demo-contrib-b`,
`demo-selecteur` et `essai-postman`, les trois groupes et les quatre fiches du
corpus pilote ne doivent pas être supprimés ni réattribués : Anansi reste la
propriété du contributeur A, Oya, Mokele-mbembe et Shango restent sans
propriétaire.

## 8. État Git des deux dépôts

Rien n'est committé ni poussé : la revue et les exercices doivent précéder la
clôture, et la roadmap n'est pas cochée.

### `afrimyth-api` — HEAD `e2a1f9f`

```
 M README.md
 M config/settings.py
 M mythology/schema.py
 M mythology/serializers.py
 M mythology/tests/test_openapi.py
 M mythology/tests/test_private_read.py
 M mythology/views.py
 M tests/test_auth_does_not_change_reads.py
?? docs/guide-postman-creation.md
?? mythology/tests/test_private_create.py
```

Ce rapport s'ajoute à la liste des fichiers non suivis.

### `django-portfolio` — HEAD `558d9cf`

Le `Pipfile` non suivi reste hors périmètre. Codex a également modifié
`AGENTS.md` à la demande de l'auteur pour réserver les guides pédagogiques
et la documentation d'accompagnement à Codex. Ces consignes ne sont pas une
modification de Claude. La roadmap n'est pas cochée et l'ADR 0004 n'est pas
touché.

## 9. Extraits à expliquer en revue

| Quoi | Où |
| --- | --- |
| La liste explicite des champs d'entrée | `mythology/serializers.py`, `PrivateEntityCreateSerializer.Meta.fields` |
| Le refus nommé, avant toute conversion | `mythology/serializers.py`, `to_internal_value()`, `reject_entity_keys()`, `reject_profile_keys()` |
| La clé de profil imposée par le type | `mythology/serializers.py`, `reject_mismatched_profiles()` |
| Principal et secondaire disjoints | `mythology/serializers.py`, `reject_overlapping_attachments()` |
| `variant_of` et la réutilisation de la politique privée | `mythology/serializers.py`, `validate_variant_of()` |
| Propriétaire, brouillon, transaction unique, conversion ciblée | `mythology/serializers.py`, `create()` |
| Le rattachement isolé pour être testable | `mythology/serializers.py`, `attach_collections()` |
| La réponse 201 rendue par le détail privé | `mythology/serializers.py`, `to_representation()` |
| La création ajoutée seule | `mythology/views.py`, `PrivateEntityViewSet` et son annotation `create` |
| Les trois cas d'atomicité | `mythology/tests/test_private_create.py`, section *Atomicité* |
| Les garde-fous de configuration des vues | `mythology/tests/test_private_create.py`, dernière section |

## 10. Copie destinée à Codex

Une copie identique de ce rapport est déposée dans le scratchpad de session, à
l'emplacement indiqué en dernière ligne de la réponse de l'agent.

## 11. Revue Codex — 27 octobre 2026

### Avis et sobriété

Le code livré a été confronté au prompt : création seule sur la collection
privée, permissions conservées, champs d'entrée explicites, service du couple
entité/profil réutilisé, transaction englobant les M2M et références privées
filtrées selon l'appelant. Aucun moteur générique ou validation JWT réécrite.
Le volume des serializers vient aussi des déclarations de champs, messages et
explications ; une refonte n'est pas nécessaire pour cet incrément.

### Défaut reproduit et correction localisée

Le refus des mauvais types était incomplet :
`PrivateEntityCreateSerializer().fields['characteristics'].run_validation([7])`
retournait `['7']`. Même résultat pour `hero_profile.titles`. Le test fourni
ne couvrait qu'un nombre à la place du tableau, pas un nombre dans le tableau.

Codex a ajouté `string_array_errors()` avant la conversion, partagé entre
les champs communs et les profils. Il refuse uniquement les éléments non
textuels des listes de chaînes ; forme du tableau, longueur et autres règles
restent validées par DRF et Django. Aucun modèle, rôle ou choix métier modifié.
Quatre régressions ajoutées : un élément numérique commun et un dans chacun
des trois profils. La création invalide ne laisse ni entité ni profil.

### Corrections documentaires

- Base de comparaison corrigée : 577 tests après l'incrément 2, pas 573.
  La livraison initiale de 691 comprend 88 cas de création, 24 cas OpenAPI
  supplémentaires et deux cas nets de refus privés supplémentaires.
- Explication corrigée : un champ DRF de relation peut dépendre du contexte ;
  le choix UUID + résolution explicite n'est pas imposé par une impossibilité
  de `PrimaryKeyRelatedField`.
- Les dates techniques sont posées par le serveur Django, pas par des valeurs
  par défaut de PostgreSQL ; description OpenAPI corrigée.
- Guide conservé et ajusté par Codex : données fictives en anglais, JSON
  lisible, URL locale explicite et référence au secret Vault déjà utilisé.
  Aucun exercice n'est présenté comme exécuté. Les prochains guides relèvent
  directement de Codex, conformément à la nouvelle consigne de l'auteur.

### Vérifications réellement exécutées par Codex

- Reproduction de la conversion `[7]` vers `['7']` sur les champs du serializer,
  sans sauvegarde ni création en base de développement.
- Première sélection de tests sur les listes, champs valides, profils par
  défaut et atomicité : **14 passants**, 78 désélectionnés, en 21,11 s.
- Deuxième sélection distincte : trois types et leur profil, profil renseigné,
  rattachements valides/redondants et cibles de variantes : **10 passants**,
  82 désélectionnés, en 16,33 s.
- Tests OpenAPI : **99 passants**, en 31,51 s.
- Mypy sur les deux fichiers Python de la correction : conforme.
- Ruff et format sur les deux fichiers et le schéma : conformes.
- `spectacular --validate --fail-on-warn` vers un fichier temporaire : sortie 0.
- Collecte complète : **695 cas**, dont 92 de création, 99 OpenAPI et 81 de
  lecture privée. La suite complète de 695 n'a pas été relancée par Codex :
  les 691 passants avant correction restent le résultat rapporté par Claude.
- `git diff --check` : aucune erreur.

Au total, Codex a exécuté 123 tests ciblés. Aucun compte, appartenance ou fiche
du corpus modifié. Rien committé ni poussé ; revue pédagogique et exercices
de création Postman encore à faire avant clôture.

## 12. Clôture après revue pédagogique et Postman — 30 octobre 2026

### Résultats manuels confirmés par l'auteur

- Création de `demo-create-hero-a`, nom `Demo Create Hero A`, via le compte
  `demo-contrib-a` : réponse contenant `status: draft`, `created_by: 3`,
  `hero_profile.titles: ["Village guardian"]`, les deux autres profils à null.
  UUID de la fiche : `072bc48e-37e6-4a36-acaf-b13cc2065ae3`.
- Relecture du détail privé : même fiche et même représentation.
- Détail public de ce brouillon : 404, `No Entity matches the given query.`
- Tentative de création de `demo-create-hero-refus` avec `status: published` :
  refus explicite sur la clé `status`. Sa consultation privée suivante
  donne 404 : aucune fiche accessible n'a été laissée par cette tentative.
- Tentative de création d'un héros `demo-wrong-profile` avec
  `divinity_profile: {}` : refus sur `divinity_profile`, désignant
  `hero_profile` comme clé attendue.
- Tentative de création d'une fiche au nom différent mais au slug existant
  `demo-create-hero-a` : refus sur `slug`, `entity with this slug already exists.`

Les corps de création et de refus ont été fournis par l'auteur ; les codes
201/400 attendus sont vérifiés automatiquement, mais n'ont pas tous été
confirmés explicitement dans les captures ou messages de ces essais.
L'essai avec un autre contributeur et les refus supplémentaires du guide
ne sont pas présentés comme exécutés manuellement.

La saisie de `GET` dans le champ URL de Postman a été corrigée. Les propositions
de l'assistant Postman ont été distinguées des résultats attendus de nos tests
de refus : un 404 ou un 400 volontaire n'appelle pas une correction automatique.
Aucun secret ou jeton n'est enregistré dans ce rapport.

### Allègement demandé

Codex a retiré 91 lignes de commentaires/docstrings redondants de la partie
création de `mythology/serializers.py` (886 → 795 lignes pour le fichier).
Les raisons utiles restent près du code ; la description détaillée du contrat
reste dans OpenAPI, le README et le présent rapport. Aucun message d'erreur,
contrôle, champ, permission ou instruction n'a été modifié par cet allègement.

La comparaison des AST avant/après, en retirant uniquement les docstrings et
les métadonnées de position, donne une empreinte identique. Ruff et format
restent conformes. Les tests fonctionnels acquis en revue sont donc réutilisés ;
seuls les tests OpenAPI et la validation du schéma, concernés par les descriptions
raccourcies, ont été relancés : **99 tests passants en 38,84 s**, validation
`spectacular --validate --fail-on-warn` en sortie 0, sans avertissement.
`CLAUDE.md` est actualisé pour ne plus annoncer le refus de toutes les écritures.

### Décision de clôture

Incrément 3 validé ; roadmap actualisée. La fiche fictive créée est conservée
pour les exercices de modification de l'incrément 4, sans nettoyage destructif.
Anansi reste attribuée au contributeur A ; les autres fiches du corpus ne sont
pas modifiées par Codex. L'évolution des consignes de délégation dans le
`AGENTS.md` du dépôt de pilotage est incluse dans cette clôture.

Les états Git des sections précédentes sont historiques. Commits et pushes
normaux seront effectués sous l'identité de l'auteur, sans trailer d'assistant,
en indexant uniquement les fichiers de l'incrément et les documents concernés.
Le `Pipfile` non suivi du dépôt de pilotage reste hors périmètre. Les SHA et
le résultat sont communiqués dans le message final de clôture.
