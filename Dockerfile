# Image de l'API pour le démarrage local. Python 3.12, la version déjà
# employée par le projet : aucun changement opportuniste de version.
FROM python:3.12-slim

# `PYTHONDONTWRITEBYTECODE` évite d'écrire des `.pyc` dans le conteneur,
# `PYTHONUNBUFFERED` rend les logs Django visibles immédiatement.
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

# Les dépendances d'abord, le code ensuite : modifier un fichier Python ne
# réinstalle pas les paquets. Seul `requirements.txt` est installé — les
# outils de développement (pytest, ruff, mypy, ipython) n'ont rien à faire
# dans l'image de service.
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Utilisateur non privilégié : rien dans ce conteneur n'exige root.
RUN useradd --create-home --uid 1000 app && chown -R app:app /app
USER app

EXPOSE 8000

# Le serveur de développement de Django, et rien d'autre. Ce lot est local :
# aucune promesse de déploiement en production n'est faite ici.
CMD ["python", "manage.py", "runserver", "0.0.0.0:8000"]
