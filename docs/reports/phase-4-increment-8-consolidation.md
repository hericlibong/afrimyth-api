# Phase 4 — Incrément 8 : consolidation

Rapport d'intervention, en français. Aucun secret, aucune valeur de `.env`,
aucun mot de passe et aucun jeton n'y figure.

Intervention : Claude CLI, 1er novembre 2026, sur le prompt
`docs/prompts/phase-4-increment-8-consolidation.md`. Départ API `f3c098f`,
1 109 cas collectés.

## 1. Garanties déjà couvertes, réutilisées telles quelles

Lecture des suites existantes avant toute écriture. Le contrat des incréments 1
à 7 est couvert par des scénarios que je n'ai ni refaits ni dupliqués :

| Point du contrat | Où il est garanti |
| --- | --- |
| JWT et groupes, aucun droit par authentification ou `is_staff` | `tests/test_auth_jwt.py`, `tests/test_role_groups.py`, et le refus `403` au début de chaque suite privée |
| Public : `published` non supprimé, aucun champ éditorial, aucune cible masquée | `test_public_visibility.py`, `test_api.py`, `test_navigation.py`, plus les contrôles de visibilité de `test_private_moderation.py` et `test_private_deletion.py` |
| Privé : sélection rôle/propriété, références filtrées | `test_private_read.py` |
| Création en `draft`, propriétaire serveur, profil exact | `test_private_create.py` |
| PATCH partiel, aucun transfert de propriété/type/statut | `test_private_update.py` |
| Sources et relations sous leur parent, cible unique, doublons documentaires permis | `test_private_children.py` |
| submit/withdraw/resume et blocage des écritures du contributeur en `submitted` | `test_private_transitions.py` |
| publish/reject/reopen, motif obligatoire, dates et acteurs serveur, revue conservée ou effacée | `test_private_moderation.py`, dont le parcours soumission → rejet → reprise → correction → resoumission → publication → réouverture par les routes réelles |
| Suppression logique selon sa matrice, restore administrateur seul, statut conservé | `test_private_deletion.py` |
| Protection des références par les variantes actives, ordre des verrous | `test_private_deletion.py` et `test_variant_lock_order.py` |
| Codes 401/403/404 et non-divulgation | répartis dans les sept suites privées, sans batterie JWT dupliquée |

Les conventions anciennes explicitement testées — dont le `401` d'un en-tête
`Bearer` invalide sur une lecture publique — sont restées inchangées.

## 2. Écart réel trouvé, et sa correction

**Un seul écart démontré.** Aucun test n'enchaînait un `DELETE` réel avec un
`restore/` réel : les sept scénarios de restauration partaient d'un
`deleted_at` posé par la fabrique. Deux garanties n'étaient donc pas établies :

- l'aller-retour des marques — celles que `apply_deletion()` écrit sont
  exactement celles que `apply_restoration()` efface ;
- la modérabilité après restauration — une fiche restaurée est bien revenue
  dans la sélection privée, avec son statut intact.

**Correction.** Un scénario court ajouté à `test_private_deletion.py`, par les
routes réelles et sans mise à jour directe du statut : création avec profil →
soumission → publication → visible en public → `DELETE` → absente du public et
du privé → `restore/` → publique de nouveau, `created_by` et `reviewed_by`
conservés → réouverture → brouillon privé. Il complète la queue du parcours de
référence, dont la tête est déjà couverte par le parcours de
`test_private_moderation.py` ; rien n'a été recopié.

**Aucun code métier ajouté ou modifié.** Les autres points du mandat étaient
déjà couverts, et je n'ai créé ni croisement supplémentaire rôle × statut ×
corps, ni produit cartésien.

## 3. Contrat documentaire

Contrôle des passages concernés de `README.md`, de la description OpenAPI
globale et des descriptions de `mythology/schema.py` : **aucune contradiction
factuelle trouvée**. Les opérations annoncées, les formes d'entrée, les droits,
les dates, la frontière public/privé, la suppression et la restauration
correspondent au code livré, et les limites réelles restent visibles — y
compris « the reclassification of an entity's type is not implemented yet ».
`CLAUDE.md` est à jour jusqu'à l'incrément 7. Aucun texte n'a été réécrit pour
le style.

Une seule correction documentaire, interne : le commentaire de
`EntityAdmin.readonly_fields` annonçait encore les actions de transition au
futur (« seront posés par les services de transition de la phase 4 »). Il
décrit désormais l'état réel et nomme les limites du back-office.

## 4. Administration Django : constats et décisions requises

Examen de `mythology/admin.py`, sans y dupliquer la matrice de l'API.

**Déjà garanti.** Les formulaires de profil refusent un rattachement à une
entité d'un autre type : `DivinityProfile.clean()`, `HeroProfile.clean()` et
`CreatureProfile.clean()` sont appelés par le `ModelForm`, et la règle est
testée au niveau du modèle (`test_profiles.py`). `submitted_at`,
`reviewed_at`, `deleted_at` et `deleted_by` sont en lecture seule : aucune date
ni acteur de suppression ne se saisit à la main.

**Deux écarts constatés, qui exigent une décision — non implémentée.**

1. **Couple type/profil.** Une écriture normale peut produire une entité
   **sans profil** : `EntityAdmin` n'a pas d'inline, et rien sur `Entity` ne
   vérifie le profil. De même, changer `entity_type` sur une fiche existante
   laisse son profil devenu incompatible. L'API refuse ensuite ces fiches en
   `400` explicite, sans les réparer — comportement voulu depuis
   l'incrément 4A. Rendre le profil obligatoire dans l'admin, interdire le
   changement de type ou réparer automatiquement supposerait de choisir qui en
   a le droit et ce qu'il advient des données de culte : c'est une règle
   métier nouvelle, pas une incohérence au comportement attendu non ambigu.
2. **Suppression physique.** L'action de suppression de l'admin reste une
   suppression physique en cascade, à l'opposé du `DELETE` logique de l'API.
   La retirer, la restreindre ou la remplacer par la suppression logique est
   également une décision de politique.

Ces deux limites sont assumées hors API depuis la phase 2 — les docstrings des
modèles les énoncent — et ne sont pas des blocages pour la clôture : elles
n'affectent aucune garantie de l'API. Elles demandent un arbitrage avant toute
implémentation, que je n'ai pas pris. Aucune donnée, aucun compte et aucun
groupe n'ont été touchés pour les démontrer.

**Portée des verrous, rappelée sans extension.** L'acquisition ordonnée des
lignes protège les chemins API coordonnés. Elle ne couvre pas les écritures de
l'administration, de l'import ou du SQL direct, et `test_variant_lock_order.py`
reste un seul scénario concurrent borné — les autres tests de concurrence sont
des simulations séquentielles, décrites comme telles.

## 5. Vérifications exécutées, dans l'ordre du prompt

1. **Lecture de l'existant**, puis annonce des seuls écarts réels. Aucune
   batterie de commandes exploratoire.
2. **Test nouveau seul**, puis lint, format et typage sur le périmètre :

| Commande | Résultat |
| --- | --- |
| `pytest mythology/tests/test_private_deletion.py -k parcours` | 1 passé |
| `ruff check .` / `ruff format --check .` | `All checks passed!` / `64 files already formatted` |
| `mypy mythology` | `Success: no issues found in 39 source files` |

3. **Contrôles globaux, une seule fois :**

| Commande | Résultat |
| --- | --- |
| `python manage.py check` | aucun problème |
| `python manage.py makemigrations --check --dry-run` | `No changes detected`, sortie `0` |
| `python manage.py spectacular --validate --fail-on-warn` | sortie `0`, aucun avertissement |
| `mypy .` | `Success: no issues found in 64 source files` |

4. **Un seul passage complet final :**

| Commande | Résultat |
| --- | --- |
| `pytest` | **1 110 passés** en 20 min 23 s, aucun échec, aucun ignoré (1 109 au départ) |

Aucune relance : aucune correction n'a été nécessaire après un échec, et les
anciennes suites n'ont pas été lancées séparément avant ce passage. Le schéma a
été écrit dans un fichier temporaire hors du dépôt.

## 6. Limites et décisions en attente

- **Décisions requises, hors de mon mandat** : les deux écarts de
  l'administration du point 4 — profil obligatoire ou reclassement de type, et
  suppression physique. Ce sont des arbitrages, pas des défauts de l'API.
- **Limites déjà assumées, inchangées** : aucune purge ni corbeille, aucun
  historique ni audit permanent, aucune révocation de jeton, aucune limitation
  de débit, pas d'`ETag` ni de version de ligne, pas de reclassement de type.
- **Concurrence** : garantie bornée aux chemins API, démontrée par un scénario
  multiconnexion unique ; les autres tests restent séquentiels.
- **Réglage JWT** : 20 minutes en développement et 5 hors debug sont
  conservées. Le retour à 5 avant finalisation reste suivi hors de cette
  intervention.
- Aucun chantier de phase 5 ouvert, aucune roadmap cochée, aucune phase close :
  la validation finale revient à l'auteur après revue et exercices.

## 7. Fichiers touchés et état Git

| Fichier | Changement |
| --- | --- |
| `mythology/tests/test_private_deletion.py` | Un scénario d'intégration : publication, suppression, restauration, réouverture par les routes réelles |
| `mythology/admin.py` | Commentaire interne devenu faux, corrigé ; limites du back-office nommées |
| `docs/reports/phase-4-increment-8-consolidation.md` | Ce rapport |

Rien n'est committé ni poussé.

### `afrimyth-api` — HEAD `f3c098f`

```
 M mythology/admin.py
 M mythology/tests/test_private_deletion.py
?? docs/reports/phase-4-increment-8-consolidation.md
```

### `django-portfolio` — HEAD `646719a`

Aucun fichier de ce dépôt n'a été modifié par cette intervention. Son arbre
porte, de l'auteur : `docs/roadmap-projet-1.md` modifié, `Pipfile` et
`docs/prompts/phase-4-increment-8-consolidation.md` non suivis.

## 8. Vérification Codex, décision de l'auteur et clôture — 1er novembre 2026

Rapport et copie contrôlés identiques. Aucun pytest encore actif ; les traces
confirment **1 110 réussites en 1 222,65 secondes**. Le diff ne contient qu'un
nouveau scénario d'intégration et des commentaires admin, sans code métier
modifié. Le test relie les routes réelles jusqu'à la réouverture après
restauration, avec vérification des marques effacées et des acteurs conservés.
Les décomptes partiels ambigus du tableau ont été retirés pour ne pas confondre
fonctions de test et cas paramétrés ; le résultat complet reste inchangé.

L'auteur confirme explicitement la clôture de la phase 4 **sans développement
ou Postman supplémentaire** : les exercices antérieurs et le test automatique
du parcours final sont suffisants. Les limites admin du point 4 ne sont plus
des arbitrages suspendant cette clôture : Django Admin reste réservé au
responsable technique, pas à la création/correction courante des entités.
La future interface éditoriale simple utilisera l'API et les rôles ; elle ne
doit pas être construite maintenant. Les restrictions de formulaires et de
suppression physique restent reportées, avec solutions minimales consignées
dans `docs/notes/admin-et-interface-editoriale.md` du dépôt de pilotage.

Les explications de consolidation sont dans
`docs/verifications-code/phase-4-increment-8-consolidation.md`. Roadmap et
consignes actualisées ; README précise la frontière et les limites de l'admin.
Phase 4 terminée. Phase 5 engagée par la préparation de l'extension de l'import,
sans exécution réelle à ce stade. Aucun test complet relancé pour les seules
retouches documentaires de clôture. Aucun secret, compte, fiche ou donnée du
corpus modifié ; aucune correction admin implémentée. Clôture Git normale
des deux dépôts sous l'identité de l'auteur ; Pipfile non suivi hors périmètre.
