# Rapport — Publication de la phase 1 sur GitHub

- **Date :** 13 octobre 2026
- **Opération :** push des deux dépôts, sans création de commit
- **Résultat :** les deux pushes ont réussi

## 1. Dépôts publiés

| Dépôt local | Remote `origin` | Branche |
|---|---|---|
| `C:\Users\heric\dev\afrimyth-api` | `git@github.com:hericlibong/afrimyth-api.git` | `main` |
| `C:\Users\heric\dev\django-portfolio` | `git@github.com:hericlibong/django-portfolio.git` | `main` |

URL de consultation :

- <https://github.com/hericlibong/afrimyth-api>
- <https://github.com/hericlibong/django-portfolio>

## 2. Contrôles avant push

Effectués sur les deux dépôts, aucun n'a révélé d'anomalie.

| Contrôle | `afrimyth-api` | `django-portfolio` |
|---|---|---|
| `origin` conforme à l'URL attendue | OK | OK |
| Branche courante | `main` | `main` |
| Arbre de travail propre pour les fichiers suivis | OK | OK |
| Fichiers non suivis restant hors du push | aucun | `_audit/` seul, non indexé |
| `.env`, `.venv`, `__pycache__`, `_audit`, `.claude` dans **tout** l'historique | aucun | aucun |
| Auteur et committer de chaque commit | `héric Libong <hericlibong@gmail.com>` | idem sur les 6 commits |

Le contrôle des fichiers sensibles a porté sur l'intégralité de l'historique,
pas seulement sur le dernier commit :
`git log --all --name-only` filtré sur ces motifs ne retourne rien dans les
deux dépôts. Un fichier retiré d'un commit ultérieur resterait visible dans
l'historique publié, d'où ce contrôle élargi.

Aucun commit n'a été créé, aucun fichier non suivi n'a été ajouté à l'index,
et ni `--force`, ni `amend`, ni `rebase`, ni réécriture d'auteur n'ont été
employés.

## 3. Commandes de push

```
# afrimyth-api
git push -u origin main
branch 'main' set up to track 'origin/main'.
 * [new branch]      main -> main

# django-portfolio
git push origin main
   d7ecc60..84ffa24  main -> main
```

`afrimyth-api` n'avait jamais été poussé : la branche distante est créée par
cette opération et l'option `-u` établit le suivi. `django-portfolio` existait
déjà à `d7ecc60` et avance de cinq commits.

## 4. SHA publiés

### `afrimyth-api` — 2 commits, l'intégralité de l'historique

| SHA | Message |
|---|---|
| `cf3bd815ef3d68b290291175cc5b724c8704ae30` | `feat: add entity read API` |
| `7196daa42a786f8d2bb81523878b6450e2d0014e` | `chore: initialize Django REST API` |

### `django-portfolio` — 5 commits publiés par cette opération

| SHA | Message |
|---|---|
| `84ffa24cf75e69ff41f4cd59fd21d244f99e3396` | `docs: complete project 1 phase 1` |
| `1c220a5ecc87f397cb7f3fd1f3544313262f0ae1` | `docs: record phase 1 first increment` |
| `b323a3f` | `docs: refine moderation and deletion rules` |
| `a931c38` | `docs: record phase 0 decisions` |
| `38a21dd` | `docs: roadmap projet 1` |

Le commit `d7ecc60` (`docs: add bilingual portfolio index`) était déjà publié
et constitue la base de ce push.

## 5. Contrôles après push

### Correspondance des SHA

`git ls-remote origin refs/heads/main` comparé à `git rev-parse main` :

| Dépôt | SHA local | SHA distant | Identiques |
|---|---|---|---|
| `afrimyth-api` | `cf3bd815…` | `cf3bd815…` | oui |
| `django-portfolio` | `84ffa24c…` | `84ffa24c…` | oui |

### Suivi et écart

| Dépôt | `git status --short --branch` | `rev-list --left-right --count origin/main...main` |
|---|---|---|
| `afrimyth-api` | `## main...origin/main` | `0 0` |
| `django-portfolio` | `## main...origin/main` puis `?? _audit/` | `0 0` |

`branch.main.remote = origin` et `branch.main.merge = refs/heads/main` dans les
deux dépôts : `main` suit bien `origin/main`, et n'est plus en avance.

### Identité des commits publiés

Relue sur `origin/main` après le push, et non sur les références locales :
les 2 commits de `afrimyth-api` et les 6 de `django-portfolio` portent tous
`héric Libong <hericlibong@gmail.com>` comme auteur **et** comme committer.
Aucun trailer `Co-authored-by`, aucune mention d'un autre auteur.

### Contenu réellement publié

Énuméré par `git ls-tree -r --name-only origin/main`.

`afrimyth-api` — 40 fichiers : `manage.py`, `pyproject.toml`,
`requirements.txt`, `requirements-dev.txt`, `.gitignore`, `.env.example`,
`README.md`, `CLAUDE.md`, `AGENTS.md`, les apps `config/`, `accounts/` et
`mythology/` avec leurs migrations et tests, `tests/` et les deux rapports
`docs/reports/phase-1-increment-1.md` et `phase-1-increment-2.md`.

`django-portfolio` — 8 fichiers : `README.md`, `docs/roadmap-projet-1.md`,
`docs/modele-donnees.md`, les deux ADR et les trois prompts de phase 1.

**Absents de l'arbre publié, comme attendu :** `.env`, `.venv/`, `_audit/`,
`.claude/`, `__pycache__/`, `.pytest_cache/`, `.mypy_cache/`, `.ruff_cache/`.
`.env.example` est publié, mais ne contient que des placeholders
(`change-me-in-production`, `change-me`) et aucune valeur réelle.

## 6. État Git final

```
# afrimyth-api
## main...origin/main
(aucun fichier modifié ni non suivi, hors le présent rapport)

# django-portfolio
## main...origin/main
?? _audit/
```

`_audit/` reste volontairement non suivi dans `django-portfolio` : environ 3 Mo
de médias et une base SQLite issus des trois dépôts audités, qui n'ont pas à
être publiés.

## 7. Statut de ce rapport

Ce fichier — `docs/reports/phase-1-push.md` — n'est **pas committé**,
conformément à la consigne. Il apparaît donc en fichier non suivi dans
`afrimyth-api` jusqu'à décision contraire.
