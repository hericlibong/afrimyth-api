# Rapport — Phase 2, incrément 5 : propriété et état éditorial

- **Date :** 18 octobre 2026
- **Dépôt :** `afrimyth-api`
- **Branche :** `main`
- **Statut :** revue technique et pédagogique validée le 20 octobre 2026 ; prêt pour clôture Git

## 1. Objectif et périmètre

Préparer les champs de plateforme de `Entity` : propriété, état éditorial,
traces de revue et suppression logique. Déclarer les deux managers prévus par
la décision 7 de l'ADR 0002 et brancher la vue sur le manager `active`.

Ces champs sont **posés, non pilotés**. Hors périmètre, conformément au
prompt : groupes et permissions, services de transition, CRUD, restauration,
attribution automatique du propriétaire, machine à états — tout cela relève de
la phase 4. Le filtrage éditorial sur les seules fiches publiées relève de la
phase 3. L'API reste strictement en lecture seule.

La roadmap n'a **pas** été cochée, rien n'a été committé ni poussé.

## 2. Fichiers changés

**Créés**

- `mythology/migrations/0006_entity_created_by_entity_deleted_at_and_more.py`
  — générée par `makemigrations`
- `mythology/tests/test_editorial_fields.py` — 22 cas
- `docs/reports/phase-2-increment-5-editorial-fields.md` — ce rapport

**Modifiés**

- `mythology/models.py` — `EntityStatus`, `ActiveEntityManager`, les huit
  champs de plateforme de `Entity`, les deux managers, docstring du module
  actualisée
- `mythology/admin.py` — `EntityAdmin` : colonnes, filtres et champs en
  lecture seule
- `mythology/views.py` — passage de `Entity.objects` à `Entity.active`, avec
  la portée documentée
- `mythology/tests/test_api.py` — sept tests ajoutés, constante
  `INTERNAL_KEYS`

Aucune migration existante n'a été touchée. Les serializers n'ont **pas** été
modifiés : les nouveaux champs restent internes.

## 3. Champs ajoutés à `Entity`

| Champ | Définition |
|---|---|
| `created_by` | `FK(settings.AUTH_USER_MODEL, SET_NULL, null, blank, related_name="created_entities")` |
| `status` | `CharField(max_length=20, choices=EntityStatus.choices, default=EntityStatus.DRAFT)` |
| `submitted_at` | `DateTimeField(null=True, blank=True)` |
| `reviewed_at` | `DateTimeField(null=True, blank=True)` |
| `reviewed_by` | `FK(settings.AUTH_USER_MODEL, SET_NULL, null, blank, related_name="reviewed_entities")` |
| `review_notes` | `TextField(blank=True)` |
| `deleted_at` | `DateTimeField(null=True, blank=True)` |
| `deleted_by` | `FK(settings.AUTH_USER_MODEL, SET_NULL, null, blank, related_name="deleted_entities")` |

`EntityStatus` porte quatre valeurs techniques et libellés anglais :
`draft` / Draft, `submitted` / Submitted, `published` / Published,
`rejected` / Rejected.

**Aucun statut `deleted`.** La suppression logique est portée séparément par
`deleted_at`, de sorte qu'une fiche supprimée conserve l'état éditorial
qu'elle avait. Un champ unique mêlant les deux notions obligerait à choisir
entre « était publiée » et « est supprimée ». Un test vérifie que `deleted`
n'est pas une valeur de `EntityStatus`.

**`SET_NULL` sur les trois acteurs.** Supprimer un compte ne supprime aucune
fiche et vide seulement les clés étrangères concernées. C'est précisément
pourquoi **aucune contrainte ne lie acteur, date et statut** : une date de
revue historique peut légitimement subsister avec un relecteur devenu nul.
Un test le démontre.

**Rien n'est rempli automatiquement.** Aucun `save()` surchargé, aucun signal.
Changer `status` ne pose ni `submitted_at` ni `reviewed_at` — un test le
constate. `created_at` et `updated_at` conservent leur comportement.

Aucun champ `role` sur l'utilisateur, aucun `is_deleted`, aucun second champ
de vérification redondant. Les groupes Django viendront en phase 4.

### Portée réelle des garanties

| Règle | Garantie en base | Validation Django |
|---|---|---|
| Statut par défaut `draft` | `default` au niveau Django, appliqué à l'`INSERT` | — |
| `status` limité aux quatre valeurs | **non** | `full_clean()` |
| Supprimer un compte n'efface pas la fiche | `on_delete=SET_NULL` | — |
| Acteurs facultatifs | `null=True` | — |
| Pas de lien imposé entre acteur, date et statut | aucune contrainte, **par choix** | — |

Point à lire précisément : **la base n'énumère pas les statuts.**
`Entity.objects.create(status="archived")` serait accepté — seul
`full_clean()` le refuse. Deux tests fixent cette asymétrie plutôt que de la
masquer : `test_statut_inconnu_refuse_par_full_clean` et
`test_statut_inconnu_passe_en_ecriture_directe`. La validation des
transitions appartiendra aux services de la phase 4.

Il n'y a **aucune machine à états** : `status` est un champ libre parmi quatre
valeurs validées, rien n'interdit de passer directement de `draft` à
`published` par l'ORM.

## 4. Managers effectifs

```python
objects = models.Manager()        # déclaré en premier → manager par défaut
active = ActiveEntityManager()    # filtre deleted_at__isnull=True
```

`objects` est déclaré en premier, donc **manager par défaut** : vérifié par
test, `Entity._default_manager.name == "objects"`. Conséquence voulue par
l'ADR 0002 — ni l'administration, ni le parcours des relations, ni une future
restauration ne masquent silencieusement de lignes.

`ActiveEntityManager.get_queryset()` ne filtre **que** `deleted_at`. Le statut
éditorial n'entre pas en jeu : un test paramétré sur les quatre statuts le
confirme. Aucune bibliothèque de soft delete, aucun `delete()` personnalisé,
aucun comportement de suppression modifié.

| Manager | Fiches visibles |
|---|---|
| `Entity.objects` | toutes, y compris supprimées logiquement |
| `Entity.active` | uniquement `deleted_at IS NULL`, tous statuts confondus |

## 5. API et limite de visibilité

`EntityViewSet.get_queryset()` part désormais de `Entity.active`, pour la
liste comme pour le détail, en conservant intégralement les `select_related`
et `prefetch_related` existants.

- une fiche marquée supprimée disparaît de la liste ;
- son URL renvoie **404**, la ligne existant toujours en base ;
- le filtrage ne dépend pas de `status` : une fiche `draft`, `submitted`,
  `published` ou `rejected` reste accessible à ce stade. Un test paramétré sur
  les quatre statuts le vérifie.

Les serializers sont **inchangés** : ni compte, ni email, ni nom, ni note
privée de relecture, ni champ de suppression n'apparaît dans l'API. Deux tests
le contrôlent, dont un qui cherche la chaîne de la note privée dans la charge
utile brute, afin d'attraper une fuite même sous une autre clé. Aucun endpoint
ni méthode d'écriture n'a été ajouté.

### Limite à traiter avant la livraison publique de la phase 3

**Le manager `active` filtre la racine de la vue, pas les cibles imbriquées.**
Une fiche supprimée logiquement reste exposée comme `variant_of` ou comme
cible d'une relation, car ces objets sont atteints par les relations et non
par le queryset racine. Le test
`test_cible_imbriquee_supprimee_reste_visible` fixe ce comportement réel pour
qu'il soit constaté maintenant.

Il serait donc faux d'affirmer que le manager règle à lui seul la
confidentialité de tout le graphe. La visibilité cohérente des cibles selon
leur statut et leur suppression devra être traitée avant la livraison publique
de la phase 3 — probablement par des querysets de préchargement filtrés, dans
la méthode réutilisable de sélection des objets visibles que la roadmap prévoit
déjà.

## 6. Migration et base de développement

`0006_entity_created_by_entity_deleted_at_and_more`, générée par Django, avec
la dépendance appropriée vers le modèle utilisateur :

```python
dependencies = [
    ("mythology", "0005_source"),
    migrations.swappable_dependency(settings.AUTH_USER_MODEL),
]
```

Huit `AddField`, aucune modification des migrations précédentes.

Appliquée sur PostgreSQL de développement. État de `shango` vérifié après
coup :

| Champ | Valeur |
|---|---|
| `status` | `'draft'` |
| `created_by`, `reviewed_by`, `deleted_by` | `None` |
| `submitted_at`, `reviewed_at`, `deleted_at` | `None` |
| `review_notes` | `''` |
| `created_at`, `updated_at` | **13 octobre 2026**, inchangés |
| `symbols` | `['Hache à double tranchant', 'Foudre']`, intacts |

La fiche n'a donc pas été publiée automatiquement, ne s'est vu inventer aucun
propriétaire, et ses autres données n'ont pas été réécrites. Les horodatages
inchangés prouvent que la ligne n'a pas été réécrite.

Base de développement : 1 entité, 0 source, 0 relation, 1 compte préexistant.
**Aucune donnée de démonstration persistante** n'a été créée, et aucune
migration de données n'a été écrite. Les tests travaillent exclusivement sur
la base de test de pytest.

## 7. Administration

`EntityAdmin` affiche `status` et `created_by` en colonnes, avec `status` en
tête des filtres. Le queryset reste **complet** : l'administration utilise le
manager par défaut, donc les fiches supprimées logiquement y restent
consultables — condition nécessaire à une restauration en phase 4. Un test
compare les deux : l'administration voit les deux fiches, `Entity.active`
n'en voit qu'une.

Champs en lecture seule : `id`, `created_at`, `updated_at`, `submitted_at`,
`reviewed_at`, `deleted_at`, `deleted_by`. Ces horodatages seront posés par
les services de transition, non saisis à la main.

Restent modifiables : `status`, `created_by`, `reviewed_by`, `review_notes`.
Cela permet de préparer manuellement des statuts et des jeux de test ; **cela
ne constitue ni une implémentation de la matrice de permissions, ni du
workflow.** Un test vérifie cette répartition.

Aucune action de publication, de suppression logique ou de restauration n'a
été ajoutée, ni aucune gestion de rôles. `delete()` et les suppressions
physiques ne sont pas modifiés.

## 8. Tests

**171 cas exécutés**, dont 31 ajoutés par cet incrément. Répartition réelle
obtenue par `pytest --collect-only` :

| Fichier | Cas |
|---|---|
| `mythology/tests/test_api.py` | 43 |
| `mythology/tests/test_relations.py` | 31 |
| `mythology/tests/test_reference.py` | 28 |
| `mythology/tests/test_sources.py` | 25 |
| `mythology/tests/test_editorial_fields.py` | 22 |
| `mythology/tests/test_profiles.py` | 11 |
| `mythology/tests/test_models.py` | 7 |
| `tests/` (socle) | 4 |

### `test_editorial_fields.py` — 22 cas

Valeurs par défaut et statuts : valeurs par défaut des huit champs, les quatre
statuts acceptés par `full_clean()` (test paramétré), statut inconnu refusé
par `full_clean()`, statut inconnu **accepté** en écriture directe — limite
documentée —, absence de statut `deleted`.

Acteurs : attribution explicite des trois acteurs avec horodatages et notes,
`related_name` distincts vérifiés par introspection *et* par requête, aucun
horodatage métier rempli automatiquement, suppression d'un compte conservant
la fiche et laissant une date historique avec un acteur nul.

Managers : manager par défaut complet, `objects` voyant les fiches
supprimées, `active` n'excluant que les lignes dont `deleted_at` est
renseigné, indépendance vis-à-vis du statut (test paramétré),
`deleted_by` seul ne masquant rien.

Administration : accès aux lignes supprimées via le queryset de
`EntityAdmin`, répartition des champs en lecture seule.

### `test_api.py` — 7 cas ajoutés

Aucune fuite de champ interne dans la liste ; aucune fuite dans le détail,
note privée incluse, contrôlée sur la charge utile brute ; fiche active
accessible pour chacun des quatre statuts (test paramétré) ; fiche supprimée
absente de la liste ; détail d'une fiche supprimée en 404 avec la ligne
toujours présente en base ; cible imbriquée supprimée encore visible — limite
documentée.

### Non-régression

Les 140 cas antérieurs passent **sans modification**. Le budget du détail
reste de **7 requêtes**, les nouveaux champs n'étant pas exposés : aucun
`select_related` supplémentaire vers les comptes n'a été ajouté, puisque
aucune donnée utilisateur n'est sérialisée. Le test imposant zéro requête
pendant la sérialisation du queryset préchargé passe tel quel.

Aucun test de transition ni de permission n'a été écrit : ces comportements
n'existent pas. Le marquage de `deleted_at` dans les tests est une préparation
explicite par l'ORM, non l'appel d'un service.

## 9. Contrôles

Exécutés sur la version finale. Aucune valeur du `.env` n'est affichée.

| Commande | Sortie | Code |
|---|---|---|
| `python manage.py check` | `System check identified no issues (0 silenced).` | 0 |
| `python manage.py makemigrations --check --dry-run` | `No changes detected` | 0 |
| `python manage.py showmigrations mythology` | `[X]` sur les six migrations, dont `0006_entity_created_by_entity_deleted_at_and_more` | 0 |
| `pytest` | `171 passed in 13.91s` | 0 |
| `ruff check .` | `All checks passed!` | 0 |
| `ruff format --check .` | `31 files already formatted` | 0 |
| `mypy .` | `Success: no issues found in 31 source files` | 0 |

Deux corrections intermédiaires, suivies de la relance des seuls contrôles
affectés :

- `ruff check` a signalé `I001` sur l'ordre des imports de `test_api.py`,
  l'ajout de `django.utils.timezone` ayant été mal placé. Corrigé par
  `ruff check --fix` ;
- `mypy` a refusé l'accès aux accesseurs inverses `user.created_entities` et
  suivants, que `django-stubs` ne type pas. Le test a été reformulé pour
  vérifier les `related_name` par introspection de `User._meta.related_objects`
  **et** par `Entity.objects.filter(...)` — il prouve donc davantage qu'avant,
  sans `type: ignore`.

## 10. Divergences avec le prompt

Une seule, documentaire : la docstring du module `models.py` a été actualisée
pour mentionner les champs de plateforme et préciser qu'ils sont posés et non
pilotés. Elle annonçait encore « le workflow éditorial et les champs de
suppression logique » comme restant à venir, ce qui devenait partiellement
faux — les champs existent, le workflow non.

Aucune autre divergence : les huit champs, les quatre statuts, les
`related_name`, les deux managers, le branchement de la vue, les clés des
serializers et le budget de requêtes correspondent au prompt.

## 11. Points restant aux phases suivantes

### Phase 3 — visibilité publique

- Normaliser en anglais les libellés publics encore en français, conformément
  à l'ADR 0003 : cette tâche appartient à la V1 et reste prévue en phase 3.
- Ne rendre visibles que les fiches `published` ; `active` ne filtre
  aujourd'hui que la suppression logique.
- **Visibilité cohérente des cibles imbriquées** : `variant_of` et les cibles
  de relations échappent au filtrage, y compris lorsqu'elles sont supprimées
  logiquement ou non publiées. À traiter avant toute livraison publique.
- Centraliser cette sélection dans la méthode réutilisable que la roadmap
  prévoit, afin que la phase 4 n'ait pas à réécrire les serializers de
  lecture.
- Pagination, recherche, filtres et schéma OpenAPI.

### Phase 4 — plateforme

- Groupes `contributor`, `reviewer`, `administrator` créés par migration de
  données ; aucun champ `role` sur l'utilisateur.
- Attribution automatique de `created_by` à la création.
- Services de transition posant `submitted_at`, `reviewed_at`, `reviewed_by`
  et `review_notes`, et validant les transitions autorisées — aujourd'hui
  l'ORM permet n'importe quel enchaînement de statuts.
- Matrice de permissions combinant rôle, propriété et statut, testée de façon
  paramétrée.
- Suppression logique comme service, posant `deleted_at` et `deleted_by`, et
  restauration réservée à l'administrateur.
- Refus de supprimer logiquement une figure de référence encore utilisée par
  des variantes : `PROTECT` ne couvre aujourd'hui que la suppression
  **physique**.
- Rappel de portée : `delete()` et les cascades physiques n'ont pas été
  modifiés dans cet incrément. La suppression physique d'une entité emporte
  toujours ses profils, ses relations et ses sources, et une suppression
  logique ne déclenche aucune cascade.
- Contrat API destiné aux contributeurs, exposant sélectivement les champs
  restés internes ici.

### Hors V1

- Module de rendu visuel, conformément à la section 8 de l'ADR 0002.

## 12. État Git final

Aucun commit, aucun push, aucun `git add` : l'index est vide.

```
# afrimyth-api
## main...origin/main
 M mythology/admin.py
 M mythology/models.py
 M mythology/tests/test_api.py
 M mythology/views.py
?? docs/reports/phase-2-increment-5-editorial-fields.md
?? mythology/migrations/0006_entity_created_by_entity_deleted_at_and_more.py
?? mythology/tests/test_editorial_fields.py

# django-portfolio
## main...origin/main
?? docs/prompts/phase-2-increment-5-editorial-fields.md
```

Les deux branches sont `main` et synchronisées avec `origin/main`. `_audit/`
et `.claude/` sont ignorés par le `.gitignore` de `django-portfolio`. La
roadmap n'a pas été modifiée : après validation, Codex effectuera la clôture.

## 13. Relecture Codex

La lecture des modèles, de la migration, de l'administration, de la vue et
des tests ne révèle aucun blocage fonctionnel par rapport au prompt. Les
nouveaux champs restent internes aux serializers publics et les managers
ont les portées prévues. Les 171 cas et les contrôles qualité ont été exécutés
par Claude ; ils ne sont pas relancés pour les corrections documentaires.

Une erreur de classement est corrigée : la normalisation linguistique du
contrat public appartient à la phase 3 de la V1, et non au hors V1.
La roadmap du dépôt de pilotage précise désormais explicitement la visibilité
des cibles imbriquées supprimées ou non publiées. Aucun comportement n'est
modifié : la limite reste connue et devra être traitée avant la livraison
publique. L'état Git de la section 12 précède ces ajouts documentaires.

La revue pédagogique est validée par l'auteur le 20 octobre 2026.

## 14. Clôture pédagogique

L'auteur a compris le rôle des champs de propriété, de statut et de revue,
la distinction entre statut éditorial et suppression logique, les portées
des managers `objects` et `active`, ainsi que le caractère encore physique
de `delete()`. Les champs n'implémentent pas les transitions ni les permissions.

La tâche correspondante est cochée dans la roadmap. Les résultats de contrôle
de Claude sont réutilisés : seuls des documents ont changé après la revue.
La section 12 conserve l'état Git antérieur à la clôture. Les commits et
pushes sont pris en charge directement par Codex selon l'autorisation de
l'auteur. La prochaine tâche concerne la cohérence type/profil.
