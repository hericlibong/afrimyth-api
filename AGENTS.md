# AGENTS.md

Ce dépôt suit les conventions décrites dans [`CLAUDE.md`](./CLAUDE.md).

Tout agent de codage — quel que soit l'outil — doit s'y référer avant
d'intervenir : structure du projet, périmètre autorisé, règles de
configuration, de migration et de test y sont décrits une seule fois.

En résumé :

- rester dans le périmètre demandé, sans anticiper la roadmap ;
- pas d'abstraction spéculative, du Django idiomatique ;
- configuration par variables d'environnement, aucun secret committé ;
- un test pour tout comportement ajouté ;
- un rapport créé ou actualisé sous `docs/reports/` à chaque intervention —
  objectif, fichiers touchés, décisions, commandes et résultats, blocages et
  état Git final, sans aucun secret ni valeur de `.env` ;
- ne pas committer ni pousser sans demande explicite.
