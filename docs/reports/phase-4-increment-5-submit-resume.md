# Phase 4 — Incrément 5 : soumission, retrait et reprise

Rapport d'intervention, en français. Aucun secret, aucune valeur de `.env`,
aucun mot de passe et aucun jeton n'y figure.

Intervention : Claude CLI, 31 octobre 2026, sur le prompt
`docs/prompts/phase-4-increment-5-submit-resume.md`. Départ API `e3d2781`.

## 1. Périmètre livré

Trois actions `POST` sous `/api/manage/entities/{slug}/` :

| Action | Route | Transition | Écrit |
| --- | --- | --- | --- |
| Soumettre | `submit/` | draft → submitted | `status`, `submitted_at`, et efface `reviewed_at`, `reviewed_by`, `review_notes` |
| Retirer | `withdraw/` | submitted → draft | `status`, `submitted_at=null` ; revue inchangée |
| Reprendre | `resume/` | rejected → draft | `status`, `submitted_at=null` ; revue du rejet conservée |

Succès : `200` au format du détail privé, références filtrées selon
l'appelant. Ces routes n'acceptent que `POST` ; `GET`, `PUT`, `PATCH` et
`DELETE` y répondent `405`.

Rien d'autre n'est ouvert : pas de publication, de rejet, de réouverture
published → draft, de suppression ou de restauration d'entité, pas de PATCH
ordinaire du statut, aucun changement du contrat public, de création, de PATCH
ni des routes sources/relations.

## 2. Fichiers touchés

### Ajoutés

| Fichier | Rôle |
| --- | --- |
| `mythology/transitions.py` | Noms d'actions, statut de départ requis, droit de l'acteur, mutation, messages |
| `mythology/tests/test_private_transitions.py` | 62 cas |
| `docs/reports/phase-4-increment-5-submit-resume.md` | Ce rapport |

### Modifiés

| Fichier | Changement |
| --- | --- |
| `mythology/permissions.py` | `CanEditEntity` ne gouverne plus les trois actions de transition |
| `mythology/views.py` | `run_transition()`, `private_detail_of()`, les trois actions et leurs annotations ; sélection privée nue pour ces actions |
| `mythology/schema.py` | Descriptions et réponses 400/403 des trois actions ; fin de la description du détail privé |
| `config/settings.py` | Description OpenAPI globale : section des transitions, et correction de la phrase 4B restée fausse |
| `README.md` | Section *Submit, withdraw and resume a record*, tableau des droits, statut du projet |
| `mythology/tests/test_openapi.py` | Chemins et méthodes attendus, 14 cas sur le contrat ajouté |

Aucun modèle, migration, compte, groupe, réglage JWT, administration Django ni
donnée de développement n'a été touché. `makemigrations --check` ne détecte
rien ; les durées de jeton (20 min en développement, 5 hors debug) sont
inchangées.

## 3. Décisions concrètes

- **Le droit de transition est distinct du droit de PATCH.** `CanEditEntity`
  et `is_privately_editable()` refusent — correctement — qu'un contributeur
  modifie sa fiche `submitted` : ils ne peuvent donc pas décider d'un
  `withdraw`. `CanEditEntity.has_object_permission()` rend donc la main sur les
  trois actions nommées dans `TRANSITION_ACTIONS`, et `may_transition()` décide
  seule : contributeur propriétaire, relecteur, administrateur. Les anciennes
  routes gardent exactement leur protection, et aucun appelant authentifié ne
  gagne de droit par défaut.
- **Un petit module métier, pas un moteur.** `mythology/transitions.py`
  contient les trois noms d'action, les statuts requis, trois fonctions et les messages. Aucun FSM, aucun
  registre de transitions futures, aucun signal. Les vues restent des
  adaptateurs : `run_transition()` enchaîne les contrôles et délègue.
- **Ordre des refus respecté et vérifié.** Sélection privée (`404`), droit de
  l'acteur (`403`), statut de départ puis corps (`400`). Un test vérifie que le
  statut est signalé avant le corps.
- **Réévaluation sur la ligne verrouillée.** `run_transition()` relit la fiche
  par `private_entities(...).select_for_update()` : visibilité, droit et statut
  sont jugés sur cet état, jamais sur l'objet lu par `get_object()`. Le `404` de
  cette relecture passe par `get_object_or_404`, donc avec le même corps que
  celui des autres `404` privés.
- **`save(update_fields=...)`** limite l'écriture aux colonnes concernées, plus
  `updated_at` : propriétaire, type, champs métier, profil, référentiels,
  enfants, marques de suppression et `created_at` ne peuvent pas bouger. Pas de
  `full_clean()` : les seules valeurs posées viennent du serveur, et rien ne
  justifiait une seconde validation.
- **Corps refusé, pas ignoré.** Seuls un corps absent et un objet JSON vide
  sont acceptés ; le test porte sur `isinstance(data, Mapping) and not data`,
  ce qui refuse aussi un tableau, une chaîne et un formulaire non vide. Aucun
  serializer d'entrée n'a été créé : `request=None` dans OpenAPI, et les deux
  formes vides sont décrites dans chaque description.
- **Aucun seuil de complétude.** La soumission ne vérifie ni description, ni
  nombre de sources, ne remplit aucune donnée métier et ne crée aucun profil.

## 4. Vérifications exécutées, dans l'ordre du prompt

**Pendant l'implémentation** — tests ciblés du nouveau fichier et de la suite
OpenAPI, seule ancienne suite directement affectée par les chemins ajoutés :

| Commande | Résultat |
| --- | --- |
| `pytest mythology/tests/test_private_transitions.py` | 62 passés |
| `pytest mythology/tests/test_openapi.py` | 147 passés |

Trois relances ciblées, chacune sur le seul contrôle affecté :

1. Deux tests de concurrence échouaient : le `monkeypatch` visait
   `Entity.objects.select_for_update`, alors que la vue appelle
   `QuerySet.select_for_update()`. La simulation patche désormais la lecture
   verrouillée elle-même, ce qui reproduit exactement la fenêtre visée.
2. Le test « droit perdu entre-temps » attendait `403` sur une simple
   réattribution : réattribuer rend la fiche non lisible, donc `404` — c'est le
   comportement correct, et l'attente du test était fausse. Le cas a été
   reformulé sur une fiche devenue publiée **et** réattribuée : lisible, donc
   `403` par la règle d'acteur. Un second ajustement a retiré une assertion sur
   l'état persisté : la mutation simulée vit dans la transaction de la requête
   et son annulation fait partie du résultat attendu.
3. Deux assertions OpenAPI citaient des fragments de texte inexacts (balises
   `**` et formulation du 403) ; corrigées, suite OpenAPI relancée seule.

**Avant le passage final :**

| Commande | Résultat |
| --- | --- |
| `python manage.py check` | aucun problème |
| `python manage.py makemigrations --check --dry-run` | `No changes detected`, sortie `0` |
| `python manage.py spectacular --validate --fail-on-warn` | sortie `0`, aucun avertissement |
| `ruff check .` | `All checks passed!` |
| `ruff format --check .` | `60 files already formatted` |
| `mypy .` | `Success: no issues found in 60 source files` |

**Passage complet final, une seule fois :**

| Commande | Résultat |
| --- | --- |
| `pytest` | **964 passés** en 14 min 48 s, aucun échec, aucun ignoré (888 avant) |

Les anciennes suites création/PATCH/lecture/enfants n'ont pas été relancées
séparément : elles sont incluses dans ce passage. Le schéma a été écrit dans un
fichier temporaire hors du dépôt.

## 5. Limites et points signalés

- **Aucune décision de modération.** Une fiche soumise ne peut être ni publiée
  ni rejetée : l'incrément 6 renseignera `reviewed_at`, `reviewed_by` et
  `review_notes`. Une fiche `rejected` ne peut être produite aujourd'hui que
  par l'administration Django.
- **Pas d'historique.** Les quatre champs portent l'état courant et la dernière
  revue conservée. Aucune table d'audit, aucun champ ajouté.
- **Concurrence bornée.** Le verrou protège la réévaluation du droit, de la
  visibilité et du statut ; il n'y a ni `ETag` ni version de ligne, et aucune
  promesse hors API.
- **Écart constaté hors de cet incrément, corrigé au passage.** La description
  OpenAPI globale affirmait encore, depuis le lot 4B, que l'écriture des
  sources et relations était différée. La phrase se trouvant dans le paragraphe
  à réécrire pour les transitions, elle a été rectifiée plutôt que laissée
  fausse. Aucun autre passage n'a été retouché.
- **Pas de limitation de débit** sur des routes qui écrivent.

Aucun blocage, aucune décision incompatible avec le prompt rencontrée.

## 6. État Git

Rien n'est coché, committé ni poussé.

### `afrimyth-api` — HEAD `e3d2781`

```
 M README.md
 M config/settings.py
 M mythology/permissions.py
 M mythology/schema.py
 M mythology/tests/test_openapi.py
 M mythology/views.py
?? mythology/tests/test_private_transitions.py
?? mythology/transitions.py
```

Ce rapport s'ajoute aux fichiers non suivis.

### `django-portfolio` — HEAD `b731625`

Aucun fichier de ce dépôt n'a été modifié. Son arbre porte, de l'auteur :
`Pipfile` et `docs/prompts/phase-4-increment-5-submit-resume.md` non suivis.

## 7. Revue Codex — 31 octobre 2026

### Conclusion

Pas de défaut bloquant relevé : le retrait du propriétaire d'un submitted
dispose du droit distinct demandé, les anciennes écritures restent protégées,
et la visibilité, l'acteur et le statut sont relus sous verrou avant mutation.
Les dates et notes correspondent au prompt ; les autres colonnes sont exclues
du save. Trois petites actions et un module métier dédié, pas de moteur de
workflow ni de découpage global ajouté. Aucune correction fonctionnelle nécessaire.

### Corrections localisées

- Description globale OpenAPI : PUT/DELETE refusés sont désormais explicitement
  ceux de la collection et du détail d'entité, pas des routes d'enfants où DELETE
  est autorisé. Le texte confirme aussi que withdraw comme resume préserve les
  marques de revue, au lieu d'affirmer que seul resume les conserve.
- Trois cas heureux doublonnaient les tests de succès dans la matrice des
  statuts interdits ; ils sont retirés de cette matrice sans perdre de garantie.
  Le test d'objet JSON vide ne refait plus le parcours sans corps déjà vérifié
  par les tests de succès : trois appels et trois réinitialisations inutiles
  sont évités. La couverture des deux formes vides est conservée.
- Le test OpenAPI existant contrôle les deux précisions documentaires.
- Date d'intervention rectifiée au 31 octobre ; 14 nouveaux cas OpenAPI,
  et non 15 ; trois fonctions de transitions, et non deux.

### Vérifications et durée

- Tests ciblés transitions (statuts refusés, objet vide, retrait du propriétaire,
  revue réinitialisée, simulation d'état/droit changé sous verrou et blocage
  des écritures après soumission) : **17 passés**.
- Tests OpenAPI relatifs aux transitions et limites de modération : **14 passés**.
- Ruff, format et mypy sur le périmètre : succès (typage, 6 fichiers).
- Collecte après simplification : **961 tests** ; il s'agit d'un décompte,
  pas d'un nouveau passage complet.
- Le passage complet de Claude est confirmé par sa trace : **964 passés en
  887,70 secondes**. Il précède la simplification locale de trois cas redondants.
  Pas de nouvelle exécution complète ; les changements de revue ne modifient
  pas les permissions ni les transitions.

Contrairement au lot 4B, les anciennes suites création/PATCH/lecture/enfants
n'ont pas été lancées séparément avant la suite complète. Les corrections
de tests en cours de développement sont justifiées par les échecs indiqués
plus haut. Le temps complet (environ quinze minutes) explique une part
importante de la durée totale. Les lectures répétées de fichiers pendant
l'attente étaient superflues mais ne sont pas des relances de pytest.
Les vérifications de concurrence sont des simulations de changement
intermédiaire, pas une mesure de concurrence réelle multithread.

Rapport et copie scratchpad synchronisés après cette revue. Aucun secret,
aucune modification des données de développement ; aucun commit ni push.
Le code est prêt pour l'explication et les exercices Postman, pas encore
pour la clôture de l'incrément 5. Le Pipfile du pilotage reste hors périmètre.

## 8. Validation pédagogique, Postman et clôture — 31 octobre 2026

L'auteur confirme la compréhension des règles d'acteur, statuts requis,
mutations ciblées, contrôle sous verrou, corps vide et trois routes.
Exercices réalisés avec demo-contrib-a sur la seule fiche fictive
demo-create-hero-a (UUID 072bc48e-37e6-4a36-acaf-b13cc2065ae3) :

- GET initial : draft, propriétaire 3, submitted_at null, sources/relations vides.
- POST submit sans corps : 200, submitted, submitted_at renseigné et contenu
  conservé. PATCH category par le contributeur : 403 attendu.
- POST withdraw sans corps : 200, draft, submitted_at null ; la catégorie
  initiale est conservée, confirmant l'absence d'écriture du PATCH refusé.
- PATCH ensuite autorisé (200), catégorie désormais
  « Village protector after withdrawal ».
- POST submit avec status=published dans le corps : 400, action sans entrée.
- POST withdraw sur ce draft : 400 pour mauvais statut de départ.
- Préparation manuelle : seul le statut de la fiche fictive a été passé à
  rejected dans l'administration, puisque le rejet API relève de l'incrément 6.
- POST resume sans corps : 200 confirmé, retour draft, submitted_at null,
  propriétaire 3 et catégorie conservés.

Le parcours est validé. La conservation d'anciennes notes de rejet et leur
effacement à la nouvelle soumission, les autres acteurs et les écritures
d'enfants bloquées sont couverts automatiquement, pas présentés comme testés
manuellement ici. Aucun compte ou nouvel enfant créé ; aucun nettoyage
supplémentaire nécessaire. La fiche fictive reste disponible pour la suite,
en draft avec ses références antérieures. Le corpus n'a pas été modifié.

Incrément 5 terminé ; phase 4 toujours ouverte. Rapport et roadmap actualisés,
résultats automatiques de la section 7 réutilisés sans nouveau passage complet,
seules retouches documentaires depuis la revue. Clôture Git normale des deux
dépôts sous l'identité de l'auteur ; Pipfile non suivi conservé hors périmètre.
Prochaine étape : incrément 6 — modération, à cadrer avant implémentation.
