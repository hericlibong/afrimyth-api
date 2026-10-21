# Rapport — Phase 3, incrément 2 : navigation dans la collection publique

- **Date :** 21 octobre 2026
- **Dépôt :** `afrimyth-api`
- **Branche :** `main`
- **Statut :** implémentation terminée, non committée, en attente de revue

## 1. Objectif et périmètre

Rendre `GET /api/entities/` praticable avec un corpus important : pagination,
recherche textuelle et filtres combinables. L'API reste publique et en
lecture seule.

Aucun changement de modèle, de migration, de corpus, de statut de
développement, de workflow ou de permissions. Swagger et ReDoc restent pour
l'incrément 3. La visibilité publique de l'incrément 1 et les protections des
références imbriquées sont conservées intactes.

Aucune dépendance n'a été ajoutée : ni `django-filter`, ni moteur de
recherche externe. Pagination et recherche viennent de DRF, les trois filtres
sont écrits explicitement.

La roadmap n'a **pas** été cochée, rien n'a été committé ni poussé.

## 2. Fichiers touchés

**Créés**

- `mythology/pagination.py` — la classe de pagination
- `mythology/tests/test_navigation.py` — 60 cas
- `docs/reports/phase-3-increment-2-navigation.md` — ce rapport

**Modifiés**

- `mythology/selectors.py` — ordre déterministe, `descendant_area_ids()`,
  `filter_public_entities()`
- `mythology/views.py` — pagination, recherche, validation des paramètres,
  garde sur `filter_queryset()`
- `README.md` — pagination, paramètres, exemple de réponse, erreurs
- `mythology/tests/test_api.py`, `test_public_visibility.py` — adaptation au
  contrat de liste paginé

Aucun modèle, aucune migration : `makemigrations --check` ne détecte rien.

## 3. Contrat exact

### Pagination

| Élément | Valeur |
|---|---|
| Paramètre | `?page=` |
| Taille | 20, **fixe** — non négociable par le client |
| Enveloppe | `count`, `next`, `previous`, `results` (standard DRF) |
| Éléments de `results` | champs inchangés du serializer de liste |
| Ordre | `name`, puis `id` |
| Page inexistante ou invalide | `404`, comportement DRF standard |

`count` ne compte que les fiches **publiques correspondant à la recherche et
aux filtres** : ni brouillon, ni fiche supprimée, ni fiche écartée par un
filtre.

Les liens `next` et `previous` **conservent tous les paramètres**, ce qui
rend la pagination d'une collection filtrée utilisable.

**Ordre déterministe.** `name` seul ne suffit pas : deux figures homonymes
pourraient changer de page d'une requête à l'autre, et la pagination
deviendrait instable. L'`id` les départage. L'ordre est posé dans
`public_entities()` plutôt que dans `Meta.ordering`, afin de ne pas modifier
l'ordre par défaut du modèle ni générer de migration.

**Changement assumé du contrat de liste.** La réponse n'est plus un tableau
brut mais l'enveloppe ci-dessus. Le détail et l'endpoint de santé gardent
leur forme — deux tests le vérifient explicitement.

### Recherche et filtres

| Paramètre | Sens |
|---|---|
| `search` | recherche DRF insensible à la casse dans `name`, `category`, `cultural_role`, `story_description` |
| `entity_type` | valeur exacte `divinity`, `hero` ou `creature` |
| `country` | code ISO alpha-2, normalisé en majuscules ; pays principal **ou** secondaire |
| `cultural_area` | slug d'aire ; rattachement principal **ou** secondaire à cette aire **ou à l'un de ses descendants** |

Les paramètres se combinent par **ET**. À l'intérieur d'un filtre, les deux
rattachements se combinent par **OU**. Un paramètre absent ou vide ne filtre
pas.

**La recherche ne couvre que les champs publics de la fiche elle-même.** Ni
les notes de revue, ni les sources, ni les fiches liées ne sont interrogées :
une recherche ne doit pas devenir un chemin d'accès indirect vers des données
que l'API n'expose pas. Un test le vérifie avec un mot-clé placé dans
`review_notes` et dans le libellé d'une source — aucun des deux ne remonte.

**Aucun doublon.** Joindre une relation multiple multiplie les lignes quand
plusieurs rattachements correspondent. `filter_public_entities()` applique
donc `distinct()` dès qu'un filtre multiple est utilisé, ce qui évite les
doublons dans `results` **et** le gonflement de `count`. Deux tests couvrent
le cas : un pays à la fois principal et secondaire, et une aire principale
avec une sous-aire secondaire.

### Hiérarchie des aires

`descendant_area_ids(slug)` lit la hiérarchie **réellement enregistrée** dans
`parent` : aucun nom de région n'est codé en dur. La descente est itérative,
niveau par niveau, et exclut les identifiants déjà vus.

- `?cultural_area=central-africa` inclut une fiche rattachée à
  `congo-basin` — testé ;
- la traversée fonctionne à **quatre niveaux** dans les tests, et à n'importe
  quelle profondeur ;
- demander une sous-région n'inclut **pas** sa région parente : la traversée
  descend, elle ne remonte pas — testé ;
- un **cycle** accidentel dans `parent` ne provoque pas de boucle infinie,
  grâce à l'exclusion des identifiants vus. Un test construit A → B → A et
  vérifie que la traversée se termine avec les deux identifiants. Le modèle
  n'a pas été modifié pour interdire ce cas.

**Aucun pays n'est déduit d'une aire.** Un test le constate : une fiche
rattachée à `congo-basin` sans pays est trouvée par `?cultural_area=` et pas
par `?country=CD`.

### Erreurs

| Situation | Réponse |
|---|---|
| `entity_type` inconnu | `400` — `{"entity_type": ["Unknown entity type 'titan'. Expected one of: divinity, hero, creature."]}` |
| `country` mal formé | `400` — `{"country": ["Invalid country code 'NGA'. Expected a two-letter ISO 3166-1 alpha-2 code, for example 'NG'."]}` |
| `country` bien formé mais absent | `200`, collection vide |
| slug d'aire absent | `200`, collection vide |
| `page` inexistante ou invalide | `404` |

La distinction est volontaire : un **format** invalide est une erreur
d'appel, tandis qu'une **valeur** inconnue donne une collection vide, afin de
ne pas révéler quels pays ou quelles aires sont enregistrés.

## 4. Un bug trouvé et corrigé en cours de route

Les filtres de collection rendaient le **détail** indisponible.

DRF applique les `filter_backends` non seulement à `list()` mais aussi à
`get_object()`. Avec `SearchFilter` déclaré sur le viewset,
`GET /api/entities/shango/?search=introuvable` renvoyait **404** pour une
fiche parfaitement publique — exactement ce que le prompt interdit.

Correction : `filter_queryset()` est surchargé pour n'appliquer les backends
que lorsque `self.action == "list"`. Un test paramétré couvre les cinq
paramètres — `search`, `entity_type`, `country`, `cultural_area`, `page` — et
vérifie que le détail répond toujours `200`.

Sans le test de portée demandé par le prompt, ce comportement serait passé
inaperçu : la liste fonctionnait correctement.

Second correctif mineur : les messages de `ValidationError` étaient passés en
chaîne et non en liste, si bien que le corps de la 400 valait
`{"entity_type": "Unknown…"}` au lieu de `{"entity_type": ["Unknown…"]}`.
Corrigé pour suivre la forme standard DRF, plus prévisible pour un client.

## 5. Tests

**346 cas exécutés**, dont 60 ajoutés et 13 adaptés.

| Fichier | Cas |
|---|---|
| `mythology/tests/test_navigation.py` | 60 |
| `mythology/tests/test_api.py` | 50 |
| `mythology/tests/test_pilot_import.py` | 52 |
| `mythology/tests/test_services.py` | 34 |
| `mythology/tests/test_relations.py` | 31 |
| `mythology/tests/test_reference.py` | 28 |
| `mythology/tests/test_sources.py` | 25 |
| `mythology/tests/test_editorial_fields.py` | 22 |
| `mythology/tests/test_public_visibility.py` | 22 |
| `mythology/tests/test_profiles.py` | 11 |
| `mythology/tests/test_models.py` | 7 |
| `tests/` (socle) | 4 |

Toutes les fiches des nouveaux tests sont **synthétiques dans la base de
test** : publiées pour les résultats attendus, privées ou supprimées pour
les cas d'exclusion. Aucun brouillon réel n'a été publié pour illustrer
ces fonctions.

### Couverture de `test_navigation.py`

**Pagination** — enveloppe et son jeu de clés, collection vide, trois pages
sur 45 fiches, absence de chevauchement et de manque sur l'ensemble des
pages, page inexistante, page invalide, ordre stable avec trois homonymes
vérifié sur deux requêtes successives, conservation des paramètres dans
`next` et `previous`.

**Recherche** — les quatre champs (test paramétré), insensibilité à la casse,
absence de résultat, paramètre vide, exclusion des notes internes et des
sources, exclusion des fiches privées et supprimées des résultats et du
compte.

**`entity_type`** — filtrage, paramètre vide, valeur inconnue en 400 avec
message exact.

**`country`** — pays principal, pays secondaire, insensibilité à la casse,
absence de doublon quand les deux rattachements correspondent, code absent
donnant une collection vide, quatre formats invalides en 400 (test
paramétré), paramètre vide.

**`cultural_area`** — aire principale, aire secondaire, descendants directs,
descendants à quatre niveaux, absence de remontée vers le parent, absence de
doublon, slug absent, paramètre vide, cycle de hiérarchie, absence de
déduction de pays.

**Combinaisons** — quatre critères simultanés avec quatre leurres ne différant
chacun que par un critère, combinaison sans correspondance, comptage après
filtrage, et un test paramétré vérifiant qu'**aucun** des quatre paramètres ne
divulgue une fiche privée ou supprimée, ni dans `results`, ni dans `count`,
ni dans le corps brut.

**Portée** — les cinq paramètres de collection sans effet sur le détail,
détail non paginé, santé inchangée, écritures toujours refusées en 405.

**Coût** — trois tests de budget, décrits ci-dessous.

## 6. Requêtes mesurées

Mesurées après coup sur une base de test peuplée, et non figées a priori :

| Cas | Requêtes |
|---|---|
| Liste nue | **2** |
| Liste page 2 | **2** |
| `?search=` | **2** |
| `?entity_type=` | **2** |
| `?country=` | **2** |
| `?cultural_area=` sur une feuille | **4** |
| `?cultural_area=` sur une racine à 3 niveaux | **6** |
| Les quatre paramètres ensemble | **6** |

**Décompte.** Deux requêtes forment le socle : le `COUNT(*)` de la pagination,
puis la page elle-même. La pagination ajoute donc **une** requête par rapport
à l'incrément précédent, ce qui est le prix de `count`.

Le filtre d'aire ajoute le coût de la traversée : 1 requête pour la racine,
puis 1 par niveau de descendants, dont la dernière revient vide et termine la
boucle. Une racine à trois niveaux coûte donc 4 requêtes de traversée, une
feuille 2. **Ce coût dépend de la profondeur de la hiérarchie, jamais du
nombre de fiches.**

**Aucune requête par entité.** Vérifié sur deux volumes : 45 fiches et 120
fiches donnent toutes deux **2 requêtes** pour la liste nue. La liste
n'expose ni profil, ni référentiel, ni relation, ni source, donc son queryset
reste nu — c'est ce qui rend le coût indépendant du volume.

Les garanties de l'incrément 1 sont conservées : le détail reste à 7
requêtes, et la sérialisation après évaluation du queryset préparé à 0.

## 7. Contrôles exécutés

| Commande | Sortie | Code |
|---|---|---|
| `python manage.py check` | `System check identified no issues (0 silenced).` | 0 |
| `python manage.py makemigrations --check --dry-run` | `No changes detected` | 0 |
| `pytest` | `346 passed in 27.12s` | 0 |
| `ruff check .` | `All checks passed!` | 0 |
| `ruff format --check .` | `41 files already formatted` | 0 |
| `mypy .` | `Success: no issues found in 41 source files` | 0 |

Trois corrections intermédiaires, suivies de la relance des seuls contrôles
affectés :

- `mypy` refusait la signature de `filter_queryset()` — DRF la type avec un
  second paramètre de `QuerySet` — résolu par `QuerySet[Entity, Any]` ;
- `mypy` refusait un `dict[str, object]` passé à `client.get()` dans un
  test, résolu par une annotation explicite ;
- `ruff format` sur quatre fichiers.

Aucune valeur du `.env` n'est affichée.

## 8. Données de développement intactes

```
statuts : anansi=draft, mokele-mbembe=draft, oya=draft, shango=draft
public_entities() : 0
```

Aucune fiche n'a été publiée, aucun statut modifié. La collection publique
reste donc légitimement vide en développement, et les paramètres de
navigation s'y appliquent sans rien révéler.

## 9. Limites

- **Taille de page fixe.** Pour parcourir 100 éléments, un client doit faire
  cinq requêtes. Une taille configurable avec un plafond serait possible,
  mais n'est pas nécessaire pour le contrat retenu.
- **Pas de tri configurable.** L'ordre est `name`, `id`, sans paramètre
  `ordering`. Rien ne le demandait, et un tri libre complique la stabilité de
  la pagination.
- **Recherche `icontains` simple.** Aucun index spécialisé de recherche n'a
  été ajouté. Aucun seuil de volume ni temps de réponse n'a été établi par
  un benchmark dans cet incrément : le nombre de requêtes ne mesure pas
  leur durée. Une évolution vers la recherche plein-texte ou la tolérance
  aux fautes devra répondre à un besoin et à des mesures, pas à un seuil
  arbitraire de 400 fiches.
- **Le filtre d'aire coûte une requête par niveau.** Acceptable sur une
  hiérarchie à deux ou trois niveaux ; une requête récursive serait possible
  mais prématurée.
- **Pas de filtre par ethnie, domaine, genre ou alignement.** Seuls les
  quatre paramètres demandés existent.
- **Aucun en-tête de cache HTTP.** Hors périmètre.

## 10. Travaux reportés

**Incrément 3 de la phase 3** — schéma OpenAPI, Swagger et ReDoc, avec
documentation des paramètres de navigation, exemples de réponses et erreurs.
La forme exacte des réponses et les messages d'erreur consignés ici sont la
matière de cette documentation.

**Phase 4** — JWT, groupes, permissions objet, CRUD, transitions,
suppression logique et restauration. La sélection privée s'ajoutera à côté de
`public_entities()` ; les filtres actuels s'appliquent à la sélection reçue,
donc ils resteront réutilisables.

**Travail éditorial, hors code** — publication des fiches du pilote, qui
restent en brouillon jusqu'à revue, selon
`docs/notes/revue-editoriale-corpus-pilote.md`.

## 11. État Git des deux dépôts

Aucun commit, aucun push, aucun `git add` : l'index est vide.

```
# afrimyth-api
## main...origin/main
 M README.md
 M mythology/selectors.py
 M mythology/views.py
 M mythology/tests/test_api.py
 M mythology/tests/test_public_visibility.py
?? docs/reports/phase-3-increment-2-navigation.md
?? mythology/pagination.py
?? mythology/tests/test_navigation.py

# django-portfolio
## main...origin/main
(arbre propre)
```

Les deux branches sont `main` et synchronisées avec `origin/main`. Après
validation, Codex prendra en charge la clôture documentaire et Git.

## 12. Revue Codex

La lecture du code et des tests ne révèle pas de blocage fonctionnel. Le bug
de recherche appliquée au détail a été corrigé par Claude avant cette revue.
La garde `filter_queryset()` et son test paramétré sont présents.

Corrections légères de Codex, sans changement du code applicatif :

- Les deux tests anti-doublons avaient chacun un seul rattachement secondaire.
  Cela ne multipliait pas réellement les lignes de jointure. Ajout d'un second
  rattachement dans chaque cas pour exercer effectivement `distinct()`.
- Ajout du leurre manquant sur l'aire culturelle dans le test combinant les
  quatre critères. Le nombre de cas reste inchangé.
- Précision sur les fiches synthétiques privées des tests d'exclusion ; retrait
  du seuil non mesuré de 400 fiches pour la recherche et clarification de la
  taille de page fixe (un plafond configurable serait également possible).

Après ces changements, Codex a exécuté les 60 cas de navigation :
`60 passed in 5.33s`. Ruff et sa vérification de format passent sur le fichier.
Les 346 cas de la suite complète et les contrôles globaux de la section 7
restent les résultats de Claude avant ces seuls renforcements de tests.

La revue pédagogique a couvert les extraits de pagination, les filtres `Q`
et `distinct()`, la traversée des sous-régions et la garde du détail, avec
leurs effets concrets. Le rôle distinct de la commande d'import pilote a
également été expliqué : outil d'alimentation, pas moteur des requêtes HTTP.

## 13. Validation pratique et clôture

L'auteur confirme les réponses attendues de la collection vide, de la recherche,
des filtres et des erreurs 400/404 proposées pour l'exercice. Il confirme
ensuite la démonstration ORM/API et son nettoyage : création d'une divinité
et d'un héros fictifs publiés, recherche par repère unique (deux résultats),
filtrage par type (un résultat pour chaque type créé, zéro créature), puis
suppression ciblée des deux fiches et de leurs profils.

Ces constats pratiques sont rapportés par l'auteur, pas issus d'une inspection
directe de sa session par Codex. Aucun brouillon du corpus n'a été publié
pour l'exercice. Les scénarios multi-pages, pays et sous-régions sont couverts
par les tests automatisés, sans nouvelle démonstration manuelle.

Pagination maintenue à 20 après discussion : la liste n'expose que cinq
champs par fiche ; le détail complet porte sur une seule fiche et n'est pas
paginé. Aucun changement de configuration n'en résulte.

L'auteur a clarifié la langue des docstrings : anglais pour le nouveau code,
traduction globale des existantes reportée avant livraison V1. ADR 0003,
roadmap et consignes des deux dépôts actualisées ; aucune traduction massive
ni changement fonctionnel pendant cette clôture.

Le typage du fichier de tests renforcé a également été vérifié par Codex :
`Success: no issues found in 1 source file`. Les résultats de tests déjà acquis
sont réutilisés, le code n'ayant pas changé depuis leur exécution.
La section 11 conserve l'état Git à la remise initiale du rapport.

L'incrément est validé. La clôture comprend les commits et pushes normaux
des fichiers du périmètre sous l'identité de l'auteur. OpenAPI, Swagger/ReDoc
et la consolidation finale restent à l'incrément 3.
