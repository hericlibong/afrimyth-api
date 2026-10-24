# Vérifier JWT dans Postman — guide interne

Document de travail interne, en français. Il sert à vérifier **à la main** les
trois routes d'authentification, dans un client HTTP, pour voir ce que les
tests automatiques prouvent sans le montrer.

## Ce qui a déjà été exécuté, ce qui reste à faire ensemble

**Après revue :** 55 tests couvrent les routes JWT et leurs non-régressions, dont
l'obtention avec des identifiants valides et invalides, le refus d'un jeton
expiré, malformé, mal signé ou de mauvais type, le renouvellement, et le fait
qu'un jeton n'ouvre aucun accès supplémentaire au corpus. Voir
`tests/test_auth_jwt.py` et `tests/test_auth_does_not_change_reads.py`.

**Validation pratique du 24 octobre 2026 :** l'auteur a préparé sa collection
Postman et son Local Vault, créé un compte fictif non administrateur et
confirmé l'obtention des deux jetons, l'expiration d'un accès en 401,
son renouvellement et l'identité en 200. La collection reste dans son Postman,
sans export de secrets dans le dépôt. Les autres essais ci-dessous sont des
exercices proposés, pas des manipulations manuelles toutes exécutées.

Les tests automatiques restent isolés dans leur propre base. La clé locale
a été remplacée par l'auteur sans transmission de sa valeur.

## Préparation

### 1. Lancer le serveur

```bash
python manage.py runserver
```

### 2. Créer un compte fictif

Il n'y a pas d'inscription en libre-service : les comptes se créent par
l'administration Django. Si tu n'as pas encore de superutilisateur :

```bash
python manage.py createsuperuser
```

Puis, sur `http://127.0.0.1:8000/admin/` :

1. ouvre **Utilisateurs** → **Ajouter** ;
2. choisis un nom d'utilisateur reconnaissable comme fictif, par exemple
   `essai-postman`, et un mot de passe **fort et unique que tu choisis**, même
   pour cet exercice local ; ne réutilise pas un mot de passe personnel ;
3. enregistre, puis sur l'écran suivant **laisse** `Statut équipe` et
   `Statut super-utilisateur` décochés, et **laisse** `Actif` coché.

Un compte sans privilège est exactement ce qu'il faut : le but est de vérifier
qu'un jeton fonctionne, pas qu'un administrateur peut tout faire. C'est aussi
ce qui rend la vérification honnête — si la route `me` répondait seulement aux
comptes d'équipe, on ne le verrait pas avec un superutilisateur.

### 3. Préparer l'environnement Postman

Crée un environnement avec une seule variable :

| Variable | Valeur |
| --- | --- |
| `base_url` | `http://127.0.0.1:8000` |

Toutes les requêtes utilisent ensuite `{{base_url}}/api/...`. Quand l'API sera
déployée, il suffira de changer cette valeur.

**Garde les secrets dans le Local Vault.** Ne partage ni ne synchronise les
valeurs de mots de passe ou de jetons ; un masquage visuel ne garantit pas
qu'une valeur est absente d'un export. La portée et le partage des variables
dépendent du mode utilisé, pas du seul fait d'être connecté.
Stocke mot de passe, accès et renouvellement dans le **Local Vault** et utilise
leurs références `{{vault:nom-de-la-clef}}`. Ne sauvegarde pas leurs valeurs
dans des requêtes, exemples ou fichiers texte. Aucun script automatique de
gestion des jetons n'est nécessaire pour ces exercices.

Ne mets pas en place de script qui copie les jetons dans un environnement
partagé : ils pourraient être divulgués lors de la synchronisation.

## Les deux jetons, et ce qu'ils ne sont pas

Avant de commencer, deux distinctions qui expliquent tout le reste.

**Accès et renouvellement ne jouent pas le même rôle.** Le jeton d'**accès**
vit 5 minutes et s'envoie dans l'en-tête `Authorization` de chaque requête
authentifiée. Le jeton de **renouvellement** vit 1 jour, ne s'envoie **qu'à**
la route de renouvellement, et dans le corps de la requête — jamais dans
l'en-tête. Les deux ne sont pas interchangeables, et l'API refuse l'un à la
place de l'autre.

Pourquoi deux ? Parce qu'un jeton d'accès voyage sans arrêt, donc on veut
qu'il expire vite ; et parce que retaper son mot de passe toutes les cinq
minutes serait intenable, donc on garde un jeton long qu'on expose rarement.

**S'authentifier n'est pas être autorisé.** L'authentification répond « qui
appelle ? ». L'autorisation répond « qu'a-t-il le droit de faire ? ». À ce
stade, l'API ne fait que la première : un jeton valide ne débloque rien. La
lecture du corpus est anonyme, les brouillons restent invisibles, et l'écriture
reste refusée. C'est la quatrième vérification ci-dessous, et c'est la plus
importante à constater de ses yeux.

## Les vérifications, dans l'ordre

### 1. Obtenir une paire de jetons

```
POST {{base_url}}/api/auth/token/
```

En-tête `Content-Type: application/json`, corps en JSON brut :

```json
{
  "username": "essai-postman",
  "password": "{{vault:afrimyth-essai-postman}}"
}
```

**Attendu :** `200`, avec deux champs, `access` et `refresh`.

Essaie aussi un mot de passe erroné, puis un nom d'utilisateur qui n'existe
pas. **Attendu :** `401` dans les deux cas, avec exactement le même corps —
l'API ne dit pas lequel des deux a échoué, sinon elle confirmerait l'existence
d'un compte. Enfin, envoie un corps sans `password` : **attendu** `400`, car
il s'agit d'une requête mal formée, pas d'une identité refusée.

Stocke les deux jetons dans le Local Vault. Ils comportent trois blocs séparés
par des points : leur charge est lisible, pas chiffrée, mais le jeton complet
est un **secret au porteur**. Ne colle jamais un jeton utilisable dans un site
externe, un rapport ou cette conversation. Si nous examinons sa structure,
nous le ferons localement, ou avec un exemple synthétique inutilisable.

### 2. Appeler `me` sans jeton, puis avec

D'abord sans rien :

```
GET {{base_url}}/api/auth/me/
```

**Attendu :** `401`, `"Authentication credentials were not provided."`

Ajoute ensuite l'en-tête, en remplaçant la valeur par le jeton d'**accès** :

```
Authorization: Bearer eyJhbGciOi...
```

**Attendu :** `200`, et un corps de deux champs :

```json
{"id": 3, "username": "essai-postman"}
```

Vérifie ce qui **n'y est pas** : pas d'adresse de courriel, pas d'empreinte de
mot de passe, aucun indicateur d'administration, aucune permission. La route
répond « qui suis-je », pas « que puis-je faire ». Voir
`accounts/serializers.py`.

Essaie aussi, par curiosité, de te connecter à l'administration dans le même
navigateur puis de rappeler `me` : **attendu** `401` quand même. Cette vue
n'accepte que JWT, délibérément — elle existe pour prouver qu'un *jeton*
fonctionne, et une session ouverte donnerait une fausse impression de succès
(`accounts/views.py`).

### 3. Essayer un jeton invalide

Reprends la requête précédente et abîme le jeton : supprime quelques
caractères au milieu du troisième bloc, celui de la signature.

**Attendu :** `401`, `"Given token not valid for any token type"`. La signature
est vérifiée, donc on ne peut pas fabriquer un jeton sans la clef du serveur.

Essaie aussi d'envoyer le jeton de **renouvellement** dans l'en-tête
`Authorization`. **Attendu :** `401`. Les deux types sont distingués, pas
seulement par convention.

**Un piège à connaître.** Garde l'en-tête abîmé, et appelle une route
publique :

```
GET {{base_url}}/api/entities/
```

**Attendu :** `401`, alors que cette route ne demande aucune authentification.
Ce n'est pas une panne. Django REST Framework authentifie **avant** de vérifier
les permissions : un en-tête `Authorization` présent mais invalide fait échouer
l'étape d'authentification, et la requête n'atteint jamais la permission qui
l'aurait laissée passer. Retire l'en-tête, rappelle la route : `200`. C'est la
cause la plus fréquente d'un « l'API est cassée » qui n'en est pas un.

### 4. Constater qu'un jeton n'ouvre rien

Remets un jeton d'accès valide, et appelle le corpus :

```
GET {{base_url}}/api/entities/
```

**Attendu :** exactement la même réponse qu'un appel anonyme. Sur la base de
développement actuelle, dont les fiches importées sont encore des brouillons,
cela veut dire `200` avec `count: 0`. Un jeton ne révèle aucun brouillon.

Tente ensuite une écriture, avec le jeton :

```
POST {{base_url}}/api/entities/
```

**Attendu :** `405 Method Not Allowed`. Pas `403`, pas `401` : la méthode
n'existe pas, pour personne. Être authentifié n'ouvre pas l'écriture.

### 5. Renouveler, puis réutiliser

```
POST {{base_url}}/api/auth/token/refresh/
```

Corps JSON, avec le jeton de **renouvellement** :

```json
{"refresh": "eyJhbGciOi..."}
```

Pas d'en-tête `Authorization` ici : le jeton dans le corps *est*
l'identifiant.

**Attendu :** `200`, et un seul champ, `access`. Pas de nouveau `refresh` : la
rotation est désactivée, tu gardes celui que tu as.

Reprends la requête `me` avec ce nouvel accès : **attendu** `200`.

Puis reprends-la avec l'**ancien** accès, celui de l'étape 1 : **attendu**
`200` aussi, s'il n'a pas encore expiré. C'est la limite la plus importante de
cet incrément : renouveler n'invalide pas le jeton précédent. Sans liste de
révocation, rien ne peut annuler un jeton signé avant son expiration. Il n'y a
donc pas de déconnexion : supprimer un jeton dans Postman ne le révoque pas
côté serveur, cela l'efface seulement de chez toi.

Pour la même raison, tu peux rejouer la requête de renouvellement plusieurs
fois avec le même `refresh` : elle marchera chaque fois.

### 6. Voir expirer un jeton (facultatif)

Attends cinq minutes sans rien faire, puis rappelle `me` avec le premier jeton
d'accès. **Attendu :** `401`, `"Given token not valid for any token type"`.
Renouvelle, et tout refonctionne. C'est le cycle de vie normal d'un client
d'API.

## Après la vérification

Après les essais, désactive le compte fictif si tu souhaites le conserver,
ou supprime uniquement celui créé pour l'exercice. Si `is_staff` a été coché
par erreur, décoche-le. Nettoie également les secrets de cet exercice dans
Postman ; ne supprime aucun compte préexistant.

Si tu exportes la collection Postman pour la partager, **relis l'export**
avant : vérifie qu'aucun jeton ni mot de passe n'y figure en clair. Rien de
tout cela n'a à entrer dans le dépôt Git.

## Les réglages, si tu veux les lire

| Quoi | Où |
| --- | --- |
| Durées de vie, rotation, révocation | `config/settings.py`, bloc `SIMPLE_JWT` |
| Ordre des mécanismes d'authentification | `config/settings.py`, `REST_FRAMEWORK` |
| Les trois routes | `accounts/urls.py` |
| Les trois vues | `accounts/views.py` |
| Ce que `me` expose | `accounts/serializers.py` |
| Textes publics du schéma | `accounts/schema.py` |
| Mises en garde pour les clients | `README.md`, section *Authentication* |
