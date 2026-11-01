# Phase 4 — Incrément 6 : décisions de modération

Rapport d'intervention, en français. Aucun secret, aucune valeur de `.env`,
aucun mot de passe et aucun jeton n'y figure.

Intervention : Claude CLI, 31 octobre 2026, sur le prompt
`docs/prompts/phase-4-increment-6-moderation.md`. Départ API `87da2e9`.

## 1. Périmètre livré

Trois actions `POST` sous `/api/manage/entities/{slug}/` :

| Route | Transition | Acteurs | Corps |
| --- | --- | --- | --- |
| `publish/` | submitted → published | reviewer, administrator | absent, `{}`, ou `review_notes` facultatif |
| `reject/` | submitted → rejected | reviewer, administrator | objet avec `review_notes` obligatoire non blanc |
| `reopen/` | published → draft | administrator seul | absent ou `{}` |

Succès : `200` au détail privé, références filtrées. Ces routes n'acceptent que
`POST`. `submit/`, `withdraw/` et `resume/` sont inchangées.

Rien d'autre : pas de suppression/restauration d'entité, pas de changement de
type, pas de PATCH du statut ou de la revue, aucun modèle, migration,
bibliothèque, compte, groupe, réglage JWT ni donnée de développement touchés.
Aucune écriture hors base de tests ; la fiche fictive n'a pas été publiée.

## 2. Fichiers touchés

### Ajoutés

| Fichier | Rôle |
| --- | --- |
| `mythology/tests/test_private_moderation.py` | 84 cas |
| `docs/reports/phase-4-increment-6-moderation.md` | Ce rapport |

### Modifiés

| Fichier | Changement |
| --- | --- |
| `mythology/transitions.py` | Trois actions ; `ALLOWED_ROLES` et `OWNER_ACTIONS` ; `may_transition()` prend l'action ; `not_allowed_reason()` ; branche décision d'`apply_transition()` |
| `mythology/serializers.py` | `PublishNotesSerializer`, `RejectNotesSerializer` et le refus de clés des décisions |
| `mythology/views.py` | Les trois actions, `validated_review_notes()`, l'acteur passé à `apply_transition()` |
| `mythology/schema.py` | Descriptions, exemples et réponse 400 des décisions ; 403 des transitions ; `review_notes` dans le corps d'erreur ; description du détail privé |
| `config/settings.py` | Section OpenAPI de modération ; paragraphe général rectifié ensuite par Codex lors de la revue |
| `README.md` | Section *Publish, reject and reopen a record*, tableau des droits, statut du projet |
| `mythology/tests/test_openapi.py` | Chemins et méthodes attendus, 16 cas nets ajoutés à la livraison, paramétrages existants compris |

## 3. Décisions concrètes

- **Le droit dépend de l'action, pas de la route.** C'était le point de
  sécurité du prompt : `may_transition()` admettait le propriétaire pour les
  six noms exemptés de `CanEditEntity`. Elle prend désormais l'action en
  argument et croise deux tables explicites — `ALLOWED_ROLES` par action, et
  `OWNER_ACTIONS` qui ne contient que `submit`, `withdraw` et `resume`. La
  propriété n'ouvre donc jamais `publish`/`reject`, et `REVIEWER` n'ouvre
  jamais `reopen`. L'exemption de `CanEditEntity` reste compensée par ce droit
  spécifique, jamais par un accès authentifié permissif.
- **Un message de refus par action.** `not_allowed_reason(action)` nomme
  l'acteur requis — « owning the record grants nothing here » pour une
  décision, « requires an administrator » pour une réouverture — sans rien
  dire du statut ni du corps : un acteur refusé ne reçoit aucun diagnostic
  sur une fiche qu'il n'a pas le droit de modérer, ce qu'un test vérifie.
- **Trois branches dans `apply_transition()`**, pas un moteur : soumission,
  décisions (`DECISIONS`), retours au brouillon. `update_fields` reste la
  garantie que rien d'autre ne bouge ; `submitted_at` n'est pas touché par une
  décision, même quand il vaut `null`, et la réouverture n'inscrit pas
  l'administrateur comme relecteur.
- **Deux petits serializers de note**, sur le modèle des serializers d'enfants
  de l'incrément 4B : `review_notes` facultatif et `allow_blank` à la
  publication, obligatoire et non blanc au rejet — `trim_whitespace` de DRF
  écarte une note d'espaces. Les clés serveur et inconnues passent par le
  `rejected_key_errors()` existant, sans nouvelle infrastructure de payload. Un
  corps JSON non objet est refusé par DRF lui-même.
- **Une note omise enregistre une chaîne vide**, jamais l'ancienne note : la
  vue lit `validated_data.get("review_notes", "")`.
- **Le contrat vide des quatre autres actions est préservé** :
  `validated_review_notes()` ne consulte un serializer que pour les deux
  décisions, et garde sinon le refus de tout corps.
- **Ordre des contrôles inchangé** et étendu : sélection privée (`404`), droit
  propre à l'action (`403`), statut de départ puis corps (`400`), le tout relu
  sous `select_for_update()`.
- **Aucune réécriture des selectors publics.** La visibilité publique suit les
  nouveaux statuts par la sélection existante ; seuls des tests l'attestent.

## 4. Vérifications exécutées, dans l'ordre du prompt

**Pendant le développement** — nouveaux tests ciblés, puis la seule ancienne
suite directement affectée par les chemins ajoutés :

| Commande | Résultat |
| --- | --- |
| `pytest mythology/tests/test_private_moderation.py` | 84 passés |
| `pytest mythology/tests/test_openapi.py` | 161 passés, 2 échoués |

Une relance ciblée, motivée par une correction locale : deux assertions
OpenAPI citaient une formulation que `REOPEN_DESCRIPTION` n'employait pas
(« Send no body or an empty JSON object »). La description a été alignée sur la
phrase commune aux quatre actions sans entrée, et l'assertion redondante
remplacée par celle qui porte la spécificité de la réouverture. Seuls les
33 tests OpenAPI concernés ont été relancés — **33 passés** — et non la suite
entière, la correction étant locale.

**Avant le passage final :**

| Commande | Résultat |
| --- | --- |
| `python manage.py check` | aucun problème |
| `python manage.py makemigrations --check --dry-run` | `No changes detected`, sortie `0` |
| `python manage.py spectacular --validate --fail-on-warn` | sortie `0`, aucun avertissement |
| `ruff check .` | `All checks passed!` |
| `ruff format --check .` | `61 files already formatted` |
| `mypy .` | `Success: no issues found in 61 source files` |

**Passage complet final, une seule fois :**

| Commande | Résultat |
| --- | --- |
| `pytest` | **1061 passés** en 17 min 47 s, aucun échec, aucun ignoré (961 collectés au départ) |

Les anciennes suites transitions/lecture/création/PATCH/enfants n'ont pas été
relancées séparément : elles sont incluses dans ce passage. Le schéma a été
écrit dans un fichier temporaire hors du dépôt.

## 5. Limites

- **Pas de suppression ni de restauration d'entité** : l'incrément 7 n'est pas
  entamé, et la documentation continue de l'annoncer comme non livré.
- **Pas d'historique.** Les quatre champs portent l'état courant et la dernière
  revue conservée ; aucune table d'audit, aucun champ ajouté. La revue d'une
  publication réouverte survit jusqu'à la soumission suivante, qui l'efface.
- **Aucune règle d'auto-revue ni double validateur** : la matrice ne les exige
  pas, et un relecteur peut publier une fiche qu'il a lui-même rédigée.
- **Aucun seuil de complétude** à la publication : c'est une décision humaine.
- **Concurrence bornée.** Le verrou protège la réévaluation de la visibilité,
  du droit et du statut ; ni `ETag`, ni version de ligne, et aucune promesse
  pour les écritures hors API. Les tests de concurrence sont des simulations de
  la fenêtre entre sélection et lecture verrouillée, pas des essais
  multithread.
- **Pas de limitation de débit** sur des routes qui écrivent.

Aucun blocage, aucune décision incompatible avec le prompt rencontrée.

## 6. État Git

Rien n'est coché, committé ni poussé.

### `afrimyth-api` — HEAD `87da2e9`

```
 M README.md
 M config/settings.py
 M mythology/schema.py
 M mythology/serializers.py
 M mythology/tests/test_openapi.py
 M mythology/transitions.py
 M mythology/views.py
?? mythology/tests/test_private_moderation.py
```

Ce rapport s'ajoute aux fichiers non suivis.

### `django-portfolio` — HEAD `db3bc69`

Aucun fichier de ce dépôt n'a été modifié. Son arbre porte, de l'auteur :
`Pipfile` et `docs/prompts/phase-4-increment-6-moderation.md` non suivis.

## 7. Revue Codex — 31 octobre 2026

### Conclusion et périmètre

Pas de défaut bloquant relevé dans les droits par action, la réévaluation sous
verrou, les notes/dates côté serveur ou la visibilité publique. Les décisions
sont intégrées aux transitions existantes ; pas de FSM ou d'architecture
générique supplémentaire. Aucun changement fonctionnel des transitions ou
des permissions nécessaire après revue. L'incrément reste à expliquer et à
vérifier manuellement avant clôture.

### Corrections légères appliquées

- Malgré la mention initiale du rapport, le paragraphe général OpenAPI
  annonçait encore publication/rejet/réouverture comme futurs, en contradiction
  avec la section de modération ajoutée. Il est corrigé et un test existant
  vérifie l'absence de cette formulation périmée.
- Le message de refus des marques de revue à la création n'annonce plus des
  actions indisponibles ; il oriente vers les actions dédiées. La docstring
  d'ouverture des serializers est actualisée sans réorganisation.
- Trois succès de la matrice des statuts interdits répétaient des réussites
  déjà couvertes : retirés de cette matrice, sans perte de protection.
- Deux tests OpenAPI de reopen répétaient ceux déjà paramétrés sur les actions
  sans entrée : supprimés du second paramétrage. Une boucle sur les méthodes
  de routes faisait aussi doublon avec leur comparaison exacte globale ; les
  assertions documentaires utiles du test sont conservées sous un nom adapté.
- Le test de publication ne crée plus à la fois un relecteur et un admin
  alors qu'il n'utilise qu'un seul de ces acteurs : fixture chargée à la demande.
- Le test intitulé « droit de l'acteur relu » demandait reopen à un reviewer,
  qui est toujours interdit, même avant la mutation simulée. Il ne prouvait
  donc pas la relecture annoncée. Il est remplacé par une suppression simulée
  entre la sélection et la lecture verrouillée : réponse 404 attendue, sans
  modération. Le test d'état de soumission changé entre-temps est conservé.

### Vérifications de revue

- Modération ciblée : **20 passés** (publication, motif de rejet, états refusés,
  suppression intermédiaire, décision déjà rendue, parcours complet, visibilité
  publique sans fuite).
- OpenAPI ciblé : **11 passés**, dont la correction du paragraphe contradictoire.
- Ruff, format et mypy : succès sur le périmètre (typage de 6 fichiers).
- Collecte : **1 056 tests**, après retrait de cinq doublons. Ce n'est pas
  un passage complet. Les autres garanties et comptes de tests sont conservés.
- La trace de Claude confirme **1 061 réussites en 1 066,82 secondes** avant
  la revue. Ce résultat est réutilisé ; aucune suite complète supplémentaire.
  Après une retouche de format d'assertion, seuls les contrôles de format/lint
  ont été relancés, pas les tests déjà réussis.

Les anciennes suites transitions/lecture/création/PATCH/enfants n'ont pas été
cumulées avec le passage final. La relance OpenAPI localisée après échec est
justifiée ; la durée de presque dix-huit minutes de la suite complète est
distincte du temps d'implémentation. Les simulations sous verrou ne sont pas
des essais PostgreSQL multithread.

Rapport et copie scratchpad synchronisés. Aucune lecture de secrets, aucune
écriture dans la base de développement, aucun compte ou donnée de démonstration
créé par cette revue. Aucun commit/push ; le Pipfile du pilotage reste intact.

## 8. Postman et clôture — 1er novembre 2026

La nouvelle méthode pédagogique est consignée dans le pilotage : explications
du code dans `docs/verifications-code/phase-4-increment-6-moderation.md`,
lecture différée et liste des vérifications avec leur objectif avant Postman.
La revue technique reste préalable et proportionnée, sans déroulé de code
obligatoire dans le chat.

Exercices réalisés et confirmés par l'auteur sur la seule fiche fictive
demo-create-hero-a (072bc48e-37e6-4a36-acaf-b13cc2065ae3) :

- Point initial en draft, propriétaire 3 ; soumission par demo-contrib-a.
- Publication tentée par le contributeur : 403, bon message.
- Avec demo-selecteur : reject sans motif refusé (400, review_notes requis),
  puis rejet avec motif accepté ; GET public sans authentification en 404.
- Avec demo-contrib-a : resume conserve le motif de rejet ; nouvelle
  soumission efface la revue antérieure et revient en submitted.
- Avec le relecteur : publication acceptée avec la note « Reviewed and approved
  during the Postman exercise. » ; GET public en 200 confirmé. L'absence des
  champs de revue dans ce GET a été demandée, sans réponse détaillée distincte :
  cette garantie reste vérifiée automatiquement, pas suraffirmée ici.
- Reopen par le relecteur : 403 attendu.
- Avec l'administrateur heric : reopen accepté ; réponse fournie confirmant
  draft, submitted_at null, propriétaire 3, reviewed_by 5 et revue conservée
  (reviewed_at 2026-11-01T11:22:54.404608Z).
- GET public final sans authentification : disparition confirmée, 404 attendu.

La disparition publique après reopen n'est pas une suppression : la fiche
reste en privé, sans version publiée conservée en parallèle dans cette V1.
État final : draft, catégorie « Village protector after withdrawal », sources
et relations vides, Ghana en pays secondaire. Aucun nouvel enfant ou compte
créé ; pas de nettoyage supplémentaire. Les quatre fiches du corpus restent
inchangées. Les autres cas de droits, notes et concurrence restent couverts
automatiquement et ne sont pas présentés comme exécutés à la main.

Incrément 6 validé et clôturé ; phase 4 encore ouverte. Roadmap et document
pédagogique actualisés. Résultats de la section 7 réutilisés, sans modification
fonctionnelle depuis la revue ni nouvelle exécution complète. Clôture Git normale
des deux dépôts sous l'identité de l'auteur ; Pipfile non suivi hors périmètre.
Prochaine étape : incrément 7 — suppression logique et restauration, à cadrer.
