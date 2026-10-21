# Rapport — Phase 3, incrément 3 : OpenAPI, Swagger et ReDoc

- **Date :** 21 octobre 2026
- **Dépôt :** `afrimyth-api`
- **Branche :** `main`
- **Statut :** incrément et phase 3 validés après revue du code et essais
  navigateur ; clôture documentaire et publication Git

## 1. Objectif et périmètre

Publier le contrat de lecture sous forme de schéma OpenAPI, et l'exposer par
deux interfaces qui consomment ce **même** schéma : Swagger UI pour explorer
et essayer, ReDoc pour lire.

Routes, formats de réponse, pagination, filtres, visibilité et refus
d'écriture sont inchangés. Aucun modèle, aucune migration, aucun CRUD, aucun
JWT, aucun nouveau filtre, aucun import, aucun changement de statut en base de
développement.

La phase 3 **n'est pas déclarée achevée** : elle reste en attente de la revue
et de l'essai navigateur. La roadmap n'a pas été cochée, rien n'a été
committé ni poussé.

## 2. Dépendance ajoutée

| Paquet | Contrainte | Version installée |
|---|---|---|
| `drf-spectacular` | `~=0.30` | 0.30.0 |

Ajouté à `requirements.txt`, donc aux dépendances d'**exécution** : les routes
`/api/schema/`, `/api/docs/` et `/api/redoc/` en ont besoin en production, pas
seulement en développement.

Dépendances transitives tirées par l'installation : `PyYAML`, `jsonschema`,
`inflection`, `uritemplate`, `attrs`, `referencing`, `rpds-py`,
`jsonschema-specifications`. Compatible avec Django 5.2.18 et DRF 3.16.1.

## 3. Défauts trouvés et corrigés

### Défaut de sécurité latent : la configuration DRF n'était pas lue

C'est le point le plus important de cet incrément, et il n'était pas prévu.

En branchant `DEFAULT_SCHEMA_CLASS`, j'ai constaté que le réglage restait
sans effet. Diagnostic :

```
api_settings._user_settings            : {}
api_settings.DEFAULT_PERMISSION_CLASSES: [AllowAny]
api_settings.DEFAULT_SCHEMA_CLASS      : rest_framework.schemas.openapi.AutoSchema
```

**DRF n'avait jamais lu notre dictionnaire `REST_FRAMEWORK`.** La cause est le
correctif de typage ajouté en phase 1, placé en **tête** de
`config/settings.py` :

```python
from rest_framework.generics import GenericAPIView   # en tête du fichier
django_stubs_ext.monkeypatch(extra_classes=[BaseSerializer, GenericAPIView])
```

Importer `rest_framework.generics` évalue `api_settings.DEFAULT_FILTER_BACKENDS`
dans le corps de classe de `GenericAPIView`. Cette évaluation déclenche la
lecture de `settings.REST_FRAMEWORK` — **alors que `settings.py` est encore en
cours d'exécution** et que le dictionnaire n'est pas encore défini. DRF
mémorisait donc `{}` définitivement.

Conséquences réelles, depuis la phase 1 :

| Réglage | Valeur voulue | Valeur effective avant correctif |
|---|---|---|
| `DEFAULT_PERMISSION_CLASSES` | `IsAuthenticated` | **`AllowAny`** |
| `DEFAULT_AUTHENTICATION_CLASSES` | `SessionAuthentication` seule | `SessionAuthentication` + `BasicAuthentication` |
| `DEFAULT_SCHEMA_CLASS` | spectacular | `AutoSchema` de DRF |

Le projet croyait avoir un **défaut fermé** ; il avait en réalité un défaut
ouvert. Les vues actuelles sont explicitement publiques et aucune vue privée
n'existe encore : la revue ne relève donc pas de route privée exposée par ce
défaut. Elle ne constitue pas une preuve historique d'absence de fuite.
Une future vue de phase 4 s'appuyant sur le défaut aurait pu être ouverte
sans le correctif.

**Correctif** : l'appel `monkeypatch` et ses deux imports sont déplacés en
**fin** de `settings.py`, après la définition de `REST_FRAMEWORK`, avec un
commentaire expliquant pourquoi ils doivent y rester. Vérifié après coup :

```
api_settings._user_settings            : {'DEFAULT_AUTHENTICATION_CLASSES': [...],
                                          'DEFAULT_PERMISSION_CLASSES': [...],
                                          'DEFAULT_SCHEMA_CLASS': '...'}
DEFAULT_PERMISSION_CLASSES             : [IsAuthenticated]
DEFAULT_SCHEMA_CLASS                   : drf_spectacular.openapi.AutoSchema
```

### Fuite de prose française dans le schéma public

drf-spectacular transforme la docstring de chaque serializer en `description`
du composant OpenAPI correspondant. **Douze composants publiaient donc une
description en français** — `Country`, `EntityDetail`, `EntityRelation`,
`Source`, les trois profils, etc. — et les docstrings des deux
`SerializerMethodField` apparaissaient telles quelles dans les descriptions de
champ.

C'était contraire à l'ADR 0003, et le texte interne n'était pas rédigé pour un
consommateur d'API.

**Correctif** : les docstrings de `mythology/serializers.py` sont réécrites en
anglais, et adressées à un client plutôt qu'à un mainteneur. Le raisonnement
interne — pourquoi `allow_null`, pourquoi le filtrage redondant — est déplacé
en commentaires français, qui ne sortent pas du code. Le prompt autorisait
cette traduction ciblée : ces docstrings « alimentent cette documentation ».

Le contrôle ponctuel du schéma généré n'a pas relevé de description française
restante. Aucun test linguistique dédié n'est présent dans la suite livrée ;
l'absence de caractères accentués ne prouverait de toute façon pas qu'un
texte est anglais.

### Un troisième défaut, mineur, trouvé par un test

`EntityRelation.to_entity` peut valoir `null` — c'est tout l'intérêt d'un lien
non résolu — mais n'était pas déclaré nullable. Corrigé par
`allow_null=True`, ce qui ne change pas la charge utile.

## 4. Fichiers touchés

**Créés**

- `mythology/schema.py` — annotations, paramètres, réponses d'erreur et
  exemples
- `mythology/tests/test_openapi.py` — 52 cas
- `docs/reports/phase-3-increment-3-openapi.md` — ce rapport

**Modifiés**

- `config/settings.py` — `drf_spectacular` installé, `DEFAULT_SCHEMA_CLASS`,
  `SPECTACULAR_SETTINGS`, et **déplacement du correctif de typage en fin de
  fichier**
- `config/urls.py` — les trois routes documentaires, chacune en `AllowAny`
- `config/views.py` — `HealthSerializer` et annotation de `HealthView`
- `mythology/views.py` — `@extend_schema_view` sur la liste et le détail
- `mythology/serializers.py` — docstrings publiques en anglais, `allow_null`
  sur les sept références nullables, typage des deux
  `SerializerMethodField`
- `requirements.txt` — `drf-spectacular~=0.30`
- `README.md` — section « API documentation »

Aucun modèle, aucune migration : `makemigrations --check` ne détecte rien.
**Aucun schéma n'est committé** : la route et la commande le produisent à
partir du code.

## 5. Routes documentaires

| Route | Contenu |
|---|---|
| `/api/schema/` | schéma OpenAPI 3, servi en YAML |
| `/api/docs/` | Swagger UI, branché sur `/api/schema/` |
| `/api/redoc/` | ReDoc, branché sur le même schéma |

Les trois sont consultables **sans connexion**. `AllowAny` est posé vue par
vue, et non en changeant le défaut du projet : le reste du projet conserve
`IsAuthenticated` comme défaut — désormais réellement appliqué, voir
section 3.

`SERVE_INCLUDE_SCHEMA=False` empêche les routes documentaires de se décrire
elles-mêmes dans le contrat ; un test le vérifie.

## 6. Annotations nécessaires, et pourquoi

L'introspection seule ne suffisait pas sur cinq points. Chaque annotation
compense une information que le code ne porte pas de façon lisible par le
générateur.

| Annotation | Raison |
|---|---|
| `LIST_PARAMETERS` (5 paramètres) | `entity_type`, `country` et `cultural_area` sont appliqués à la main dans `get_queryset()` : le générateur ne peut pas les deviner. `page` et `search` sont détectés, mais avec une description pauvre. |
| `parameters=[]` sur le détail | garantit qu'aucun paramètre de collection ne se glisse dans la signature du détail |
| `responses={400: ..., 404: ...}` | les erreurs sont levées à l'exécution ; rien dans le code ne les déclare |
| `@extend_schema_field` ×2 | un `SerializerMethodField` est typé `object` sans indication ; il pointe désormais sur `EntityReference` et `EntityRelation` |
| `allow_null=True` ×8 | rend le schéma fidèle aux `null` réellement renvoyés, sans toucher au JSON |
| `auth=[]` | sans cela, les opérations annonçaient `cookieAuth`, laissant croire qu'une authentification est possible ou attendue |
| `HealthSerializer` + `@extend_schema` | `HealthView` est une `APIView` sans serializer : le générateur échouait avec « unable to guess serializer » |

Aucune seconde définition des modèles n'a été écrite : l'enveloppe de
pagination, les composants d'entité et les énumérations restent entièrement
générés par introspection.

### Pourquoi `mythology/schema.py`

Les descriptions publiques font plusieurs paragraphes chacune. Les laisser
dans `views.py` aurait noyé une quarantaine de lignes de logique sous trois
cents lignes de prose. Le module ne contient **aucun comportement** : des
constantes, deux serializers d'erreur et des exemples. Ce n'est pas une couche
générique.

## 7. Ce que le schéma décrit

Vérifié par inspection du schéma généré, et figé par les tests.

**Chemins et méthodes** — trois chemins, `get` uniquement sur chacun. Aucune
opération d'écriture n'est déclarée ; leur refus en `405` est documenté dans
les descriptions et le README.

**Liste** — enveloppe `count` / `next` / `previous` / `results`, items à cinq
champs, taille fixe de 20. Cinq paramètres de requête, sans doublon, dont
`entity_type` avec ses trois valeurs en énumération. Réponses 200, 400, 404.

**Détail** — paramètre de chemin `slug`, `id` en `string` / `format: uuid`,
profils et référentiels imbriqués, sources et relations. Réponses 200 et 404.

**Nullabilité** — les sept clés qui valent réellement `null` sont déclarées
`nullable` : `primary_country`, `primary_ethnicity`, `primary_cultural_area`,
`variant_of`, et les trois profils. Plus `to_entity` dans une relation.

**Messages d'erreur** — les exemples de 400 et de 404 sont ceux que l'API
renvoie vraiment. Trois tests le prouvent en comparant l'exemple documenté à
la réponse réelle, et non en les supposant identiques.

**Accès anonyme** — aucun `security` global, aucun `security` par opération.
Un test le vérifie.

**Confidentialité** — aucun des huit champs de plateforme n'apparaît dans un
composant publié, et aucune mention de `password`, `email` ou `username`.
Deux tests le contrôlent.

**Visibilité et brouillons** — la description globale énonce la règle « publié
**et** non supprimé », le masquage des références imbriquées, le fait qu'une
collection vide est le comportement attendu tant que rien n'est publié, et une
réserve éditoriale sur l'exactitude du corpus importé.

**Génération sans données** — un test s'exécute sur une base vide et vérifie
que le schéma est complet : la génération repose sur l'introspection, jamais
sur les données ni sur des paramètres de requête.

Les avertissements du générateur ne sont **pas** masqués globalement : le seul
réel — `HealthView` — a été corrigé, et
`spectacular --validate --fail-on-warn` sort en 0.

## 8. Exemples

Trois jeux d'exemples, tous **synthétiques** et étiquetés comme tels :

- un item de collection ;
- un détail complet avec profil de divinité, une relation résolue, une
  relation non résolue et `variant_of` à `null` ;
- deux corps d'erreur 400 et un corps 404.

Ils sont écrits à la main, ne sont **jamais lus dans la base**, et leurs
libellés portent « synthetic » ou « invented » — un test l'impose. Le domaine
`example.invalid` est utilisé pour les URL, et aucun corpus de démonstration
n'a été ajouté au dépôt.

Deux tests comparent le jeu de clés des exemples à celui des serializers : un
exemple qui dériverait du contrat fait échouer la suite.

### Limite de l'exemple de liste

Quand une vue est paginée, drf-spectacular insère l'exemple **dans**
`results` et complète l'enveloppe avec ses propres valeurs génériques —
`count: 123`, liens `api.example.org`. Deux conséquences :

- l'exemple de liste ne porte qu'**un** item, car fournir une liste produisait
  `results: [[…]]`, imbriqué deux fois ;
- l'exemple de **collection vide** n'est pas exprimable sous forme d'exemple.
  Il est documenté dans la description de l'opération, avec son JSON exact.

L'alternative aurait été de redéfinir à la main un serializer d'enveloppe pour
reprendre la main sur les exemples. Je l'ai écartée : elle dupliquerait une
définition que le générateur produit correctement, au seul bénéfice de
l'affichage d'un exemple.

## 9. Tests

**398 cas exécutés**, dont 52 ajoutés par cet incrément.

| Fichier | Cas |
|---|---|
| `mythology/tests/test_navigation.py` | 60 |
| `mythology/tests/test_openapi.py` | 52 |
| `mythology/tests/test_pilot_import.py` | 52 |
| `mythology/tests/test_api.py` | 50 |
| `mythology/tests/test_services.py` | 34 |
| `mythology/tests/test_relations.py` | 31 |
| `mythology/tests/test_reference.py` | 28 |
| `mythology/tests/test_sources.py` | 25 |
| `mythology/tests/test_editorial_fields.py` | 22 |
| `mythology/tests/test_public_visibility.py` | 22 |
| `mythology/tests/test_profiles.py` | 11 |
| `mythology/tests/test_models.py` | 7 |
| `tests/` (socle) | 4 |

`test_openapi.py` vérifie ce que le schéma **déclare**, et ne redouble pas les
suites fonctionnelles : aucune seconde suite de visibilité n'a été créée.

Couverture : disponibilité anonyme et type de contenu, schéma analysable,
génération sur base vide, méthodes déclarées, exclusion des routes
documentaires, absence d'authentification annoncée, les cinq paramètres sans
doublon, énumération des types, portée documentée de chaque paramètre, détail
limité au slug, règles de combinaison, réponses déclarées, concordance des
messages 400 et 404 avec la réalité, enveloppe de pagination, items à cinq
champs, santé non paginée, `id` en UUID, nullabilité, collections en tableaux,
typage des deux méthodes, non-récursivité des références, deux formes de
cible, absence des champs internes, absence de composant utilisateur,
étiquetage des exemples, concordance des exemples avec les serializers,
réserves de la description globale.

### Ce que les tests ne prouvent pas

Un `200` sur `/api/docs/` ou `/api/redoc/` établit que Django sert la page
HTML et qu'elle référence bien `/api/schema/`. **Il ne prouve pas** que le
JavaScript se charge, que le schéma est récupéré, ni que la page s'affiche
correctement — a fortiori parce que les ressources viennent d'un CDN.

À vérifier au navigateur, et c'est l'essai qui reste à faire :

1. `/api/docs/` affiche bien les trois opérations, leurs paramètres et leurs
   exemples ;
2. **Try it out** sur la collection renvoie `200` avec `count: 0` ;
3. **Try it out** sur le détail avec un slug quelconque renvoie `404` ;
4. un `entity_type` invalide renvoie `400` avec le message documenté ;
5. `/api/redoc/` affiche la description globale et les composants ;
6. aucune opération d'écriture n'apparaît.

## 10. Contrôles exécutés

| Commande | Sortie | Code |
|---|---|---|
| `python manage.py check` | `System check identified no issues (0 silenced).` | 0 |
| `python manage.py makemigrations --check --dry-run` | `No changes detected` | 0 |
| `python manage.py spectacular --file <tmp> --validate --fail-on-warn` | aucune sortie | 0 |
| `pytest` | `398 passed in 37.63s` | 0 |
| `ruff check .` | `All checks passed!` | 0 |
| `ruff format --check .` | `43 files already formatted` | 0 |
| `mypy .` | `Success: no issues found in 43 source files` | 0 |

Le schéma a été dirigé vers un fichier temporaire hors du dépôt. Aucune
valeur du `.env` n'est affichée.

Corrections intermédiaires, suivies de la relance des seuls contrôles
affectés : l'erreur `HealthView`, le déplacement du correctif de typage, le
double enveloppement de l'exemple de liste, `to_entity` nullable, les
docstrings françaises publiées, et un passage de `ruff format` sur quatre
fichiers.

## 11. Données de développement intactes

```
statuts : anansi=draft, mokele-mbembe=draft, oya=draft, shango=draft
public_entities() : 0
```

Aucun statut modifié, aucune fiche publiée. La collection publique reste donc
vide, ce que le schéma et le README documentent explicitement comme le
comportement attendu.

## 12. Limites

- **Dépendance CDN.** Swagger UI et ReDoc chargent leurs ressources depuis un
  CDN public. Sans accès réseau, la page HTML est servie mais ne s'affiche
  pas. Aucun paquet hors ligne n'a été ajouté, faute de besoin établi ; c'est
  signalé dans le README.
- **Rendu navigateur non testé automatiquement**, voir section 9.
- **Exemple de collection vide** en prose et non en exemple structuré, voir
  section 8.
- **Enveloppe de pagination aux valeurs génériques** dans l'exemple affiché :
  `count: 123` et des liens `api.example.org` côtoient un item synthétique. La
  description de l'exemple le précise.
- **Pas de versionnement du contrat.** `VERSION` vaut `0.1.0` et ne suit
  aucune politique de compatibilité. La phase 4 ajoutera les opérations
  d'écriture et de modération ; aucun ajout de champ au détail public n'est
  décidé par cet incrément.
- **Aucun schéma committé**, par choix : il est produit du code. En
  contrepartie, aucun fichier exporté n'est livré dans le dépôt. La commande
  permet néanmoins d'en produire un pour partage hors ligne. La CI de phase 6
  devra intégrer la validation du générateur et les tests de contrat.

## 13. Section pédagogique — ce qu'il faut regarder ensemble

Cinq pièces, dans l'ordre où elles agissent.

**1. La configuration** — `config/settings.py`

- `INSTALLED_APPS` : ajout de `drf_spectacular`, nécessaire pour ses gabarits
  Swagger et ReDoc.
- `REST_FRAMEWORK["DEFAULT_SCHEMA_CLASS"]` : c'est **la** bascule. Sans elle,
  DRF génère son propre schéma, incompatible, et spectacular refuse de
  travailler.
- `SPECTACULAR_SETTINGS` : les métadonnées du document — titre, version — et
  la grande `DESCRIPTION`, qui est la page d'accueil de Swagger et de ReDoc.
  C'est l'endroit où dire ce qu'un client doit savoir avant de lire les
  endpoints : règle de visibilité, lecture seule, collection vide attendue,
  réserve éditoriale.
- **La fin du fichier** : le correctif de typage et le commentaire qui
  explique pourquoi il doit y rester. C'est l'extrait le plus instructif de
  l'incrément — un import mal placé a silencieusement désactivé toute la
  configuration DRF pendant plusieurs phases.

**2. Le routage** — `config/urls.py`

Trois `path` qui montrent la séparation des rôles : `SpectacularAPIView`
produit le document, les deux autres ne sont que des pages HTML qui le
consomment via `url_name="schema"`. Un seul schéma, deux lecteurs. Noter
`permission_classes=[AllowAny]` posé vue par vue, et non en ouvrant le défaut
du projet.

**3. Les annotations** — `mythology/views.py`, lignes 48 à 77

Le bloc `@extend_schema_view` est le cœur du travail. Deux choses à observer :

- `parameters=LIST_PARAMETERS` sur `list` et `parameters=[]` sur `retrieve` :
  c'est ce qui matérialise, dans la documentation, la règle « ces paramètres
  ne concernent que la collection » — la même règle que `filter_queryset()`
  applique à l'exécution ;
- `auth=[]` : dire « aucune authentification » est une information, pas une
  absence d'information.

**4. Le typage des méthodes** — `mythology/serializers.py`,
`get_variant_of()` et `get_relations()`

Les deux `@extend_schema_field` montrent la limite de l'introspection : un
`SerializerMethodField` n'a pas de type déductible. L'annotation est la seule
façon de dire au schéma que l'une renvoie une `EntityReference` nullable et
l'autre un tableau d'`EntityRelation`. À comparer avec les docstrings
réécrites juste à côté, qui deviennent les descriptions publiques.

**5. Les exemples** — `mythology/schema.py`

Comparer `LIST_EXAMPLE` et `DETAIL_EXAMPLE` : le premier ne porte qu'un item
parce que la pagination l'enveloppe, le second est complet. Et observer
comment chaque libellé annonce « synthetic » — un exemple d'API ne doit pas
pouvoir se lire comme une donnée mythologique validée.

## 14. État Git des deux dépôts

Aucun commit, aucun push, aucun `git add` : l'index est vide.

```
# afrimyth-api
## main...origin/main
 M README.md
 M config/settings.py
 M config/urls.py
 M config/views.py
 M mythology/serializers.py
 M mythology/views.py
 M requirements.txt
?? docs/reports/phase-3-increment-3-openapi.md
?? mythology/schema.py
?? mythology/tests/test_openapi.py

# django-portfolio
## main...origin/main
?? docs/prompts/phase-3-increment-3-openapi.md
```

Les deux branches sont `main` et synchronisées avec `origin/main`. Le prompt
non suivi du dépôt de pilotage appartient à Codex. Après validation et essai
navigateur, Codex prendra en charge la clôture documentaire et Git.

## 15. Revue Codex — avant essai navigateur

La lecture de la configuration, des routes, des annotations, des serializers
et des tests ne révèle pas de blocage fonctionnel pour l'essai navigateur.
Les copies du rapport étaient identiques avant revue. Aucun modèle, statut
ou comportement de lecture n'a été modifié par Codex.

Le déplacement des imports DRF après les réglages traite bien le défaut décrit.
En revanche, aucun test explicite des défauts de permissions/authentification
n'était livré malgré la mention dans le commentaire de configuration.
Codex ajoute `test_drf_defaults_are_loaded_before_view_classes` dans
`tests/test_settings.py` : il vérifie les valeurs de `api_settings` **et**
les attributs hérités par `APIView`, afin de détecter le repli sur les valeurs
initiales lors d'un import prématuré.

Corrections documentaires circonscrites : distinction entre absence de route
privée actuellement identifiée et preuve d'absence de fuite passée ; retrait
de l'affirmation d'un test linguistique non présent ; distinction entre
validation du schéma et preuve de concordance avec toute réponse réelle ;
correction des comptages dans les commentaires et clarification de l'export
hors ligne. Aucun ajout de champ public de phase 4 n'est décidé ici.

Contrôles de Codex :

- `pytest tests/test_settings.py mythology/tests/test_openapi.py -q` :
  **54 passed in 8.73s** ; après l'ajustement purement typé du test,
  `pytest tests/test_settings.py -q` : **2 passed in 0.12s** ;
- Ruff et vérification du format : propres sur `tests/test_settings.py`,
  `mythology/schema.py`, `mythology/serializers.py` ;
- mypy : **Success: no issues found in 1 source file** sur le test modifié ;
- `spectacular --file <tmp> --validate --fail-on-warn` : code **0**,
  sans avertissement.

Deux ajustements du seul test ont été nécessaires avant les contrôles finaux :
respect de SIM300, puis annotation des valeurs dynamiques dont les stubs
DRF décrivent les chemins textuels plutôt que les classes résolues.

Les **398 tests** de la section 10 sont les résultats de Claude. Le test
supplémentaire de Codex porte le total attendu à 399 ; la suite complète
n'a pas été relancée, seuls les contrôles affectés l'ont été.

La validation finale, la mise à jour de la roadmap et les commits/pushes
attendent la revue pédagogique et l'essai visuel Swagger/ReDoc. La section 14
conserve l'état Git à la remise initiale, avant les corrections de Codex.

## 16. Correction légère — page ReDoc blanche pendant l'essai

L'auteur a signalé une page blanche. Codex a reproduit le problème dans
l'onglet du navigateur intégré : page HTML en HTTP 200, mais erreur console
`Cannot use 'import.meta' outside a module` dans le script
`https://cdn.jsdelivr.net/npm/redoc@latest/bundles/redoc.standalone.js`.
Le script répondait lui aussi en 200 : ce n'était pas une route Django
introuvable ni une indisponibilité générale du CDN.

La version courante ReDoc 3 attend un chargement en module ; le gabarit
installé de drf-spectacular utilise une balise de script classique.
Référence officielle : https://redocly.com/docs/redoc/deployment/html.

Correction localisée : `SPECTACULAR_SETTINGS["REDOC_DIST"]` fixe
`https://cdn.jsdelivr.net/npm/redoc@2.5.3`, compatible avec ce gabarit.
Aucun remplacement de gabarit, nouvelle dépendance, changement de schéma,
permission ou donnée. README actualisé ; test
`test_redoc_uses_a_pinned_classic_script` ajouté, contrôlant l'URL complète
du script dans la page et l'absence de `redoc@latest`.

Contrôles exécutés : 53 tests OpenAPI passent en 14.38 s. Après ajustement
de la longueur de ligne et formatage du seul nouveau test, Ruff et son
contrôle de format passent, mypy passe sur les deux fichiers Python concernés.
Le test ciblé est relancé sur la version formatée. Le total attendu de la
suite devient 400 (398 de Claude, deux tests de régression ajoutés par Codex),
sans affirmer une nouvelle exécution de la suite complète.

Après rechargement, Codex a vérifié le rendu dans le navigateur : titre
Afrimyth API, présentation, opérations et paramètres visibles. Capture
temporaire : `C:\Users\heric\AppData\Local\Temp\afrimyth-redoc-fixed.jpg`.
Le log d'erreur antérieur est conservé dans l'historique de console ; il ne
décrit pas le rendu corrigé. L'auteur peut reprendre l'exercice ReDoc.

## 17. Validation finale de l'auteur et clôture de la phase 3

L'auteur a validé les explications du code : configuration, ordre des imports,
routage, annotations des opérations et champs, et exemples documentaires.
Il a ensuite confirmé les exercices Swagger :

- titre, version, descriptions et paramètres visibles ;
- exécution de la liste : 200, enveloppe vide attendue avec les brouillons ;
- `country=NGA` : 400 documentée ; `country=NG` : 200 ;
- détail d'Oya non publiée puis slug inexistant : même réponse 404.

Après le correctif de la section 16, l'auteur confirme ReDoc fonctionnel,
puis la correspondance des paramètres et des profils/références nullables
avec le contrat attendu. Codex avait également constaté le rendu effectif
dans le navigateur, au-delà du seul statut HTTP de la page.

Le test ReDoc ciblé a terminé avec `1 passed in 2.90s` après formatage.
Les résultats déjà acquis (suite complète de Claude et contrôles ciblés de
Codex) sont réutilisés : seuls README, roadmap et rapport changent à cette
clôture, sans nouvelle modification de code ni de donnée.

La roadmap est cochée pour OpenAPI, exemples/erreurs et tests transverses.
Le README annonce la phase 3 terminée. La publication consiste en commits
et pushes normaux des deux dépôts sous l'identité de l'auteur, sans trailer
d'assistant. Les états Git des sections précédentes sont historiques.

La phase 4 reste à réaliser : JWT, rôles, CRUD, permissions et modération.
Les descriptions « lecture seule » et le schéma seront mis à jour avec les
opérations effectivement implémentées ; aucun accès en écriture n'est annoncé
ni activé par cette clôture. Les brouillons du corpus restent non publiés.
