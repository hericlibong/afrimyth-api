# Rapport — Phase 2, incrément 4 : sources documentaires

- **Date :** 18 octobre 2026
- **Dépôt :** `afrimyth-api`
- **Branche :** `main`
- **Statut :** revue technique et pédagogique validée le 18 octobre 2026 ; prêt pour clôture Git

## 1. Objectif et périmètre

Permettre de rattacher plusieurs références documentaires à une fiche, puis de
les consulter dans le détail de l'API. C'est la tâche « Ajouter les sources
documentaires » de la phase 2.

Hors périmètre, conformément au prompt : workflow, rôles, permissions,
suppression logique, services d'écriture, import, rendu, carte,
authentification, nouvelle architecture. Aucun endpoint autonome de source.

La roadmap n'a **pas** été cochée, rien n'a été committé ni poussé.

## 2. Fichiers changés

**Créés**

- `mythology/migrations/0005_source.py` — générée par `makemigrations`
- `mythology/tests/test_sources.py` — 25 cas
- `docs/reports/phase-2-increment-4-sources.md` — ce rapport

**Modifiés**

- `mythology/models.py` — `SourceKind`, `Source`, docstring du module
  actualisée
- `mythology/admin.py` — `SourceAdmin`
- `mythology/serializers.py` — `SourceSerializer`, détail élargi à `sources`
- `mythology/views.py` — `sources` ajouté au `prefetch_related` du détail
- `mythology/tests/factories.py` — `create_source`
- `mythology/tests/test_sources.py` — nouveau module
- `mythology/tests/test_api.py` — cinq tests ajoutés, deux budgets de requêtes
  relevés, test de sérialisation enrichi

Aucune migration existante n'a été touchée. Aucune app ni abstraction
supplémentaire.

## 3. Modèle `Source`

| Champ | Définition |
|---|---|
| `entity` | `ForeignKey(Entity, on_delete=CASCADE, related_name="sources")` |
| `label` | `CharField(max_length=255)`, requis |
| `kind` | `CharField(max_length=20, choices=SourceKind.choices)`, requis, sans défaut |
| `url` | `URLField(max_length=2048, blank=True)` — absence représentée par `""` |
| `accessed_at` | `DateField(null=True, blank=True)` |
| `notes` | `TextField(blank=True)` |

`SourceKind` porte six valeurs techniques anglaises avec libellés anglais :
`book` / Book, `article` / Article, `encyclopedia` / Encyclopedia,
`museum` / Museum, `oral` / Oral tradition or testimony, `other` / Other.

`Meta.ordering = ["label", "id"]` — ordre déterministe, le `id` départageant
deux références homonymes. `__str__` renvoie
`« Fictional Museum Catalogue (book) — Shango »`.

### Choix de modélisation

**Une source appartient à une seule entité.** Pas de catalogue partagé, pas de
`ManyToManyField`. La même référence bibliographique peut donc être saisie
pour plusieurs fiches, ce qui crée des lignes distinctes. Mutualiser
supposerait une identité bibliographique stable — édition, pagination, tirage
— que le corpus ne fournit pas.

**Aucun champ bibliographique supplémentaire.** `label` reste libre : titre
d'ouvrage, nom de site, cote de musée, description d'un témoignage. Auteur,
pages, édition ou contexte d'entretien vont dans `notes`. Le corpus V2 ne
contient aujourd'hui **aucune** source — 0 sur 44 entités — et construire un
modèle bibliographique complet avant d'avoir une seule donnée réelle serait
prématuré.

**Aucune unicité** sur `label`, `url` ou leur combinaison : deux éditions,
deux pages ou deux usages d'une même référence sont légitimes. Écarter les
doublons relève du contrôle éditorial, pas de la structure de la base. Un test
fixe explicitement ce comportement.

**`accessed_at` est une date de consultation**, non de publication. Elle peut
être renseignée sans URL — date d'un entretien, d'une visite de musée. Aucune
valeur n'est remplie automatiquement, ce qu'un test vérifie.

**Aucun accès réseau.** Ni vérification de disponibilité de l'URL, ni liste de
domaines autorisés, ni téléchargement. Seul le **format** est validé.

### Règles et portée réelle des garanties

| Règle | Garantie en base | Validation Django |
|---|---|---|
| Une source disparaît avec sa fiche | `on_delete=CASCADE` | — |
| `label` et `kind` obligatoires | **non** (`NOT NULL` mais `""` accepté) | `full_clean()` |
| `kind` limité aux six valeurs | **non** | `full_clean()` |
| Format de l'URL | **non** | `full_clean()` via `URLField` |
| `label` non composé uniquement d'espaces | **non** | `clean()` seulement |
| Ordre déterministe | `Meta.ordering` | — |

Ce tableau est le point important du rapport. **Aucune de ces validations
n'est une contrainte PostgreSQL** : `save()` ne déclenche pas `full_clean()`.
Concrètement, `Source.objects.create(entity=e, label="   ", kind="podcast")`
serait **accepté en base** — le `kind` inconnu comme le libellé blanc. Les
garanties ne portent que sur les chemins passant par `full_clean()` :
formulaires et administration Django.

Deux tests documentent cette asymétrie plutôt que de la masquer :
`test_libelle_blanc_refuse_par_full_clean` pour la validation, et
`test_libelle_blanc_passe_en_ecriture_directe` pour la limite réelle. La
normalisation incombera au service d'import.

`clean()` normalise `label` par `strip()` avant de refuser le résultat vide ;
un libellé entouré d'espaces est donc accepté et nettoyé.

## 4. Migration et base de développement

`0005_source`, générée par Django :

```
Migrations for 'mythology':
  mythology\migrations\0005_source.py
    + Create model Source

Applying mythology.0005_source... OK
```

Appliquée sur PostgreSQL de développement. Données préservées, vérifié après
coup :

- `shango` existe toujours, type `divinity` ;
- ses `symbols` sont intacts : `['Hache à double tranchant', 'Foudre']` ;
- ses horodatages restent au **13 octobre 2026** — la ligne n'a donc pas été
  réécrite ;
- `shango.sources` est vide.

Une seule entité en base, **zéro source**, zéro relation : aucune donnée de
démonstration persistante n'a été créée, et aucune migration de données n'a
été écrite. La capture JSON de la section 6 provient d'une **base de test
jetable**, créée puis détruite par un script du scratchpad.

## 5. Administration

`SourceAdmin` : colonnes `label`, `entity`, `kind`, `accessed_at` ; filtre sur
`kind` ; recherche sur `label` et `entity__name` ; autocomplétion de `entity` ;
`list_select_related = ["entity"]` pour éviter un N+1 dans la liste
d'administration. Aucun formulaire ni interface personnalisée.

Le message de refus d'un libellé blanc — « Provide a non-empty source
label. » — est en anglais, conformément à l'ADR 0003, et s'affiche comme
erreur de formulaire.

`CASCADE` retire les sources lors d'une suppression **physique** de leur
entité. La suppression logique, prévue plus tard, ne déclenchera pas ce
mécanisme.

## 6. API de lecture

La **liste** garde exactement ses clés actuelles : `id`, `slug`, `name`,
`entity_type`, `category`. Un test le vérifie sur une entité porteuse d'une
source. La liste ne charge pas les sources.

Le **détail** ajoute `sources`, liste d'objets portant exactement `id`,
`label`, `kind`, `url`, `accessed_at`, `notes`. Le serializer est imbriqué et
en lecture seule ; `entity` n'est pas réexposé, la source étant déjà lue
depuis sa fiche. Sans source : `sources=[]`. Sans URL : `url=""`. Sans date :
`accessed_at=null`. Une date renseignée est exposée au format `YYYY-MM-DD`.

L'API reste strictement en lecture seule, et aucun endpoint autonome de source
n'est ajouté.

### JSON représentatif — **références fictives**

`GET /api/entities/shango/`, clé `sources` seule. Les trois références
ci-dessous sont **inventées pour la démonstration** ; aucune publication
réelle n'est citée, et aucune source n'est attribuée au corpus.

```json
{
  "sources": [
    {
      "id": 1,
      "label": "Fictional Encyclopedia of Imaginary Myths",
      "kind": "encyclopedia",
      "url": "https://example.invalid/fictional-entry",
      "accessed_at": "2026-05-20",
      "notes": "Volume 2, page 118 — fictional reference for demonstration."
    },
    {
      "id": 3,
      "label": "Fictional Handbook of Test Myths",
      "kind": "book",
      "url": "",
      "accessed_at": null,
      "notes": ""
    },
    {
      "id": 2,
      "label": "Fictional oral testimony, village of Testville",
      "kind": "oral",
      "url": "",
      "accessed_at": "2026-03-14",
      "notes": "Fictional interview, recorded for demonstration purposes."
    }
  ]
}
```

Noter l'ordre : trié par `label`, donc `id` 1, 3, 2. Le livre sans lien porte
`url=""` et `accessed_at=null` ; le témoignage oral a une date de consultation
sans URL.

Le domaine `example.invalid` est réservé par la RFC 2606 : il ne peut
désigner aucun site réel.

## 7. Budget de requêtes

`sources` a été ajouté au `prefetch_related` du détail, les autres jointures
et préchargements étant conservés.

| Cas | Attendu | Mesuré |
|---|---|---|
| Détail entièrement relié : variante, 3 relations, 2 sources, référentiels, profil | 7 | 7 |
| Détail d'une entité sans aucun rattachement, pour chacun des trois types | 7 | 7 |
| Sérialisation après évaluation du queryset réel de la vue | 0 | 0 |

Décompte : **1** requête pour l'entité, qui ramène par jointure les trois
profils, les trois ancrages principaux et la figure de référence, puis **6**
requêtes de préchargement — quatre collections de référentiels, les relations
sortantes et les sources. Le budget passe donc de 6 à 7 : **une seule**
requête supplémentaire pour toutes les sources d'une fiche, quel qu'en soit le
nombre. Comme les autres préchargements, Django l'exécute même sans aucune
source.

**Ce que chaque test prouve.** Le budget global ne démontre pas la présence du
préchargement : pour une entité unique, une collection non préchargée
coûterait aussi une requête. C'est
`test_detail_precharge_se_serialise_sans_requete` qui l'établit — il évalue le
queryset réel de la vue puis impose **zéro requête** pendant la sérialisation.
Il a été enrichi de **trois sources** et vérifie leur ordre dans la charge
utile, en plus de la variante, des deux relations résolues et de la cible
absente déjà couvertes.

## 8. Tests

**140 cas exécutés**, dont 30 ajoutés par cet incrément. Répartition réelle
obtenue par `pytest --collect-only` :

| Fichier | Cas |
|---|---|
| `mythology/tests/test_api.py` | 34 |
| `mythology/tests/test_relations.py` | 31 |
| `mythology/tests/test_reference.py` | 28 |
| `mythology/tests/test_sources.py` | 25 |
| `mythology/tests/test_profiles.py` | 11 |
| `mythology/tests/test_models.py` | 7 |
| `tests/` (socle) | 4 |

Toutes les références employées par les tests sont **fictives** et
identifiées comme telles, en anglais, conformément au prompt. Le module
`test_sources.py` l'indique dans sa docstring, et `create_source` dans la
sienne.

### `test_sources.py` — 25 cas

Création et rattachement : plusieurs sources ordonnées par référence, entité
sans source, même référence sur deux entités, doublon exact autorisé sur une
même entité, représentation lisible.

Champs facultatifs : source sans URL ni date, source orale avec date et notes
mais sans URL, date de consultation sans URL, URL et date renseignées, aucune
valeur remplie automatiquement.

Validation : les six `kind` valides acceptés (test paramétré), `kind` inconnu
refusé, `label` vide refusé, `label` blanc refusé par `full_clean()`, `label`
blanc **accepté** en écriture directe — limite documentée —, normalisation du
libellé, URL invalide refusée.

Suppressions : cascade depuis l'entité, suppression d'une seule source
préservant la fiche et les autres sources, sources portées par un héros.

### `test_api.py` — 5 cas ajoutés

Liste n'exposant pas les sources ; détail exposant les sources avec le jeu de
clés exact, le format de date ISO et l'absence de réimbrication de l'entité ;
détail sans source ; source sans URL ni date ; ordre déterministe sur trois
sources.

### Non-régression

Les 110 cas antérieurs passent, à l'exception des deux budgets de requêtes
relevés de 6 à 7 pour la raison expliquée en section 9. Profils,
référentiels, variantes et relations conservent leur comportement.

## 9. Contrôles

Exécutés une fois sur la version finale. Aucune valeur du `.env` n'est
affichée.

| Commande | Sortie | Code |
|---|---|---|
| `python manage.py check` | `System check identified no issues (0 silenced).` | 0 |
| `python manage.py makemigrations --check --dry-run` | `No changes detected` | 0 |
| `python manage.py showmigrations mythology` | `[X]` sur les cinq migrations, dont `0005_source` | 0 |
| `pytest` | `140 passed in 4.56s` | 0 |
| `ruff check .` | `All checks passed!` | 0 |
| `ruff format --check .` | `30 files already formatted` | 0 |
| `mypy .` | `Success: no issues found in 30 source files` | 0 |

Une seule correction intermédiaire, suivie de la relance des seuls contrôles
affectés : `ruff check` a signalé `I001` sur l'ordre des imports de
`test_api.py`, l'ajout de `import datetime` ayant été placé après les imports
tiers. Corrigé par `ruff check --fix`.

## 10. Divergences avec le prompt

Deux ajustements, tous deux prévus par le prompt lui-même ou rendus
nécessaires.

**Les deux budgets de requêtes existants sont passés de 6 à 7.**
`test_detail_entierement_relie_ne_provoque_pas_de_n_plus_un` et
`test_detail_a_un_cout_constant_quel_que_soit_le_type`. Le prompt annonçait ce
passage « normalement de six à sept requêtes » : c'est bien ce qui est
constaté. Les docstrings portent le décompte détaillé et rappellent que le
budget global ne prouve pas le préchargement.

**La docstring du module `models.py` a été actualisée.** Elle annonçait
`Source` comme « restant à venir », ce qui devenait faux. Ne figurent plus que
le workflow éditorial et les champs de suppression logique.

Aucune autre divergence : champs, choix, `related_name`, ordre, clés JSON,
absence d'unicité, absence d'endpoint autonome et absence d'accès réseau
correspondent au prompt.

## 11. Limites reportées

- **Libellé blanc et `kind` inconnu en écriture directe** — acceptés en base ;
  seules les validations Django les refusent. À normaliser dans le service
  d'import.
- **Pas de catalogue bibliographique partagé** — la même référence saisie pour
  dix entités crée dix lignes. À réexaminer si un besoin de dédoublonnage
  éditorial apparaît, sur la base de données réelles.
- **Aucune vérification de disponibilité des URL** — ni au moment de la
  saisie, ni périodiquement.
- **Aucun endpoint autonome de source**, ni filtre, ni recherche par source :
  phase 3 si un besoin client est confirmé.
- **Suppression logique** — non implémentée ; `CASCADE` ne concerne donc que
  la suppression physique.
- **Corpus sans source** — les 44 entités de V2 n'en contiennent aucune. Le
  modèle est prêt, mais son remplissage est un travail éditorial, non un
  import automatique.
- **Libellés publics en français** — les `verbose_name` du nouveau modèle
  suivent la convention existante ; leur normalisation en anglais reste une
  tâche de roadmap au titre de l'ADR 0003. Les valeurs techniques, les
  libellés de `SourceKind` et le message d'erreur sont en anglais.

## 12. État Git final

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
?? docs/reports/phase-2-increment-4-sources.md
?? mythology/migrations/0005_source.py
?? mythology/tests/test_sources.py

# django-portfolio
## main...origin/main
?? docs/prompts/phase-2-increment-4-sources.md
```

Les deux branches sont `main` et synchronisées avec `origin/main`. `_audit/`
et `.claude/` sont ignorés par le `.gitignore` de `django-portfolio`. La
roadmap n'a pas été modifiée : après validation pédagogique, Codex effectuera
la clôture documentaire, les commits et les pushes.

## 13. Validation de revue et clôture

Codex a relu les modèles, la migration, l'administration, les serializers,
le queryset et les tests ; aucun blocage fonctionnel n'a été relevé. Les
copies du rapport étaient identiques. Les résultats acquis de Claude
(140 tests et contrôles qualité validés) sont réutilisés : aucun code
fonctionnel n'a changé pendant cette revue.

L'auteur a validé la revue pédagogique et l'exercice ORM le 18 octobre 2026.
La référence fictive a été créée avec `full_clean()` et `save()`, puis
consultée. Le rollback ayant été saisi après la sortie du bloc atomique,
l'enregistrement avait été validé ; l'auteur a ensuite supprimé la seule
source créée via `source.delete()`. Sa sortie `(1, {'mythology.Source': 1})`
et `list(shango.sources.values('label', 'kind')) == []` confirment le nettoyage
de l'exercice et la conservation de la fiche.

La tâche des sources est cochée dans la roadmap. La section 12 conserve
l'état Git de fin d'implémentation, antérieur à cette clôture. Codex prend
en charge les commits et les pushes normaux selon l'autorisation permanente.
