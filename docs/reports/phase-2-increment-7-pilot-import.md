# Rapport — Phase 2, incrément 7 : consolidation et import pilote

- **Date :** 20 octobre 2026
- **Dépôt :** `afrimyth-api`
- **Branche :** `main`
- **Statut :** revue technique et pédagogique validée le 21 octobre 2026 ; phase 2 clôturée

## 1. Les quatre tâches de roadmap, validables séparément

| Tâche de roadmap | État | Où la vérifier |
|---|---|---|
| Écrire le squelette de la commande d'import et charger une entité réelle de chaque type | **faite** | sections 4 et 8 |
| Confronter ce pilote aux contraintes, longueurs, valeurs nulles, caractères spéciaux et relations vers des cibles absentes | **faite** | section 9 |
| Ajouter les contraintes, index et tests de validation utiles | **faite, sans ajout de contrainte** | section 7 |
| Vérifier les requêtes avec `select_related` et `prefetch_related` | **faite** | section 10 |

Les quatre sont couvertes. Je ne déclare pas pour autant la phase 2 terminée :
sa clôture appartient à la revue, et plusieurs limites connues restent
ouvertes (section 12).

## 2. Source de données

| | |
|---|---|
| Chemin | `C:\Users\heric\dev\django-portfolio\_audit\african_mythology_V2\src\data\mythology_data.json` |
| Taille | 132 630 octets |
| SHA-256 | `6D9C94CD21FCB8629D19B2C2401D31DD289C0499DD802F3564FCDFBB3A1A58BF` |
| Contenu | liste JSON de 44 figures, aucun doublon de nom |

Le fichier reste **externe et intact** : son chemin est passé par `--input`,
aucun chemin absolu n'est codé en dur, et rien du dossier `_audit` — code,
images, corpus — n'a été recopié dans ce dépôt. Les tests committés sont
autonomes : ils écrivent leur propre JSON synthétique et n'ouvrent jamais le
corpus réel. Aucun appel réseau ni IA.

## 3. Fichiers changés

**Créés**

- `mythology/management/__init__.py`, `mythology/management/commands/__init__.py`
- `mythology/management/commands/import_mythology_pilot.py` — la commande
- `mythology/tests/test_pilot_import.py` — 52 cas après revue Codex
- `docs/reports/phase-2-increment-7-pilot-import.md` — ce rapport

**Modifiés**

- `README.md` — section « Pilot corpus import » en anglais, statut du projet
- `CLAUDE.md` — règle `_audit` assouplie pour la lecture, interdiction de
  copie conservée

Aucun modèle, aucune migration, aucun serializer, aucune vue, aucun service
n'a été modifié. **Aucune migration n'a été nécessaire** : `makemigrations
--check` ne détecte aucun changement.

La revue Codex a ensuite ajusté la commande et ajouté deux tests : voir
section 14. Les garanties et résultats ci-dessous intègrent ces corrections.

## 4. La commande

```bash
python manage.py import_mythology_pilot --input "CHEMIN_JSON" [--dry-run]
```

**Sélection fixe**, vérifiée avant toute écriture : chaque nom doit exister
**une seule fois** dans le corpus et porter le type attendu.

| Nom | Type attendu | Profil |
|---|---|---|
| `Oya` | `divinity` | `DivinityProfile` |
| `Anansi` | `hero` | `HeroProfile` |
| `Mokele-mbembe` | `creature` | `CreatureProfile` |

Les 41 autres figures ne sont pas importées.

**Création par le service.** Les fiches passent par
`create_entity_with_profile`, qui garantit le couple entité/profil. Les
collections — pays secondaires, domaines — et les relations sont rattachées
ensuite, dans la **même** transaction.

**Une seule transaction** englobe référentiels, fiches, profils, collections
et relations. Toute erreur bloquante annule l'intégralité de l'apport de
l'appel, référentiels compris — vérifié par
`test_erreur_sur_une_fiche_annule_tout_l_appel`, qui constate que les quatre
tables de référentiel restent vides après un échec sur la troisième fiche.

**`--dry-run`** exécute la validation et toutes les écritures dans une
transaction close par `transaction.set_rollback(True)`, puis affiche le même
bilan. Ni base temporaire, ni restauration de sauvegarde.

**Validation** : `full_clean()` est appelé sur chaque référentiel et chaque
relation avant enregistrement, et le service l'applique à l'entité et au
profil.

**Erreurs lisibles** pour : fichier absent, JSON invalide, racine non-liste,
sélection incomplète, nom dupliqué dans le corpus, type inattendu, genre
inconnu, aire non préparée, conflit d'identité.

### Relance sans écrasement

Une fiche dont le **nom, le type et le slug** correspondent à une ligne
existante est signalée comme ignorée, sans que ses champs, son profil, ses
collections ou ses relations soient touchés. Une concordance **partielle**
est un conflit explicite — par exemple un slug déjà pris par une autre figure
— et arrête la commande, sans suffixage arbitraire. Il n'existe ni `--force`,
ni fusion, ni mise à jour globale.

Quatre tests couvrent ce point, dont
`test_relance_preserve_une_fiche_modifiee` : une fiche éditée entre deux
appels — catégorie, statut passé à `published`, offrandes du profil —
conserve ses modifications, et
`test_relance_ne_touche_pas_les_collections_d_une_fiche_ignoree` : des
domaines retirés à la main ne sont pas réattachés.

## 5. Transformations appliquées

Correspondances écrites explicitement, en tables lisibles dans la commande.

| Source | Cible |
|---|---|
| `entity_type` : `Divinity` / `Hero` / `Creature` | `divinity` / `hero` / `creature` |
| `identity.gender` : `Male` / `Female` / `Neutral` / `Androgynous` / `Fluid` | valeurs techniques correspondantes |
| `name` | `slug` par `slugify()`, déterministe |
| `category`, `identity.cultural_role`, `identity.alignment` | champs de même rôle |
| `story.description`, `story.characteristics` | `story_description`, `characteristics` |
| `appearance.physical_signs`, `appearance.manifestations` | mêmes champs |
| `attributes.symbols`, `power_objects`, `symbolic_animals` | mêmes champs |
| `type_specific.<type>` | champs du profil correspondant |

**Listes normalisées** : espaces de bord retirés, doublons écartés en
conservant l'ordre, marqueurs d'absence (`None`, `N/A`, `Unknown`, `-`, `""`)
retirés et **signalés**. Conserver `"None"` comme objet de pouvoir aurait
inscrit un faux fait.

**Clés absentes non fournies** au profil : les valeurs par défaut du modèle
s'appliquent, et une absence ne devient pas un fait.

**Statut** : les trois fiches sont créées en `draft`, sans propriétaire, sans
marque de revue ni de suppression, et `sources=[]` — le corpus du pilote n'en
contient aucune. Aucune variante culturelle n'a été créée : les données n'en
mentionnent pas.

### Domaines réconciliés

Union dédupliquée de `attributes.domains` et de
`type_specific.divinity.domains`, conformément à la décision 4 de l'ADR 0002.

Pour **Oya** :

| Source | Valeurs |
|---|---|
| `attributes.domains` | Wind, Storms, Cemeteries, Transformation |
| `type_specific.divinity.domains` | Wind, Storms, **Ceteris**, **Change** |
| **Résultat en base** | Wind, Storms, Cemeteries, Transformation, Change |

- `Ceteris` → `Cemeteries` : correction validée en phase 0, appliquée et
  signalée ;
- `Change` est **conservé à côté** de `Transformation` : ce sont des synonymes
  discutables, non fusionnés, et le bilan demande une revue éditoriale ;
- aucune valeur n'est perdue, ce qu'aurait fait le choix d'un seul des deux
  emplacements.

### Géographie et référentiels

Aires préparées : `West Africa`, `Central Africa`, `East Africa`,
`Southern Africa` (`african_region`, sans parent) et `Diaspora`
(`diasporic`, sans parent), même lorsque le pilote ne les utilise pas.
`Congo Basin` est une aire `african_region` dont le **parent** est
`Central Africa`. `Pan-African` n'a pas été créé : aucune des trois fiches ne
le réclame.

**Mokele-mbembe** : `origin.country` vaut `Congo Basin`, qui n'est pas un
pays. Conformément à la décision 2 de l'ADR 0002, aucune ligne `Country`
n'est créée, `primary_country` reste **nul**, et l'aire principale est
`Congo Basin` — la région parente restant accessible par `parent`, sans
duplication artificielle en aire secondaire.

**Origines multiples** : le premier pays réel devient principal, les suivants
secondaires, sans doublon entre les deux. Le pilote réel n'en contient pas ;
deux tests le démontrent sur des données synthétiques.

**Pays** : table ISO explicite limitée aux valeurs rencontrées — Nigeria/NG,
Ghana/GH. Aucun géocodage, aucune dépendance ajoutée.

**Ethnies** : `primary_cultural_area` est laissé **nul**. Le corpus donne la
région de la *figure*, pas celle de l'*ethnie* ; l'inférer aurait été inventer
un fait culturel. Une valeur vague comme `Multi-ethnic` est signalée et non
créée comme ethnie réelle — testé.

**Référentiel existant divergent** : réutilisé tel quel, jamais réécrit, et le
conflit est signalé. Testé avec un `Nigeria` préexistant au code `XX`, qui
reste inchangé.

### Omissions assumées

| Non importé | Raison |
|---|---|
| `rendering` | données de rendu hors V1 — ADR 0002, section 8 |
| `appearance.image_generation_prompt` | instruction pour un moteur d'images, pas un fait mythologique |
| `appearance.imageUrl` | appartient au module de rendu |
| `origin.pantheon` | exclu du modèle cible : les valeurs mêlent traditions religieuses, folklore, régions et catégories narratives |

Les quatre figurent dans le bilan de chaque exécution, avec leur raison. Les
prompts eux-mêmes ne sont pas recopiés ici.

## 6. Relations en deux passes

Les fiches sont créées d'abord, les relations ensuite — c'est ce qui permet
de résoudre une référence vers une figure créée plus tard dans le même appel.

**Sens conservé** : `parents` → `parent` (la cible est le parent de la fiche),
`conjoint` → `consort`.

**`descendants` n'est pas converti** en lien `child` : rien ne garantit qu'un
nom cité soit un enfant direct plutôt qu'un descendant lointain. Les valeurs
non vides sont signalées pour arbitrage et conservées dans le bilan. Les trois
fiches du pilote ont `descendants: []` ; un test synthétique vérifie le
comportement.

**Résolution limitée à la sélection du pilote.** Une fiche du pilote déjà
présente peut être utilisée comme cible après concordance de son nom, type
et slug, sans modifier ses données. Les fiches préexistantes hors sélection,
même homonymes, ne sont pas rapprochées. Aucune quatrième fiche n'est importée
pour résoudre une cible. Aucun lien inverse n'est créé.
`Yemaya` n'est fusionné avec aucun autre nom.

**Résultat sur le corpus réel** — les trois relations d'Oya restent **non
résolues**, et c'est voulu :

| Lien | Cible | État |
|---|---|---|
| `Oya —parent→ Yemaya` | hors pilote | `to_name="Yemaya"` |
| `Oya —consort→ Shango` | **fiche homonyme en base** | `to_name="Shango"`, non résolu |
| `Oya —consort→ Ogun` | hors pilote | `to_name="Ogun"` |

Le cas de `Shango` est le plus instructif : une fiche `shango` existe depuis
la phase 1, et le lien n'est **pas** rapproché d'elle. Le test
`test_aucun_rapprochement_avec_une_fiche_preexistante` fixe ce comportement
et vérifie que la fiche historique ne reçoit aucun lien entrant.

Le pilote réel ne produisant donc aucune résolution, la **seconde passe est
démontrée sur données synthétiques** par `test_resolution_en_deux_passes` :
un lien d'Oya vers Anansi — créé après elle — est bien résolu, avec
`to_name=""`.

## 7. Consolidation : aucune contrainte ni index ajouté

Les contraintes et tests existants ont suffi. **Rien n'a été ajouté**, ni
index, ni contrainte, ni migration — conformément à la consigne : un ajout
doit répondre à un manque constaté.

En particulier, les longueurs du modèle ont tenu. L'élément de liste le plus
long des trois fiches réelles est `"Long neck reaching above canopy"`
(31 caractères), très en dessous de la limite de 100 ; `diet` vaut
`"Herbivorous (Malombo vines)"` et `size` `"Gigantic (Sauropod-sized)"`, sous
les 255 caractères. **Aucun dépassement réel**, donc aucune migration de
longueur à justifier.

Le comportement en cas de dépassement est tout de même testé, sur données
synthétiques : un élément de 150 caractères fait **échouer** l'import, qui est
annulé, plutôt que d'être tronqué en silence
(`test_depassement_de_longueur_est_signale_sans_troncature`).

## 8. Exécution réelle

### État initial

```
entites     : ['shango']
profils     : divinity=0 hero=0 creature=0
referentiels: country=0 area=0 ethnicity=0 domain=0
liens       : 0 | sources : 0
```

### Dry run

Bilan annonçant 3 créations et 3 relations, puis :

```
Dry run: the transaction was rolled back, nothing was persisted.
```

État vérifié juste après : `entites : ['shango']`, référentiels à 0.
**Aucun apport persistant.**

### Import réel

```
Mode            : COMMIT
Entities created: 3
  + Oya (divinity) slug=oya
  + Anansi (hero) slug=anansi
  + Mokele-mbembe (creature) slug=mokele-mbembe
Entities skipped: 0
Relations       : 3
  → Oya —parent→ Yemaya (unresolved)
  → Oya —consort→ Shango (unresolved)
  → Oya —consort→ Ogun (unresolved)
Notes           : 15
```

État après import :

| | |
|---|---|
| Entités | 4 — `anansi`, `mokele-mbembe`, `oya`, `shango` |
| Profils | divinity 1, hero 1, creature 1 ; chacun sur la bonne fiche |
| Statuts | les trois fiches importées en `draft` |
| Pays | Ghana/GH, Nigeria/NG |
| Aires | Central Africa, Congo Basin, Diaspora, East Africa, Southern Africa, West Africa |
| Ethnies | Akan, Bakwele, Yoruba |
| Domaines | 13 : Caves, Cemeteries, Change, Cunning, Mystery, Stories, Storms, Swamps, Transformation, Water, Wind, Wisdom, Wit |
| Relations | 3, toutes non résolues |
| Sources | 0 |

Noter l'absence de `Ceteris` parmi les domaines, et la présence conjointe de
`Change` et `Transformation`.

### Seconde exécution

```
Entities created: 0
Entities skipped: 3
  = Oya (divinity)
  = Anansi (hero)
  = Mokele-mbembe (creature)
```

Après cette seconde exécution : **4 entités**, un seul profil par type, mêmes
référentiels — country 2, area 6, ethnicity 3, domain 13 — et **3 relations**.
Aucun doublon, aucune réécriture.

### Préservation de `shango`

```
name/type   : Shango divinity
created_at  : 2026-10-13T20:15:12.389454+00:00
updated_at  : 2026-10-13T20:15:12.389454+00:00
symbols     : ['Hache à double tranchant', 'Foudre']
profil      : aucun (inchangé)
liens entrants : 0
```

Les horodatages au 13 octobre prouvent que la ligne n'a pas été réécrite. La
fiche n'a été **ni réparée, ni supprimée, ni rapprochée** du lien `Shango`
d'Oya.

## 9. Confrontation aux données réelles — anomalies relevées

Ce que le pilote a révélé, et comment chaque cas est traité :

| Anomalie réelle | Traitement |
|---|---|
| `Oya` : `Ceteris` dans `type_specific.divinity.domains` | corrigé en `Cemeteries`, signalé |
| `Oya` : `Change` vs `Transformation` | les deux conservés, revue éditoriale demandée |
| `Oya` : trois cibles de relation absentes du pilote | conservées en `to_name`, signalées |
| `Mokele-mbembe` : `power_objects: ["None"]` | marqueur d'absence écarté, signalé — `power_objects` vaut `[]` |
| `Mokele-mbembe` : `origin.country: "Congo Basin"` | n'est pas un pays : aire principale, `primary_country` nul |
| Les 44 fiches : `origin.pantheon` renseigné | hors modèle cible, omission consignée |
| Les 3 fiches : aucune source documentaire | `sources=[]`, rien d'inventé |
| `Anansi`, `Mokele-mbembe` : pas de bloc `divinity` | absence normale, **non** signalée comme anomalie |

Comportements testés sans prétendre qu'ils surviennent dans les trois fiches
réelles : liste vide, valeur nulle, forme inattendue (chaîne au lieu de
liste), caractères Unicode (`Ṣàngó`), dépassement de longueur, doublon dans
une liste, origine composite, ethnie vague, aire inconnue, genre inconnu.

Aucun fait culturel, propriétaire ou source n'a été inventé.

## 10. Requêtes

| Cas | Attendu | Mesuré |
|---|---|---|
| Détail d'une fiche importée | 7 | 7 |
| Sérialisation après évaluation du queryset de la vue | 0 | 0 |

Le budget de sept requêtes est inchangé : l'incrément n'a touché ni la vue ni
les serializers. Les deux tests portent cette fois sur des fiches issues de
l'import, et non sur des factories — `test_detail_d_une_fiche_importee_coute_sept_requetes`
et `test_fiche_importee_se_serialise_sans_requete`, ce dernier vérifiant
qu'une relation résolue expose le slug de sa cible sans requête
supplémentaire.

Réponses API relevées sur la base de développement réelle : la liste renvoie
les 4 fiches ; le détail d'Oya expose Nigeria/NG, Yoruba, West Africa, ses 5
domaines, ses offrandes de culte et ses 3 relations non résolues ; celui de
Mokele-mbembe expose `primary_country: null`, l'aire `Congo Basin`, un
`power_objects` vide et son habitat ; celui d'Anansi ses titres et son
héritage. Aucun champ interne — `status`, `created_by` — ne fuit.

## 11. Contrôles

| Commande | Sortie | Code |
|---|---|---|
| `python manage.py check` | `System check identified no issues (0 silenced).` | 0 |
| `python manage.py makemigrations --check --dry-run` | `No changes detected` | 0 |
| `pytest` | `257 passed in 21.03s` après corrections Codex | 0 |
| `ruff check .` | `All checks passed!` | 0 |
| `ruff format --check .` | `37 files already formatted` | 0 |
| `mypy .` | `Success: no issues found in 37 source files` | 0 |

**257 cas exécutés**, dont 52 ajoutés par cet incrément après revue Codex :

| Fichier | Cas |
|---|---|
| `mythology/tests/test_pilot_import.py` | 52 |
| `mythology/tests/test_api.py` | 43 |
| `mythology/tests/test_services.py` | 34 |
| `mythology/tests/test_relations.py` | 31 |
| `mythology/tests/test_reference.py` | 28 |
| `mythology/tests/test_sources.py` | 25 |
| `mythology/tests/test_editorial_fields.py` | 22 |
| `mythology/tests/test_profiles.py` | 11 |
| `mythology/tests/test_models.py` | 7 |
| `tests/` (socle) | 4 |

Deux corrections intermédiaires, suivies de la relance des seuls contrôles
affectés : quatre `E501` et un `B007` sur une variable de boucle inutilisée,
puis `ruff format`. Aucun secret dans les sorties.

## 12. Limites et points restant ouverts

**Dans cet incrément**

- Le pilote réel ne produit **aucune** relation résolue : la seconde passe est
  démontrée sur données synthétiques. Un pilote plus large ou l'import complet
  fournira des résolutions réelles.
- `Change` / `Transformation` sur Oya attend un arbitrage éditorial.
- `shango` reste sans profil et n'est pas rapprochée du lien `Shango` d'Oya.
  Deux décisions éditoriales à prendre : réparer, supprimer, ou résoudre
  explicitement le lien.
- Les ethnies créées n'ont pas d'aire culturelle principale, faute de donnée
  fiable dans le corpus.

**Phase 3** — visibilité publique : filtrage sur `published`, et visibilité
cohérente des cibles imbriquées, `variant_of` et cibles de relations
échappant encore au manager `active`.

**Phase 4** — rôles, permissions, transitions, attribution automatique du
propriétaire, suppression logique et restauration. Les autres chemins
d'écriture et les changements de `entity_type` après création restent à
encadrer : le service garantit ses propres appels, pas l'ORM direct.

**Phase 5** — import des 44 fiches et généralisation de la commande : gestion
des 11 origines composées réelles, des valeurs d'ethnie vagues, du vocabulaire
d'`alignment`, et rapprochement éventuel des cibles entre fiches importées.

**Phase 3 de la V1** — normalisation en anglais des `verbose_name` et autres
libellés publics encore français, inscrite à la roadmap au titre de l'ADR 0003.

**Hors V1** — module de rendu.

## 13. État Git final

Aucun commit, aucun push, aucun `git add` : l'index est vide. La roadmap n'a
pas été modifiée.

```
# afrimyth-api
## main...origin/main
 M CLAUDE.md
 M README.md
?? docs/reports/phase-2-increment-7-pilot-import.md
?? mythology/management/
?? mythology/tests/test_pilot_import.py

# django-portfolio
## main...origin/main
?? docs/prompts/phase-2-increment-7-pilot-import.md
```

Les deux branches sont `main` et synchronisées avec `origin/main`. `_audit/`
et `.claude/` restent ignorés par le `.gitignore` de `django-portfolio`, et
rien du corpus n'a été copié dans le dépôt API. Après validation, Codex
prendra en charge la clôture documentaire et Git.

## 14. Relecture et corrections Codex

Deux corrections fonctionnelles localisées, sans changement de modèle ni
écriture supplémentaire dans la base de développement :

- La seconde passe peut résoudre une cible appartenant aux trois fiches du
  pilote même si elle a été ignorée car déjà présente. Son identité est
  vérifiée par nom, type et slug ; elle n'est pas modifiée. Un test recrée
  uniquement la source d'un lien et vérifie sa résolution vers la cible du
  pilote déjà importée. Les fiches hors sélection, dont Shango, restent exclues.
- Un référentiel d'aire existant avec un parent renseigné alors qu'une racine
  est attendue est désormais signalé comme conflit. Il était conservé sans
  avertissement car la valeur attendue `None` était ignorée. Un test vérifie
  le signalement et l'absence de réécriture de ce parent.

Une erreur documentaire est aussi corrigée : la normalisation en anglais
du contrat public est prévue en phase 3 de la V1 et non hors V1.

Contrôles Codex sur la version corrigée : 257 tests réussis en 21,03 s ; Ruff
et formatage validés (37 fichiers) ; mypy validé (37 fichiers) ; contrôle
Django sans problème ; `makemigrations --check --dry-run` sans changement.

La lecture seule de PostgreSQL confirme quatre fiches en `draft` : Anansi,
Mokele-mbembe, Oya et la Shango historique. Les trois profils existent, un de
chaque type. Oya conserve trois liens non résolus (Ogun, Shango, Yemaya).
Congo Basin a pour parent Central Africa. Shango conserve ses symboles et son
`updated_at` du 13 octobre 2026. Aucun nouvel import réel n'a été relancé par
Codex ; les modifications sont vérifiées sur la base de test.

Les quatre tâches de phase 2 sont couvertes techniquement. La validation
pédagogique avec l'auteur est terminée le 21 octobre 2026. L'état Git de la
section 13 est la capture avant ces petites corrections de revue.

## 15. Validation manuelle et clôture de phase 2

L'auteur a consulté et partagé les trois réponses API HTTP 200 le 21 octobre
2026, puis confirmé leur conformité :

- Oya : Nigeria/NG, Yoruba, West Africa, les cinq domaines réconciliés,
  offrandes et interdits, trois relations non résolues, profil de divinité seul ;
- Anansi : Ghana/GH, Akan, West Africa, titres, réalisations, objets et héritage
  dans le profil de héros, les deux autres profils nuls ;
- Mokele-mbembe : pays nul, Bakwele, Congo Basin, `power_objects=[]`, habitat,
  pouvoirs, forces/faiblesses, alimentation et taille dans le profil de créature.

Ces observations valident la transformation et la restitution du corpus,
pas la véracité documentaire de chaque récit. Aucune source n'a été inventée.
La roadmap coche les quatre tâches restantes : la phase 2 est terminée dans
son périmètre, avec les limites de la section 12. Le README public est actualisé
en anglais. Aucun comportement n'a changé depuis les 257 tests validés ;
seuls les documents sont modifiés pour cette clôture. Codex réalise les commits
et pushes normaux selon l'autorisation permanente de l'auteur.
