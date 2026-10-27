# Groupes et lecture privée — guide interne

Document de travail interne, en français. Il sert à voir **de ses yeux** ce
que les tests prouvent sans le montrer : qu'un rôle et une propriété
sélectionnent réellement des fiches différentes, et que la lecture publique
n'a pas bougé d'un champ.

## Ce qui est déjà vérifié, ce qui reste à faire ensemble

**Automatiquement :** 79 cas couvrent les deux routes privées — matrice rôle ×
propriétaire × statut, comptes sans groupe, `is_staff` seul, groupes étrangers
et multiples, superutilisateur sans groupe, propriétaire nul, fiches
supprimées, 401/403/404, champs ajoutés, références imbriquées autorisées et
interdites, changement de groupe avec le même jeton, et l'impossibilité de
changer la politique par un paramètre. Voir
`mythology/tests/test_private_read.py` et `tests/test_role_groups.py`.

**À faire à la main :** tout ce qui suit est une suite d'**étapes proposées**,
pas un compte rendu d'essais déjà exécutés. Les comptes et les fiches de
démonstration seront créés par toi, dans l'administration : rien n'a été créé
automatiquement dans ta base de développement.

**Ce qui n'a pas été touché.** La migration n'a créé que trois groupes vides,
sans permission Django et sans aucun membre. Les deux comptes existants
conservent exactement leurs droits ; les quatre fiches de la base de
développement conservent leur statut `draft` et leur propriétaire vide.

## État de ta base avant de commencer

```bash
python manage.py showmigrations accounts
```

`0002_business_role_groups` doit être cochée. Les trois groupes
`contributor`, `reviewer` et `administrator` existent alors dans
**Authentification et autorisation → Groupes**, vides.

Point à connaître avant la démonstration : les quatre fiches déjà présentes
ont un propriétaire **vide**. Un contributeur ne les verra donc pas, même sur
la route privée — c'est précisément la règle « un propriétaire nul
n'appartient à aucun contributeur ». C'est pour cela que la démonstration a
besoin de fiches neuves, qui t'appartiennent.

## Préparation

### 1. Lancer le serveur

```bash
python manage.py runserver
```

### 2. Créer les trois comptes de démonstration

Sur `http://127.0.0.1:8000/admin/`, dans **Utilisateurs → Ajouter**, crée
trois comptes reconnaissables comme fictifs :

| Compte proposé | Groupe à cocher |
| --- | --- |
| `demo-contrib-a` | `contributor` |
| `demo-contrib-b` | `contributor` |
| `demo-relecteur` | `reviewer` |

Pour chacun : un mot de passe **fort et unique que tu choisis**, jamais un mot
de passe personnel. Sur le second écran, laisse `Actif` coché, et laisse
`Statut équipe` et `Statut super-utilisateur` **décochés** — y compris pour le
relecteur. C'est volontaire : la démonstration doit montrer que le rôle vient
du groupe, pas de l'accès à l'administration.

Le groupe se coche dans la section **Permissions**, zone *Groupes* : sélectionne
le groupe à gauche et passe-le à droite. Ne touche pas à *Permissions de
l'utilisateur* : les droits de ce projet ne sont pas des permissions Django.

Ne modifie pas le compte que tu utilisais à l'incrément 1, et ne lui ajoute
aucun groupe : il reste utile tel quel, pour voir un refus `403`.

### 3. Créer quatre fiches de démonstration

Dans **Entités → Ajouter**. Chaque fiche demande au minimum un nom, un slug
(prérempli depuis le nom), un type et un genre. Renseigne ensuite `status` et
`created_by`, tous deux modifiables dans ce formulaire.

| Nom proposé | Slug | `status` | `created_by` |
| --- | --- | --- | --- |
| `Demo Brouillon A` | `demo-brouillon-a` | `draft` | `demo-contrib-a` |
| `Demo Soumise A` | `demo-soumise-a` | `submitted` | `demo-contrib-a` |
| `Demo Brouillon B` | `demo-brouillon-b` | `draft` | `demo-contrib-b` |
| `Demo Publiee A` | `demo-publiee-a` | `published` | `demo-contrib-a` |

Type et genre n'ont aucune importance ici ; prends `divinity` et `neutral`.

**Ne change ni le propriétaire ni le statut des quatre fiches existantes**
(Oya, Anansi, Mokele-mbembe, Shango) : elles doivent rester des brouillons
sans propriétaire, c'est leur état de corpus.

Si tu veux aussi observer une référence masquée, ouvre `Demo Brouillon A` et
renseigne son champ **Variante de** avec `Demo Brouillon B`. Cette seule
ligne suffit pour l'étape 5.

### 4. Postman

Réutilise l'environnement de l'incrément 1 : une variable `base_url` valant
`http://127.0.0.1:8000`. Les mots de passe et les jetons des trois comptes
restent dans le **Local Vault**, référencés par `{{vault:…}}`. Aucun export de
collection ne doit contenir un jeton ou un mot de passe ; relis l'export avant
de le partager, et ne le mets pas dans Git.

## Les vérifications, dans l'ordre

Obtiens d'abord un jeton d'accès pour chaque compte, comme à l'incrément 1 :

```
POST {{base_url}}/api/auth/token/
```

Rappel : l'accès vit cinq minutes. Si une requête répond `401` en cours
d'exercice, renouvelle-le — ce n'est pas un refus de rôle.

### 1. Sans jeton, et avec un jeton sans rôle

```
GET {{base_url}}/api/manage/entities/
```

Sans en-tête `Authorization` : **attendu** `401`.

Avec le jeton du compte de l'incrément 1, qui n'appartient à aucun groupe :
**attendu** `403`, et un message qui nomme les trois groupes. Demande ensuite
une fiche *publiée* avec ce même jeton :

```
GET {{base_url}}/api/manage/entities/demo-publiee-a/
```

**Attendu :** `403` là aussi, pas `200`. C'est la distinction la plus
importante de cet incrément : le refus porte sur la **route**, pas sur la
fiche. Lire du contenu publié, c'est exactement à quoi servent les routes
publiques.

### 2. La liste du contributeur A

Avec le jeton de `demo-contrib-a` :

```
GET {{base_url}}/api/manage/entities/
```

**Attendu :** `200`, et une liste contenant `demo-publiee-a`,
`demo-brouillon-a` et `demo-soumise-a` — mais **pas** `demo-brouillon-b`, ni
les quatre fiches de corpus sans propriétaire. Regarde le `count` : il ne
compte que ces trois fiches.

Chaque élément porte deux champs de plus que la liste publique : `status` et
`created_by`.

### 3. La liste du contributeur B

Même requête, jeton de `demo-contrib-b`. **Attendu :** `demo-publiee-a` et
`demo-brouillon-b`, et **pas** les deux fiches de A.

C'est la démonstration centrale : deux contributeurs, la même route, deux
sélections. Rien dans la requête ne diffère.

### 4. La vue du relecteur

Même requête, jeton de `demo-relecteur`. **Attendu :** les quatre fiches de
démonstration **et** les quatre fiches de corpus sans propriétaire, soit huit
au total. Un relecteur lit tout ce qui n'est pas supprimé, propriétaire vide
compris.

Essaie ensuite le détail d'une fiche qui n'est pas la sienne :

```
GET {{base_url}}/api/manage/entities/demo-brouillon-b/
```

**Attendu :** `200` pour le relecteur, `404` pour `demo-contrib-a`. Et le même
`404`, au corps identique, pour un slug qui n'existe pas :

```
GET {{base_url}}/api/manage/entities/jamais-vue/
```

Rien ne permet de distinguer « interdit » de « inexistant ». C'est voulu : un
`403` sur une fiche précise confirmerait son existence.

### 5. Une référence imbriquée, vue par deux rôles

Si tu as relié `Demo Brouillon A` à `Demo Brouillon B` à l'étape 3 :

```
GET {{base_url}}/api/manage/entities/demo-brouillon-a/
```

**Attendu** avec le jeton de `demo-contrib-a` : `variant_of` vaut `null`. Ni
identifiant, ni slug, ni nom de la cible n'apparaissent dans la réponse —
cherche `Demo Brouillon B` dans le corps, il n'y est pas.

**Attendu** avec le jeton de `demo-relecteur` : la même fiche, mais
`variant_of` renseigné avec les quatre champs compacts de la cible.

La même fiche, deux rendus. C'est pour cela qu'élargir le queryset ne
suffisait pas : la garde est dans la représentation elle-même.

### 6. Le détail privé et ses champs éditoriaux

```
GET {{base_url}}/api/manage/entities/demo-soumise-a/
```

Avec le jeton de A. **Attendu :** tous les champs métier du détail public,
plus `status`, `created_by`, `submitted_at`, `reviewed_at`, `reviewed_by` et
`review_notes`.

Vérifie ce qui **n'y est pas** : `created_by` est un nombre, pas un objet. Pas
de nom d'utilisateur, pas d'adresse, pas d'empreinte de mot de passe, aucune
permission. Pas de `deleted_at` ni de `deleted_by` non plus : la suppression
reste hors du contrat.

`submitted_at` vaudra `null` : l'administration ne laisse pas saisir cet
horodatage, qui sera posé par l'action de soumission d'un incrément ultérieur.
C'est normal, pas un bug.

### 7. Le contrat public n'a pas bougé

Avec le jeton du **relecteur**, appelle la route publique :

```
GET {{base_url}}/api/entities/
```

**Attendu :** une seule fiche, `demo-publiee-a`. Pas les brouillons, pas les
fiches de corpus. Compare avec le même appel sans aucun en-tête : réponse
identique, au caractère près.

Puis le détail public de cette fiche :

```
GET {{base_url}}/api/entities/demo-publiee-a/
```

**Attendu :** aucun `status`, aucun `created_by`. Les champs éditoriaux
n'existent que sur la route privée.

Enfin, le détail public d'un brouillon, toujours avec le jeton de relecteur :

```
GET {{base_url}}/api/entities/demo-brouillon-a/
```

**Attendu :** `404`. Détenir un rôle ne change rien à une route publique.

### 8. Un changement de groupe agit tout de suite

Garde le jeton de `demo-contrib-a` tel quel, sans le renouveler. Dans
l'administration, ajoute-lui le groupe `reviewer`. Rappelle sa liste privée :

```
GET {{base_url}}/api/manage/entities/
```

**Attendu :** les huit fiches, avec le **même** jeton. Retire le groupe,
rappelle : la liste redescend à trois.

C'est ce qui justifie de lire les rôles en base à chaque requête plutôt que de
les inscrire dans le jeton : un retrait de droits prendrait sinon effet avec
cinq minutes de retard.

### 9. Aucune écriture, pour personne

Avec le jeton du relecteur :

```
POST {{base_url}}/api/manage/entities/
PATCH {{base_url}}/api/manage/entities/demo-brouillon-a/
```

**Attendu :** `405 Method Not Allowed` dans les deux cas. La route existe en
lecture seule ; aucune action administrative n'a été ajoutée au passage.

### 10. Un paramètre ne change pas la politique

Toujours avec le jeton de `demo-contrib-a` :

```
GET {{base_url}}/api/manage/entities/?status=draft
GET {{base_url}}/api/manage/entities/?search=Demo Brouillon B
```

**Attendu :** `200`, et toujours au plus les trois fiches de A. Un paramètre
inconnu est ignoré ; un paramètre connu **restreint**, il n'ouvre rien.

Vérifie aussi que la navigation est bien la même qu'en public :

```
GET {{base_url}}/api/manage/entities/?entity_type=titan
```

**Attendu :** `400`, avec exactement le message de la collection publique.

## Après la démonstration

Rien ne presse : tu peux garder ces comptes et ces fiches le temps des
incréments suivants, ils serviront aux exercices d'écriture.

Quand tu voudras nettoyer, la voie sûre est l'administration : supprime les
quatre fiches indiquées à l'étape 3, puis les trois comptes indiqués à l'étape 2.
Si tu as renseigné **Variante de**, vide d'abord ce champ sur
`demo-brouillon-a` : `PROTECT` empêche sinon de supprimer sa cible.
**Ne supprime pas les trois
groupes** : ils appartiennent au modèle, pas à la démonstration.

Si tu préfères le terminal, ouvre `python manage.py shell`, puis exécute les
lignes suivantes une par une. Elles ciblent exclusivement les noms de cet
exercice, jamais tous les objets dont le nom commence par `demo-`.
Vérifie d'abord dans l'administration que ces noms désignent bien tes objets
d'exercice. S'ils existaient avant, ne les supprime pas avec ces commandes.

La première mise à jour retire uniquement le lien de variante proposé dans
ce guide. Si une autre fiche référence une des cibles, `PROTECT` continuera
de bloquer sa suppression : examine ce lien, sans le supprimer aveuglément.

```python
from mythology.models import Entity
from accounts.models import User
slugs = ['demo-brouillon-a', 'demo-soumise-a', 'demo-brouillon-b', 'demo-publiee-a']
Entity.objects.filter(slug='demo-brouillon-a', variant_of__slug='demo-brouillon-b').update(variant_of=None)
Entity.objects.filter(slug__in=slugs).delete()
User.objects.filter(username__in=['demo-contrib-a', 'demo-contrib-b', 'demo-relecteur']).delete()
```

Supprime les fiches **avant** les comptes : `created_by` est en `SET_NULL`, si
bien que supprimer un compte d'abord laisserait des fiches orphelines au lieu
de les effacer. Chaque commande affiche ce qu'elle a supprimé ; relis le
décompte avant de passer à la suivante.

Nettoie enfin les mots de passe et jetons de cet exercice dans ton Local
Vault.

## Les extraits à lire, si tu veux comprendre le code

Les principaux extraits sont regroupés ci-dessous.

| Quoi | Où |
| --- | --- |
| La migration qui crée les trois groupes, et son inverse sans effet | `accounts/migrations/0002_business_role_groups.py` |
| D'où viennent les rôles : groupes en base, superutilisateur, `is_staff` ignoré | `accounts/roles.py`, `business_roles()` |
| Le contrôle du rôle sur la route — le 403 | `mythology/permissions.py`, et `PrivateEntityViewSet.caller_roles` dans `mythology/views.py` |
| La sélection des fiches autorisées — le 404 et le `count` | `mythology/selectors.py`, `private_filter()` et `private_entities()` |
| Le rendu des références imbriquées | `mythology/serializers.py`, `PrivateEntityDetailSerializer.get_variant_of()` et `get_relations()` |
| Les jointures et préchargements qui évitent le N+1 | `mythology/selectors.py`, `private_entity_detail()` |
| Les textes publics du schéma | `mythology/schema.py`, section *Private editorial endpoints* |
| Le contrat côté client | `README.md`, section *Private editorial read API* |

Les deux niveaux de contrôle — permission sur la route, filtrage dans le
queryset — ne sont pas une redondance : une permission d'objet n'est jamais
consultée pour les fiches qu'une liste ne renvoie **pas**. Sans le filtrage du
queryset, `count` et `results` divulgueraient des fiches interdites. C'est la
raison pour laquelle le prompt l'exigeait explicitement.
