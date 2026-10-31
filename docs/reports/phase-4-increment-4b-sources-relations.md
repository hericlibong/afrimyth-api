# Phase 4 — Incrément 4B : écritures des sources et relations

Rapport d'intervention, en français. Aucun secret, aucune valeur de `.env`,
aucun mot de passe et aucun jeton n'y figure.

Intervention : Claude CLI, 30 octobre 2026, sur le prompt
`docs/prompts/phase-4-increment-4b-sources-relations.md`. Lot 4B seulement.
Les modifications non committées du lot 4A et du réglage JWT de développement
ont été préservées ; aucune n'a été refaite ni clôturée.

## 1. Périmètre

Six opérations ouvertes, toutes privées :

| Méthode | Route sous `/api/manage/entities/` | Réponse |
| --- | --- | --- |
| POST | `{slug}/sources/` | `201`, source créée |
| PATCH | `{slug}/sources/{source_id}/` | `200`, source modifiée |
| DELETE | `{slug}/sources/{source_id}/` | `204` sans corps |
| POST | `{slug}/relations/` | `201`, relation créée |
| PATCH | `{slug}/relations/{relation_id}/` | `200`, relation modifiée |
| DELETE | `{slug}/relations/{relation_id}/` | `204` sans corps |

Aucune route GET d'enfant, aucune pagination : la lecture reste dans le GET
privé de l'entité. `PUT` reste fermé partout, et `GET`/`PUT` sur ces URL
répondent `405`. Les suppressions ne retirent que la ligne `Source` ou
`EntityRelation` visée : ni entité, ni profil, ni fiche cible, sans corbeille
ni historique.

Hors périmètre, inchangés : transitions de statut, suppression et restauration
d'entités, reclassement de type, schéma, migrations, import, configuration JWT.

## 2. Fichiers touchés

### Ajouté

| Fichier | Rôle |
| --- | --- |
| `mythology/tests/test_private_children.py` | 66 cas : parcours, contrats, cibles, droits, isolement du parent |
| `docs/reports/phase-4-increment-4b-sources-relations.md` | Ce rapport |

### Modifiés

| Fichier | Changement |
| --- | --- |
| `mythology/serializers.py` | `SourceWriteSerializer`, `RelationWriteSerializer`, `rejected_key_errors()`, `save_validated()`, `patched_and_saved()` ; messages 4A/3 réorientés vers les nouvelles routes |
| `mythology/views.py` | Quatre actions imbriquées, `locked_record()`, `saved_child()`, `readable_relations()`, annotations OpenAPI des six opérations |
| `mythology/schema.py` | Descriptions, paramètres d'identifiant, exemples et réponses 400/404 des enfants ; textes de l'entité réorientés |
| `README.md` | Section *Write the documentary sources and relations of a record*, tableaux et statut du projet |
| `mythology/tests/test_openapi.py` | Chemins et méthodes attendus, 25 cas sur le contrat réellement ajouté |

Aucun modèle, aucune migration, aucun compte ni donnée de développement n'a été
touché. `makemigrations --check` ne détecte rien. Le corpus et
`demo-create-hero-a` n'ont pas été modifiés.

## 3. Choix concrets

- **Quatre actions DRF plutôt qu'un routeur imbriqué.** `@action(detail=True,
  url_path="sources/(?P<source_id>[0-9]+)")` sur le viewset privé existant
  suffit : le `DefaultRouter` construit la route, le parent est déjà celui du
  détail, et ses droits sont déjà évalués par `get_object()` et
  `CanEditEntity`. Aucune bibliothèque, aucune nouvelle vue, aucune couche.
- **Un seul contrat de sécurité, celui du parent.** `is_privately_editable`
  n'est pas redéfinie : une écriture d'enfant demande exactement le droit de
  modifier la fiche porteuse. `401` sans JWT, `403` sans rôle ou sur un parent
  lisible non modifiable, `404` identique pour un parent inconnu, non lisible
  ou supprimé.
- **Verrou puis réévaluation.** `locked_record()` est un gestionnaire de
  contexte : il relit la fiche en `select_for_update()`, refait le contrôle de
  droit sur cet état, dans la transaction ouverte avant la lecture verrouillée.
  L'enfant est
  chargé et écrit. Une transition concurrente ne peut donc pas être contournée.
  L'enfant est relu dans cette même transaction pour le PATCH.
- **L'enfant est cherché dans son parent.** `entity.sources` pour une source,
  `private_relations(...).filter(from_entity=entity)` pour une relation. Un
  identifiant inexistant, appartenant à une autre fiche, ou désignant une
  relation vers une cible masquée, donne le même `404` — sans fuite du nom, de
  l'UUID ni du statut de la cible.
- **Le parent vient de l'URL.** `entity` et `from_entity` sont injectés par
  `serializer.save(...)`, jamais lus dans le corps ; `id`, `entity`,
  `entity_id`, `from_entity`, `from_entity_id`, `to_entity_id` et toute clé
  inconnue sont refusés nommément, par le même `rejected_key_errors()` que les
  écritures d'entité.
- **Validations réutilisées, pas réécrites.** `save_validated()` appelle
  `full_clean()` : choix de `kind`, longueurs, format d'URL et de date, label
  non blanc, règle « exactement une cible », refus de l'auto-relation et
  unicité du triplet viennent du modèle, avec exclusion de la ligne elle-même
  lors d'un PATCH. Aucune requête réseau n'est faite sur une URL. Aucune
  unicité n'est ajoutée sur les sources : les doublons documentaires restent
  permis.
- **`to_entity` par UUID, résolu dans la politique privée.** `validate_to_entity`
  cherche la cible dans `private_entities(roles, caller_id)` : lisible et non
  supprimée suffit, être modifiable n'est pas requis. Cible interdite,
  supprimée ou inconnue : même message.
- **Réponses existantes réutilisées.** `SourceSerializer` et
  `EntityRelationSerializer` servent les corps `201`/`200` ; aucune nouvelle
  forme de sortie.
- **Le parent n'est jamais écrit.** Aucun `save()` sur l'entité : statut,
  propriétaire, type, profil, marques de revue et `updated_at` restent
  identiques, comme pour les éditions directes actuelles des enfants.
- **Messages 4A/3 réorientés.** Les refus de `sources`, `relations`,
  `relations_from` et `relations_to` dans le corps d'une entité nomment
  désormais la route dédiée au lieu d'annoncer une écriture indisponible.

## 4. Vérifications exécutées

| Commande | Résultat |
| --- | --- |
| `python manage.py check` | aucun problème |
| `python manage.py makemigrations --check --dry-run` | `No changes detected`, sortie `0` |
| `python manage.py spectacular --validate --fail-on-warn` | sortie `0`, aucun avertissement |
| `pytest mythology/tests/test_private_children.py` | 66 passés |
| `pytest mythology/tests/test_openapi.py` | 133 passés |
| `pytest` | **888 passés** en 12 min 55 s, aucun échec, aucun ignoré (796 avant) |
| `ruff check .` | `All checks passed!` |
| `ruff format --check .` | `58 files already formatted` |
| `mypy .` | `Success: no issues found in 58 source files` |

Le schéma a été écrit dans un fichier temporaire hors du dépôt. Les six
opérations apparaissent bien comme quatre chemins distincts, avec les
composants d'entrée `SourceWriteRequest`, `PatchedSourceWriteRequest`,
`RelationWriteRequest` et `PatchedRelationWriteRequest`.

Aucun blocage rencontré : aucune correction n'a été nécessaire après la
première passe de contrôles statiques.

## 5. Limites connues

- **Une ligne par requête.** Aucune écriture en lot : attacher cinq sources
  demande cinq appels. Chaque appel est atomique, mais la série ne l'est pas.
- **Pas de verrouillage optimiste.** Aucun `ETag`, aucune version de ligne :
  deux PATCH simultanés sur le même enfant se sérialisent, et le dernier écrit
  ses valeurs sans détection de conflit. Le verrou ne protège que la
  réévaluation du droit sur le parent.
- **Le nom d'une contrainte peut apparaître.** Une violation d'unicité de
  relation remonte le message Django par défaut, sous `non_field_errors` ;
  ce message technique est conservé ici. Le reformuler à la frontière API
  ne nécessiterait pas forcément de migration.
- **Aucune résolution automatique par nom.** Passer d'un `to_name` à un
  `to_entity` reste une requête explicite portant les deux clés, et l'inverse
  aussi. Aucun rapprochement de noms n'est tenté.
- **Aucun inverse, réciproque ni contrôle de cycle**, conformément au modèle :
  une relation écrite est une seule ligne orientée.
- **Les routes d'écriture des enfants restent privées** et les enfants restent
  refusés dans les corps POST/PATCH d'une entité. Leur représentation reste
  imbriquée dans les détails privés et publics, selon la visibilité existante.
- **Pas de limitation de débit** sur des routes qui écrivent.

## 6. État Git

Rien n'est committé ni poussé.

### `afrimyth-api` — HEAD `86d7fd8`

```
 M .env.example
 M CLAUDE.md
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
 M tests/test_settings.py
?? docs/reports/phase-4-increment-4a-update.md
?? mythology/tests/test_private_children.py
?? mythology/tests/test_private_update.py
```

Ce rapport s'ajoute aux fichiers non suivis. `.env.example`, `CLAUDE.md`,
`config/settings.py` pour la durée de jeton et `tests/test_settings.py`
appartiennent aux changements antérieurs de l'auteur, préservés tels quels ;
`mythology/tests/test_private_update.py` et le rapport 4A appartiennent au
lot 4A.

### `django-portfolio` — HEAD `5633bce`

Aucun fichier de ce dépôt n'a été modifié par cette intervention.

## 7. Revue Codex — 30 octobre 2026

### Conclusion et corrections localisées

Pas de défaut bloquant relevé dans la sélection du parent, les droits repris
du lot 4A, le rattachement serveur ou le filtrage des cibles. Quatre actions DRF
pour six opérations, sans routeur tiers ni couche générique anticipée : les
petites fonctions partagées servent réellement aux deux types d'enfants.
Les 66 cas API couvrent principalement des comportements distincts ; aucune
suppression de protection n'est proposée pour réduire artificiellement ce total.

Corrections appliquées directement par Codex :

- Le schéma des réponses 400 utilisait `CreationErrorSerializer`, qui décrit
  surtout les champs d'une Entity. Il décrit désormais correctement un objet
  à clés de champs variables et listes de messages, sans nouvelle classe.
  Un test protège cette forme sur les quatre écritures POST/PATCH d'enfants.
- Le test dédié à l'absence de GET d'enfant doublonnait la comparaison exacte
  des méthodes de toutes les routes : il est remplacé par ce test des erreurs.
  Quatre boucles d'exclusion de champs, déjà garanties par leur ensemble exact,
  sont aussi retirées, sans perte de couverture.
- Le test paramétré des droits ne crée plus systématiquement un relecteur et
  un administrateur inutilisés : seul le compte nécessaire au cas est créé.
- Précisions documentaires : enfants lisibles dans le détail public quand la
  fiche est publique, transactions ouvertes avant le verrou, cinq minutes hors
  debug préservées, refus de suppression concernant les entités et non les enfants.
  Le commentaire du test des routes est actualisé. Le message technique Django
  d'unicité n'impose pas à lui seul une future migration pour être reformulé.

### Vérifications de revue

- Parcours sources/relations, permissions échantillonnées, isolation du parent,
  relation masquée et contrôle sous verrou : **13 passés**.
- Schéma des opérations d'enfants et règles de cible : **26 passés**.
- Ruff, format et mypy sur les trois fichiers concernés : succès.
- Collecte : **888 tests**, sans nouveau passage complet. Les 888 réussites
  de Claude ci-dessus précèdent les corrections localisées de cette revue.
- Le total antérieur exact était 796 (794 après revue 4A, puis deux tests
  debug/hors debug), pas 804. Le rapport est rectifié sans réécrire les
  résultats historiques de Claude.

### Relances et durée

Les traces montrent la suite enfants (66), OpenAPI (133), le lancement séparé
des trois anciennes suites création/modification/lecture, puis la suite complète
(888, environ treize minutes). Les dernières modifications visibles avant le
passage complet concernaient le README ; aucun échec ou changement fonctionnel
n'y justifie le cumul des anciennes suites avec la suite complète. Cette partie
est donc une répétition évitable, sans remettre en cause l'utilité des tests.
Les résultats des anciennes suites ne sont pas détaillés dans le tableau
initial du rapport : on ne leur attribue pas de décompte de réussites non vérifié.

La consigne est précisée dans les deux dépôts : ne pas lancer séparément les
anciennes suites juste avant le passage complet, sauf modification pertinente
ou échec identifié entre les deux. Aucun motif interne de Claude n'est supposé.

Prêt pour la revue pédagogique puis les exercices Postman 4B, pas pour une
clôture déjà acquise. Aucun secret ni donnée de développement consulté/modifié
par cette revue, aucun commit ou push. Le `Pipfile` du pilotage reste intact.

## 8. Validation pédagogique et pratique — 31 octobre 2026

L'auteur confirme la compréhension des routes, transactions, droits du parent,
serializers, règles de cible et recherches d'enfants limitées à leur fiche.
Les exercices Postman ont utilisé le contributeur A et la seule fiche fictive
`demo-create-hero-a`, sans changement du corpus.

- Source fictive id 2 : POST réussi, PATCH notes/date avec champs omis
  conservés ; label vide refusé, puis GET du parent confirmant que les notes
  de la tentative refusée n'ont pas été enregistrées.
- Relation fictive id 10 : POST vers le nom libre Demo Ancestor, PATCH des
  seules notes, et refus d'une cible égale à la fiche porteuse.
- Une répétition involontaire du POST de relation a confirmé le refus du
  doublon (400, contrainte unique_unresolved_relation), sans seconde création.
  La différence Save/Send dans Postman a été expliquée.
- PATCH de la source 2 sous le slug anansi : 404, confirmant l'isolation
  des enfants entre fiches, sans modification d'Anansi.
- DELETE ciblés de la relation 10 puis de la source 2 : 204 sans corps.
  GET final confirmé par l'auteur : héros toujours présent, sources et
  relations vides. Ces deux éléments fictifs sont supprimés physiquement,
  sans corbeille ; la fiche du héros est conservée.

Les autres croisements de droits/cibles sont couverts par les tests
automatiques et ne sont pas présentés comme exécutés manuellement.
Lot 4B validé ; l'incrément 4 (4A + 4B) est terminé. La phase 4 ne l'est pas :
prochaine étape fonctionnelle, incrément 5 — soumission et reprise.

Clôture Git conjointe des lots 4A/4B le 31 octobre 2026, sans relance des suites
inchangées. Les résultats de revue restent ceux de la section 7. La durée
d'accès de développement reste à 20 minutes (5 hors debug) et devra être
réévaluée avant la finalisation de l'API. Aucun secret ou export de jeton
n'est ajouté aux dépôts. Le Pipfile non suivi du pilotage reste hors commit.
