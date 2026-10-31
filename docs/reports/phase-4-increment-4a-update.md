# Phase 4 — Incrément 4A : modification contrôlée

Rapport d'intervention, en français. Aucun secret, aucune valeur de `.env`,
aucun mot de passe et aucun jeton n'y figure.

Intervention : Claude CLI, 30 octobre 2026, sur le prompt
`docs/prompts/phase-4-increment-4a-update.md` du dépôt de pilotage. Lot 4A
seulement ; le lot 4B n'est pas commencé.

## 1. Fichiers touchés

### Ajouté

| Fichier | Rôle |
| --- | --- |
| `mythology/tests/test_private_update.py` | 91 cas : droits, contrat partiel, refus, atomicité |
| `docs/reports/phase-4-increment-4a-update.md` | Ce rapport |

### Modifiés

| Fichier | Changement |
| --- | --- |
| `mythology/selectors.py` | `is_privately_editable()` et les deux tuples de statuts modifiables |
| `mythology/permissions.py` | `CanEditEntity` (niveau objet) et `NOT_EDITABLE_MESSAGE` |
| `mythology/serializers.py` | `PrivateEntityUpdateSerializer`, `update_profile()`, `existing_profile()`, deux attributs de classe pour les raisons de refus |
| `mythology/views.py` | `partial_update()`, le serializer et la permission d'objet, l'annotation OpenAPI `partial_update` |
| `mythology/schema.py` | Description, exemple de requête, réponses 400 et 403 du PATCH ; fin de la description du détail privé |
| `config/settings.py` | Description OpenAPI globale : section *Private editorial update* |
| `README.md` | Section *Update an entity, its profile and its attachments*, tableau des droits, statut du projet |
| `mythology/tests/test_openapi.py` | Méthodes déclarées par chemin, 20 cas sur l'opération de PATCH |
| `mythology/tests/test_private_read.py` | Les refus `405` ne couvrent plus `PATCH` sur le détail ; permissions de la vue |
| `mythology/tests/test_private_create.py` | Garde-fou de la vue : `partial_update` est désormais routé |

Aucun modèle, aucune migration, aucun compte, aucun groupe, aucune donnée de
développement n'a été touché. `makemigrations --check` ne détecte rien.
`demo-create-hero-a` et les quatre fiches du corpus n'ont pas été modifiées.

## 2. Contrat livré

### Route et droits

`PATCH /api/manage/entities/{slug}/`, JWT seul, rôle métier obligatoire.

| Appelant | Fiches modifiables |
| --- | --- |
| contributeur | ses propres `draft` et `rejected` |
| relecteur | tous les `draft`, `rejected` et `submitted` |
| administrateur, superutilisateur actif | toutes les fiches non supprimées |

`is_staff` seul n'accorde rien ; les groupes se cumulent et sont relus en base
à chaque requête. Codes : `401` sans JWT utilisable, `403` sans rôle métier
**ou** sur une fiche lisible mais non modifiable, `404` identique pour un slug
inconnu, une fiche non lisible et une fiche supprimée. Les droits portent sur
la fiche visée, pas seulement sur la route.

### Sémantique

Champ absent : valeur conservée. Liste fournie : cette seule liste est
remplacée ; `[]` la vide. Collections omises intactes. `null` accepté sur les
seuls champs nullables — les trois ancrages principaux et `variant_of`. Corps
vide accepté, sans changement métier (`updated_at` est toutefois actualisé).
Réponse `200` au format du détail privé.

`entity_type` est refusé en `400` (ADR 0005). L'UUID ne change pas ; le `slug`
est modifiable et conserve son unicité, sans conflit avec la fiche elle-même,
comme `(name, entity_type)`.

Le profil se modifie partiellement sous la clé du type **actuel**. Profil
absent ou `{}` : aucun effacement. Refusés : profil `null`, clé de profil d'un
autre type, `entity`, `entity_id`, `id`, `pk` dans un profil, nom de champ de
profil inconnu. `threat_level` vide reste normalisé en `null`.

Refusés explicitement et nommés, comme à la création : `id`, `pk`, `status`,
`created_by`, `created_by_id`, `submitted_at`, `reviewed_at`, `reviewed_by`,
`review_notes`, `deleted_at`, `deleted_by`, `created_at`, `updated_at`,
`sources`, `relations`, `relations_from`, `relations_to`, et tout nom inconnu.
Aucun transfert de propriété, administrateur compris.

Rattachements par identifiants existants, aucun référentiel créé. La règle
principal/secondaire de l'ADR 0002 est évaluée sur l'**état final**, en
combinant les valeurs stockées et les champs du PATCH : échanger un ancrage et
une valeur secondaire en une requête est donc accepté. `variant_of` reste
limité aux cibles privées lisibles et non supprimées, avec un refus uniforme,
et l'auto-lien est refusé.

Tout est écrit dans une transaction unique — entité, profil, M2M. Une erreur
annule l'ensemble. Seule `django.core.exceptions.ValidationError` est convertie
en `400` ; toute autre exception reste une erreur serveur visible.

### Ce qui reste fermé

`PUT` et `DELETE` : `405` sur les deux URL privées. `POST` sur le détail :
`405`. `PATCH` sur la collection privée : `405`. Les routes publiques
n'acquièrent aucune écriture. Sources, relations, transitions de statut,
suppression, restauration et reclassement de type ne sont pas implémentés.

## 3. Décisions de conception

- **Deux niveaux de contrôle.** Le queryset privé décide du `404` ; une
  permission d'objet, `CanEditEntity`, décide du `403`. Les méthodes sûres la
  traversent sans effet, donc la lecture est inchangée.
- **Le droit est réévalué sur la ligne verrouillée.** `update()` relit la fiche
  en `select_for_update()` et refait le contrôle avant d'écrire : sans cela, une
  transition de statut concurrente entre la permission et la sauvegarde serait
  écrasée. Un test simule précisément cette fenêtre.
- **Pas de `ModelViewSet`, pas d'`UpdateModelMixin`.** `partial_update()` est
  écrit à la main, six lignes : `UpdateModelMixin` aurait aussi routé `PUT`
  comme remplacement complet.
- **Réutilisation par héritage.** `PrivateEntityUpdateSerializer` sous-classe le
  serializer de création : mêmes champs, mêmes refus de clés, même résolution
  privée de `variant_of`, même représentation de sortie. Il retire
  `entity_type` de `Meta.fields` et redéfinit deux attributs de classe pour que
  les raisons de refus parlent de modification et non de création.
- **`full_clean()` sur l'entité patchée.** DRF ne construit pas le validateur
  d'unicité `(name, entity_type)` ici, puisque `entity_type` n'est plus un
  champ du serializer : `full_clean()` est ce qui conserve cette protection de
  doublon, et il exclut la fiche d'elle-même.
- **Fiche incohérente refusée, jamais réparée.** Une fiche sans le profil de
  son type, ou portant en plus le profil d'un autre type, est refusée en `400`
  sans aucune mutation. Ce cas n'est pas théorique : l'administration Django et
  un `objects.create()` direct peuvent encore le produire, et la réparer au
  passage d'un PATCH sans lien créerait ou supprimerait des données de profil
  silencieusement. Deux tests couvrent les deux formes d'incohérence.

## 4. Vérifications exécutées

| Commande | Résultat |
| --- | --- |
| `python manage.py check` | aucun problème |
| `python manage.py makemigrations --check --dry-run` | `No changes detected`, sortie `0` |
| `python manage.py spectacular --validate --fail-on-warn` | sortie `0`, aucun avertissement |
| `pytest mythology/tests/test_private_update.py` | 91 passés |
| `pytest` sur les suites OpenAPI, lecture privée et création | 290 passés |
| `pytest` | **804 passés** en 10 min 4 s, aucun échec, aucun ignoré (695 avant) |
| `ruff check .` | `All checks passed!` |
| `ruff format --check .` | `57 files already formatted` |
| `mypy .` | `Success: no issues found in 57 source files` |

Le schéma a été écrit dans un fichier temporaire hors du dépôt.

Deux corrections `mypy` en cours de route, suivies du seul contrôle affecté :
`self.instance` est typé `Entity | None`, d'où une propriété `patched` qui
documente l'invariant ; et un dépaquetage de dictionnaire dans un test
paramétré, remplacé par un paramètre de fabrique.

## 5. Limites connues

- **Aucune transition de statut.** Une fiche modifiée garde son statut : un
  contributeur ne peut pas soumettre, ni un relecteur publier, par PATCH.
- **`sources` et `relations` restent refusés** et non écrivables : c'est le
  lot 4B, non commencé.
- **Le type ne change pas.** Aucun chemin de reclassement n'existe ; une fiche
  créée avec le mauvais type doit être traitée hors API pour l'instant.
- **Une fiche incohérente est bloquée en écriture.** Le refus `400` empêche
  toute modification, y compris d'un champ sans rapport, jusqu'à correction
  délibérée hors API.
- **Le refus des champs inconnus reste strict**, comme à la création : une clé
  supplémentaire donne `400`.
- **La règle principal/secondaire n'est imposée que par l'API.** L'admin Django
  et un `objects.create()` direct peuvent encore produire un recouvrement.
- **Pas de limitation de débit** sur une route qui écrit.
- **Pas de détection de conflit d'édition.** Le verrou protège l'évaluation
  du droit et, après revue Codex, la cohérence principal/secondaire ;
  deux PATCH simultanés sur des champs différents se
  sérialisent, mais le dernier écrit ses propres valeurs sans détection de
  conflit — pas d'`ETag` ni de version de ligne.

## 6. État Git

Rien n'est committé ni poussé ; la roadmap n'est pas cochée.

### `afrimyth-api` — HEAD `86d7fd8`

```
 M README.md
 M config/settings.py
 M mythology/permissions.py
 M mythology/schema.py
 M mythology/selectors.py
 M mythology/serializers.py
 M mythology/tests/test_openapi.py
 M mythology/tests/test_private_create.py
 M mythology/tests/test_private_read.py
 M mythology/views.py
?? mythology/tests/test_private_update.py
```

Ce rapport s'ajoute aux fichiers non suivis.

### `django-portfolio` — HEAD `5633bce`

Aucun fichier de ce dépôt n'a été modifié par cette intervention. Son arbre
porte, de l'auteur : `docs/roadmap-projet-1.md` modifié,
`docs/adr/0005-perimetre-modification.md`,
`docs/prompts/phase-4-increment-4a-update.md` et `Pipfile` non suivis.

## 7. Exercices manuels

Non préparés : aucun guide Postman n'est demandé à Claude pour cet incrément,
et aucune donnée n'a été créée dans la base de développement.
`demo-create-hero-a` reste disponible pour les essais de Codex.

## 8. Revue Codex — 30 octobre 2026

### Sobriété des vérifications

Les consignes sont désormais inscrites dans `AGENTS.md` du dépôt de pilotage
et `CLAUDE.md` de l'API : tests ciblés pendant le développement, passage complet
final sans cumul rituel des mêmes suites sur un code inchangé, nouvelles relances
proportionnées aux corrections. Conserver les tests de sécurité, d'intégrité et
de contrat ; retirer les vrais doublons, sans quota arbitraire de tests.

Douze cas OpenAPI de `test_no_server_controlled_field_is_offered_for_update`
ont été retirés : la comparaison exacte de l'ensemble des champs dans
`test_the_update_input_is_the_creation_input_without_the_type` garantit déjà
la même exclusion. Les tests API de refus des champs, de permissions et
d'atomicité sont conservés. Cette revue ciblée n'est pas un audit exhaustif
de tous les tests historiques.

### Correction localisée de validation

La cohérence principal/secondaire était vérifiée sur l'objet initial, avant
le verrou transactionnel. Un changement intervenant avant la lecture verrouillée
pouvait donc faire accepter un recouvrement interdit. Deux tests simulant ce
changement (côté principal ou secondaire) ont reproduit le défaut : réponse
`200` au lieu de `400` avant correction.

Dans `PrivateEntityUpdateSerializer.update()`, la validation existante est
désormais réutilisée sur l'entité relue sous verrou, avant toute sauvegarde.
Aucune nouvelle règle métier, aucun changement de permissions ou de schéma.
Les deux tests vérifient aussi le rollback ; il s'agit d'une simulation du
changement intermédiaire, pas d'un test multithread.

### Vérifications complémentaires

- Tests ciblés PATCH (rattachements, rollback et réévaluation sous verrou) :
  **9 passés**, dont les deux régressions nouvelles.
- Tests OpenAPI concernant PATCH et son entrée : **9 passés**.
- Mypy sur le sérialiseur et les tests PATCH : succès, 2 fichiers.
- Ruff et contrôle du format sur les trois fichiers concernés : succès.
- Collecte : **794 tests** (804 livrés, moins 12 doublons, plus 2 régressions).
  Ce nombre est une collecte, pas un nouveau passage complet.
- Le passage complet de Claude (804 réussites avant ces corrections) reste
  consigné ci-dessus ; il n'a pas été relancé systématiquement.

Le nombre de tests antérieur à la livraison a été rectifié de 691 à 695.
La description du PATCH vide précise l'actualisation de `updated_at`, et
`CLAUDE.md` mentionne maintenant le PATCH disponible, en attente de validation.

Le code est prêt pour la revue pédagogique et les essais Postman. Aucune donnée
de développement modifiée, aucun secret consulté. Aucun commit ni push :
clôture après validation manuelle de l'auteur. Le `Pipfile` non suivi du dépôt
de pilotage reste hors périmètre et inchangé.

## 9. Confort des exercices — durée des jetons en développement

À la demande de l'auteur, pause des exercices pour porter les nouveaux jetons
d'accès à 20 minutes lorsque `DJANGO_DEBUG=True`. La variable
`JWT_DEV_ACCESS_MINUTES` est déclarée dans `.env.example` ; elle est ignorée
hors debug, où la durée reste de 5 minutes. Le renouvellement reste à un jour.
Aucun secret ni fichier `.env` modifié. Les jetons déjà émis gardent leur
expiration initiale : un nouvel accès doit être obtenu après rechargement
du serveur. Remettre le réglage de développement à 5 avant la fin de l'API,
comme demandé ; hors développement les 5 minutes sont déjà conservées.

Fichiers concernés : `config/settings.py`, `.env.example`, `README.md`,
`tests/test_settings.py`. Vérifications ciblées : 6 tests de configuration
réussis (dont debug activé/désactivé), Ruff et typage conformes. Pytest force
son propre DEBUG à False après le chargement : le test de durée tient compte
du mode utilisé au chargement du projet. Aucune relance de la suite complète.

## 10. Validation pédagogique et pratique — 30 et 31 octobre 2026

L'auteur confirme la compréhension du code et les exercices Postman 4A.
Sur la seule fiche fictive `demo-create-hero-a` : lecture initiale, PATCH
simultané de category et hero_profile.legacy avec conservation des champs
omis, refus du status avec absence de modification à la relecture, vidage
explicite de titles et conservation de legacy, refus du changement de type
et d'un profil incompatible. Le test created_by a été proposé mais son
résultat n'a pas été explicitement reproduit ; il reste couvert automatiquement.

Le contributeur B obtient 404 sur cette fiche appartenant à A ; le relecteur
peut modifier legacy sans changer propriétaire ou statut. Le Ghana (id 6)
a été rattaché en principal ; son ajout simultané en secondaire est refusé ;
le déplacement principal null / secondaire [6] dans le même PATCH est accepté.
PUT est refusé. Les résultats ont été confirmés progressivement par l'auteur.

La fiche est conservée en draft, propriétaire 3, catégorie Village protector,
titles vide, legacy « Reviewed during the PATCH exercise. », Ghana en
secondaire. Aucun nettoyage de cette fiche demandé : elle sert aussi au lot 4B.
Les quatre fiches du corpus n'ont pas été modifiées pendant ces exercices.

Lot 4A validé. Clôture Git conjointe avec le lot 4B le 31 octobre 2026 ;
résultats automatiques déjà acquis réutilisés, sans changement fonctionnel
après la revue. La phase 4 reste ouverte.
