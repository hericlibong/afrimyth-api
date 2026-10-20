# Rapport — Phase 2, incrément 6 : création cohérente entité/profil

- **Date :** 20 octobre 2026
- **Dépôt :** `afrimyth-api`
- **Branche :** `main`
- **Statut :** revue technique et pédagogique validée le 20 octobre 2026 ; prêt pour clôture Git

## 1. Objectif et périmètre

Créer une entité et exactement son profil métier dans une seule transaction,
conformément à la décision 6 de l'ADR 0002, qui prévoit que cette cohérence
soit « garantie par le service de création » et non par une abstraction
polymorphe.

Aucun nouveau modèle, aucune migration, aucun endpoint. L'API reste
strictement en lecture seule.

Hors périmètre : rôles, transitions de statut, permissions, attribution
automatique du propriétaire, CRUD, import. Le statut par défaut reste `draft`.

La roadmap n'a **pas** été cochée, rien n'a été committé ni poussé.

## 2. Fichiers changés

**Créés**

- `mythology/services.py` — la fonction métier
- `mythology/tests/test_services.py` — 34 cas
- `docs/reports/phase-2-increment-6-entity-profile-consistency.md` — ce rapport

**Modifiés**

- `CLAUDE.md` — règle sur les abstractions actualisée, `services.py` ajouté à
  la description de l'app

Aucun modèle, aucune migration, aucun serializer, aucune vue et aucune
factory existante n'a été touché. Les validations `clean()` des profils sont
conservées telles quelles.

## 3. Signature exacte

```python
def create_entity_with_profile(
    *,
    entity_data: Mapping[str, Any],
    profile_data: Mapping[str, Any] | None = None,
) -> Entity:
```

Les deux paramètres sont exclusivement nommés. `Mapping` plutôt que `dict`
dans la signature : la fonction ne modifie pas ses entrées, et le type le dit.

### Exemple d'appel — données fictives

```python
from mythology.models import EntityType, Gender
from mythology.services import create_entity_with_profile

entity = create_entity_with_profile(
    entity_data={
        "name": "Fictional Thunder Figure",
        "slug": "fictional-thunder-figure",
        "entity_type": EntityType.DIVINITY,
        "gender": Gender.MALE,
        "category": "Fictional test subtitle",
    },
    profile_data={"cult_offerings": ["Yam"], "cult_taboos": ["Lying"]},
)
```

Résultat observé, exécuté dans une base de test jetable :

```
entite creee     : fictional-thunder-figure | type divinity
statut           : draft
profil divinite  : ['Yam']
profil heros     : False
profil creature  : False
```

Et le refus d'une collection hors périmètre :

```python
create_entity_with_profile(
    entity_data={..., "domains": []}
)
# ValidationError: {"domains": ["Many-to-many and related collections are out
# of scope for this function. Create the entity first, then attach them."]}
```

## 4. Implémentation

L'ordre suit exactement celui demandé :

1. **vérification du type** — absent, vide ou inconnu : `ValidationError`
   immédiate, avant toute écriture ;
2. **vérification des champs** — champs interdits puis champs inconnus, pour
   l'entité comme pour le profil, toujours avant d'ouvrir la transaction ;
3. **dans `transaction.atomic()`** — `Entity(**entity_data)`, `full_clean()`,
   `save()` ;
4. puis le profil sélectionné, `entity=entity` imposé par la fonction,
   `full_clean()`, `save()` ;
5. retour de l'entité.

Le type choisit seul le modèle de profil, par un dictionnaire explicite :

```python
PROFILE_MODELS = {
    EntityType.DIVINITY: DivinityProfile,
    EntityType.HERO: HeroProfile,
    EntityType.CREATURE: CreatureProfile,
}
```

Il n'existe **aucun paramètre concurrent** permettant de demander un profil
d'un autre type que celui de l'entité.

**Champs autorisés déduits par introspection.** `_writable_field_names()`
parcourt `model._meta.concrete_fields` et retient les champs `editable`. Deux
conséquences : la liste suit l'évolution des modèles sans intervention, et
`id`, `created_at`, `updated_at` sont écartés d'office puisque non éditables.
Pour une clé étrangère, les deux formes sont acceptées — `primary_country` et
`primary_country_id` — la seconde étant utile à l'import.

**Aucune exception absorbée.** Il n'y a ni `try`/`except` ni `return` de
repli à l'intérieur de la transaction. Toute erreur remonte à l'appelant et
annule les deux créations.

**Entrées non modifiées.** Les dictionnaires sont recopiés au moment du
dépaquetage (`dict(entity_data)`), et `clean()` du profil n'opère que sur
l'instance. Un test compare les dictionnaires avant et après appel.

## 5. Garanties et limites

### Ce que le service garantit

| Garantie | Mécanisme |
|---|---|
| Une entité créée possède exactement le profil de son type | sélection par `PROFILE_MODELS` + rattachement imposé |
| Jamais d'entité sans profil, même sans `profile_data` | profil créé avec ses valeurs par défaut |
| Aucune écriture partielle | `transaction.atomic()` englobant les deux `save()` |
| Aucune modification d'une fiche existante | `id`/`pk` refusés, `entity`/`entity_id` refusés |
| Champs inconnus ou hors périmètre signalés | vérification avant la transaction |
| Entrées de l'appelant intactes | copies défensives |

### Ce qu'il ne garantit pas

C'est le point à retenir : **le service garantit le résultat de ses propres
appels réussis, rien de plus.**

- **L'ORM direct le contourne.** `Entity.objects.create(...)` produit toujours
  une entité sans profil. L'administration Django, un script ou un import mal
  écrit font de même. Le test
  `test_l_orm_direct_contourne_encore_le_service` fixe ce comportement réel
  pour qu'il ne soit pas confondu avec une garantie globale.
- **Le type peut changer après création.** Modifier `entity_type` laisse le
  profil d'origine en place, désormais incohérent. Vérifié par
  `test_le_type_peut_encore_changer_apres_creation`. Aucun verrou n'est posé.
- **Aucun `save()` surchargé, aucun signal, aucun trigger PostgreSQL.** La
  cohérence n'est pas imposée au niveau du schéma, et ne peut pas l'être
  simplement : elle porte sur l'existence d'une ligne dans une autre table.
- **La fonction n'est pas une frontière HTTP.** Ce n'est ni un serializer, ni
  une authentification, ni un contrôle d'autorisation. Brancher un JSON client
  arbitraire sur ses arguments serait une faute : `created_by`, `status` ou
  `reviewed_by` y sont acceptés comme n'importe quel champ éditable. Le CRUD
  de la phase 4 devra interposer un serializer et des permissions.

### Frontière des collections

Les quatre relations multiples — `secondary_countries`,
`secondary_ethnicities`, `secondary_cultural_areas`, `domains` — ainsi que
`sources`, `relations_from` et `relations_to` sont **refusées** dans
`entity_data`, avec un message qui explique pourquoi.

Cette séparation limite le rôle du service au couple entité/profil. Une
relation multiple exige une entité déjà enregistrée, mais son rattachement
pourrait tout à fait être réalisé dans la même transaction : une erreur
annulerait alors aussi les écritures précédentes. La frontière est un choix
de périmètre, pas une impossibilité technique ou une faiblesse d'atomicité.

L'import appellera donc `create_entity_with_profile` dans sa propre
transaction, puis rattachera ces collections — sans compromettre le couple
entité/profil.

## 6. État des fiches existantes — lecture seule

Inventaire exécuté sans aucune écriture :

```
'shango'  type=divinity  profils=[]  attendu='divinity_profile'  -> SANS PROFIL

total entites     : 1
coherentes        : 0
sans profil       : 1  ['shango']
profil incoherent : 0
profils en base   : divinity=0 hero=0 creature=0
```

**`shango` est sans profil.** Elle a été créée via l'administration Django
lors de la vérification manuelle de la phase 1, bien avant l'existence de ce
service — ce qui illustre concrètement la limite décrite ci-dessus : les
autres chemins d'écriture ne sont pas couverts.

Aucune incohérence de type n'a été trouvée — aucune fiche ne porte un profil
d'un type différent du sien.

**`shango` n'a pas été réparée**, conformément au prompt : aucun changement
persistant n'a été apporté à la base de développement. Deux options se
présenteront : lui créer son profil à la main, ou la supprimer puisqu'il
s'agit d'une fiche de démonstration. C'est une décision éditoriale, pas une
correction automatique à glisser dans cet incrément.

## 7. `CLAUDE.md`

La règle « Pas d'abstraction anticipée » interdisait toute couche de service.
Elle a été actualisée pour autoriser les **fonctions métier concrètement
demandées** lorsqu'une règle ne peut pas être portée par un modèle seul, en
citant `mythology/services.py` et la décision 6 de l'ADR 0002. Le refus des
abstractions spéculatives — `BaseModel`, repository générique, mixins — est
conservé mot pour mot.

`services.py` a par ailleurs été ajouté à la description de l'app dans la
section « Structure ». Aucune autre modification du fichier.

## 8. Tests

**205 cas exécutés**, dont 34 ajoutés par cet incrément. Répartition réelle
obtenue par `pytest --collect-only` :

| Fichier | Cas |
|---|---|
| `mythology/tests/test_api.py` | 43 |
| `mythology/tests/test_services.py` | 34 |
| `mythology/tests/test_relations.py` | 31 |
| `mythology/tests/test_reference.py` | 28 |
| `mythology/tests/test_sources.py` | 25 |
| `mythology/tests/test_editorial_fields.py` | 22 |
| `mythology/tests/test_profiles.py` | 11 |
| `mythology/tests/test_models.py` | 7 |
| `tests/` (socle) | 4 |

Les factories existantes n'ont **pas** été remplacées par le service :
plusieurs tests ont besoin d'entités sans profil ou de données invalides pour
vérifier des limites. Les tests du service vivent dans leur module dédié.

Chaque test vérifie l'état **stocké** — par `Entity.objects.get()` ou
`refresh_from_db()` — et non le seul objet en mémoire. Aucun test ne se
contente de constater la présence d'un décorateur `atomic`.

### `test_services.py` — 34 cas

**Les trois types** — pour chacun, l'entité est créée, le bon profil existe en
un seul exemplaire, et les deux autres sont absents, vérifié aussi par les
compteurs globaux.

**Données conservées** — champs du tronc commun et clé étrangère retrouvés en
base ; clé étrangère acceptée sous la forme `_id` ; statut par défaut `draft`
et aucun propriétaire attribué.

**Profil absent ou vide** — les deux produisent un profil avec ses valeurs par
défaut, jamais une entité sans profil.

**Type** — absent, vide ou inconnu : refus, et `Entity.objects.count() == 0`.

**Champs refusés** — champ d'un autre profil (`habitat` sur une divinité),
champ d'entité inexistant, six collections hors périmètre (test
paramétré ; le code en refuse sept, dont `relations_to`), `id` et `pk` (test paramétré), `entity` et `entity_id` dans
`profile_data` (test paramétré). Dans tous les cas, aucune ligne créée.

**Non-écrasement** — réutiliser l'`id` d'une fiche existante échoue et laisse
la fiche intacte.

**Atomicité** — le cas central : un `threat_level` invalide échoue au
`full_clean()` du profil, donc **après** l'enregistrement de l'entité. Sans
transaction, une entité orpheline subsisterait ; le test vérifie que les deux
tables sont vides. Un second test contrôle qu'un échec préserve les fiches
préexistantes, un troisième qu'une entité invalide n'écrit rien non plus.

**Unicité** — slug dupliqué et couple `(name, entity_type)` dupliqué refusés,
sans résidu ; même nom sous deux types toujours possible.

**Entrées** — les dictionnaires de l'appelant ne sont pas modifiés.

**Portée de la garantie** — trois tests fixent les limites réelles : l'ORM
direct contourne le service, le type peut changer après création, et le
`OneToOneField` reste la seule barrière contre un second profil du même type.

## 9. Contrôles

Exécutés sur la version finale. Aucune valeur du `.env` n'est affichée.

| Commande | Sortie | Code |
|---|---|---|
| `python manage.py check` | `System check identified no issues (0 silenced).` | 0 |
| `python manage.py makemigrations --check --dry-run` | `No changes detected` | 0 |
| `pytest` | `205 passed in 16.25s` | 0 |
| `ruff check .` | `All checks passed!` | 0 |
| `ruff format --check .` | `33 files already formatted` | 0 |
| `mypy .` | `Success: no issues found in 33 source files` | 0 |

`No changes detected` confirme qu'**aucune migration n'est nécessaire** :
l'incrément n'a touché aucun modèle.

Une correction intermédiaire, suivie de la relance des seuls contrôles
affectés : `ruff check` a signalé `E501` sur un message d'erreur trop long
dans `services.py`, découpé puis reformaté.

### Interruption en cours d'intervention

Le service PostgreSQL de développement était **arrêté** au début de cette
intervention — `Get-Service postgresql-x64-16` renvoyait `Stopped` et le port
5432 était fermé. `Start-Service` a échoué faute de droits administrateur.

L'implémentation, les tests et les contrôles indépendants de la base —
`manage.py check`, `ruff check`, `ruff format --check`, `mypy` — ont été menés
dans cet état. `pytest`, `makemigrations --check` et l'inventaire ont attendu
le redémarrage du service, obtenu ensuite, puis ont été exécutés et sont
consignés ci-dessus. Aucun résultat n'a été supposé pendant l'indisponibilité.

## 10. Divergences avec le prompt

Aucune divergence de fond.

Deux précisions de forme :

- le prompt annonçait « aucune modification de schéma ni migration ne devrait
  être nécessaire » : c'est confirmé, `makemigrations --check` ne détecte
  aucun changement ;
- le comptage final est de **34** cas dans `test_services.py`, et non 33 : les
  tests paramétrés produisent plus de cas que de fonctions.

## 11. Suites prévues

**Import pilote** — devra appeler `create_entity_with_profile` pour toutes les
créations, dans sa propre transaction, puis rattacher les collections et les
sources.

**Phase 4** — couvrir les autres chemins d'écriture : CRUD passant par le
service, contrôle des changements de `entity_type` après création, et décision
sur le sort des fiches sans profil déjà en base. Le service devra être placé
derrière un serializer et des permissions, puisqu'il accepte aujourd'hui
`created_by` et `status` comme n'importe quel champ éditable.

**Décision éditoriale en attente** — `shango` est sans profil : lui créer son
profil ou la supprimer.

## 12. État Git final

Aucun commit, aucun push, aucun `git add` : l'index est vide.

```
# afrimyth-api
## main...origin/main
 M CLAUDE.md
?? docs/reports/phase-2-increment-6-entity-profile-consistency.md
?? mythology/services.py
?? mythology/tests/test_services.py

# django-portfolio
## main...origin/main
?? docs/prompts/phase-2-increment-6-entity-profile-consistency.md
```

Les deux branches sont `main` et synchronisées avec `origin/main`. `_audit/`
et `.claude/` sont ignorés par le `.gitignore` de `django-portfolio`. La
roadmap n'a pas été modifiée : après validation, Codex prendra en charge la
clôture documentaire et Git.

## 13. Relecture Codex

La lecture du service et des tests ne révèle aucun blocage fonctionnel par
rapport au prompt. La sélection du profil, les validations, le rattachement
imposé et la transaction couvrent le chemin de création demandé. Les
205 cas exécutés et contrôles qualité ci-dessus sont les résultats de Claude.
L'inventaire de Shango reste inchangé ; aucune réparation n'est effectuée.

Une précision documentaire est apportée au service et au rapport : les
collections restent hors de cette fonction pour en limiter le périmètre,
et non parce qu'elles compromettraient l'atomicité. Le décompte des collections
effectivement couvertes par le test paramétré est également précisé.
Aucun comportement n'est modifié et les tests ne sont pas relancés pour ces
ajustements documentaires. La revue pédagogique est validée le 20 octobre
2026. L'état Git de la section 12 précède ces ajouts.

## 14. Clôture pédagogique

L'auteur a validé l'exercice ORM avec `create_entity_with_profile` et compris
la création couplée de l'entité et de son profil. Un essai a rencontré une
fiche de démonstration déjà présente : les validations d'unicité ont refusé
le doublon sans nouvelle création. L'auteur a ensuite confirmé la vérification.
Cette confirmation ne constitue pas un nouvel inventaire de la base et ne
modifie pas le constat historique concernant Shango.

La roadmap coche la cohérence sur le chemin de création encadré par le
service. Les résultats de contrôle existants sont réutilisés. Codex effectue
directement la clôture documentaire et Git selon l'autorisation permanente.
La prochaine étape est l'import pilote, avec consolidation des contraintes
et vérifications transverses restantes de phase 2.
