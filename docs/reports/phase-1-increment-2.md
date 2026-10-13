# Rapport — Phase 1, incrément 2 : `Entity`, `DivinityProfile` et API de lecture

- **Date :** 13 octobre 2026
- **Dépôt :** `afrimyth-api`
- **Branche :** `main`
- **Statut :** incrément terminé, vérification manuelle réussie, phase 1 close

## 1. Objectif et périmètre

Rendre la première tranche métier exécutable et observable : le tronc commun
`Entity`, le premier profil `DivinityProfile`, leur administration Django et
une API liste/détail en lecture seule.

Hors périmètre, conformément au prompt et à la roadmap :

- référentiels `Country`, `Ethnicity`, `CulturalArea`, `Domain` et app dédiée ;
- `HeroProfile`, `CreatureProfile`, `EntityRelation`, `Source` ;
- champs de workflow, de propriété, de revue et de suppression logique ;
- pagination, recherche HTTP, filtres, schéma OpenAPI (phase 3) ;
- authentification, rôles, permissions objet, CRUD, modération (phase 4) ;
- import du corpus V2 (phase 5).

## 2. Modèle `Entity`

`Entity` porte les faits mythologiques réutilisables quel que soit le type.

| Champ | Type | Choix retenu |
|---|---|---|
| `id` | `UUIDField(primary_key=True, default=uuid.uuid4, editable=False)` | Le corpus V2 n'a aucun identifiant ; une clé stable et non devinable est le préalable à toute relation et à toute URL publique |
| `slug` | `SlugField(max_length=255, unique=True)` | Identifiant lisible, saisi explicitement pour l'instant |
| `name` | `CharField(255)` | |
| `entity_type` | `CharField(20, choices=EntityType)` | `divinity`, `hero`, `creature` |
| `category` | `CharField(255, blank=True)` | Sous-titre éditorial libre : 44 valeurs pour 44 entités, ce n'est pas une taxonomie |
| `gender` | `CharField(20, choices=Gender)` | `male`, `female`, `neutral`, `androgynous`, `fluid` — les 5 valeurs observées. Requis : le corpus le renseigne pour les 44 entités |
| `cultural_role` | `CharField(255, blank=True)` | |
| `alignment` | `CharField(100, blank=True)` | Reste du texte contraint : la décision éditoriale est reportée dans l'ADR 0001 |
| `story_description` | `TextField(blank=True)` | Le récit, rétabli au tronc commun |
| `characteristics`, `physical_signs`, `symbols`, `power_objects`, `symbolic_animals` | `ArrayField(CharField(100), default=list, blank=True)` | Vocabulaires trop instables pour justifier une table de référence |
| `manifestations` | `TextField(blank=True)` | `TextField` plutôt que `CharField(255)` : la limite des versions antérieures était arbitraire |
| `created_at`, `updated_at` | `DateTimeField(auto_now_add / auto_now)` | Horodatages perdus en V2, rétablis |

Les champs textuels facultatifs utilisent `blank=True` sans `null=True` :
une seule représentation de l'absence, la chaîne vide.

**Contraintes et index**

- `UniqueConstraint(fields=["name", "entity_type"], name="unique_entity_name_per_type")`
  — reprise de la seule contrainte réelle de `AfrMyth_API`. Deux entités de
  types différents peuvent donc porter le même nom, ce qui est nécessaire :
  Mami Wata existe comme créature et pourra exister comme divinité régionale.
- `Index(fields=["entity_type"], name="entity_type_idx")` — le filtre par type
  sera le plus fréquent.
- `ordering = ["name"]` — ordre stable des réponses, sans quoi la pagination de
  la phase 3 serait non déterministe.

Aucune génération automatique de slug n'a été ajoutée, conformément au prompt.
L'administration le préremplit depuis le nom via `prepopulated_fields`.

## 3. Relation `OneToOne` et validation

`DivinityProfile.entity` est un `OneToOneField(Entity, on_delete=CASCADE,
related_name="divinity_profile")`. Le profil ne contient que le culte —
`cult_offerings`, `cult_taboos`, `cult_rituals`, `cult_places`,
`cult_festivals`, tous `ArrayField(CharField(100), default=list, blank=True)`.
Les attributs symboliques communs restent sur `Entity`, conformément à la
décision 4 de l'ADR 0002 qui impose un emplacement unique.

Trois conséquences de ce choix, vérifiées par les tests :

- l'accès inverse est `entity.divinity_profile` ;
- supprimer l'entité supprime le profil (`CASCADE`) ;
- `select_related("divinity_profile")` fonctionne dans les deux sens, ce qui
  permet de charger le détail en une seule requête.

**Validation du type.** `DivinityProfile.clean()` refuse une entité dont
`entity_type != "divinity"`. Cette règle ne peut pas devenir une contrainte de
base : elle porte sur une colonne d'une autre table. Elle est donc appliquée
par `full_clean()`, donc par l'administration et par tout formulaire, mais
**pas** par un appel direct à `objects.create()`. C'est une limite assumée et
documentée dans le code : la garantie complète « une entité possède exactement
le profil correspondant à son type » viendra avec les services de création
métier et les deux autres profils, comme le prévoit l'ADR 0002. Aucun moteur
de service générique n'a été introduit ici.

## 4. Routes exposées

| Méthode | Route | Réponse |
|---|---|---|
| `GET` | `/api/entities/` | Collection compacte : `id`, `slug`, `name`, `entity_type`, `category` |
| `GET` | `/api/entities/{slug}/` | Détail : champs communs + `divinity_profile` imbriqué, `null` s'il n'existe pas |
| `GET` | `/api/` | Racine navigable produite par le `DefaultRouter` |

Mise en œuvre : un `ReadOnlyModelViewSet` avec `lookup_field = "slug"`, enregistré
sur un `DefaultRouter` monté sous `api/`. `get_serializer_class()` choisit la
représentation compacte ou détaillée selon l'action ; `get_queryset()` n'ajoute
`select_related("divinity_profile")` que pour `retrieve`, la liste n'exposant
pas le profil.

`permission_classes = [AllowAny]` surcharge explicitement le défaut
`IsAuthenticated` du projet. **Cette ouverture et cette lecture seule sont
provisoires et limitées à cet incrément** : la phase 4 apportera les comptes,
les rôles, les permissions au niveau objet, le CRUD et les transitions de
modération de l'ADR 0002. Il n'existe encore aucun statut éditorial, donc
aucune entité n'est filtrée ; le filtrage sur `published` arrivera avec le
workflow.

Ni pagination, ni recherche, ni filtre, ni OpenAPI : phase 3.

Le rendu HTML navigable de DRF est conservé — `DEFAULT_RENDERER_CLASSES` vaut
`['JSONRenderer', 'BrowsableAPIRenderer']`, le défaut du framework, aucune
configuration n'a été ajoutée.

### Vérification manuelle — réalisée et réussie

Aucun superutilisateur n'est créé automatiquement et aucune donnée de
démonstration n'est persistée : la vérification a donc été conduite à la main,
dans un navigateur, sur l'installation locale. **Résultat : concluant.**

| Étape | Résultat |
|---|---|
| Administration accessible sur <http://127.0.0.1:8000/admin/> | OK |
| Création d'une `Entity` de type « Divinité », slug prérempli depuis le nom | OK |
| Création du `DivinityProfile` rattaché à cette entité | OK |
| Collection <http://127.0.0.1:8000/api/entities/> visible dans le navigateur | OK |
| Détail <http://127.0.0.1:8000/api/entities/{slug}/> visible dans le navigateur | OK |
| `divinity_profile` correctement imbriqué dans le détail | OK |

Le rendu HTML navigable de DRF a donc bien été servi aux deux routes, en plus
de leur représentation JSON déjà couverte par les tests automatisés.

Deux étapes du scénario initialement prévu n'ont pas été rejouées à la main,
car elles sont déjà couvertes par les tests automatisés : le détail d'une
entité sans profil (`divinity_profile: null`, voir
`test_detail_sans_profil`) et le refus d'un profil de divinité rattaché à un
héros (voir `test_profil_refuse_une_entite_d_un_autre_type`).

## 5. Frontière avec la génération de médias

Les champs de cet incrément décrivent des **faits mythologiques** réutilisables
quelle que soit la restitution : récit, caractéristiques, apparence physique,
symboles, objets de pouvoir, animaux symboliques, manifestations et culte. Ils
constituent un socle, non la déclaration que le modèle serait terminé — la
phase 2 le complétera.

Tout ce qui relève de la **production de médias** reste hors de cet incrément
et devra vivre dans ses propres modèles : prompt canonique, variantes de
prompt, prompt négatif, styles visuels, paramètres de génération, et
métadonnées d'image, de son ou de vidéo. Cette séparation est volontaire :
`appearance.image_generation_prompt` et le bloc `rendering` de V2 mêlent un
fait mythologique et une instruction destinée à un moteur d'images, et cette
confusion ne doit pas entrer dans le schéma relationnel.

## 6. Fichiers créés ou modifiés

**Créés**

- `mythology/serializers.py` — `EntityListSerializer`, `EntityDetailSerializer`, `DivinityProfileSerializer`
- `mythology/views.py` — `EntityViewSet` (l'app n'avait aucun module de vues)
- `mythology/urls.py` — `DefaultRouter` et enregistrement du viewset
- `mythology/migrations/0001_initial.py` — générée par `makemigrations`
- `mythology/tests/__init__.py`
- `mythology/tests/factories.py` — deux constructeurs nommés, pas de bibliothèque de factories
- `mythology/tests/test_models.py` — 7 tests
- `mythology/tests/test_api.py` — 7 fonctions de test dont 2 paramétrées, soit 13 cas exécutés
- `docs/reports/phase-1-increment-2.md` — ce rapport

**Modifiés**

- `mythology/models.py` — `EntityType`, `Gender`, `string_array()`, `Entity`, `DivinityProfile`
- `mythology/admin.py` — `EntityAdmin`, `DivinityProfileAdmin`
- `config/urls.py` — `include("mythology.urls")` sous `api/`
- `config/settings.py` — appel à `django_stubs_ext.monkeypatch()` (voir arbitrage ci-dessous)
- `requirements.txt` — ajout de `django-stubs-ext~=6.1`

## 7. Administration

`EntityAdmin` : colonnes `name`, `entity_type`, `category`, `gender`,
`updated_at` ; filtres sur `entity_type` et `gender` ; recherche par nom ;
`prepopulated_fields = {"slug": ["name"]}` ; `id`, `created_at` et `updated_at`
en lecture seule.

`DivinityProfileAdmin` : colonne `entity`, recherche par nom d'entité,
`autocomplete_fields = ["entity"]` — ce qui exige le `search_fields` déclaré sur
`EntityAdmin`. Aucune personnalisation au-delà.

## 8. Arbitrage technique — classes génériques et mypy strict

Un obstacle réel a été rencontré. Sous `mypy strict`, `disallow_any_generics`
exige d'indexer les classes génériques : `ModelAdmin[Entity]`,
`ModelSerializer[Entity]`, `ReadOnlyModelViewSet[Entity]`,
`ArrayField[list[str], list[str]]`. Or ces classes ne sont génériques que dans
les stubs : à l'exécution, `admin.ModelAdmin[Entity]` lève
`TypeError: type 'ModelAdmin' is not subscriptable`.

Trois options étaient possibles :

1. renoncer aux paramètres de type — refusé par `mypy strict` ;
2. désactiver `disallow_any_generics` sur `mythology.admin`, `serializers` et
   `views` — cela aurait affaibli le typage sur l'essentiel du code d'API ;
3. appliquer `django_stubs_ext.monkeypatch()`, solution documentée par
   `django-stubs`, qui rend ces classes indexables à l'exécution.

**Option 3 retenue.** L'appel est placé en tête de `config/settings.py`, avec
`extra_classes=[BaseSerializer, GenericAPIView]` pour couvrir DRF en plus de
Django. Conséquence à assumer : `django-stubs-ext` passe de dépendance de
développement à dépendance d'exécution, et figure désormais dans
`requirements.txt`. C'est un paquet minuscule dont c'est la raison d'être.
Si cette dépendance devenait indésirable, l'alternative serait l'option 2,
documentée ici pour ne pas refaire l'analyse.

## 9. Tests

24 tests au total dans le dépôt, dont 20 ajoutés par cet incrément.

**Modèles** (`mythology/tests/test_models.py`)

- création d'une divinité et de son profil, relation vérifiée dans les deux sens ;
- UUID comme clé primaire ;
- refus par `full_clean()` d'un profil de divinité rattaché à un héros ;
- acceptation du même profil sur une entité de type `divinity` ;
- `IntegrityError` sur un doublon `(name, entity_type)` ;
- même nom autorisé pour deux types différents ;
- suppression en cascade du profil avec l'entité.

**API** (`mythology/tests/test_api.py`)

- liste publique et strictement compacte, jeu de clés vérifié exactement ;
- détail avec profil imbriqué, listes vides incluses ;
- détail d'une entité sans profil → `divinity_profile: null` ;
- détail obtenu en **une seule requête SQL** (`django_assert_num_queries(1)`),
  ce qui prouve l'effet du `select_related` ;
- `404` sur un slug inconnu ;
- `405` sur `POST`, `PUT`, `PATCH`, `DELETE`, sur la liste comme sur le détail
  (deux tests paramétrés, 8 cas).

Les tests de modèle et d'API vivent dans `mythology/tests/`, le répertoire
`tests/` de la racine restant réservé au socle technique.

## 10. Commandes de vérification et résultats

| Commande | Sortie | Code |
|---|---|---|
| `python manage.py check` | `System check identified no issues (0 silenced).` | 0 |
| `python manage.py makemigrations --check --dry-run` | `No changes detected` | 0 |
| `python manage.py migrate` | `Applying mythology.0001_initial... OK` puis `No migrations to apply.` au second passage | 0 |
| `pytest` | `24 passed in 3.23s` | 0 |
| `ruff check .` | `All checks passed!` | 0 |
| `ruff format --check .` | `26 files already formatted` | 0 |
| `mypy .` | `Success: no issues found in 26 source files` | 0 |

La migration `mythology.0001_initial` a été générée par `makemigrations` puis
appliquée sur PostgreSQL 16. La base de test est créée et détruite par
`pytest-django` sans intervention : le rôle applicatif possède bien le droit
de créer des bases.

Les six commandes de contrôle ont été relancées après la vérification manuelle
et la mise à jour de ce rapport : toutes conservent le même résultat.

## 11. État Git

État avant commit :

```
 M config/settings.py
 M config/urls.py
 M mythology/admin.py
 M mythology/models.py
 M requirements.txt
?? docs/reports/phase-1-increment-2.md
?? mythology/migrations/0001_initial.py
?? mythology/serializers.py
?? mythology/tests/
?? mythology/urls.py
?? mythology/views.py
```

L'incrément est ensuite rassemblé dans un commit local unique
`feat: add entity read API`, sur la branche `main`. Aucun push. Ni `.env`, ni
`.venv`, ni cache n'est indexé — exclusions confirmées par `git check-ignore`.

## 12. Tâches reportées

**Phase 2** — `HeroProfile` et `CreatureProfile` ; référentiels `Country`,
`Ethnicity`, `CulturalArea`, `Domain` et les relations correspondantes de
`Entity` (`primary_*`, `secondary_*`) ; `variant_of` ; `EntityRelation` et
`Source` ; cohérence stricte entre `entity_type` et le profil associé ; pilote
d'import sur trois entités réelles.

**Phase 3** — pagination, recherche, filtres, OpenAPI avec drf-spectacular,
visibilité restreinte aux entités `published`, méthode réutilisable de
sélection des objets visibles.

**Phase 4** — JWT, groupes `contributor` / `reviewer` / `administrator`,
`created_by` automatique, CRUD, actions de transition, matrice de permissions
testée, remplacement de l'`AllowAny` provisoire de cet incrément.

**Hors V1** — données de génération de médias (prompts, variantes, styles,
métadonnées d'image), internationalisation, journal d'audit.

**Dette identifiée, à traiter avant la CI de la phase 6** — aucun des deux
dépôts n'a de `.gitattributes` ; Git signale une conversion LF → CRLF à chaque
ajout de fichier. Un `* text=auto eol=lf` éviterait des diffs parasites entre
machines.
