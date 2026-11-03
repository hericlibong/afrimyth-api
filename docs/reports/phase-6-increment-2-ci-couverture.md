# Phase 6 — Incrément 2 : couverture et GitHub Actions

Rapport d'intervention, en français. Aucun secret, aucune valeur de `.env`
ou de `.env.docker`, aucun mot de passe et aucun jeton réel n'y figure.

Intervention : Claude CLI, 3 novembre 2026, sur le prompt
`docs/prompts/phase-6-increment-2-ci-couverture.md`. HEAD au départ
**`9699006`**, conforme à la référence, arbre propre, aucun workflow existant.

**Aucun code métier modifié.** Les changements portent sur la configuration,
la CI et la documentation. Aucune règle d'authentification, de permission ou
de schéma métier n'a été touchée, aucune migration créée, et **aucun test
ajouté** — en particulier aucun test destiné à relever le pourcentage.

## 1. Fichiers livrés

| Fichier | Changement |
| --- | --- |
| `requirements-dev.txt` | `pytest-cov~=7.1` ajouté aux dépendances de développement |
| `pyproject.toml` | Sections `[tool.coverage.run]` et `[tool.coverage.report]` : périmètre, exclusions, couverture de branches, `fail_under` |
| `.github/workflows/ci.yml` | Workflow unique, nouveau |
| `README.md` | Deux sous-sections anglaises sous « Verification » : commande locale de couverture et contrôles de CI |
| `CLAUDE.md` | La mention « CI et couverture » hors périmètre remplacée par le périmètre réellement livré |
| `docs/reports/phase-6-increment-2-ci-couverture.md` | Ce rapport |

Versions installées : `pytest-cov 7.1.0`, `coverage 7.17.1`.

## 2. Périmètre de la mesure

Mesuré : les trois paquets applicatifs — `accounts`, `config`, `mythology` —
nommés explicitement plutôt que `.`, afin que le dépôt entier n'entre pas
dans le dénominateur.

Exclus : `*/tests/*` — les tests ne se mesurent pas eux-mêmes — et
`*/migrations/*`, code généré rejoué à chaque création de base de test, dont
le décompte gonflerait la mesure sans rien garantir.

**Couverture de branches activée** (`branch = true`) : un `if` dont une seule
issue est exercée compte comme partiel. La mesure est donc plus exigeante
qu'une couverture de lignes seule.

`--cov` n'est **pas** dans `addopts` : le travail courant lance des tests
ciblés, et mesurer à chaque exécution l'alourdirait. La commande complète est
documentée dans le README.

## 3. Mesure, seuil et sa justification

Passage complet unique, avec couverture, sur une **base de test isolée** :
pytest-django crée et détruit `test_afrimyth`, distincte de la base des
exercices `afrimyth`. Celle-ci n'a reçu aucune écriture, aucune migration et
aucun nettoyage.

| Mesure | Valeur réelle |
| --- | --- |
| Tests | **1 126 passés**, aucun échec, aucun ignoré, en 1 297,00 s (21 min 37 s), sortie `0` |
| Instructions | 1 839, dont 24 non couvertes |
| Branches | 382, dont 16 partielles |
| **Couverture totale** | **98,20 %** — soit 2 181 éléments couverts sur 2 221 |

**Seuil retenu : `fail_under = 95`**, soit une marge de **3,2 points** sous la
mesure. La marge est délibérée et dimensionnée sur ce que la mesure contient
réellement :

- deux fichiers sont à **0 %** par nature — `config/asgi.py` et
  `config/wsgi.py`, 8 instructions au total : ce sont les points d'entrée des
  serveurs, jamais importés par la suite. Je ne les ai **pas** exclus pour
  gonfler le chiffre ; ils restent dans le dénominateur ;
- le reste des manques est diffus et légitime : branches défensives de
  `import_mythology_pilot.py` (97 %), de `selectors.py` (96 %) et quelques
  branches de `serializers.py` et `models.py` (99 %) ;
- 3,2 points représentent environ 70 éléments : de quoi absorber un
  remaniement ordinaire sans rendre la CI rouge pour du bruit, tout en
  arrêtant une régression réelle.

Un seuil collé à 98 % transformerait la CI en alarme permanente ; un seuil
bas ne garantirait rien. 95 se vérifie, et le garde-fou a été éprouvé.

**Vérification du seuil sur le rapport déjà produit**, sans rejouer pytest :

| Commande | Résultat |
| --- | --- |
| `coverage report --precision=2` (seuil 95 lu dans `pyproject.toml`) | `TOTAL … 98.20%`, **sortie `0`** |
| `coverage report --fail-under=99` — contre-épreuve | **sortie `2`** : le garde-fou échoue bien quand la mesure est sous le seuil |

La contre-épreuve importe : sans elle, une sortie `0` ne prouverait pas que
le seuil est réellement appliqué.

## 4. Workflow de CI

`.github/workflows/ci.yml`, **un seul** workflow et **un seul** job, sur les
pull requests et les pushes vers `main`. Aucune matrice, aucun service
supplémentaire.

| Point | Choix |
| --- | --- |
| Runner | `ubuntu-latest` |
| Python | **3.12**, via `actions/setup-python@v7`, cache `pip` sur les deux fichiers de dépendances |
| Checkout | `actions/checkout@v7` |
| Base de données | service `postgres:16`, `--health-cmd pg_isready`, port publié `5432:5432` |
| Identifiants | `afrimyth_ci` / base `afrimyth_ci`, **réservés à cette base éphémère**, détruite avec le runner, partagés avec aucune installation locale |
| Permissions | `contents: read` uniquement |

**Versions et syntaxe vérifiées dans la documentation officielle** : les
dépôts `actions/checkout` et `actions/setup-python` annoncent tous deux `v7`
comme version majeure courante, et la page GitHub « Creating PostgreSQL
service containers » donne la forme du bloc `services` et la règle de
connexion retenue — un job exécuté **sur le runner** joint le service par
`localhost` et le port publié, et non par le nom du service.

**Indépendance de l'environnement.** Les variables sont fournies par le bloc
`env` du job. Aucun fichier `.env` n'existe sur le runner : `load_dotenv()`
n'y trouve rien et les variables du job s'appliquent. Le job ne dépend ni du
corpus V2, ni de Docker Desktop, ni de la base PostgreSQL de Windows.

**Sept contrôles, chacun une étape distincte**, sans `continue-on-error` : le
premier échec arrête le job et fait échouer la CI.

`ruff check .` · `ruff format --check .` · `mypy .` · `manage.py check` ·
`makemigrations --check --dry-run` ·
`spectacular --validate --fail-on-warn` · `pytest --cov --cov-report=term-missing`

Les configurations sont celles de `pyproject.toml` : la CI ne redéfinit aucune
règle de lint, de typage ou de seuil.

## 5. Contrôles locaux — ce qui est prouvé ici

| Commande | Résultat réel |
| --- | --- |
| `ruff check .` | `All checks passed!`, sortie `0` |
| `ruff format --check .` | `64 files already formatted`, sortie `0` |
| `mypy .` | `Success: no issues found in 64 source files` |
| `python manage.py check` | `System check identified no issues (0 silenced).` |
| `python manage.py makemigrations --check --dry-run` | `No changes detected`, sortie `0` |
| `python manage.py spectacular --validate --fail-on-warn` | **sortie `0`**, aucun avertissement ; schéma écrit hors du dépôt |
| `pytest --cov --cov-report=term-missing` (passage complet unique) | **1 126 passés**, 98,20 %, sortie `0` |
| `coverage report` avec le seuil, puis contre-épreuve à 99 | `0` puis `2` |
| Validité du workflow | YAML analysé sans erreur : déclencheurs, permissions, service et dix étapes conformes à l'intention |

**Une différence local/CI identifiée et ciblée.** Localement `DJANGO_DEBUG`
vaut `True` ; la CI emploie `False`, ce qui change la durée d'accès JWT
calculée à l'import de `config/settings.py`. Plutôt que de supposer, j'ai
rejoué **la seule suite concernée** avec `DJANGO_DEBUG=False` :
`pytest tests/` → **83 passés**, sortie `0`. Les tests de réglages lisent la
valeur effective et s'adaptent dans les deux sens ; cette différence
d'environnement ne fera donc pas échouer la CI.

Aucune relance redondante : les contrôles rapides ont précédé l'unique
passage complet, et le seuil a été vérifié sur le rapport déjà obtenu.

## 6. CI distante — statut séparé

**Le workflow n'a jamais été exécuté sur GitHub Actions.** Aucun commit,
aucun push, aucune pull request : il n'existe donc aucun résultat distant, et
je n'en présente aucun. Ce qui est établi localement est listé au point 5 ;
ce qui reste à établir est l'exécution réelle sur le runner.

Écarts qui ne peuvent être levés que par cette exécution : `ubuntu-latest`
contre Windows, l'installation des dépendances depuis `requirements-dev.txt`
sur un interpréteur neuf, la disponibilité du service `postgres:16` par son
healthcheck, et la création de la base de test par le rôle `afrimyth_ci`.
La durée est à prévoir : le passage complet prend environ 21 minutes en
local.

Conformément au prompt, **l'exécution distante sera vérifiée par Codex après
revue et publication**.

## 7. Obstacles

**Aucun défaut applicatif ne bloque la CI.** Les sept contrôles passent
localement, dans l'ordre et avec les commandes exactes du workflow. Rien n'a
dû être contourné, désactivé ni corrigé dans le code.

Deux limites, assumées et sans incidence sur ce lot :

- `config/asgi.py` et `config/wsgi.py` restent à 0 % : les couvrir
  demanderait des tests dont la seule fonction serait d'importer un point
  d'entrée, ce que le prompt exclut.
- Les artefacts de couverture (`.coverage`, rapports) ne sont pas versionnés
  et ne sont pas téléversés vers un service externe : aucun badge, aucun
  artefact publié, hors périmètre.

## 8. État Git

Aucun commit, aucun push, aucun tag. HEAD **`9699006`**, inchangé. La roadmap
n'a pas été modifiée et aucune phase n'est déclarée close.

```
 M CLAUDE.md
 M README.md
 M pyproject.toml
 M requirements-dev.txt
?? .github/
?? docs/reports/phase-6-increment-2-ci-couverture.md
```

`.github/` contient le seul fichier `workflows/ci.yml`. Les artefacts de
couverture n'apparaissent pas : `.coverage` est déjà ignoré par `.gitignore`,
et les rapports ont été écrits hors du dépôt.
