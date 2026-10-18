# Rapport — Phase 2, incrément 3 : variantes culturelles et relations

- **Date :** 17 octobre 2026
- **Dépôt :** `afrimyth-api`
- **Branche :** `main`
- **Statut :** revue technique et pédagogique validée le 18 octobre 2026 ; prêt pour clôture Git

## 1. Objectif et périmètre

Relier les figures entre elles, y compris lorsque la figure citée n'a pas
encore de fiche, et permettre à une figure d'être la variante culturelle d'une
autre. Modèles, migration, administration, API de lecture et tests sont livrés
dans le même incrément.

Hors périmètre, conformément au prompt : `Source`, utilisateurs et rôles,
workflow éditorial, services d'écriture, import pilote ou complet, rendu et
prompts, carte, endpoints supplémentaires, suppression logique.

La roadmap n'a **pas** été cochée, rien n'a été committé ni poussé.

## 2. Fichiers changés

**Créés**

- `mythology/migrations/0004_entityrelation_entity_variant_of_and_more.py`
  — générée par `makemigrations`
- `mythology/tests/test_relations.py` — 31 cas
- `docs/reports/phase-2-increment-3-relations.md` — ce rapport

**Modifiés**

- `mythology/models.py` — `RelationKind`, `Entity.variant_of` avec sa
  contrainte et son `clean()`, `EntityRelation`, docstring du module
  actualisée
- `mythology/admin.py` — `variant_of` en autocomplétion, `EntityRelationAdmin`
- `mythology/serializers.py` — `EntityReferenceSerializer`,
  `EntityRelationSerializer`, détail élargi à `variant_of` et `relations`
- `mythology/views.py` — `select_related("variant_of")` et `Prefetch` des
  relations sortantes
- `mythology/tests/factories.py` — `create_relation`
- `mythology/tests/test_api.py` — six tests ajoutés, deux budgets de requêtes
  réajustés

Aucune migration existante n'a été réécrite.

## 3. Variantes culturelles

`Entity.variant_of` : `ForeignKey("self", null=True, blank=True,
on_delete=PROTECT, related_name="variants")`.

Une variante reste une **entité autonome** : ses pays, ethnies, aires, textes
et profils ne sont ni hérités ni recopiés. Un test le vérifie explicitement —
la référence conserve un `story_description` vide quand la variante en porte
un.

Son `entity_type` **peut différer** de celui de la figure de référence, sans
aucune contrainte d'égalité : une forme régionale peut être une divinité là où
la référence est une créature, conformément à la décision 3 de l'ADR 0002.

### Règles et garanties, par portée

| Règle | Garantie en base | Validation de formulaire |
|---|---|---|
| Une entité n'est pas sa propre référence | `CheckConstraint entity_variant_of_is_not_self` | `clean()`, message « An entity cannot be a variant of itself. » |
| Une référence citée n'est pas supprimable physiquement | `on_delete=PROTECT` → `ProtectedError` | — |
| `variant_of` est facultatif | `null=True` | — |

La distinction importe : la `CheckConstraint` s'applique à **tout** chemin
d'écriture, y compris un `save()` direct ; le `clean()` ne s'exécute que via
`full_clean()`, donc l'administration et les formulaires. Deux tests distincts
couvrent les deux portées.

### Limite assumée — cycles indirects

Seule l'auto-référence **directe** est interdite. Un cycle A → B → A n'est pas
détecté : il faudrait un parcours récursif, hors périmètre. Le test
`test_cycle_indirect_de_variantes_n_est_pas_detecte` fixe ce comportement réel
pour qu'il soit constaté maintenant plutôt que découvert plus tard.

La protection contre une **suppression logique** d'une référence encore
utilisée arrivera avec les champs et services correspondants ; `PROTECT` ne
couvre que la suppression physique.

## 4. Relations entre figures

`EntityRelation` dans `mythology` :

| Champ | Définition |
|---|---|
| `from_entity` | `FK(Entity, CASCADE, related_name="relations_from")` |
| `to_entity` | `FK(Entity, CASCADE, related_name="relations_to", null=True, blank=True)` |
| `to_name` | `CharField(max_length=255, blank=True)` |
| `kind` | `CharField(max_length=20, choices=RelationKind.choices)` |
| `notes` | `TextField(blank=True)` |

`RelationKind` porte cinq valeurs techniques anglaises avec libellés anglais :
`parent` / Parent, `child` / Child, `consort` / Consort, `ally` / Ally,
`enemy` / Enemy.

### Sens de lecture — à ne pas inverser à l'import

Le lien se lit **toujours depuis `from_entity`**, et `kind` qualifie la cible :

- `Shango — parent → Oranyan` signifie « **Oranyan est un parent de
  Shango** » ;
- `Shango — child → Dada` signifie « **Dada est un enfant de Shango** ».

Ce sens est documenté dans la docstring de `EntityRelation`, dans celle de
`RelationKind`, dans la factory `create_relation` et dans le test
`test_sens_de_lecture_de_la_relation`, qui sert de garde-fou : s'il échoue,
c'est que le sens a été retourné quelque part.

Un descendant lointain n'est **jamais** converti en enfant direct. Les cas
ambigus seront signalés par le rapport d'import, pas résolus silencieusement.

### Cible résolue ou simplement citée

Exactement une cible : soit `to_entity` renseigné et `to_name` vide, soit
`to_entity` nul et `to_name` non vide. Sur les 44 entités du corpus V2, les
noms cités désignent souvent des figures absentes ; `to_name` conserve le nom
brut. Une fois la fiche disponible, le lien pourra être résolu explicitement :
sa création seule ne modifie pas la relation.

**Aucune résolution par nom n'est tentée.** Créer la fiche homonyme ne modifie
pas un lien existant — un test le démontre. Les noms sont culturellement
ambigus, et une fusion automatique de fiches serait une perte de donnée.

**Aucune relation inverse n'est créée.** `parent` n'engendre pas de `child`,
une alliance n'engendre pas sa réciproque : une seule ligne est écrite, celle
qui a été saisie.

### Règles et garanties, par portée

| Règle | Garantie en base | Validation de formulaire |
|---|---|---|
| Exactement une cible | `CheckConstraint entity_relation_exactly_one_target` | `clean()` : « Leave the target name empty… » / « Provide either a target entity or a target name. » |
| Pas de lien résolu vers soi-même | `CheckConstraint entity_relation_target_is_not_source` | `clean()` : « An entity cannot be related to itself. » |
| Unicité des liens résolus | `UniqueConstraint(from_entity, to_entity, kind)` conditionnelle sur `to_entity__isnull=False` | — |
| Unicité des liens cités | `UniqueConstraint(from_entity, to_name, kind)` conditionnelle sur `to_entity__isnull=True` | — |
| Nom composé uniquement d'espaces refusé | **non garantie** | `clean()` seulement |

Le dernier point mérite d'être lu précisément : `"   "` n'est pas la chaîne
vide, donc la contrainte `entity_relation_exactly_one_target` le laisse
passer. Seul `clean()` l'intercepte, en normalisant d'abord par `strip()` puis
en traitant le résultat vide comme une absence de cible. Un
`objects.create(to_name="   ")` serait donc accepté en base. Ce sera au service
d'import de normaliser les noms avant écriture.

Deux unicités complémentaires plutôt qu'une seule : une contrainte unique sur
`(from_entity, to_entity, kind)` ne protège pas les liens cités, `NULL` ne
participant pas à l'unicité en PostgreSQL. Les doublons exacts non résolus
sont donc couverts par la seconde contrainte. **Aucun rapprochement flou**
n'est effectué.

Plusieurs **types** de relation peuvent concerner la même paire de figures :
seul le triplet est unique. Trois tests couvrent ce point, dont un vérifiant
que deux sources différentes peuvent citer le même nom.

### Portée des suppressions en cascade

`CASCADE` sur les deux clés étrangères, conformément au schéma proposé dans
`docs/modele-donnees.md`. Conséquence à connaître : la suppression
**physique** d'une entité efface les liens où elle figure, y compris comme
**cible** — le lien n'est pas dégradé en `to_name`, il disparaît. Deux tests
fixent ce comportement.

L'API V1 utilisera la suppression logique, qui n'est pas implémentée dans cet
incrément ; cette portée n'est donc pas encore un problème pour les clients.

## 5. Migration et base de développement

`0004_entityrelation_entity_variant_of_and_more`, générée par Django :

```
+ Create model EntityRelation
+ Add field variant_of to entity
+ Create constraint entity_variant_of_is_not_self on model entity
+ Add field from_entity to entityrelation
+ Add field to_entity to entityrelation
+ Create constraint entity_relation_exactly_one_target on model entityrelation
+ Create constraint entity_relation_target_is_not_source on model entityrelation
+ Create constraint unique_resolved_relation on model entityrelation
+ Create constraint unique_unresolved_relation on model entityrelation
```

Appliquée sur PostgreSQL de développement. Données préservées, vérifié après
coup : `shango` existe toujours, ses `symbols` sont intacts, ses horodatages
restent au **13 octobre 2026** — la ligne n'a donc pas été réécrite —,
`variant_of` vaut `None` et `relations_from` est vide. Une seule entité en
base, zéro relation : **aucune donnée de démonstration persistante** n'a été
créée, et aucune migration de données n'a été écrite.

La capture JSON de la section 7 provient d'une **base de test jetable**, créée
puis détruite par un script du scratchpad.

## 6. Administration

`variant_of` ajouté aux champs d'autocomplétion de `EntityAdmin`.

`EntityRelationAdmin` : colonnes `from_entity`, `kind`, `to_entity`,
`to_name` ; filtre sur `kind` ; recherche sur `from_entity__name`,
`to_entity__name` et `to_name` ; autocomplétion sur les deux clés étrangères ;
`list_select_related` pour éviter un N+1 dans la liste d'administration.
Aucune interface personnalisée.

Les messages d'erreur de `clean()` sont en anglais, conformément à l'ADR 0003,
et s'affichent comme erreurs de formulaire plutôt qu'en `IntegrityError`.

## 7. API de lecture

La **liste** reste exactement aussi compacte qu'avant : `id`, `slug`, `name`,
`entity_type`, `category`. Un test le vérifie sur une entité porteuse d'une
variante et d'une relation.

Le **détail** ajoute deux clés :

- `variant_of` : référence synthétique, ou `null` ;
- `relations` : liste des relations **sortantes** (`relations_from`).

Une référence d'entité imbriquée contient uniquement `id`, `slug`, `name`,
`entity_type`. Chaque relation expose `id`, `kind`, `to_entity` — cet objet
synthétique ou `null` —, `to_name` et `notes`. Une cible résolue conserve
`to_name=""`. Sans lien : `variant_of=null` et `relations=[]`.

Le détail complet des cibles n'est **pas** imbriqué : il exposerait à son tour
ses propres `relations` et `variant_of`, donc une récursion. Un test vérifie
l'absence de ces clés dans une cible. Les relations **entrantes** et les
variantes inverses ne sont pas exposées, et aucun endpoint autonome n'est
ajouté. L'API reste strictement en lecture seule.

### JSON représentatif

`GET /api/entities/shango/`, extrait des parties nouvelles :

Cet extrait provient d'un jeu de test artificiel : le rattachement de Shango
à Mami Wata sert uniquement à vérifier la structure JSON et la différence
de types. Il ne représente pas une affirmation mythologique et ne doit pas
être repris dans le corpus canonique. Les autres associations de cet extrait
ne constituent pas non plus des données sourcées.

```json
{
  "slug": "shango",
  "name": "Shango",
  "entity_type": "divinity",
  "variant_of": {
    "id": "2613319c-f20b-4ef8-999c-066bf3eb9454",
    "slug": "mami-wata",
    "name": "Mami Wata",
    "entity_type": "creature"
  },
  "relations": [
    {
      "id": 2,
      "kind": "consort",
      "to_entity": null,
      "to_name": "Oya",
      "notes": ""
    },
    {
      "id": 1,
      "kind": "parent",
      "to_entity": {
        "id": "bc7f6184-9b02-43e8-993c-3bd2b9528754",
        "slug": "oranyan",
        "name": "Oranyan",
        "entity_type": "divinity"
      },
      "to_name": "",
      "notes": "Royal line of Oyo."
    }
  ]
}
```

Dans ce jeu technique, la référence est de type `creature` et l'entité de
type `divinity` : cette différence est autorisée par le modèle ; sa pertinence
culturelle doit être établie séparément pour de véritables données.

### Ordre déterministe

`Meta.ordering = ["kind", "to_name", "id"]`. L'ordre est donc stable entre
deux requêtes, ce qui est nécessaire à la reproductibilité des réponses et à
la future pagination. Dans l'exemple ci-dessus, `consort` précède `parent` par
ordre alphabétique de `kind`. Deux tests vérifient cet ordre, dont un sur
trois relations mêlant cibles résolues et citées.

## 8. Budget de requêtes

Le queryset de détail joint `variant_of` par `select_related`, et précharge
les relations sortantes par un `Prefetch` dont le queryset applique
`select_related("to_entity")`. Les préchargements existants — profils,
ancrages, quatre collections de référentiels — sont conservés.

| Cas | Attendu | Mesuré |
|---|---|---|
| Détail entièrement relié : variante, 3 relations dont 2 résolues, référentiels, profil | 6 | 6 |
| Détail d'une entité sans aucun rattachement, pour chacun des trois types | 6 | 6 |
| Sérialisation après évaluation du queryset réel de la vue | 0 | 0 |

Décompte : **1** requête pour l'entité, qui ramène par jointure les trois
profils, les trois ancrages principaux et la figure de référence, puis **5**
requêtes de préchargement — quatre collections de référentiels et les
relations sortantes. Une collection sortante préchargée ajoute **une** requête,
pas une par cible : les trois relations et leurs cibles résolues tiennent dans
cette unique requête.

Le budget global est passé de 5 à 6 par rapport à l'incrément précédent, du
fait du `Prefetch` des relations. Comme pour les quatre collections, Django
l'exécute même lorsqu'il n'y a aucune relation.

**Ce que chaque test prouve réellement.** Le budget global ne démontre pas la
présence de chaque préchargement : pour une entité unique, une collection non
préchargée coûterait aussi une requête. C'est
`test_detail_precharge_se_serialise_sans_requete` qui apporte la preuve — il
évalue le queryset réel de la vue, puis impose **zéro requête** pendant la
sérialisation. Il a été enrichi pour cet incrément d'une variante, de deux
relations résolues et d'une cible absente ; il vérifie en outre que les noms
des cibles résolues sont lus sans requête, ce qui atteste du
`select_related("to_entity")` interne au `Prefetch`.

## 9. Tests

**110 cas exécutés** dans le dépôt, dont 37 ajoutés par cet incrément.
Répartition réelle obtenue par `pytest --collect-only` :

| Fichier | Cas |
|---|---|
| `mythology/tests/test_relations.py` | 31 |
| `mythology/tests/test_api.py` | 29 |
| `mythology/tests/test_reference.py` | 28 |
| `mythology/tests/test_profiles.py` | 11 |
| `mythology/tests/test_models.py` | 7 |
| `tests/` (socle) | 4 |

### `test_relations.py` — 31 cas

Variantes : autonomie de la variante, type différent de la référence,
caractère facultatif, auto-référence refusée par `full_clean()` **et** en
base (deux tests), `ProtectedError` à la suppression d'une référence citée,
cycle indirect non détecté.

Relations : sens de lecture, absence de relation inverse, cible résolue, cible
citée, absence de rapprochement par nom, deux cibles refusées en base et par
`full_clean()`, aucune cible refusée en base et par `full_clean()`, nom blanc
refusé par `clean()`, normalisation du nom, auto-lien refusé en base et par
`full_clean()`, doublon résolu, doublon cité, plusieurs types pour une paire,
même nom sous deux types, deux sources citant le même nom, cascade depuis la
source, cascade depuis la cible, liste des types disponibles, type inconnu
refusé, ordre déterministe, relations portées par un héros.

### `test_api.py` — 6 cas ajoutés

Liste n'exposant ni variante ni relations ; détail exposant la figure de
référence avec son jeu de clés exact ; détail sans variante ni relation ;
détail exposant les relations sortantes avec vérification du jeu de clés, de
l'ordre, de `to_name=""` sur une cible résolue et des `notes` ; absence
d'imbrication du détail des cibles ; absence des relations entrantes.

Deux tests existants ont vu leur budget passer de 5 à 6 requêtes, et le test
de sérialisation sans requête a été enrichi.

## 10. Contrôles

Exécutés une fois sur la version finale. Aucune valeur du `.env` n'est
affichée ici.

| Commande | Sortie | Code |
|---|---|---|
| `python manage.py check` | `System check identified no issues (0 silenced).` | 0 |
| `python manage.py makemigrations --check --dry-run` | `No changes detected` | 0 |
| `python manage.py showmigrations mythology` | `[X] 0001_initial`, `[X] 0002_creatureprofile_heroprofile`, `[X] 0003_domain_country_entity_primary_country_and_more`, `[X] 0004_entityrelation_entity_variant_of_and_more` | 0 |
| `pytest` | `110 passed in 4.27s` | 0 |
| `ruff check .` | `All checks passed!` | 0 |
| `ruff format --check .` | `29 files already formatted` | 0 |
| `mypy .` | `Success: no issues found in 29 source files` | 0 |

Deux corrections intermédiaires ont été nécessaires, suivies d'une relance des
seuls contrôles affectés : une erreur `mypy union-attr` sur
`EntityRelation.__str__`, où `self.to_entity_id` ne suffisait pas à écarter
`None` — remplacé par `self.to_entity is not None` — et un passage de
`ruff format` sur deux fichiers.

## 11. Divergences avec le prompt

Deux ajustements, tous deux nécessaires et signalés.

**Deux budgets de requêtes existants ont été relevés de 5 à 6.**
`test_detail_entierement_relie_ne_provoque_pas_de_n_plus_un` et
`test_detail_a_un_cout_constant_quel_que_soit_le_type` attendaient 5 requêtes.
Le `Prefetch` des relations en ajoute une, exécutée même sans relation. Le
prompt demandait d'adapter le budget au coût réel : c'est fait, avec le
décompte expliqué dans les docstrings. Le prompt demandait aussi de ne pas
présenter le budget global comme une preuve de préchargement — les deux
docstrings le disent désormais explicitement et renvoient au test à zéro
requête.

**La docstring du module `models.py` a été actualisée.** Elle annonçait encore
`variant_of` et `EntityRelation` comme « restant à venir », ce qui devenait
faux. Seul `Source`, le workflow et la suppression logique y figurent encore.

Aucune autre divergence : les champs, contraintes, `related_name`, choix,
clés JSON et interdictions — pas de relation inverse, pas de résolution par
nom, pas de récursion, pas d'endpoint autonome — correspondent au prompt.

## 12. Limites reportées

- **Cycles indirects de variantes** — non détectés, par choix.
- **Nom cible composé d'espaces** — refusé par `clean()` seulement ; un appel
  ORM direct passerait. À normaliser dans le service d'import.
- **Résolution des cibles citées** — manuelle ; aucune reprise automatique
  lorsqu'une fiche homonyme apparaît. L'import pilote décidera du traitement.
- **Relations entrantes et variantes inverses** — non exposées par l'API.
- **Suppression logique** — non implémentée ; `CASCADE` s'applique donc à la
  suppression physique, y compris pour les liens dont l'entité est la cible.
- **Cohérence `entity_type` / profil** — toujours non garantie hors
  `full_clean()`.
- **Règle « principal ≠ secondaire »** sur les référentiels — toujours non
  imposée, comme à l'incrément précédent.
- **Libellés publics en français** — les `verbose_name` des nouveaux modèles
  suivent la convention existante ; leur normalisation en anglais reste une
  tâche de roadmap au titre de l'ADR 0003. Les valeurs techniques et les
  nouveaux messages d'erreur sont bien en anglais.
- **`Source`, workflow, rôles, import, rendu, carte** — incréments et phases
  suivants.

## 13. État Git final

Aucun commit, aucun push, aucun `git add` : l'index est vide.

```
# afrimyth-api
## main...origin/main
 M mythology/admin.py
 M mythology/models.py
 M mythology/serializers.py
 M mythology/tests/factories.py
 M mythology/tests/test_api.py
 M mythology/views.py
?? docs/reports/phase-2-increment-3-relations.md
?? mythology/migrations/0004_entityrelation_entity_variant_of_and_more.py
?? mythology/tests/test_relations.py

# django-portfolio
## main...origin/main
?? docs/prompts/phase-2-increment-3-relations.md
```

Les deux branches sont `main` et synchronisées avec `origin/main`. `_audit/`
et `.claude/` sont ignorés par le `.gitignore` de `django-portfolio` et
n'apparaissent pas. La roadmap n'a pas été modifiée : sa validation appartient
à la relecture, après laquelle Codex prendra en charge la clôture Git.

## 14. Relecture Codex

La lecture des modèles, de la migration, des serializers, du queryset et des
tests n'a révélé aucun blocage fonctionnel par rapport au prompt. Deux
précisions documentaires ont été appliquées directement : la résolution d'un
lien cité est explicite, jamais déclenchée par la seule création d'une fiche ;
le JSON représentatif utilise des associations artificielles et n'est pas une
source de faits mythologiques. La docstring d'`EntityRelation` a été précisée
dans le même sens, sans changement de comportement.

Les 110 tests et les contrôles qualité ci-dessus ont été exécutés par Claude.
Codex a vérifié le diff et l'identité des copies du rapport ; la suite n'est
pas relancée pour ces précisions documentaires. La revue pédagogique avec
l'auteur est terminée et validée le 18 octobre 2026.

## 15. Clôture pédagogique

L'auteur a revu la distinction entre variante culturelle et relation entre
figures, les cibles résolues ou simplement nommées, l'exclusivité des deux
champs de cible, l'unicité des liens et leur représentation JSON. Plusieurs
conjoints distincts sont autorisés : l'unicité porte sur source, cible et type
de relation, jamais sur le seul couple source/type.

La roadmap coche la tâche des relations entre entités. Les contraintes
générales et les requêtes restent des tâches transverses ouvertes. Les états
Git de la section 13 et l'attente de revue des premières sections sont des
captures antérieures à cette clôture. Aucun changement fonctionnel n'a suivi
les contrôles de Claude ; les résultats acquis sont réutilisés.
