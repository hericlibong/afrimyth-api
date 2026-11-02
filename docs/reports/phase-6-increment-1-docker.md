# Phase 6 — Incrément 1 : démarrage local Docker et PostgreSQL

Rapport d'intervention, en français. Aucun secret, aucune valeur de `.env`
ni de `.env.docker`, aucun mot de passe et aucun jeton n'y figure.

Intervention : Claude CLI, 3 novembre 2026, sur le prompt
`docs/prompts/phase-6-increment-1-docker.md`. HEAD au départ **`b7560dc`**,
conforme à l'attendu, arbre propre.

**Aucun code applicatif modifié, aucun test relancé.** Les 1 126 tests de la
phase 5 n'ont pas été rejoués : seuls des fichiers Docker et de documentation
ont été ajoutés, et les essais d'intégration en conteneur sont les contrôles
pertinents. Aucune migration créée, aucune dépendance ajoutée, aucune règle
API ou JWT modifiée.

## 1. Prérequis Windows : état réel

Le constat Codex du 2 novembre signalait le moteur Linux indisponible. **Au
moment de cette intervention, il était disponible** — l'auteur avait donc
déjà ouvert Docker Desktop, et tous les essais ont pu être exécutés :

| Contrôle | Résultat réel |
| --- | --- |
| Client Docker | `27.4.0` |
| Compose | `v2.31.0-desktop.2` |
| Moteur (serveur) | `27.4.0`, `OSType=linux`, `Driver=overlay2` — **prêt** |

**Aucune action manuelle n'est encore nécessaire.** Rien n'a été installé,
mis à jour ni reconfiguré : ni Docker, ni WSL, ni Windows, ni le réseau, ni
les droits système, ni aucun service personnel. Aucune invite interactive
n'est apparue. La seule condition à retenir pour les prochaines sessions est
celle déjà connue : **Docker Desktop doit être ouvert et son moteur annoncé
prêt avant toute commande Compose**, sinon `docker compose` échoue à joindre
le démon. PostgreSQL n'a pas à être installé sur Windows pour ces conteneurs.

## 2. Fichiers livrés

| Fichier | Rôle |
| --- | --- |
| `Dockerfile` | Image de l'API : `python:3.12-slim`, **seul** `requirements.txt` installé, utilisateur non privilégié, serveur de développement Django |
| `docker-compose.yml` | Deux services — `api` et `db` (`postgres:16`) — projet nommé `afrimyth-docker`, volume nommé, healthcheck, publication sur `127.0.0.1:8001` |
| `.dockerignore` | Exclut `.env` réels, `.venv`, caches, `.git`, `docs/`, rapports, tests, sauvegardes et sorties locales |
| `.env.docker.example` | Modèle à **valeurs fictives**, sans aucun secret réel |
| `.gitignore` | Une ligne ajoutée : `!.env.docker.example`, sinon la règle `.env.*` préexistante aurait masqué le modèle |
| `README.md` | Une section « Running with Docker » ajoutée ; le reste intact |
| `CLAUDE.md` | La mention « Docker, CI » hors périmètre devenue « CI et couverture », plus le périmètre Docker réellement autorisé |
| `docs/reports/phase-6-increment-1-docker.md` | Ce rapport |

Versions reprises telles quelles : **Python 3.12** et **PostgreSQL 16**, déjà
employés par le projet. Aucun changement opportuniste.

## 3. Isolement : ce qui a été vérifié

| Exigence | Contrôle réel |
| --- | --- |
| `.env` des exercices ni ouvert, ni copié, ni réutilisé | Son contenu n'a jamais été lu. `.dockerignore` exclut `.env` et `.env.*` ; dans le conteneur, `/app` ne contient que les deux fichiers d'exemple (`.env.example`, `.env.docker.example`) |
| Environnement Docker distinct et ignoré par Git | `.env.docker` généré avec des valeurs aléatoires, **non affichées** ; `git check-ignore` le confirme ignoré, et `git status` ne le montre pas |
| Choix explicite de l'environnement | Toutes les commandes passent `--env-file .env.docker`, et chaque service déclare `env_file: .env.docker`. Aucune dépendance implicite au `.env` local |
| Connexion par le nom de service | `printenv POSTGRES_HOST` dans le conteneur → **`db`**. Ni `localhost`, ni `host.docker.internal` ; la valeur est imposée par `docker-compose.yml`, pas par le fichier d'environnement |
| Port PostgreSQL non publié | `docker compose port db 5432` → aucun mappage ; `ps` montre `5432/tcp` interne seulement |
| Projet et volume distincts | Projet `afrimyth-docker`, volume `afrimyth-docker_afrimyth-db-data`, réseau `afrimyth-docker_default` |
| API sur 8001 | `127.0.0.1:8001->8000/tcp`. Le port 8001 était **libre** avant démarrage |
| Services personnels intacts | Le port **8000** (API des exercices) et le **5432** (PostgreSQL local) étaient en écoute avant et après : aucun service arrêté |
| Base `afrimyth` locale et ses 45 fiches | **Aucune connexion**, aucune migration, aucun import, aucune sauvegarde ou restauration, aucun nettoyage. Je ne l'ai délibérément pas interrogée pour « vérifier » sa préservation : s'y connecter aurait violé la consigne. La preuve d'isolement est indirecte et suffisante — la base du conteneur répond `entities=0` |
| Contexte d'image propre | Dans `/app` : pas de `.git`, pas de `.venv`, pas de `docs/`, pas de `tests/` ni `mythology/tests/`. Aucun corpus JSON V2, aucune image externe, aucune sauvegarde |
| Aucun compte ni corpus automatiques | `users=0`, `entities=0`, `relations=0` après démarrage |

## 4. Commandes et résultats réels

| Commande | Résultat |
| --- | --- |
| `docker compose --env-file .env.docker config --quiet` | **sortie `0`**, aucune valeur affichée (avant et après la documentation) |
| `docker compose --env-file .env.docker build` | **sortie `0`** ; image `afrimyth-docker-api`, 20 paquets installés depuis `requirements.txt` |
| `docker compose --env-file .env.docker up -d` | **sortie `0`** ; `db` passé **`Healthy`** avant le démarrage de `api` |
| `docker compose ps` | `api` : `Up`, `127.0.0.1:8001->8000/tcp` — `db` : `Up (healthy)`, `5432/tcp` |
| Logs `api` | **28 migrations appliquées** à la création, dont les 7 de `mythology`, avant tout service HTTP |

Endpoints, tous en **HTTP 200** :

| URL | Résultat |
| --- | --- |
| `/api/health/` | `{"status":"ok"}`, `application/json` |
| `/api/docs/` | Swagger UI, `text/html`, titre `Afrimyth API` |
| `/api/schema/` | `application/vnd.oai.openapi`, **191 942 octets**, `openapi: 3.0.3`, titre présent |
| `/api/entities/` | `{"count":0,"next":null,"previous":null,"results":[]}` — consultation publique **vide en 200**, comme attendu d'une base métier neuve |
| `/static/admin/css/base.css` | 22 120 octets — les statiques nécessaires au mode `runserver` sont servis |

## 5. Persistance du volume

Contrôle par un arrêt complet **sans suppression de volume**, puis
redémarrage. Aucune donnée de démonstration créée, aucun import relancé.

| Mesure | Avant l'arrêt | Après redémarrage |
| --- | --- | --- |
| Migrations appliquées (`showmigrations --plan`) | 27 | **27** |
| Tables du schéma `public` | 24 | **24** |
| Journal de l'API au redémarrage | — | **`No migrations to apply.`** |
| `/api/health/` | `{"status":"ok"}` | `{"status":"ok"}` |

`docker compose down` a retiré les conteneurs et le réseau ; le volume
`afrimyth-docker_afrimyth-db-data` est resté présent et a été réutilisé.
**`down -v`, purge, reset ou suppression de volume n'ont jamais été employés.**

## 6. État des services à la remise

**Les deux services sont laissés démarrés** — `api` et `db` en marche, API
joignable sur <http://127.0.0.1:8001>, pour que la revue et les lectures
Postman puissent se faire sans redémarrage. `restart: unless-stopped` est
déclaré : ils repartiront avec Docker Desktop. L'arrêt se fait par
`docker compose --env-file .env.docker down`, sans `-v`.

## 7. Limites assumées

- **Serveur de développement Django**, explicitement : pas de serveur WSGI,
  de reverse proxy, de Kubernetes, de Celery ni de Redis. Aucune promesse de
  déploiement en production.
- **Code de l'application monté par copie dans l'image**, sans volume de
  développement : modifier un fichier Python demande une reconstruction. Je
  n'ai pas ajouté de montage, qui n'est pas demandé par ce lot.
- **Swagger UI charge ses ressources depuis un CDN**, comme dans
  l'installation locale. Aucune dépendance de distribution statique n'a été
  ajoutée pour l'éviter.
- **CI et couverture** restent hors périmètre, pour le prochain incrément.
- Aucun essai bloqué : le moteur était disponible et tous les contrôles
  prévus ont été exécutés.

## 8. État Git

Aucun commit, aucun push, aucun tag. HEAD **`b7560dc`**, inchangé. La roadmap
n'a pas été modifiée et aucune phase n'est déclarée close.

```
 M .gitignore
 M CLAUDE.md
 M README.md
?? .dockerignore
?? .env.docker.example
?? Dockerfile
?? docker-compose.yml
?? docs/reports/phase-6-increment-1-docker.md
```

`.env.docker` est bien absent de cet état : il est ignoré, comme voulu.
