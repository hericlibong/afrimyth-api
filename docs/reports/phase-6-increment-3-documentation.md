# Phase 6 — Incrément 3 : documentation et langue

Rapport d'intervention, en français. Aucun secret, aucune valeur de `.env` ou
de `.env.docker`, aucun mot de passe et aucun jeton n'y figure.

Intervention : Claude CLI, 3 novembre 2026, sur le prompt
`docs/prompts/phase-6-increment-3-documentation.md`. HEAD au départ
**`dbb44f3`**, conforme à la référence, arbre propre.

**Aucun comportement modifié.** Les 27 fichiers touchés ne changent que de la
documentation : le README, `CLAUDE.md` et des docstrings. Docker, le workflow
de CI, les données métier et le corpus sont intacts. Aucune migration, aucune
dépendance, aucune route, aucune permission.

## 1. Le parcours d'un lecteur extérieur

Le README est réorganisé en quatre sections numérotées, précédées d'une
présentation du projet. Un lecteur qui ne connaît rien d'Afrimyth suit donc
cet ordre :

**Avant les sections** — ce qu'est Afrimyth : un projet culturel à vocation
encyclopédique consacré aux mythologies africaines et diasporiques, ce que
l'API y fait (consulter, contribuer), puis deux encadrés qui séparent
explicitement **l'ambition** du **périmètre livré**, et énoncent ce que le
projet **ne prétend pas** : ni exhaustivité, ni autorité éditoriale, ni
instance publique hébergée, ni jeu de données publié. Les questions laissées
ouvertes — nom canonique, ethnonymes proches, sens d'un descendant cité —
sont nommées comme telles.

**1. Discover** — ce qu'une fiche peut documenter, en quatre familles
(la figure, son contexte culturel, ses relations, ses références), les profils
par type, la notion de variante culturelle ; à qui le projet sert ; le passage
du brouillon à la publication expliqué en mots accessibles, avec un schéma des
quatre états et le rôle de chacun ; enfin ce qu'un lecteur peut consulter
aujourd'hui — et pourquoi une installation neuve ne montre légitimement rien.

**2. Install** — deux chemins annoncés comme **indépendants et sans base
commune** : Docker d'abord (prérequis, préparation du fichier local, démarrage,
URL sur **8001**, santé et Swagger, arrêt sans suppression du volume, compte
administratif facultatif), puis le parcours **hors Docker** comme section
distincte sur 8000. Suivent le tableau des variables d'environnement, le fait
qu'une installation neuve a sa propre base vide, et l'import du corpus
historique — en précisant que **ce corpus n'est pas dans le dépôt** et que le
chemin du fichier externe se passe explicitement.

**3. Try it** — exemples courts, reproductibles, **tous en données
fictives** : lecture publique sans compte, obtention d'un jeton, création
puis correction d'un brouillon, ajout d'une source, soumission, relecture
(publication et rejet), administration (suppression logique et restauration).
Chaque exemple indique son prérequis et le **résultat attendu**. La section se
clôt sur un tableau « At a glance » des droits par action.

**4. Understand the code** — l'arborescence commentée, les deux choix
d'architecture utiles à savoir avant de lire (la visibilité vit dans le
queryset, et chaque règle est appliquée au niveau où elle peut l'être), les
trois routes du schéma OpenAPI avec l'usage de Swagger UI, et le renvoi aux
contrôles.

La partie de référence — contrats de lecture, API publique, API éditoriale
privée, authentification, import, vérification — est **conservée intégralement
en aval**, introduite par une sous-section « Reference » qui dit explicitement
qu'elle n'est pas une première lecture. Le README passe de 1 020 à
1 108 lignes : la tête a été réécrite, la référence n'a pas été amputée.

## 2. Langue — docstrings traduites

**377 docstrings françaises traduites en anglais, dans 25 fichiers. Il n'en
reste aucune.** Un relevé par AST avant et après le confirme : 841 docstrings
au total, 377 détectées comme françaises au départ, **0** à l'arrivée.

| Périmètre | Docstrings |
| --- | --- |
| Code applicatif (`accounts`, `config`, `mythology`) | 70 |
| Tests (`tests/`, `mythology/tests/`) | 307 |

Les commentaires internes, les prompts et les rapports **restent en
français**, conformément à l'ADR 0003. Le sens de chaque docstring est
préservé, y compris les sections `Args`/`Returns`/`Raises`, les mises en
valeur et les renvois aux ADR.

**Méthode, pour que rien d'autre ne bouge.** Un outil temporaire, hors du
dépôt, remplace chaque docstring par les positions exactes de son nœud
`ast.Constant`, et rien d'autre dans le fichier. L'indentation est calculée
par l'outil, non saisie à la main. Après chaque fichier, son AST **privé de
toutes les docstrings** est comparé à celui de la version `HEAD` : une
différence signifierait qu'autre chose que de la documentation a changé.

## 3. Libellés publics encore en français — relevé

**Aucun.** La dette inscrite à l'ADR 0003 est déjà résorbée par les
incréments antérieurs. Un relevé par introspection de tous les modèles de
`mythology` et `accounts` — `verbose_name`, `verbose_name_plural`,
`help_text` et libellés de choix — ne trouve **aucune** valeur française
(0 sur l'ensemble). Le schéma OpenAPI généré ne contient **aucun caractère
accentué**. Deux tests existants gardent déjà cette règle :
`test_libelles_de_choix_sont_en_anglais` et
`test_verbose_names_sont_en_anglais`.

**Aucune modification touchant le contrat public n'a donc été nécessaire, ni
faite.** Aucun nom de champ, valeur technique, description publique ou message
d'erreur client n'a été changé. Aucune traduction localisée n'était à
proposer.

## 4. Vérifications réellement effectuées

### Exemples du README, contre les routes et permissions réelles

Relevé préalable des routes exposées et des classes de permission par vue,
puis des matrices de rôles de `transitions.py`, `deletion.py` et
`permissions.py`. Les exemples ont ensuite été **exécutés**, et non seulement
relus, avec les charges utiles exactes du README :

| Mesure | Résultat |
| --- | --- |
| Vérifications | **58**, dont les codes de statut, les charges utiles et les refus |
| Échecs | **0** |

Couverts : enveloppe vide en `200` sur base neuve, `404` d'un slug inconnu,
obtention du couple de jetons, `403` d'un compte sans rôle éditorial, `401`
sans jeton, création en `201` avec statut et propriétaire imposés par le
serveur, absence du public avant publication, `PATCH` partiel laissant les
champs omis, ajout d'une source en `201`, `submit/` sans corps avec
`submitted_at` posé, `403` du `PATCH` d'un contributeur sur `submitted` alors
que la lecture reste ouverte, `403` du `publish/` par le propriétaire, `400`
d'un rejet sans motif puis `200` avec motif, `resume/` conservant la note,
publication avec `reviewed_at`, apparition en public sans note de revue,
`403` du `reopen/` par un relecteur et `200` par un administrateur, `204` du
`DELETE` puis disparition du public et du privé, `403` du `restore/` par un
relecteur et `200` par un administrateur avec statut conservé, `405` des
écritures publiques et du `PUT`, santé, schéma, Swagger et ReDoc.

**Aucune écriture hors base de test.** Ces vérifications tournent dans une
base `test_*` créée puis détruite. La base des exercices n'a pas été ouverte,
et je n'ai **rien écrit** dans la base des conteneurs Docker — qui tournaient
toujours — pour ne pas y introduire de données de démonstration.

### Docstrings et contrôles de code

| Contrôle | Résultat |
| --- | --- |
| AST hors docstrings, fichier par fichier, contre `HEAD` | **identique pour les 25 fichiers** |
| Détecteur de docstrings françaises, après traduction | **0 sur 841** |
| `ruff check .` | `All checks passed!` — après correction de deux lignes trop longues que j'avais introduites |
| `ruff format --check .` | `64 files already formatted` |
| `mypy .` | `Success: no issues found in 64 source files` |
| `python manage.py check` | aucun problème |
| `pytest --collect-only -q` | **1 126 tests collectés**, soit le compte inchangé |

**Pas de passage complet local**, conformément au prompt : les changements
sont documentaires, la CI verte de l'incrément 2 sert de référence, et la
collecte confirme que les 1 126 tests sont intacts. Le schéma OpenAPI n'a pas
été revalidé : aucune description publique n'a changé.

Deux lignes de mes traductions dépassaient 88 caractères dans
`test_pilot_import.py`. Le contrôle global les a attrapées ; elles sont
corrigées, et l'AST hors docstrings de ce fichier a été revérifié après
correction.

## 5. Fichiers touchés

| Fichier | Changement |
| --- | --- |
| `README.md` | Tête réécrite : présentation du projet et quatre sections Discover / Install / Try it / Understand the code ; référence conservée en aval |
| `CLAUDE.md` | Deux passages devenus faux corrigés : la passe de traduction n'est plus reportée, et la dette des libellés publics est résorbée |
| `mythology/models.py` | 32 docstrings |
| `mythology/management/commands/import_mythology_pilot.py` | 15 docstrings |
| `mythology/views.py` | 6 docstrings |
| `mythology/selectors.py`, `mythology/services.py` | 5 docstrings chacun |
| `mythology/pagination.py`, `config/settings.py` | 2 docstrings chacun |
| `accounts/models.py`, `config/asgi.py`, `config/wsgi.py` | 1 docstring chacun |
| `mythology/tests/` (11 fichiers) | 303 docstrings, dont 51 pour `test_pilot_import.py`, 41 pour `test_api.py`, 36 pour `test_navigation.py` |
| `tests/` (3 fichiers) | 4 docstrings |
| `docs/reports/phase-6-increment-3-documentation.md` | Ce rapport |

L'actualisation de `CLAUDE.md` n'était pas demandée par ce prompt ; je l'ai
faite parce que ses deux affirmations devenaient factuellement fausses du fait
de cette intervention, et une contradiction dans un incrément documentaire
serait un défaut. Elle est limitée à ces deux passages.

## 6. Limites et points restants

- **Relecture éditoriale à faire.** Le texte du README est le mien : le ton,
  les formulations culturelles et le choix des mots employés pour décrire les
  mythologies méritent votre relecture. Le prompt la confie à Codex.
- **Pas de passage complet local** : la non-régression repose sur la
  comparaison d'AST, la collecte des 1 126 tests et la CI verte, non sur une
  exécution complète.
- **Les ancres internes du README** (`#verification`,
  `#private-editorial-api`, `#corpus-import`) suivent la convention GitHub ;
  elles n'ont pas été vérifiées par un rendu.
- **Conteneurs Docker laissés démarrés**, comme à l'incrément 1, sans aucune
  écriture de ma part dans leur base.
- Les prompts, ADR et rapports antérieurs **ne sont pas traduits** : l'ADR
  0003 les laisse en français.

## 7. État Git

Aucun commit, aucun push, aucun tag. HEAD **`dbb44f3`**, inchangé. La roadmap
n'a pas été modifiée et aucune phase n'est déclarée close.

27 fichiers modifiés, aucun ajouté hors ce rapport :

```
 M CLAUDE.md
 M README.md
 M accounts/models.py
 M config/asgi.py
 M config/settings.py
 M config/wsgi.py
 M mythology/management/commands/import_mythology_pilot.py
 M mythology/models.py
 M mythology/pagination.py
 M mythology/selectors.py
 M mythology/services.py
 M mythology/tests/factories.py
 M mythology/tests/test_api.py
 M mythology/tests/test_editorial_fields.py
 M mythology/tests/test_models.py
 M mythology/tests/test_navigation.py
 M mythology/tests/test_pilot_import.py
 M mythology/tests/test_profiles.py
 M mythology/tests/test_public_visibility.py
 M mythology/tests/test_reference.py
 M mythology/tests/test_relations.py
 M mythology/tests/test_services.py
 M mythology/tests/test_sources.py
 M mythology/views.py
 M tests/test_health.py
 M tests/test_settings.py
 M tests/test_user_model.py
?? docs/reports/phase-6-increment-3-documentation.md
```

Les outils de traduction et de vérification employés sont temporaires et
restent **hors du dépôt**, dans le scratchpad de la session.
