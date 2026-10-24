# CLAUDE.md

Instructions pour les agents Claude travaillant sur `afrimyth-api`.

## Nature du projet

API REST Django (Python 3.12, Django 5.2 LTS, Django REST Framework,
PostgreSQL) pour le projet Afrimyth.

La phase 1 est terminée : socle technique, modèle utilisateur personnalisé,
endpoint de santé, tronc commun `Entity`, premier profil `DivinityProfile`,
administration Django et API de lecture liste/détail. La phase 2 complète
progressivement le modèle métier, incrément par incrément.

## Structure

```
config/        Projet Django (settings, urls, wsgi/asgi, vues techniques)
accounts/      Utilisateurs et authentification — contient le modèle `User`
mythology/     Domaine mythologique — `Entity`, profils, référentiels, liens
               et `services.py` pour les fonctions métier demandées
tests/         Tests transverses (socle, endpoints techniques)
docs/reports/  Rapport d'intervention, un fichier par incrément
```

## Règles de travail

- **Périmètre.** N'implémente que ce qui est demandé. Ne devance pas la
  roadmap : le modèle métier se complète un incrément à la fois, et chaque
  incrément nomme explicitement ce qu'il laisse de côté.
- **Pas d'abstraction anticipée.** Pas de couche service/repository générique,
  pas de `BaseModel`, pas de mixins spéculatifs. Du Django idiomatique.
  Réutiliser les validations des bibliothèques plutôt que les vérifier deux
  fois. Éviter fonctions auxiliaires et assertions redondantes ; conserver
  les protections de sécurité et tests de contrat réellement utiles.
  En revanche, une **fonction métier concrètement demandée** est légitime
  lorsqu'une règle ne peut pas être portée par un modèle seul : ainsi
  `mythology/services.py`, prévu par la décision 6 de l'ADR 0002 pour
  garantir le couple entité/profil, et `mythology/selectors.py`, demandé par
  la phase 3 pour définir la visibilité publique en un seul endroit. La règle
  exclut les abstractions spéculatives, pas les fonctions explicitement
  commandées par la roadmap.
- **Configuration.** Toute valeur dépendante de l'environnement passe par une
  variable d'environnement déclarée dans `.env.example`. Jamais de secret en
  dur ni dans le dépôt.
- **Modèle utilisateur.** `accounts.User` est déclaré via `AUTH_USER_MODEL` et
  créé dans `accounts/migrations/0001_initial.py`. Ne le remplace pas et ne
  supprime pas cette migration.
- **Migrations.** Une migration par changement de modèle, générée avec
  `makemigrations`, committée avec le code qu'elle accompagne.
- **Tests.** Tout endpoint ou comportement ajouté vient avec un test pytest.
- **Rapport.** Chaque intervention crée ou actualise un rapport sous
  `docs/reports/`, contenant : objectif et périmètre, fichiers touchés,
  décisions prises, commandes de vérification et leurs résultats, blocages
  rencontrés et leur résolution, état Git final. Aucun secret, aucune valeur de
  `.env`, aucun mot de passe n'y figure.
- **Langue.** Le français est la langue de travail interne, l'anglais celle du
  produit public. Décision complète dans l'ADR 0003 du dépôt de pilotage.
  - **En anglais** — identifiants du code ; `README.md` et toute documentation
    publique ; contrat d'API : noms de champs, valeurs techniques,
    descriptions et messages destinés aux clients ; futur schéma OpenAPI et
    ses interfaces Swagger ou ReDoc ; contenu canonique du corpus, y compris
    les noms et les descriptions importés ; toutes les docstrings du code,
    y compris celles des modules, classes, fonctions et tests internes.
  - **En français** — commentaires internes hors docstrings ; prompts ; rapports
    de `docs/reports/` ; documentation interne.
  - Les nouvelles docstrings sont en anglais. La traduction des docstrings
    françaises existantes est reportée à une passe documentaire avant la
    livraison V1, sans changement fonctionnel (précision de l'ADR 0003).
  - **Aucune internationalisation n'est ajoutée à ce stade** : pas de tables de
    traduction, pas de champs suffixés par langue, pas de `gettext` sur les
    chaînes publiques.
  - Ne traduis pas les fichiers sources existants au passage. Les libellés
    encore en français et techniquement visibles — `verbose_name`, libellés de
    choix, `help_text`, messages d'erreur de `clean()` — sont une dette connue,
    inscrite dans la roadmap, à normaliser avant la stabilisation du contrat
    public.

## Hors périmètre à ce stade

Docker, CI.

**Authentification.** JWT est en place depuis la phase 4 : trois routes sous
`/api/auth/` (obtention, renouvellement, identité), par Simple JWT. Restent
hors périmètre la rotation des jetons, la liste de révocation, la
déconnexion, l'inscription en libre-service et la réinitialisation de mot de
passe. Surtout : être authentifié n'ouvre **aucun** accès supplémentaire au
corpus — l'autorisation viendra avec l'écriture, portée par des groupes
Django vérifiés côté serveur.

**Dossier `_audit`.** Ne recopie jamais le dossier, son code, ses images ni un
corpus complet dans ce dépôt. En revanche, **lire** un fichier de données
externe situé dans `_audit` est autorisé lorsqu'un import le demande
explicitement : le chemin est alors passé en argument de commande, jamais
codé en dur, et les tests committés restent autonomes avec des données
synthétiques.

**Rendu visuel et génération d'images.** Les modèles ne portent que des faits
mythologiques. Les données de rendu — prompt canonique, variantes de prompt,
prompt négatif, styles visuels, matrice de styles et métadonnées d'image, de
son ou de vidéo — restent hors des incréments en cours et vivront dans leur
propre module, après la V1. N'ajoute aucun champ `prompt` à `Entity` ni à ses
profils.

## Commandes

```bash
py -3.12 -m venv .venv && .venv/Scripts/activate   # Windows
pip install -r requirements-dev.txt
cp .env.example .env

python manage.py migrate
python manage.py runserver

pytest                 # tests
ruff check .           # lint
ruff format --check .  # format
mypy .                 # typage
```

Un fichier `.env` est nécessaire à toutes ces commandes : `config/settings.py`
refuse de démarrer sans `DJANGO_SECRET_KEY` hors `DJANGO_DEBUG=True`.

`pytest` n'a pas besoin de PostgreSQL tant qu'aucun test ne touche la base ;
`migrate` et `runserver` en ont besoin.
