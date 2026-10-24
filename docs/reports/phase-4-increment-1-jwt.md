# Phase 4 — incrément 1 : authentification JWT

Rapport d'intervention. Rédigé le 22 octobre 2026.

## 1. Objectif de l'incrément

Permettre à un utilisateur d'obtenir un couple de jetons, de renouveler son
jeton d'accès, et de lire sa propre identité. Trois routes, aucune écriture sur
le corpus, aucune autorisation nouvelle.

| Méthode | Route | Authentification | Rôle |
| --- | --- | --- | --- |
| `POST` | `/api/auth/token/` | aucune | échanger des identifiants contre une paire de jetons |
| `POST` | `/api/auth/token/refresh/` | aucune | échanger un jeton de renouvellement contre un nouvel accès |
| `GET` | `/api/auth/me/` | jeton d'accès | renvoyer l'identité de l'appelant |

## 2. Dépendance ajoutée

`djangorestframework-simplejwt~=5.5` (version installée : 5.5.1), inscrite dans
`requirements.txt`. Les vues d'obtention et de renouvellement sont celles de la
bibliothèque ; aucun mécanisme de signature, aucune vérification
d'identifiants n'a été réécrit. La revue ajoute uniquement la conversion
de l'exception de compte supprimé au renouvellement en réponse 401 (section 14).

## 3. Réglages

### 3.1 Mécanismes d'authentification

```python
"DEFAULT_AUTHENTICATION_CLASSES": [
    "rest_framework_simplejwt.authentication.JWTAuthentication",
    "rest_framework.authentication.SessionAuthentication",
],
```

JWT en premier, parce que c'est le mécanisme des clients d'API. La session
reste derrière pour l'API navigable de DRF. L'administration Django gère ses
sessions indépendamment des classes d'authentification DRF. Le défaut de
permission reste `IsAuthenticated` : il n'a pas été touché.

### 3.2 Durées de vie

```python
SIMPLE_JWT = {
    "ACCESS_TOKEN_LIFETIME": timedelta(minutes=5),
    "REFRESH_TOKEN_LIFETIME": timedelta(days=1),
    "ROTATE_REFRESH_TOKENS": False,
    "BLACKLIST_AFTER_ROTATION": False,
}
```

Signature HS256 avec `SECRET_KEY`, réglage standard de la bibliothèque. Aucun
secret supplémentaire, aucun rôle métier dans les claims.

### 3.3 Limite assumée : pas de révocation

Ni rotation, ni liste de révocation, ni route de déconnexion. Les conséquences,
énoncées sans les adoucir :

- renouveler **n'invalide pas** l'accès précédent, qui reste valable jusqu'à
  son expiration ;
- un même jeton de renouvellement peut être rejoué indéfiniment pendant sa
  durée de vie ;
- supprimer un jeton côté client ne le révoque pas côté serveur ;
- un jeton compromis reste donc utilisable jusqu'à 5 minutes (accès) ou 1 jour
  (renouvellement) ;
- il n'existe aucune promesse de déconnexion, et aucune n'est sous-entendue.

Deux tests gardent ces comportements au lieu de les laisser à l'état
d'intention : `test_le_renouvellement_n_invalide_pas_l_acces_precedent` et
`test_un_refresh_reste_utilisable_plusieurs_fois`. Ils ne constatent pas un
défaut, ils constatent une décision — si la révocation arrive un jour, ils
échoueront, et c'est exactement ce qu'on veut d'eux.

## 4. Code ajouté

| Fichier | Contenu |
| --- | --- |
| `accounts/urls.py` | les trois routes, montées sous `api/auth/` |
| `accounts/views.py` | deux sous-classes minimales de Simple JWT, plus `CurrentUserView` |
| `accounts/serializers.py` | `CurrentUserSerializer` — `id` et `username`, rien d'autre |
| `accounts/schema.py` | annotations OpenAPI publiques, en anglais |
| `config/apps.py` | `TypingPatchConfig`, voir § 7 |

`config/urls.py` monte `api/auth/` **avant** `api/`, et `accounts` était déjà
dans `INSTALLED_APPS`.

### 4.1 Ce que `me` expose, et ce qu'elle n'expose pas

`CurrentUserSerializer` déclare `fields = ["id", "username"]`. Ni courriel, ni
empreinte de mot de passe, ni `is_staff`, ni `is_superuser`, ni permissions, ni
appartenance à un groupe, ni `last_login`. La route répond « qui suis-je », pas
« que puis-je faire ».

`get_object()` renvoie `self.request.user` : il n'y a pas de recherche par
identifiant, donc la vue ne peut structurellement pas renvoyer un autre compte
que l'appelant.

`authentication_classes = [JWTAuthentication]` restreint volontairement cette
vue, alors que le projet accepte aussi la session. Raison : la vue existe pour
vérifier qu'un *jeton* fonctionne. Une session d'administration ouverte la
ferait répondre `200` sans qu'aucun JWT soit valide, ce qui rendrait la
vérification trompeuse. Un test le garde
(`test_me_refuse_une_session_django`).

### 4.2 Ouverture des deux routes de jetons

Les routes de jetons ne redéclarent pas `AllowAny`. Ce n'est pas un oubli :
`TokenViewBase`, de Simple JWT, pose déjà `permission_classes = ()`, ce qui
neutralise le défaut fermé du projet. Redéclarer `[AllowAny]` changerait le
type d'un attribut hérité (`tuple[()]`), ce que mypy refuse à juste titre.

Plutôt qu'un `type: ignore` pour une ligne purement décorative, deux tests
gardent le comportement effectif : un corps vide sur ces routes doit répondre
`400` — la requête est atteinte et validée — et non `401` ou `403`, qui
signaleraient un blocage par la permission.

## 5. Schéma OpenAPI

### 5.1 Schéma de sécurité Bearer

Seule l'opération `auth_me` déclare `security: [{jwtAuth: []}]`. Il n'y a
aucune exigence globale : une déclaration à la racine ferait croire à un client
que toute lecture est protégée, ce qui serait faux, et ferait croire qu'obtenir
un jeton exige déjà un jeton, ce qui serait absurde. Les deux routes de jetons
portent `auth=[]`.

Swagger UI peut afficher un bouton **Authorize** global à l'interface ;
seule l'opération `me` déclare une exigence de sécurité dans le schéma.

### 5.2 Réponses `200` décrites explicitement

Les serializers de Simple JWT ne déclarent que les champs d'**entrée** : les
réponses de succès se généraient en « No response body », ce qui ne disait pas
au client où trouver ses jetons. Deux serializers de documentation ont été
ajoutés dans `accounts/schema.py` — `TokenPairSerializer` (`access`,
`refresh`) et `AccessTokenSerializer` (`access` seul). Ils ne valident ni ne
produisent rien ; ils décrivent.

Le second traduit la désactivation de la rotation : le renouvellement ne
renvoie pas de nouveau `refresh`, et le schéma dit la même chose que l'API.

### 5.3 Jetons d'exemple tronqués

Les exemples utilisent `"eyJhbGciOi...<truncated access token>"`. Un jeton
d'exemple complet, même expiré, invite à le coller tel quel dans un client.

### 5.4 Correction de la description globale

La description annonçait « Only `GET` is available », désormais faux. Elle
distingue maintenant le contenu mythologique — en lecture seule, écritures
refusées en `405` — des routes d'authentification, qui sont des `POST` parce
qu'elles transportent des identifiants dans un corps de requête, et qui ne
créent aucun contenu.

Trois sections ont été ajoutées : l'usage des deux jetons, le fait que
l'authentification **n'est pas** requise pour lire et n'accorde aucun accès
supplémentaire, et l'absence de révocation.

**Le refus d'écriture sur les entités n'a pas été affaibli.** Le test qui
l'imposait a été scindé : `test_content_paths_only_declare_get` conserve la
règle sur tous les chemins hors `/api/auth/`, avec un garde-fou qui échoue si
le préfixe est mal écrit et vide la boucle ;
`test_authentication_paths_only_declare_post_or_get` fixe explicitement les
méthodes des trois routes d'authentification. Aucun chemin n'échappe
désormais à l'un des deux.

### 5.5 Composant utilisateur publié, volontairement

`test_no_user_component_is_published` affirmait qu'aucun composant ne décrivait
de compte. C'est devenu faux : `CurrentUser` est publié à dessein. Le test a
été remplacé par deux tests plus précis :

- `test_no_account_data_leaks_into_content_components` : les composants du
  corpus — entités, profils, référentiels, sources, relations — ne mentionnent
  toujours ni `password`, ni `email`, ni `username`. Les composants
  d'authentification sont exclus nommément, et un garde-fou échoue si une faute
  de nom vidait la comparaison ;
- `test_the_identity_component_exposes_only_id_and_username` : `CurrentUser`
  déclare exactement `id` et `username`. Le contrôle porte sur les propriétés
  et non sur le texte, car la description mentionne le mot « password » — pour
  dire qu'il n'est **pas** exposé.

## 6. Tests

**État livré par Claude : 461 cas passants, contre 400 à la clôture de la
phase 3** : 61 ajoutés. La collecte de Codex confirme les 461 cas avant
corrections ; les résultats de revue sont distingués en section 14.

| Fichier | Cas | Portée |
| --- | --- | --- |
| `tests/test_auth_jwt.py` | 39 (31 fonctions, dont 3 paramétrées) | les trois routes |
| `tests/test_auth_does_not_change_reads.py` | 14 (8 fonctions, dont 2 paramétrées) | non-régressions du contrat de lecture |
| `tests/test_settings.py` | +2 (2 → 4) | chaîne d'authentification, durées de jetons |
| `mythology/tests/test_openapi.py` | +6 (53 → 59) | schéma de sécurité, réponses, description |

### 6.1 Comptes synthétiques uniquement

Tous les comptes sont créés dans la base de test et détruits avec elle. Aucun
identifiant réel, aucun mot de passe personnel n'apparaît dans un fichier de
test. Le mot de passe utilisé est une chaîne manifestement inventée, et les
courriels utilisent le domaine réservé `example.invalid`.

### 6.2 Expirations fabriquées, jamais attendues

Les jetons expirés sont obtenus en reculant l'expiration dans le passé
(`token.set_exp(from_time=...)`), puis en signant. Le jeton est alors valide en
tout point sauf la date. Aucun test ne dort : un test qui attend cinq minutes
est un test qu'on finit par désactiver.

### 6.3 Ce qui est couvert

**Obtention.** Identifiants valides ; mot de passe erroné ; compte inexistant ;
indistinguabilité des deux précédents ; trois formes de champ manquant ; compte
désactivé ; identifiant du compte porté par le jeton ; absence de donnée de
compte dans la réponse ; refus de `GET` ; ouverture effective de la route.

**Identité.** Identité correcte ; absence de jeton ; session Django refusée ;
quatre formes d'en-tête invalide ; jeton expiré ; jeton signé avec une autre
clef ; jeton de renouvellement refusé comme accès ; compte désactivé après
émission ; compte supprimé après émission ; absence de courriel, d'empreinte,
d'indicateur et de permission dans la réponse ; refus de `POST`.

**Renouvellement.** Renouvellement valide ; accès renouvelé accepté par `me` ;
absence de nouveau `refresh` ; rejouabilité du `refresh` ; accès précédent
toujours valide ; trois formes de corps invalide ; `refresh` expiré ; jeton
d'accès refusé comme `refresh` ; distinction structurelle des deux types ;
refus de `GET` ; ouverture effective de la route.

**Non-régressions.** Lecture de la liste, du détail, de la santé et des trois
routes documentaires sans jeton ; un jeton valide ne révèle aucun brouillon ;
un jeton valide voit exactement la même liste qu'un anonyme ; les quatre
méthodes d'écriture refusées en `405` sans jeton **et** avec jeton.

### 6.4 Un test qui documente un piège

`test_un_en_tete_bearer_invalide_fait_echouer_meme_une_lecture_publique`
constate un comportement surprenant mais correct : DRF authentifie avant de
vérifier les permissions, donc un en-tête `Authorization` présent mais invalide
produit `401` sur une route pourtant ouverte à tous. Ce n'est pas une panne de
l'API — c'est l'en-tête qu'il faut retirer. Le piège est signalé dans le README
et dans le guide Postman, parce qu'il est la cause la plus plausible d'un
futur « l'API est cassée » qui n'en serait pas un.

### 6.5 Deux ajustements imposés par la bibliothèque

- Simple JWT 5.5 sérialise l'identifiant du compte **en chaîne** dans la
  charge du jeton, quel que soit le type de la clef primaire. La comparaison
  porte donc sur `str(account.pk)`. Noté parce que c'est un piège exact :
  `token["user_id"] == account.pk` échoue silencieusement sur un `'26' == 26`.
- Pour prouver que la signature est vérifiée, le jeton est forgé avec PyJWT à
  partir de la charge d'un jeton authentique et d'une autre clef. Modifier
  `settings.SIMPLE_JWT` en cours de test ne suffisait pas : la vérification
  retombait sur `SECRET_KEY` et le jeton restait accepté. Le test aurait donc
  passé pour une mauvaise raison.

## 7. Incident de démarrage résolu : `AppRegistryNotReady`

Le correctif de typage `django_stubs_ext.monkeypatch()` est une dépendance
d'exécution du projet : sans lui, `ModelAdmin[Entity]`,
`ModelSerializer[Entity]` et `ReadOnlyModelViewSet[Entity]` lèvent
`TypeError: type 'ModelAdmin' is not subscriptable` à l'évaluation des classes
de base.

Son emplacement a maintenant cassé le projet **deux fois, en sens opposés** :

1. **En tête de `settings.py`** (incident de la phase 3) : l'import de
   `rest_framework.generics` faisait lire `REST_FRAMEWORK` avant sa définition,
   et DRF mémorisait un dictionnaire vide. `DEFAULT_PERMISSION_CLASSES`
   retombait silencieusement sur le défaut ouvert `AllowAny`.
2. **En fin de `settings.py`** (cet incrément) : le même import résout
   désormais `JWTAuthentication`, qui importe `django.contrib.auth.models`
   avant que le registre d'applications soit peuplé — `AppRegistryNotReady`.

**Correction retenue.** Le correctif vit dans `config/apps.py`, appliqué par le
`ready()` de `TypingPatchConfig`, placée **en premier** dans `INSTALLED_APPS`.
Cet emplacement résout les deux cas : `ready()` s'exécute après l'import de
tous les modèles — donc le registre est prêt — et avant que l'autodiscover de
`django.contrib.admin` importe `mythology/admin.py` — donc avant toute
évaluation de classe générique. C'est le moment le plus tardif qui soit encore
assez tôt.

`settings.py` ne contient plus aucun import de DRF ; un commentaire y
documente les deux modes de défaillance, pour qu'ils ne soient pas reproduits
une troisième fois.

**Vérification.** Un test garde désormais les valeurs effectivement appliquées
(`test_drf_defaults_are_loaded_before_view_classes`) et un second vérifie que
`REST_FRAMEWORK` a bien été lu, et non ignoré au profit des défauts
(`test_les_reglages_drf_ne_sont_pas_le_repli_vide`).

## 8. Un défaut de `extend_schema` traversé en route

Première rédaction de `accounts/urls.py` : `extend_schema(...)` appliqué au
résultat de `TokenObtainPairView.as_view(...)`. L'import échouait avec
`AttributeError: type object 'TokenObtainPairView' has no attribute 'get'` —
le décorateur itère sur toutes les méthodes HTTP, alors que la vue ne définit
que `post`.

Corrigé en décorant les **classes** avec
`extend_schema_view(post=extend_schema(...))`, ce qui a par ailleurs imposé les
deux sous-classes du § 4. Pour `CurrentUserView`, `@extend_schema` posé sur la
classe produisait l'erreur « using `@extend_schema` on viewset class … with
parameters `operation_id` will most likely result in a broken schema » ; la
forme `extend_schema_view(get=...)` est la bonne.

## 9. Documentation

| Document | Langue | Modification |
| --- | --- | --- |
| `README.md` | anglais | section *Authentication* complète : les trois routes, entrées, réponses, erreurs, et six mises en garde |
| `README.md` | anglais | *Not available yet* corrigée ; usage du bouton **Authorize** de Swagger ; schéma public y compris pour les routes de jetons |
| `CLAUDE.md` | français | JWT retiré du hors-périmètre, remplacé par ce qui reste effectivement hors périmètre |
| `docs/guide-postman-jwt.md` | français | guide de vérification manuelle, nouveau |

### 9.1 Mises en garde inscrites au README

Absence de révocation ; HTTPS obligatoire hors `localhost`, les jetons étant
des identifiants au porteur ; absence de limitation de débit sur la route de
jetons, donc aucune protection contre la force brute ; rotation de
`SECRET_KEY` invalidant tous les jetons en circulation, et recommandation
d'une clef d'au moins 32 octets ; le piège de l'en-tête invalide du § 6.4 ;
absence d'inscription et de réinitialisation de mot de passe.

Sur la longueur de clef : PyJWT signale une clé locale de 28 octets, sous
les 32 octets recommandés pour HS256. L'avertissement n'est pas masqué et
ne doit pas être banalisé parce que l'environnement est local. Aucun secret
n'est modifié ni recopié pendant la revue ; l'auteur devra remplacer sa clé
locale par une valeur aléatoire suffisamment forte, sans la transmettre.

### 9.2 Le guide Postman

Guide interne, en français, qui suit l'ordre demandé : obtenir les jetons,
appeler `me` sans puis avec l'accès, essayer un jeton invalide, constater qu'un
jeton n'ouvre rien, renouveler et réutiliser, voir expirer.

Il explique la différence entre jeton d'accès et jeton de renouvellement, et
celle entre authentification et autorisation. Il explique comment créer un
compte fictif **non** `is_staff` dans l'administration, avec un mot de passe au
choix du lecteur. Il recommande une variable `base_url`, le **Local Vault** de
Postman pour mot de passe et jetons. Après revue, il ne suppose plus que toute
variable est automatiquement synchronisée : il demande explicitement de ne
pas partager ni exporter les valeurs secrètes.

Il distingue nettement ce qui a été exécuté — 53 tests automatiques, sur une
base de test créée et détruite à chaque exécution — de ce qui reste à faire
ensemble : aucune collection Postman n'existe dans le dépôt, aucun compte n'a
été créé en base de développement, et aucune des manipulations décrites n'a
été effectuée.

## 10. Contrôles exécutés

Tous lancés depuis `C:\Users\heric\dev\afrimyth-api`, environnement `.venv`.

| Contrôle | Résultat |
| --- | --- |
| `python manage.py check` | `System check identified no issues (0 silenced).` |
| `python manage.py makemigrations --check --dry-run` | `No changes detected` |
| `python manage.py spectacular --validate --fail-on-warn` | code de sortie `0`, aucun avertissement |
| `python -m pytest` | **461 passed** |
| `python -m ruff check .` | `All checks passed!` |
| `python -m ruff format --check .` | `50 files already formatted` |
| `python -m mypy .` | `Success: no issues found in 50 source files` |

Aucune migration n'a été produite : l'incrément n'ajoute aucun champ, aucun
modèle. Le modèle `User` est inchangé.

## 11. Ce que cet incrément ne fait pas

- **Aucune autorisation.** Un jeton valide ne débloque rien : la lecture reste
  anonyme, les brouillons restent invisibles, et les quatre méthodes d'écriture
  restent refusées en `405`, avec ou sans jeton. Les autorisations viendront
  des groupes Django vérifiés côté serveur, jamais de ce que le client lit dans
  son jeton.
- **Aucune révocation, aucune déconnexion, aucune rotation** — voir § 3.3.
- **Aucune inscription en libre-service, aucune réinitialisation de mot de
  passe.** Les comptes se créent par l'administration.
- **Aucune limitation de débit.** À ajouter avant tout déploiement public.
- **Aucun contenu publié.** Les fiches pilotes de la base de développement
  sont toujours des brouillons : la collection renvoie légitimement `count: 0`.

## 12. État Git

Rien n'a été indexé, commité ni poussé. La roadmap n'a pas été cochée.

```
## main...origin/main
 M CLAUDE.md
 M README.md
 M config/settings.py
 M config/urls.py
 M mythology/tests/test_openapi.py
 M requirements.txt
 M tests/test_settings.py
?? accounts/schema.py
?? accounts/serializers.py
?? accounts/urls.py
?? accounts/views.py
?? config/apps.py
?? docs/guide-postman-jwt.md
?? docs/reports/phase-4-increment-1-jwt.md
?? tests/test_auth_does_not_change_reads.py
?? tests/test_auth_jwt.py
```

Aucun secret, aucun fichier `.env`, aucun jeton réel n'apparaît dans ces
fichiers. `_audit/` et `.claude/` n'ont pas été touchés et ne doivent pas être
indexés.

## 13. Contrat déjà fixé pour cet incrément

La restriction de `CurrentUserView` à JWT seule répond explicitement au prompt
validé. Elle est conservée, avec son test : une session d'administration ne
doit pas masquer l'absence de jeton pendant nos exercices. Ce n'est pas une
nouvelle décision à rouvrir avant la revue pédagogique.

## 14. Revue et corrections de Codex — 22 octobre 2026

### Sobriété et proportionnalité

Les vues de connexion réutilisent Simple JWT, `me` renvoie l'appelant, et
aucun moteur de rôle, signature maison ou vérification générique n'est ajouté.
Le module `config/apps.py` traite un ordre d'initialisation réel ; ce n'est
pas une couche métier spéculative. Le volume vient surtout des annotations,
commentaires et tests, pas d'un empilement de validations d'exécution.

Deux boucles d'assertions redondantes sont supprimées : après vérification
exacte de l'ensemble `{id, username}`, réinterdire chaque autre clé n'ajoute
pas de garantie. Les tests de signature, expiration et permissions restent.
La consigne de sobriété est enregistrée dans les instructions des deux dépôts.

### Défaut reproduit et correction localisée

Un test temporaire isolé crée un compte synthétique, émet son refresh, supprime
le compte puis appelle le renouvellement. Résultat avant correction : **500**,
exception `User.DoesNotExist` dans Simple JWT 5.5.1, au lieu d'un refus 401.
Aucun compte de développement n'est utilisé ou modifié pour cette reproduction.

Évaluation : correction de validation circonscrite, sans changement de matrice,
de signature ou de décision métier. `accounts.serializers.TokenRefreshSerializer`
délègue à la bibliothèque et convertit uniquement cette exception en refus
d'authentification. Il ne recherche pas le compte une seconde fois et ne
capture pas les exceptions générales. La vue de renouvellement l'utilise.
Deux cas de régression couvrent les comptes supprimé et désactivé ; les codes
400/401 du test de corps invalide sont désormais vérifiés exactement.

### Corrections complémentaires

- Le schéma d'erreur décrit maintenant les champs standard `code` et
  `messages` facultatifs en plus de `detail` ; aucune réponse d'erreur n'est
  normalisée par du code maison.
- Les nouvelles docstrings françaises des tests JWT sont traduites en anglais
  et raccourcies. Pas de traduction générale des fichiers historiques.
- Le guide ne propose plus de coller un jeton utilisable sur un site externe
  ni de le stocker dans un fichier texte. Local Vault, mot de passe fort et
  unique, prudence sur les exports et nettoyage ciblé sont explicités.
- README final corrigé : les POST d'authentification existent, seul le corpus
  reste en lecture seule. Le choix JWT seul sur `me` n'est pas rouvert.
- Comptage corrigé : 400 cas à la clôture précédente, 461 livrés, soit 61
  nouveaux (et non 62). Après les deux cas de revue, le total est 463.

### Vérifications exécutées

| Contrôle | Résultat de Codex |
|---|---|
| Suite complète après correctif | **463 passed, 53 warnings in 114.32s** |
| Après simplification de deux tests et clé fictive de mauvaise signature renforcée | **3 passed, 4 warnings in 8.09s** |
| Ruff global, format, mypy global | propres ; 50 fichiers formatés/typés |
| Après dernières simplifications de tests | Ruff et format propres sur les deux fichiers affectés |
| `manage.py check` | aucune erreur |
| `makemigrations --check --dry-run` | aucune modification |
| Schéma `--validate --fail-on-warn`, sortie temporaire | code 0 |

Les avertissements de clé courte sont réels et non ignorés. La clé fictive
du test de mauvaise signature est allongée ; ceux de la configuration locale
restent à traiter par l'auteur. Aucun secret ni corpus de développement n'est
modifié. Les états Git de la section 12 décrivent la remise initiale, avant
ces corrections ; rien n'est indexé, committé ou poussé pendant la revue.

La revue technique est favorable après ces corrections. Restent l'explication
du code, les exercices Postman et la validation de l'auteur avant clôture.

## 15. Validation pratique et clôture — 24 octobre 2026

Après explication de la configuration et de la différence accès/refresh,
l'auteur a choisi de conserver les cinq minutes pour les premiers exercices.
Une durée plus longue en développement pourra être décidée ultérieurement ;
aucune modification des durées n'est faite pendant cette clôture.

L'auteur confirme avoir remplacé la clé locale dans `.env` et redémarré le
serveur. Sa valeur n'a été ni demandée ni lue par Codex. Les avertissements
des tests de la section 14 décrivent l'état antérieur à ce remplacement ;
aucune nouvelle mesure de la clé n'est prétendue ici.

Parcours Postman confirmé par l'auteur et ses captures :

- requête de santé en 200, sauvegardée dans une collection dédiée ;
- compte fictif actif sans privilège d'administration créé par l'auteur ;
- mot de passe placé dans le Local Vault, utilisé par référence dans le POST ;
- obtention des champs `access` et `refresh` ;
- refus 401 sur `me`, avec le message explicite `Token is expired` ;
- renouvellement, remplacement du secret d'accès dans le coffre puis
  `GET /api/auth/me/` en **200**, avec uniquement `id` et `username` du compte
  d'exercice, visibles sur la capture finale.

Le 200 du renouvellement a été confirmé par l'auteur ; la capture finale
montre directement le 200 de l'identité après ce renouvellement. Les autres
cas négatifs (sans jeton, mauvaise signature, compte supprimé, etc.) restent
prouvés par les tests, pas revendiqués comme tous rejoués manuellement.

Le compte d'exercice reste disponible pour la suite : Codex ne supprime
aucun compte ni secret local. Aucun JWT ou mot de passe n'est recopié dans
les fichiers suivis ; aucun brouillon n'est publié.

L'incrément 1 est validé et la roadmap est cochée pour JWT. README et guide
sont actualisés. Les tests et contrôles acquis sont réutilisés : cette
clôture ne change que la documentation. Commits et pushes normaux des deux
dépôts sous l'identité de l'auteur, sans trailer d'assistant. Les sections
précédentes conservent l'historique de remise et de revue.

Suite : incrément 2, groupes et lecture privée. Aucun CRUD, workflow ou rôle
n'est ajouté implicitement par la clôture de l'authentification.
