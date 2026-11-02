# Phase 5 — Incrément 1 : import complet, préparation sans écriture réelle

Rapport d'intervention, en français. Aucun secret, aucune valeur de `.env`,
aucun mot de passe et aucun jeton n'y figure.

Intervention : Claude CLI, 1er novembre 2026, sur le prompt
`docs/prompts/phase-5-increment-1-import-complet.md` du dépôt de pilotage.
Départ API `8e55deb`.

**Aucune écriture réelle.** Rien n'a été importé dans la base de
développement, pas même en simulation. Les seules écritures ont eu lieu dans
des bases `test_*` créées puis détruites. Aucun fichier de `_audit` n'a été
modifié, et ni le corpus, ni le code, ni les images de ce dossier n'ont été
copiés dans ce dépôt. Le chemin du corpus reste passé par `--input`.

## 1. Écarts réels entre le pilote et le corpus complet

Lecture seule du corpus, hash contrôlé avant et pendant : SHA-256
`6D9C94CD21FCB8629D19B2C2401D31DD289C0499DD802F3564FCDFBB3A1A58BF`,
**44 figures**, conforme à l'annonce. Les écarts constatés, et eux seuls, ont
guidé l'extension :

| Écart | Constat sur les 44 fiches | Traitement |
| --- | --- | --- |
| Aires culturelles | `North Africa`, `Pan-African` et `Cross-Regional` manquaient à la table du pilote | Ajoutées, avec leur nature : `North Africa` est une région, les deux autres des portées `TRANSREGIONAL` |
| Pays | 24 chaînes `country` brutes, dont des composites (`Mozambique / Japan`, `DRC / Congo`) | 18 noms portent un code ISO factuel ; les composites restent traités par le découpage déjà validé |
| `Congo` | Le nom ne distingue pas la République du Congo de la RDC, déjà présente | Ligne créée **sans** code ISO, et signalée ; aucun arbitrage pris |
| Ethnies | 25 valeurs ; `Multi-ethnic` et `Southern Nations` déjà couvertes comme trop vagues | Inchangé. `Khoisan`, `Khoikhoi` et `Buganda` deviennent des lignes **distinctes**, jamais fusionnées |
| Domaines | 112 valeurs distinctes ; 6 présentes seulement dans `type_specific` | Union déjà en place ; la seule correction orthographique reste `Ceteris → Cemeteries` |
| Marqueurs d'absence | `'None'` dans `power_objects` (1) et `symbolic_animals` (7) | Déjà couverts par les sentinelles du pilote |
| Relations | Les 44 fiches portent `parents`/`conjoint`/`descendants` ; la seule cible hors corpus est **Olokun**, citée 4 fois | Conservée en `to_name` |
| Variantes | **Aucune clé `variant_of` ou `variants` dans le corpus** | `variant_of` reste nul ; l'invariant des variantes n'est pas touché |
| Lisibilité | Une note « créée en brouillon » et une note `descendants` par figure auraient ajouté ~88 lignes au bilan | Agrégées en deux notes uniques |

Aucun autre écart n'a demandé de code : `type_specific` est toujours cohérent
avec `entity_type`, aucun élément de tableau ne dépasse 100 caractères, aucun
nom n'est dupliqué, aucun slug n'entre en collision, aucun nom n'est non-ASCII.

## 2. Ce qui a été livré

Une **option explicite `--all`** ajoutée à la commande existante. Sans elle,
le comportement pilote est strictement inchangé : la sélection
Oya/Anansi/Mokele-mbembe, son exigence de complétude et ses contrôles de type.
Aucun fichier recopié, aucun moteur d'import générique, aucune migration,
aucune bibliothèque.

- `_select_all()` retient toutes les figures dans l'ordre du fichier, avec les
  mêmes exigences qu'au pilote : objet JSON, nom non vide, type connu, nom non
  répété. `_mapped_type()` a été extrait pour que les deux sélections
  partagent la même traduction de type.
- `handle()` choisit la sélection selon l'option ; tout le reste du chemin —
  référentiels, fiches, profils, collections, seconde passe des relations,
  transaction unique — est réutilisé tel quel.
- Le bilan annonce désormais le mode, les figures lues et sélectionnées, et
  répartit les relations entre résolues et citées par nom.
- Les `descendants` cités sont accumulés dans une note unique au lieu d'une
  note par figure.

## 3. Simulation sur le corpus réel, en base de tests

`--all --dry-run` exécuté **dans une base `test_*`** créée puis détruite par
un script temporaire hors du dépôt ; la base de développement n'a pas été
ouverte. Résultat réel, sortie `0` :

| Mesure | Valeur |
| --- | --- |
| Figures lues / sélectionnées | 44 / 44 |
| Fiches créées / ignorées | 44 / 0 |
| Relations | 26, dont 22 résolues et 4 citées par nom (Olokun) |
| Notes | 66 |
| Bilan terminal | 149 lignes au total |
| Transaction | annulée, rien persisté |

Transformations réellement observées sur ces 44 fiches : quatre exclusions
annoncées (`rendering`, `appearance.image_generation_prompt`,
`appearance.imageUrl`, `origin.pantheon`), six origines composites découpées,
trois origines qui ne sont pas des pays (`Pan-African`, `Diaspora`,
`Congo Basin`) rattachées à une aire avec `primary_country` laissé nul, deux
ethnies trop vagues signalées sans ligne créée, cinq domaines gardés par
l'union, six marqueurs `'None'` écartés, les valeurs nulles de
`creature.strengths`/`weaknesses`/`diet` normalisées, `Congo` sans code ISO
signalé, et sept `descendants` cités sur cinq figures non convertis en liens.

## 4. Limites et décisions qui vous reviennent

Ces points sont **signalés, pas tranchés** :

1. **`Congo`.** Le code ISO reste vide. Choisir `CG` ou considérer la valeur
   comme un doublon de la RDC est un arbitrage éditorial.
2. **Synonymes de domaines.** `Change`/`Transformation`,
   `Ocean`/`Oceans`/`Sea`, `Stealth`/`Sneaking`, `Thunder`/`Lightning`
   coexistent comme valeurs distinctes. Aucune fusion n'a été faite.
3. **Ethnonymes proches.** `Khoisan` et `Khoikhoi` restent deux lignes, comme
   `Buganda` face aux formes voisines. Les rapprocher demande une décision.
4. **`descendants`.** Les 7 noms cités ne sont pas convertis : rien ne garantit
   qu'un descendant cité soit un enfant direct. Le sens du lien doit être
   arbitré avant tout import de ces relations.
5. **Relations du pilote déjà en base.** Une fiche existante n'est jamais mise
   à jour. Compléter les relations d'un import antérieur est une opération
   distincte, à proposer séparément — elle n'est pas dissimulée derrière
   l'idempotence.
6. **Variantes.** Le corpus n'en porte aucune donnée ; l'import n'en crée
   donc pas. Les variantes resteront à saisir par l'API.
7. **Typage éditorial de la source.** Le corpus classe par exemple
   `Tokoloshe` en `Divinity`. L'import respecte la source et ne reclasse rien.

## 5. Vérifications exécutées

Tests ciblés pendant le travail, sur la seule suite concernée :

| Commande | Résultat |
| --- | --- |
| `pytest mythology/tests/test_pilot_import.py` | 67 passés, 1 échec (`name_local` inexistant dans un test que j'ai corrigé) en 15,77 s |
| `pytest mythology/tests/test_pilot_import.py` (après correction) | **68 passés** en 12,14 s |
| `ruff check .` / `ruff format --check .` | `All checks passed!` / `64 files already formatted` |
| `mypy mythology` | `Success: no issues found in 39 source files` |
| `python manage.py check` | aucun problème |
| `python manage.py makemigrations --check --dry-run` | `No changes detected`, sortie `0` |
| `--all --dry-run` sur le corpus réel, base de tests | sortie `0`, bilan ci-dessus |

Schéma OpenAPI **non revalidé** : le contrat de l'API n'a pas été touché.
Aucune batterie rôle/JWT relancée, pour la même raison. Aucune suite
concurrente, aucune relance redondante.

**Passage complet final, unique :** `pytest` — résultat consigné au point 7.

## 6. Tests ajoutés

Seize cas ajoutés à `mythology/tests/test_pilot_import.py`, **autonomes** :
aucun ne lit le corpus réel, chacun écrit son JSON synthétique à partir des
constructeurs déjà présents (`synthetic_divinity`, `synthetic_hero`,
`synthetic_creature`, `write_corpus`), enrichis des seules différences du
point 1. Aucune fixture ne recopie le corpus.

Ils couvrent : import de tout le fichier avec le profil exact par type et
l'état brouillon ; mode pilote inchangé sur le même fichier ; résolution en
deuxième passe, y compris vers une cible située **après** la fiche citante ;
cible absente du fichier conservée en `to_name` sans fiche fantôme ; aires
culturelles du corpus complet avec leur nature et le rattachement
`Congo Basin → Central Africa` ; codes ISO appliqués et `Congo` signalé sans
code ; refus d'une figure sans nom, d'un nom dupliqué, d'un type inconnu et
d'un fichier vide ; annulation de tous les apports, référentiels compris, sur
une erreur portant sur la dernière figure ; `--dry-run` sans persistance ;
réexécution sans doublon avec préservation intégrale d'une fiche entre-temps
publiée, attribuée, annotée et modifiée ; fiche supprimée logiquement ni
restaurée ni utilisée comme cible ; agrégation des `descendants` en une seule
note ; lisibilité du bilan et de ses décomptes.

## 7. Fichiers touchés et état Git

| Fichier | Changement |
| --- | --- |
| `mythology/management/commands/import_mythology_pilot.py` | Option `--all`, `_select_all()`, `_mapped_type()` extrait, trois aires et dix-huit codes ISO, bilan enrichi, notes `descendants` agrégées |
| `mythology/tests/test_pilot_import.py` | Seize cas pour `--all`, réutilisant les constructeurs du pilote |
| `README.md` | Section d'import : l'option `--all` et les limites de l'import |
| `docs/reports/phase-5-increment-1-import-complet.md` | Ce rapport |

Rien n'est committé ni poussé. Aucun fichier du dépôt de pilotage n'a été
modifié. La roadmap n'a pas été touchée et aucune phase n'est déclarée close :
la validation finale vous revient.

### Passage complet

`pytest` : **1 126 passés** en 1 292,84 s (21 min 33 s), sortie `0`, aucun
échec et aucun ignoré. Les 1 110 cas du départ, plus les seize cas ajoutés.
Un seul passage, aucune relance, aucune suite concurrente.

## 8. Revue et clôture Codex — 2 novembre 2026

Extension et tests revus : sélection explicite --all réutilisant le chemin
pilote, transaction globale, relations en deuxième passe, préservation des
fiches déjà présentes et exclusion des cibles supprimées. Pas de nouveau
modèle, permission ou moteur générique. Les cas ajoutés couvrent des risques
distincts ; aucune protection ni assertion de contrat retirée.

Correction documentaire localisée : docstrings du module et des nouveaux
helpers raccourcies en anglais ; description de Command actualisée ; retrait
des docstrings redondantes des nouveaux tests. Les noms de tests existants
et leurs assertions sont préservés. Équivalence AST hors docstrings contrôlée,
avec Ruff et format sur les deux fichiers affectés. Aucun test ni import
relancé : le comportement n'a pas changé et les 1 126 résultats sont réutilisés.

Import réel et essais utilisateur désormais réalisés et tracés dans le
rapport de l'incrément 3. Phase 5 clôturée, code et rapports inclus dans
la clôture Git normale ; aucune donnée du corpus ou sauvegarde ajoutée au dépôt.
