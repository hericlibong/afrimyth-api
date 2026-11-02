# Phase 5 — Incrément 3 : import réel du corpus

Rapport d'intervention, en français. Aucun secret, aucune valeur de `.env`,
aucun mot de passe, aucun jeton, aucun contenu de compte et aucun extrait de
dump n'y figure.

Intervention : Claude CLI, 1er novembre 2026, sur le prompt
`docs/prompts/phase-5-increment-3-import-reel.md`. La simulation séparée de
l'incrément 2 n'a pas été exécutée, conformément à son abandon.

**Aucun code modifié, aucun test relancé.** Les résultats de l'incrément 1 —
1 126 tests passants, 44 figures transformées en base temporaire — sont
réutilisés tels quels. Ni pytest, ni Ruff, ni mypy, ni la validation OpenAPI
n'ont été rejoués. Aucune migration, aucun nettoyage, aucun compte, aucune
décision éditoriale nouvelle.

## 1. Source et cible

| Contrôle | Résultat |
| --- | --- |
| SHA-256 du corpus | `6D9C94CD21FCB8629D19B2C2401D31DD289C0499DD802F3564FCDFBB3A1A58BF` — **conforme** à l'attendu |
| Entrées | **44** — conforme |
| Lecture | seule ; chemin passé par `--input`, rien copié dans le dépôt |
| Base cible | `afrimyth`, `localhost:5432`, moteur `django.db.backends.postgresql` |

Réglages Django chargés normalement, aucune configuration modifiée, aucun
basculement de base. Seuls moteur, nom, hôte et port ont été affichés.

## 2. Sauvegarde avant import

| Élément | Valeur |
| --- | --- |
| Fichier | `C:\Users\heric\dev\backups\afrimyth-api\afrimyth-20261101T190346Z-pre-import.dump` |
| Outil | `pg_dump` 16.3, `--format=custom` |
| Taille | **93 418 octets**, non nulle |
| Contrôle du catalogue | `pg_restore --list` : **233 lignes**, **24 entrées `TABLE DATA`** |
| Tables `mythology_*` présentes | `entity`, `entityrelation`, `source`, les trois profils, `domain`, `country`, `ethnicity`, `culturalarea` et les quatre tables de liaison |

Fichier horodaté, hors Git, aucun fichier écrasé. **Aucune restauration** et
aucune base annexe créées pour ce contrôle. Le mot de passe a été transmis au
sous-processus par son environnement : il n'apparaît ni dans les arguments
affichés, ni dans ce rapport.

## 3. Chiffres avant et après

| Table | Avant | Après le 1er appel | Après le 2e appel |
| --- | --- | --- | --- |
| `Entity` | 5 | **45** | 45 |
| `EntityRelation` | 3 | **22** | 22 |
| `Source` | 0 | 0 | 0 |
| `DivinityProfile` | 1 | 24 | 24 |
| `HeroProfile` | 2 | 9 | 9 |
| `CreatureProfile` | 1 | 11 | 11 |
| `Country` | 2 | 19 | 19 |
| `Ethnicity` | 3 | 23 | 23 |
| `CulturalArea` | 6 | 9 | 9 |
| `Domain` | 13 | 109 | 109 |

Les 5 fiches de départ étaient `shango`, `anansi`, `oya`, `mokele-mbembe` et
`demo-create-hero-a`. Les quatre premières appartiennent au corpus, la
dernière est une démonstration qui lui est étrangère : **40 créations** et non
41, le total global dépassant donc 44 fiches sans anomalie.

## 4. Les deux appels

Commande identique aux deux appels, sortie `0` les deux fois :

```text
python manage.py import_mythology_pilot --input "...\mythology_data.json" --all
```

| Mesure | 1er appel | 2e appel |
| --- | --- | --- |
| Figures lues / sélectionnées | 44 / 44 | 44 / 44 |
| Fiches créées | **40** | **0** |
| Fiches ignorées | 4 (`Shango`, `Anansi`, `Oya`, `Mokele-mbembe`) | **44** |
| Relations créées | **19** — 15 résolues, 4 citées par nom | **0** |
| Notes du bilan | 66 | 49 |

Les 19 relations créées sont inférieures aux 26 de la simulation sur base
vierge : les 3 relations de `Oya` et les 4 de `Shango` ne sont pas recréées,
ces deux fiches étant ignorées. Les fiches ignorées restent utilisables comme
**cibles** : `Oshun —consort→ Shango`, `Ogun —consort→ Oya` et
`Ibeji —parent→ Shango` sont résolues vers les fiches préexistantes.

**Idempotence.** Le relevé complet de la base après le 2e appel est
**strictement identique** à celui pris après le 1er : mêmes volumes, mêmes
contenus, mêmes profils, mêmes collections, mêmes marques éditoriales et mêmes
`updated_at`. Zéro fiche, zéro lien, zéro référentiel ajoutés. Le contrôle
s'est arrêté là, sans répétition supplémentaire.

## 5. Contrôle de préservation

Relevé déterministe en mémoire avant import — champs, profil, collections,
marques éditoriales et `updated_at` — puis comparé après chaque appel.

| Fiche antérieure | Résultat |
| --- | --- |
| `anansi` | identique, `updated_at` inchangé |
| `demo-create-hero-a` | identique, `updated_at` inchangé |
| `mokele-mbembe` | identique, `updated_at` inchangé |
| `oya` | identique, `updated_at` inchangé |
| `shango` | identique, `updated_at` inchangé |

**Aucune réécriture, affectation, suppression ou restauration.** Les deux
fiches qui avaient un propriétaire l'ont conservé ; les notes de revue de
`demo-create-hero-a` sont intactes.

État des 40 nouvelles fiches :

| Contrôle | Résultat |
| --- | --- |
| Statut | 40 en `draft` — et **45 fiches sur 45** en `draft` dans toute la base |
| Propriétaire | aucun des 40 ; les 2 seuls propriétaires sont ceux des fiches antérieures |
| Profil | **40 sur 40**, du type exact ; aucun profil incohérent dans la base |
| Marques éditoriales | aucune soumission, revue, relecteur ni suppression |
| `variant_of` | nul partout (0 dans la base) |
| Sources | 0, le corpus n'en porte aucune |
| Publication | aucune ; rien n'est visible de l'API publique |

## 6. Limites conservées, inchangées

- **`Congo`** : ligne créée **sans** code ISO, signalée au bilan. Aucun
  arbitrage pris entre République du Congo et doublon de la RDC.
- **Termes proches non fusionnés** : synonymes de domaines
  (`Change`/`Transformation`, `Ocean`/`Oceans`/`Sea`, `Stealth`/`Sneaking`,
  `Thunder`/`Lightning`) et ethnonymes voisins restent des valeurs distinctes.
  Les 109 domaines et 23 ethnies reflètent ce choix.
- **`descendants` non convertis** : 6 noms cités sur 4 figures, conservés dans
  le bilan et dans aucun lien.
- **Cibles hors corpus** : `Olokun`, cité 4 fois, reste en `to_name`. Aucune
  fiche fantôme, aucun rapprochement flou.
- **Anciennes relations du pilote inchangées** : les 3 relations de `Oya`
  restent en `to_name` (`Ogun`, `Yemaya`, `Shango`) **bien que ces trois
  fiches existent désormais**. L'import ne met pas à jour une fiche existante.
  C'est visible en base : 22 relations dont 15 résolues et 7 citées par nom.
  Les compléter est une **opération distincte**, à décider séparément — je ne
  l'ai pas faite et ne l'ai pas dissimulée derrière l'idempotence.
- **Rendu et images** exclus : `rendering`, `appearance.image_generation_prompt`,
  `appearance.imageUrl` et `origin.pantheon` restent non importés.

## 7. Anomalie préexistante, signalée et non corrigée

`shango` était déjà en base **sans profil**, et l'est resté : l'import l'a
ignorée sans la toucher, comme prévu. C'est la seule fiche sans profil des 45.
L'API refuse ce couple incomplet par un `400` explicite sans le réparer —
comportement voulu depuis l'incrément 4A. Je n'ai rien corrigé par l'ORM.

## 8. Obstacles

**Aucun.** Sauvegarde, import et second appel se sont déroulés sans erreur,
tous en sortie `0`. Aucun conflit d'identité, aucun apport partiel, aucune
transaction annulée, aucune anomalie de préservation. La sauvegarde n'a pas
eu à être restaurée.

## 9. État Git

Aucun commit, aucun push. HEAD `8e55deb`. La roadmap n'a pas été modifiée et
aucune phase n'est déclarée close.

```
 M README.md
 M mythology/management/commands/import_mythology_pilot.py
 M mythology/tests/test_pilot_import.py
?? docs/reports/phase-5-increment-1-import-complet.md
?? docs/reports/phase-5-increment-3-import-reel.md
```

Les trois fichiers modifiés et le premier rapport sont ceux de l'incrément 1,
déjà livrés et non retouchés ici. Cette intervention n'ajoute que ce rapport.
La sauvegarde est hors du dépôt et n'apparaît donc pas dans cet état.

## 10. Vérification Codex après remise — 1er novembre 2026

Rapport conforme au périmètre du prompt : sauvegarde, import réel, unique
réexécution et préservation ; aucune simulation séparée requise. À réception,
les deux copies du rapport avaient la même empreinte SHA-256.

Vérifications indépendantes effectuées sans relancer import ni tests :

- Archive présente, 93 418 octets ; `pg_restore --list` réussi : 233 lignes,
  24 entrées TABLE DATA, dont 14 pour les tables mythology. Aucun essai de
  restauration effectué ; ce contrôle confirme la lecture du catalogue.
- Lecture ORM dans une transaction explicitement `READ ONLY` : les 44 slugs
  du corpus sont présents, aucune figure manquante, 45 fiches au total.
  Tous les décomptes de tables du rapport sont corroborés.
- 40 fiches hors des cinq identités antérieures, toutes en brouillon sans
  propriétaire ni marque éditoriale ; profils cohérents, seule absence de
  profil : Shango, préexistante. 15 relations résolues et 7 citées par nom,
  dont les trois anciennes relations d'Oya, confirmées.
- Aucun processus d'import, pytest, pg_dump ou pg_restore encore en cours
  lors du contrôle des processus. Le rapport est final, sans résultat en attente.

La comparaison historique avant/après et l'identité après la deuxième
exécution sont les résultats consignés par Claude ; les relevés en mémoire
de cette intervention ne sont pas recréés après coup. Le contrôle Codex
corrobore l'état final, sans prétendre avoir réexécuté ces opérations.

Livrable d'import terminé et conforme. Les limites connues sont conservées,
pas corrigées dans ce lot. Roadmap actualisée par Codex : les deux dernières
tâches d'import sont réalisées ; les lectures Postman et la clôture technique
du code livré restent distinctes de cette validation du rapport d'import.

## 11. Validation utilisateur et clôture — 2 novembre 2026

L'auteur a confirmé la présence des fiches dans Django Admin. Dans Swagger,
avec le relecteur : liste privée en 200, count 45 et pagination constatée ;
détail d'Oshun en 200, puis relation consort résolue vers Shango confirmée.
Ces lectures remplacent les essais Postman prévus ; aucune répétition requise.

La phase 5 est terminée. Roadmap actualisée ; limites de Shango, relations
antérieures et ambiguïtés du corpus conservées sans correction implicite.
Revue et correction documentaire du code tracées dans le rapport de
l'incrément 1. Aucun nouvel import, changement en base ou test complet
pendant cette clôture. Git : publication normale du code et des rapports
dans le dépôt API, et du suivi dans le dépôt de pilotage.
