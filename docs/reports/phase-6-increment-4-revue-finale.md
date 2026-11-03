# Phase 6 — Incrément 4 : revue finale et préparation de la version

Rapport d'intervention, en français. Aucun secret, aucune valeur de `.env` ou
de `.env.docker`, aucun mot de passe et aucun jeton n'y figure.

Intervention : Claude CLI, 3 novembre 2026, sur le prompt
`docs/prompts/phase-6-increment-4-revue-finale.md`. Dernier commit publié
**`dbb44f3`**. Départ pris sur l'arbre local, qui contenait l'incrément 3 **et
les corrections du README apportées par Codex** — elles sont **préservées** :
le diagramme en six lignes, le parcours de création de comptes ordinaires par
l'administration Django, l'URL de clone concrète et la formulation sur la
suppression sont intacts.

**Aucun défaut fonctionnel important trouvé.** Un seul constat réel a demandé
une correction, et il porte sur le périmètre publiable, non sur le
comportement. Les trois autres corrections sont documentaires ou de
métadonnées.

## 1. Périmètre publiable

117 fichiers suivis. Recherche de secrets réels, de sauvegardes, de corpus et
de fichiers locaux.

| Contrôle | Résultat |
| --- | --- |
| `.env`, `.env.docker`, `.coverage` | **ignorés** par Git, confirmés par `git check-ignore` |
| Clés et mots de passe en dur dans les fichiers suivis | aucun secret réel. `.env.example` et `.env.docker.example` ne portent que des valeurs factices ; `config/settings.py` n'a qu'un repli de développement, actif **uniquement** sous `DEBUG` |
| Mots de passe des tests | une seule valeur, manifestement fictive, partagée par toutes les suites |
| Jetons JWT réels | aucun — aucune chaîne de forme `eyJ…` dans l'arbre |
| Corpus V2, sauvegardes, dumps, `.bak` dans le dépôt | **aucun** |
| Sauvegarde PostgreSQL de la phase 5 | hors de l'arbre du dépôt (`../backups/afrimyth-api`) |
| Exclusions Docker | `.dockerignore` exclut `.env` et `.env.*` en ne gardant que les deux exemples ; fichiers Docker non modifiés depuis l'incrément 1, dont la preuve d'image sans secret reste valable |
| Ajouts prévus | un seul fichier non suivi, le rapport de l'incrément 3, plus celui-ci |

Les identifiants du workflow de CI — clé Django et mot de passe PostgreSQL —
sont **volontairement en clair** : ils ne servent qu'à une base éphémère
détruite avec le runner et ne sont partagés avec aucune installation. Ce
n'est pas une fuite, c'est le choix documenté de l'incrément 2.

**Constat réel, corrigé.** Le README fait générer le schéma à la racine du
dépôt :

```bash
python manage.py spectacular --file schema.yml --validate --fail-on-warn
```

et affirme deux lignes plus haut qu'« aucun fichier de schéma n'est
committé ». Or `schema.yml` **n'était pas ignoré** : un lecteur qui suit le
README produit un fichier non suivi à la racine, exposé à un `git add .`
distrait. Même situation pour un export de base.

*Correction :* `/schema.yml`, `/schema.yaml`, `*.dump` et `*.sql` ajoutés à
`.gitignore`, avec leur raison en commentaire. Vérifié qu'ils sont désormais
ignorés et qu'**aucun fichier déjà suivi** ne devient ignoré par cette règle.

## 2. Réglages hors debug

Vérifiés par exécution, en neutralisant le chargement du `.env` local pour
tester l'absence réelle de la variable :

| Garantie | Résultat réel |
| --- | --- |
| Hors `DEBUG`, la clé Django est obligatoire | `RuntimeError` levée, démarrage refusé — pas de repli silencieux |
| Durée d'accès JWT sous `DEBUG=True` | **20 minutes** |
| Durée d'accès JWT sous `DEBUG=False` | **5 minutes** |
| Durée de rafraîchissement | 1 jour dans les deux cas |

**La durée allongée est donc bien réservée au développement** : elle est
calculée à l'import des réglages et ignorée dès que `DEBUG` est faux. Les
tests `test_durees_de_jetons_jwt` et
`test_access_extension_is_development_only` gardent déjà cette règle dans les
deux sens.

Le message de refus au démarrage est en français. Il s'adresse à l'opérateur
qui lance le processus, pas à un client de l'API : il n'entre pas dans le
contrat public et l'ADR 0003 ne l'impose donc pas en anglais. Signalé, non
modifié.

**Permissions et requêtes non réexaminées**, faute de diff touchant leur
comportement : les changements de l'incrément 3 sont des docstrings, et ceux
de cet incrément des métadonnées et de la documentation. Les preuves des
phases précédentes sont réutilisées, dont les **1 126 tests** et la
couverture de **98,20 %** du dernier passage complet.

## 3. Parcours d'une personne extérieure dans le README

Relu dans l'ordre : présentation culturelle et encyclopédique, ce que
documente une fiche, les rôles, l'installation, puis la première requête. La
présentation **reste avant l'installation**, comme demandé.

**Exemples revérifiés par exécution**, avec la configuration de comptes
exacte que Codex a introduite — deux comptes ordinaires non staff dans un
groupe, et le **superutilisateur d'origine** pour l'administrateur :

| Mesure | Résultat |
| --- | --- |
| Vérifications | **63** |
| Échecs | **0** |

Ajouté à la vérification précédente, et confirmé : les deux comptes ordinaires
n'ont ni `is_staff` ni `is_superuser` ; le superutilisateur **sans aucun
groupe métier** obtient bien le rôle d'administrateur ; un compte `is_staff`
sans groupe n'obtient **aucun** rôle. Le parcours du README est donc exact
sur ce point délicat.

Couverts par ailleurs : enveloppe vide en `200` sur base neuve, `404` d'un
slug inconnu, couple de jetons, `403` sans rôle éditorial et `401` sans
jeton, création en `201` avec statut et propriétaire imposés, `PATCH` partiel,
ajout de source, `submit/` sans corps, `403` du `PATCH` d'un contributeur sur
`submitted`, `403` du `publish/` par le propriétaire, `400` d'un rejet sans
motif, `resume/` conservant la note, publication sans note côté public, `403`
du `reopen/` par un relecteur, `204` du `DELETE`, `403` du `restore/` hors
administrateur, `405` des écritures publiques et du `PUT`.

**Aucune écriture hors base de test** : ces vérifications tournent dans une
base `test_*` créée puis détruite. La base des exercices n'a pas été ouverte,
et rien n'a été écrit dans celle des conteneurs Docker.

Contrôles mécaniques du document :

| Contrôle | Résultat |
| --- | --- |
| Ancres internes | 3 utilisées, **aucune cassée** |
| Sous-commandes `manage.py` citées | les 6 existent (`check`, `createsuperuser`, `import_mythology_pilot`, `migrate`, `runserver`, `spectacular`) |
| Ports | `8000` et `8001` seulement, cohérents avec les deux parcours |
| Blocs de code | 37, délimiteurs équilibrés |

**Cohérence des formulations sur la suppression.** La retouche de Codex au
niveau « Discover » attribue la garantie à l'API plutôt qu'au système entier.
Vérifié qu'elle ne contredit rien en aval : la section « Try it » décrit
l'effet de l'opération `DELETE`, la référence précise qu'« aucune opération »
de l'API ne retire physiquement une ligne, et « Project status » documente
que l'administration Django, elle, le permet encore. Les trois énoncés sont
correctement cadrés. **Aucune correction.**

**Constat réel, corrigé.** « Project status » s'arrêtait à la **phase 4**,
alors que le même README documente Docker, la CI et l'import complet du
corpus. Un lecteur y lisait un projet arrêté avant ce qu'il venait de lire.

*Correction :* deux paragraphes ajoutés pour les phases 5 et 6, plus un
paragraphe nommant les limites déjà reportées — une fiche enregistrée sans le
profil de son type, que l'API refuse ensuite de modifier par un `400`
explicite, et des relations citant un nom alors que la fiche existe
désormais. Formulés comme des propriétés de l'import, **non** comme l'état
d'une base particulière, et accompagnés du fait qu'une installation neuve
part vide et n'en a aucune. Les sujets Django Admin, Shango, Oya et les
ambiguïtés du corpus restent ainsi des limites documentées, sans être
corrigés.

## 4. Versions de la livraison

Relevé des versions qui **décrivent la livraison**, distinguées des versions
de dépendances :

| Déclaration | Avant | Après |
| --- | --- | --- |
| `pyproject.toml` → `version` | `0.1.0` | **`1.0.0`** |
| `config/settings.py` → `SPECTACULAR_SETTINGS["VERSION"]` | `0.1.0` | **`1.0.0`** |
| `mythology/tests/test_openapi.py` → assertion sur `info.version` | `0.1.0` | **`1.0.0`** |
| `README.md` → « Project status » | aucune mention | version `1.0.0` énoncée |

**Non touchées, et volontairement :** les versions épinglées de
`requirements.txt` et `requirements-dev.txt`, qui sont des versions de
bibliothèques ; `REDOC_DIST` épinglé à ReDoc 2.5.3, qui est une ressource de
CDN ; `python_version` de mypy et `target-version` de Ruff, qui désignent la
version du langage. Aucune n'a de rapport avec la version de la livraison.

**Changement de contrat, signalé avant application.** La seule incidence
visible d'un client est `info.version` du schéma OpenAPI, qui passe de
`0.1.0` à `1.0.0`. C'est une **métadonnée** : aucun chemin, aucun nom de
champ, aucune valeur technique, aucun code de statut et aucune sémantique ne
changent. Le seul client affecté serait un client qui épingle la chaîne de
version.

**Convention du contrat, inchangée.** `1.0.0` nomme la livraison, **pas** une
version du contrat : les routes restent sous `/api/` sans segment de version,
`SCHEMA_PATH_PREFIX` reste `/api/`, et aucune négociation de version n'est
exposée. Je l'ai écrit dans le commentaire du réglage et dans le README,
parce qu'un numéro majeur `1` laisse facilement croire le contraire. Une
future rupture exigerait un schéma de versionnement **qui n'existe pas
encore** : c'est une limite, pas un oubli de cet incrément.

La mention historique de `VERSION = 0.1.0` dans
`docs/reports/phase-3-increment-3-openapi.md` **n'a pas été réécrite** : les
rapports d'incrément sont des traces datées.

## 5. Vérifications exécutées

Choisies selon les fichiers réellement modifiés : des métadonnées, un test,
de la documentation et une règle d'exclusion.

| Contrôle | Résultat |
| --- | --- |
| `spectacular --validate --fail-on-warn` | **sortie `0`**, aucun avertissement ; `info.version` vaut bien `1.0.0`, titre inchangé |
| `pytest mythology/tests/test_openapi.py tests/test_settings.py` | **171 passés** en 95,13 s — les deux suites que le diff touche |
| Exemples du README, par exécution | **63 vérifications, 0 échec** |
| Réglages hors debug, par exécution | clé obligatoire ; 20 min sous `DEBUG`, 5 min sinon |
| `ruff check .` | `All checks passed!` |
| `ruff format --check .` | `64 files already formatted` |
| `mypy .` | `Success: no issues found in 64 source files` |
| `python manage.py check` | aucun problème |
| `python manage.py makemigrations --check --dry-run` | `No changes detected`, sortie `0` |
| `pytest --collect-only -q` | **1 126 tests collectés**, compte inchangé |
| Nouvelles exclusions Git | `schema.yml`, `schema.yaml`, `.dump`, `.sql` ignorés ; aucun fichier suivi ne le devient |

**Pas de passage complet local.** Le prompt le réserve à la CI après
publication, et les 1 126 tests avec 98,20 % de couverture du dernier passage
sont les preuves de référence. Le schéma, lui, a été revalidé parce que ses
métadonnées changent.

## 6. Corrections appliquées, et leur justification

| Correction | Pourquoi |
| --- | --- |
| `.gitignore` : `/schema.yml`, `/schema.yaml`, `*.dump`, `*.sql` | Le README fait écrire `schema.yml` à la racine et affirme qu'aucun schéma n'est committé ; l'exclusion manquait |
| `pyproject.toml` : version `1.0.0` | Alignement demandé de la livraison |
| `config/settings.py` : `VERSION` `1.0.0` + commentaire | Même alignement, avec la portée explicitée pour éviter de lire `1` comme une version de contrat |
| `mythology/tests/test_openapi.py` : assertion `1.0.0` | Sans elle, le test échouerait et la CI de livraison serait rouge |
| `README.md` : phases 5 et 6, version, limites des anciennes fiches | « Project status » contredisait le reste du document |

Rien d'autre n'a été modifié. Aucun refactoring, aucune migration, aucune
dépendance, aucune route, aucune permission, aucun changement Docker ou de
workflow.

## 7. Blocages et limites restantes

- **Aucun blocage.** Rien n'empêche la publication des incréments 3 et 4.
- **Pas de versionnement du contrat** : `1.0.0` ne crée ni segment d'URL, ni
  négociation. Une rupture future devra d'abord se donner une convention.
- **Relecture éditoriale du README** : le texte culturel reste à valider sur
  le fond ; le prompt la confie à Codex.
- **Limites reportées, inchangées** : administration Django (couple
  type/profil non imposé, suppression physique possible), la fiche
  historique sans profil, les relations du pilote citant un nom, et les
  ambiguïtés du corpus — nom canonique, ethnonymes proches, synonymes de
  domaines, sens d'un descendant cité.
- **Conteneurs Docker laissés démarrés**, sans aucune écriture de ma part
  dans leur base.
- La CI n'a pas été exécutée : elle le sera sur le commit exact de livraison.

## 8. État Git

Aucun commit, aucun push, aucun tag. HEAD **`dbb44f3`**, inchangé. La roadmap
n'a pas été modifiée et aucune phase n'est déclarée close ; le tag `v1.0.0`
vous revient, après une CI verte.

Cinq fichiers modifiés par **cet** incrément — `.gitignore`, `README.md`,
`config/settings.py`, `pyproject.toml`, `mythology/tests/test_openapi.py` —
s'ajoutant aux 27 de l'incrément 3 :

```
 M .gitignore
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
 M mythology/tests/test_openapi.py
 M mythology/tests/test_pilot_import.py
 M mythology/tests/test_profiles.py
 M mythology/tests/test_public_visibility.py
 M mythology/tests/test_reference.py
 M mythology/tests/test_relations.py
 M mythology/tests/test_services.py
 M mythology/tests/test_sources.py
 M mythology/views.py
 M pyproject.toml
 M tests/test_health.py
 M tests/test_settings.py
 M tests/test_user_model.py
?? docs/reports/phase-6-increment-3-documentation.md
?? docs/reports/phase-6-increment-4-revue-finale.md
```

Les scripts de vérification employés sont temporaires et restent **hors du
dépôt**, dans le scratchpad de la session ; le schéma validé y a également
été écrit.
