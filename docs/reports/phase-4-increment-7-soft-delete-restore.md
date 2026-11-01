# Phase 4 — Incrément 7 : suppression logique et restauration

Rapport d'intervention, en français. Aucun secret, aucune valeur de `.env`,
aucun mot de passe et aucun jeton n'y figure.

Intervention : Claude CLI, 1er novembre 2026, sur le prompt
`docs/prompts/phase-4-increment-7-soft-delete-restore.md`. Départ API
`55353da`.

## 1. Périmètre livré

| Opération | Route | Réponse |
| --- | --- | --- |
| `DELETE` | `/api/manage/entities/{slug}/` | `204` sans corps |
| `POST` | `/api/manage/entities/{slug}/restore/` | `200`, détail privé |

La suppression est **logique** : seuls `deleted_at`, `deleted_by` et
`updated_at` sont écrits. Aucun `Entity.delete()`, aucun `QuerySet.delete()`,
aucune cascade. Les `DELETE` des sources et des relations gardent leur
contrat inchangé. `PUT` reste fermé, `restore/` n'accepte que `POST`.

Rien d'autre : aucune suppression physique, purge, corbeille, liste ou `GET`
de fiches supprimées, aucun paramètre `include_deleted`, aucune action en lot,
aucun nouveau statut, champ, audit ni permission Django. Aucun modèle,
migration, bibliothèque, compte, groupe, réglage JWT ni donnée de
développement touché ; les deux managers restent inchangés.

## 2. Fichiers touchés

### Ajoutés

| Fichier | Rôle |
| --- | --- |
| `mythology/deletion.py` | Droits, protection des variantes, verrou de référence, écriture des marques |
| `mythology/tests/test_private_deletion.py` | 51 cas |
| `mythology/tests/test_variant_lock_order.py` | 1 régression multiconnexion (correction du point 6) |
| `docs/reports/phase-4-increment-7-soft-delete-restore.md` | Ce rapport |

### Modifiés

| Fichier | Changement |
| --- | --- |
| `mythology/permissions.py` | `SELF_GOVERNED_ACTIONS` : `CanEditEntity` ne gouverne ni les transitions ni ces deux opérations |
| `mythology/views.py` | `destroy()`, `restore()`, `reject_request_body()` factorisé, sélection privée nue pour ces actions |
| `mythology/serializers.py` | Acquisition ordonnée des lignes dans `create()` et `update()`, `require_active_reference()` ; message de référence non sélectionnable extrait |
| `mythology/schema.py` | Descriptions, réponses 400/403 des deux opérations ; fin de la description du détail privé |
| `config/settings.py` | Description OpenAPI globale : section suppression/restauration, paragraphe général rectifié |
| `README.md` | Section *Delete a record logically, and restore it*, tableau des droits, statut du projet |
| `mythology/tests/test_private_create.py` | Garde-fou de la vue : `destroy` est routé, `update` non |
| `mythology/tests/test_private_read.py` | Les refus `405` du détail ne couvrent plus `DELETE` |
| `mythology/tests/test_private_update.py` | Même adaptation, manquée au premier passage (point 6) |
| `mythology/tests/test_openapi.py` | Chemins et méthodes attendus, 6 cas sur le contrat ajouté |

## 3. Choix concrets

- **Un droit par opération, distinct de celui du PATCH.** `may_delete()`
  applique la matrice de l'ADR 0002 : administrateur tous statuts,
  relecteur `draft`/`rejected` seulement, contributeur ses propres
  `draft`/`rejected`. `may_restore()` exige l'administrateur. Comme
  `is_privately_editable()` autorise justement un relecteur à modifier un
  `submitted`, les deux noms d'action rejoignent `SELF_GOVERNED_ACTIONS` :
  `CanEditEntity` leur rend la main, et rien n'élargit les écritures ou
  transitions existantes. Un test prouve sur une même fiche qu'un relecteur
  PATCH un `submitted` en `200` et le supprime en `403`.
- **Restauration : rôle avant recherche.** `restore()` vérifie
  l'administrateur **avant** toute lecture, si bien qu'un non-administrateur
  reçoit le même `403` pour un slug existant et pour un slug inconnu. Le
  recherche par slug autorisant une fiche supprimée est propre à restore ;
  les lectures, PATCH, enfants et transitions gardent leur sélection privée.
- **Protection des variantes, coordonnée et non naïve.** `DELETE` verrouille
  la fiche puis appelle `has_active_variant()`. En contrepartie, les trois
  chemins API qui rendraient une fiche variante active — création, PATCH de
  `variant_of`, restauration d'une variante — verrouillent la **référence** et
  revérifient `deleted_at` sur la ligne verrouillée. Une requête concurrente
  attend donc ce verrou, puis constate la suppression ; un simple `exists()`
  sans cette discipline aurait laissé passer une variante derrière le
  contrôle.
- **Ordre de verrous.** Première version : la fiche écrite d'abord, la
  référence ensuite. La revue a montré que cet ordre était insuffisant ; il est
  corrigé au point 6, qui décrit la discipline effectivement retenue.
- **Marques et état conservés.** `save(update_fields=[...])` limite l'écriture
  aux deux colonnes plus `updated_at`. Statut, propriétaire, soumission,
  revue, contenu, profil, référentiels et enfants sont intacts ; la
  restauration conserve le statut antérieur, donc une fiche supprimée alors
  qu'elle était publiée redevient publique.
- **Corps refusé après visibilité et droit.** `reject_request_body()`, extraite
  de la validation des transitions, sert les trois cas sans entrée. Un acteur
  refusé ne reçoit aucun diagnostic sur le corps.
- **Aucun selector public réécrit.** L'invisibilité d'une fiche supprimée et
  le masquage des références viennent des filtres existants ; seuls des tests
  l'attestent.

## 4. Vérifications exécutées, dans l'ordre du prompt

**Pendant le développement** — nouveaux tests ciblés, puis les seules anciennes
suites directement affectées par l'ouverture de `DELETE` :

| Commande | Résultat |
| --- | --- |
| `pytest mythology/tests/test_private_deletion.py` | 49 passés, 2 échoués, puis **51 passés** |
| `pytest mythology/tests/test_openapi.py` | 164 passés, 1 échoué |

Trois relances ciblées, chacune limitée au contrôle concerné :

1. `test_les_references_vers_une_fiche_supprimee_sont_masquees` échouait en
   `400` : la fiche cible portait une variante active, donc la protection
   jouait. Le test ne pouvait pas atteindre cet état par l'API — c'est
   précisément l'invariant qui fonctionne — et pose désormais `deleted_at` par
   la fabrique, ce que la docstring explique.
2. `test_un_patch_de_variant_of_verrouille_la_reference` renvoyait `200` : le
   crochet de simulation visait `mythology.views.get_object_or_404`, que le
   PATCH n'emprunte pas, si bien que la suppression simulée n'avait pas lieu.
   Le point d'injection correct est `Entity.objects.select_for_update`, appelé
   par `update()` au moment de verrouiller. Les deux tests ont été relancés
   seuls, puis la suite de suppression entière.
3. Une assertion OpenAPI citait « not delete it » là où la description dit
   « allowed to delete it » ; corrigée et relancée seule (2 cas), sans refaire
   toute la suite OpenAPI.

Dans les trois cas le défaut venait des tests, pas du code livré.

**Avant le passage final :**

| Commande | Résultat |
| --- | --- |
| `python manage.py check` | aucun problème |
| `python manage.py makemigrations --check --dry-run` | `No changes detected`, sortie `0` |
| `python manage.py spectacular --validate --fail-on-warn` | sortie `0`, aucun avertissement |
| `ruff check .` | `All checks passed!` |
| `ruff format --check .` | `63 files already formatted` |
| `mypy .` | `Success: no issues found in 63 source files` |

**Passage complet final, une seule fois :**

| Commande | Résultat |
| --- | --- |
| `pytest` | **1 108 passés, 1 échoué** en 18 min 28 s |

L'unique échec est un ancien test que je n'avais pas repéré comme affecté :
`test_private_update.py::test_le_remplacement_et_la_suppression_restent_refuses[delete]`
attendait encore `405` sur `DELETE /api/manage/entities/{slug}/`, exactement
l'opération que cet incrément ouvre. J'avais adapté les refus équivalents de
`test_private_read.py` mais pas celui-là. Correction au point 6 ci-dessous.

Les anciennes suites lecture/création/PATCH/enfants/transitions/modération
n'ont pas été relancées séparément : elles sont incluses dans ce passage. Le
schéma a été écrit dans un fichier temporaire hors du dépôt.

## 5. Limites

- **Pas de purge.** Aucune suppression physique n'existe ; une fiche supprimée
  reste en base indéfiniment, avec tous ses enfants.
- **Pas d'historique.** `deleted_at` et `deleted_by` portent le dernier état,
  pas une suite d'événements. Une restauration les efface.
- **Protection limitée à `variant_of`.** Une relation sortante ou entrante ne
  bloque pas une suppression, conformément à l'ADR 0002.
- **État hérité possible.** Une variante active sous une référence supprimée
  n'est plus atteignable par l'API, mais une base préexistante peut en
  contenir : la lecture la masque alors sans la réparer.
- **Garantie bornée aux chemins API.** Le verrou coordonne les écritures
  passant par l'API ; une écriture SQL directe, l'administration Django ou
  l'import ne sont pas couverts. Les tests de `test_private_deletion.py`
  simulent la fenêtre entre sélection et lecture verrouillée dans une seule
  transaction : ce ne sont pas des essais multithread. Seul
  `test_variant_lock_order.py` est réellement concurrent, et sur un seul
  scénario.
- **Pas d'`ETag`, de version de ligne ni de limitation de débit.**

Aucun blocage, aucune décision incompatible avec le prompt rencontrée.

## 6. Correction ciblée de l'ordre des verrous — 1er novembre 2026

Constat de revue Codex, issu de la lecture du code : `update()` verrouillait sa
fiche puis la référence `variant_of`. Deux PATCH croisés autorisés — A désignant
B, B désignant A — prenaient donc les deux mêmes lignes dans des ordres
opposés, d'où un interblocage possible, annulé par PostgreSQL en erreur non
gérée. `restore()` avait la même forme. L'affirmation « aucun cycle possible »
du point 3 était fausse et a été retirée.

**Correction retenue.** `locked_in_pk_order()`, dans `mythology/deletion.py`,
acquiert toutes les lignes nécessaires en **une** requête
`… WHERE id IN (…) ORDER BY id FOR UPDATE`. Le `ORDER BY` place l'étape de
verrouillage au-dessus du tri, donc les lignes sont prises dans un ordre
identique pour tout appelant. Les chemins l'utilisent ainsi :

- PATCH : `{fiche, référence}` en une acquisition, puis droit réévalué sur la
  ligne verrouillée et `require_active_reference()` sur la référence verrouillée ;
- restauration : `{fiche, référence}` de même, les contrôles `deleted_at` et
  « référence encore supprimée » portant sur les lignes verrouillées ;
- création : une seule ligne, la référence, par la même fonction ;
- suppression : inchangée — une seule ligne, donc hors de tout cycle — puis le
  balayage des variantes sous ce verrou.

Plus aucune acquisition tardive, donc plus d'ordre contradictoire. Aucun verrou
global, aucun moteur de reprise, aucune interdiction de cycle ajoutée : un
2-cycle `A ↔ B` reste permis par le modèle, comme avant. Droits, corps,
réponses, filtres et protection des variantes sont inchangés, et la
documentation publique n'avait rien à corriger.

**Régression ajoutée.** `mythology/tests/test_variant_lock_order.py` exécute
les deux PATCH croisés sur **deux connexions réelles**
(`django_db(transaction=True)`, deux threads), bornées par
`SET lock_timeout = '5s'`, un `Barrier` et des `join(timeout=30)` : aucun test
ne peut rester bloqué. Son pouvoir discriminant a été vérifié : avec l'ancien
ordre rétabli temporairement, PostgreSQL répond « interblocage (deadlock)
détecté » et le test échoue ; avec l'acquisition ordonnée, les deux requêtes
aboutissent en `200`. Le fichier a ensuite été restauré à l'identique.

Ce scénario reste **un** cas concurrent borné, pas une preuve que tout
entrelacement est sûr : il couvre précisément le risque signalé.

**Ancien test corrigé.** `test_private_update.py` attendait encore `405` sur
`DELETE` du détail privé — l'échec du passage complet. Il ne vérifie plus que
le refus de `PUT`, le remplacement complet restant fermé.

### Vérifications de la correction

| Commande | Résultat |
| --- | --- |
| `pytest mythology/tests/test_variant_lock_order.py` | 1 passé (et échec attendu avec l'ancien ordre, vérifié puis annulé) |
| `pytest` sur création, PATCH, suppression/restauration et verrous | **236 passés** en 6 min 49 s |
| `python manage.py check` | aucun problème |
| `ruff check .` / `ruff format --check .` | `All checks passed!` / `64 files already formatted` |
| `mypy mythology` | `Success: no issues found in 39 source files` |

Aucune seconde suite complète n'a été lancée : la correction touche deux
chemins d'écriture et un test, tous couverts par les suites ci-dessus, et le
schéma OpenAPI comme la documentation publique sont inchangés.

## 7. État Git

Rien n'est coché, committé ni poussé.

### `afrimyth-api` — HEAD `55353da`

```
 M README.md
 M config/settings.py
 M mythology/permissions.py
 M mythology/schema.py
 M mythology/serializers.py
 M mythology/tests/test_openapi.py
 M mythology/tests/test_private_create.py
 M mythology/tests/test_private_read.py
 M mythology/tests/test_private_update.py
 M mythology/views.py
?? mythology/deletion.py
?? mythology/tests/test_private_deletion.py
?? mythology/tests/test_variant_lock_order.py
```

Ce rapport s'ajoute aux fichiers non suivis.

### `django-portfolio` — HEAD `f894292`

Aucun fichier de ce dépôt n'a été modifié. Son arbre porte, de l'auteur :
`Pipfile` et `docs/prompts/phase-4-increment-7-soft-delete-restore.md` non
suivis.

## 8. Revue Codex après correction — 1er novembre 2026

### Conclusion et périmètre

Le risque de verrous croisés signalé est corrigé par une acquisition commune
ordonnée des lignes. Les contrôles sur la restauration et sur la référence
portent sur les lignes verrouillées. Aucun nouveau défaut bloquant relevé
dans les droits, les marques, la conservation du contenu ou les filtres.
Pas de diversification injustifiée : le module métier, les tests ciblés,
le test multiconnexion demandé et les retouches création/PATCH sont nécessaires
à l'invariant du prompt. Pas de guide, migration, bibliothèque ou fonctionnalité
annexe produit par Claude.

Le passage complet initial n'était pas entièrement vert : 1 108 réussites
et un ancien test de refus DELETE échoué. Il ne doit pas être présenté comme
un passage complet réussi de l'état final. Le test obsolète a été adapté et
les 236 tests de création/PATCH/suppression/verrous ont passé après correction,
sans deuxième exécution complète. Cette distinction est conservée ci-dessus.

### Corrections locales de revue

- Le test de création « verrouille la référence » supprimait celle-ci avant
  l'appel HTTP : la validation du champ suffisait à le faire passer, même
  sans contrôle sous verrou. La suppression simulée intervient désormais
  après résolution du champ et juste avant l'acquisition ordonnée, ce qui
  vérifie la garantie annoncée. C'est une simulation, pas un second test
  multiconnexion.
- Dans les matrices de droits, les comptes et clients inutilisés ne sont
  plus tous créés systématiquement ; fixtures chargées selon le cas. Les
  mêmes combinaisons et assertions sont conservées, sans nouvelle abstraction.
- Commentaire du test PATCH corrigé : il ne prétend plus prendre la fiche
  puis la référence ni appeler une ancienne fonction supprimée.
- Rapport précisé sur l'usage du manager complet : la recherche de restauration
  incluant des supprimés est isolée, mais des helpers internes utilisent aussi
  ce manager avec leurs contrôles. L'état Git inclut le test PATCH modifié.

### Vérifications indépendantes ciblées

- `test_variant_lock_order.py` : **1 passé**, deux connexions réelles et
  attente bornée, sans réintroduire temporairement l'ancien code.
- Suppression/restauration, droits, variantes et création/PATCH coordonnés :
  **23 passés**, dont le test de création renforcé.
- OpenAPI suppression/restauration et marques privées : **5 passés**.
- Ruff, format et mypy conformes sur le périmètre (typage, 5 fichiers).
- Collecte finale : **1 109 tests**, pas une nouvelle suite complète.
  Aucune réexécution des 236 cas ou de la suite complète pour la revue.

Les explications pédagogiques sont déposées par Codex dans le pilotage :
`docs/verifications-code/phase-4-increment-7-soft-delete-restore.md`.
Roadmap mise à jour à l'état « implémenté, corrigé et revu ; pratique en attente ».
L'incrément n'est pas encore clôturé. Aucun secret ou donnée de développement
consulté/modifié par cette revue, aucun commit/push. Pipfile du pilotage intact.

## 9. Postman et clôture — 1er novembre 2026

Les explications du code ont été déposées dans la documentation pédagogique,
et la liste des contrôles et leurs objectifs annoncée avant la pratique.
Résultats confirmés par l'auteur, sur la seule fiche fictive demo-create-hero-a
(072bc48e-37e6-4a36-acaf-b13cc2065ae3) :

- Lecture privée initiale accessible avec demo-contrib-a.
- DELETE par le propriétaire : 204 sans corps.
- GET privé après suppression : 404 ; second DELETE : 404.
- POST restore avec le contributeur : 403, réservé à l'administrateur.
- Connexion administrateur heric puis POST restore : fiche de nouveau accessible,
  résultat attendu 200 confirmé par l'auteur.
- Second POST restore : 400 attendu confirmé, fiche non supprimée.

La fiche fictive est conservée après restauration, sans purge ni création de
compte/enfant. Aucun changement du corpus. Les détails de conservation des
colonnes et du statut, la visibilité d'un published restauré, les variantes
et la concurrence sont garantis par les tests automatiques ; ils ne sont pas
présentés comme tous revérifiés manuellement dans cette séance courte.

Incrément 7 validé et clôturé ; phase 4 toujours ouverte. Roadmap et fiche
pédagogique actualisées ; contrôles déjà acquis réutilisés, sans nouvelle suite
complète pour les seules retouches documentaires. Clôture Git normale des deux
dépôts sous l'identité de l'auteur, Pipfile non suivi conservé hors périmètre.
Prochaine étape : incrément 8 — consolidation et validation finale de la phase 4,
à préparer selon les écarts réels restants, sans lancer un chantier générique.
