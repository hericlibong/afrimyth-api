# Création privée — guide Postman interne

Document de travail interne, en français. Une étape à la fois, dans l'ordre.
Objectif : créer **une** fiche fictive avec son profil, la relire en privé,
constater son absence en public, puis provoquer une erreur et vérifier
qu'aucune donnée partielle ne subsiste.

## Ce qui est déjà vérifié, ce qui reste à faire ici

**Automatiquement :** 92 cas couvrent la création de bout en bout — les trois
types et leur profil exact, les valeurs par défaut, les doublons de nom et de
slug, les profils incohérents, les champs serveur injectés, les tableaux
invalides, les rattachements inexistants ou redondants, les variantes
interdites, les permissions, le propriétaire et le brouillon imposés, et
l'atomicité sur un échec du profil puis sur un échec de rattachement. Voir
`mythology/tests/test_private_create.py`.

**À faire à la main :** les cinq étapes ci-dessous. Elles sont **proposées**,
pas déjà exécutées. Rien n'a été créé automatiquement dans ta base de
développement : aucune fiche, aucun compte, aucun référentiel.

**Ce qui n'a pas été touché.** Les comptes existants gardent leurs groupes.
Anansi reste la propriété de `demo-contrib-a` ; Oya, Mokele-mbembe et Shango
restent sans propriétaire et en `draft`. Ne les supprime pas et ne les
réattribue pas : c'est leur état de corpus.

## Préparation

### 1. Lancer le serveur

```bash
python manage.py runserver
```

### 2. Obtenir un jeton d'accès pour `demo-contrib-a`

```
POST http://127.0.0.1:8000/api/auth/token/
```

Le mot de passe reste dans ton Local Vault, référencé par `{{vault:…}}` ;
ne l'écris ni dans la collection, ni dans un export, ni dans un rapport.

L'accès vit cinq minutes. Si une requête répond `401` en cours d'exercice,
renouvelle-le : ce n'est pas un refus de rôle.

## Les vérifications, dans l'ordre

### 1. Créer la fiche fictive

```
POST http://127.0.0.1:8000/api/manage/entities/
```

En-têtes : `Authorization: Bearer {{vault:afrimyth-access-token}}` et
`Content-Type: application/json`. Corps, en *Body → raw → JSON* :

```json
{
  "name": "Demo Create Hero A",
  "slug": "demo-create-hero-a",
  "entity_type": "hero",
  "gender": "neutral",
  "category": "Fictional demonstration figure",
  "characteristics": ["Fictional trait"],
  "hero_profile": {
    "titles": ["Fictional title"],
    "quests": ["Fictional quest"]
  }
}
```

**Attendu :** `201`. Dans la réponse, regarde trois choses.

`"status": "draft"` : tu n'as pas fourni de statut, et tu n'aurais pas pu.

`"created_by"` : l'identifiant numérique de `demo-contrib-a`, posé par le
serveur. Pas de nom d'utilisateur, pas d'adresse — un identifiant seul.

`"hero_profile"` renseigné, `"divinity_profile"` et `"creature_profile"` à
`null`. Les champs du profil que tu n'as pas donnés valent `[]` ou `""` : le
profil existe toujours, avec ses valeurs par défaut.

Note l'`id` renvoyé si tu veux t'en servir plus tard ; le slug suffit pour la
suite.

### 2. Relire la fiche en privé

```
GET http://127.0.0.1:8000/api/manage/entities/demo-create-hero-a/
```

**Attendu :** `200`, et une réponse **identique** à celle de l'étape 1. C'est
ce que signifie « la réponse 201 est la représentation du détail privé » :
aucune charge utile d'écriture séparée à apprendre.

Essaie ensuite la même URL avec le jeton de `demo-contrib-b` :

**Attendu :** `404`. Un brouillon n'appartient qu'à son propriétaire, et la
création ne change pas cette règle.

### 3. Constater son absence en public

```
GET http://127.0.0.1:8000/api/entities/demo-create-hero-a/
```

Sans en-tête `Authorization`. **Attendu :** `404`.

Puis la collection publique :

```
GET http://127.0.0.1:8000/api/entities/
```

**Attendu :** `count` à `0`, comme avant cet exercice — toutes les fiches de
ta base sont encore des brouillons. Créer ne publie pas.

Refais le détail public **avec** le jeton de `demo-contrib-a` : toujours
`404`. Détenir un rôle ne change rien à une route publique.

### 4. Provoquer une erreur, sans création partielle

Trois refus à essayer, chacun avec le jeton de `demo-contrib-a`.

**Le statut imposé.** Reprends le corps de l'étape 1, change le slug en
`demo-create-hero-refus` et le nom en `Demo Create Hero Refus`, et ajoute
`"status": "published"`.

**Attendu :** `400`, avec une clé `status` et un message qui explique que le
statut est décidé par le serveur. Pas `201` avec un brouillon silencieux.

**Le mauvais profil.** Même corps, sans `status`, mais remplace
`"hero_profile"` par `"divinity_profile"`.

**Attendu :** `400`, avec une clé `divinity_profile`. Une clé de profil d'un
autre type est refusée, pas ignorée.

**Le slug déjà pris.** Reprends exactement le corps de l'étape 1.

**Attendu :** `400`, avec une clé `slug`. La protection des doublons tient.

Vérifie enfin qu'aucune des trois tentatives n'a rien laissé :

```
GET http://127.0.0.1:8000/api/manage/entities/?search=Demo Create Hero
```

**Attendu :** un seul résultat, `demo-create-hero-a`, celui de l'étape 1.
Aucune fiche `demo-create-hero-refus`, et aucune entité sans profil.

### 5. Les autres écritures restent fermées

Avec le jeton de `demo-contrib-a` :

```
PATCH http://127.0.0.1:8000/api/manage/entities/demo-create-hero-a/
DELETE http://127.0.0.1:8000/api/manage/entities/demo-create-hero-a/
POST http://127.0.0.1:8000/api/manage/entities/demo-create-hero-a/
```

**Attendu :** `405 Method Not Allowed` dans les trois cas. La modification et
la suppression appartiennent aux incréments suivants, et la création se fait
sur la collection, pas sur le détail.

Essaie aussi la création sans jeton, puis avec le jeton d'`essai-postman`,
qui n'appartient à aucun groupe :

**Attendu :** `401` sans jeton, `403` avec `essai-postman`. Le refus porte sur
la route et sur le rôle, avant tout examen du corps.

## Après la démonstration

Rien ne presse : tu peux garder `demo-create-hero-a` pour les exercices de
modification de l'incrément 4.

Quand tu voudras nettoyer, la voie sûre est l'administration : ouvre
**Entités**, cherche `demo-create-hero-a`, et supprime cette seule fiche. Son
profil de héros part avec elle, en `CASCADE`.

Si tu préfères le terminal, ouvre `python manage.py shell` et exécute la ligne
suivante. Elle ne cible que le slug exact créé à l'étape 1 — jamais un préfixe,
jamais `demo-*`. Vérifie d'abord dans l'administration que ce slug désigne bien
ta fiche d'exercice.

```python
from mythology.models import Entity
Entity.objects.filter(slug='demo-create-hero-a').delete()
```

La commande affiche ce qu'elle a supprimé ; relis le décompte. Si une autre
fiche référence celle-ci comme **Variante de**, `PROTECT` bloquera la
suppression : examine ce lien avant de le retirer, ne le supprime pas
aveuglément.

Ne supprime ni les quatre comptes de démonstration, ni les trois groupes, ni
les quatre fiches du corpus pilote.

## Les extraits à lire, si tu veux comprendre le code

| Quoi | Où |
| --- | --- |
| La liste explicite des champs d'entrée | `mythology/serializers.py`, `PrivateEntityCreateSerializer.Meta.fields` |
| Le refus nommé des champs serveur, des collections différées et des clés inconnues | `mythology/serializers.py`, `to_internal_value()`, `reject_entity_keys()` et `reject_profile_keys()` |
| La clé de profil imposée par le type | `mythology/serializers.py`, `reject_mismatched_profiles()` |
| Le refus d'une valeur à la fois principale et secondaire | `mythology/serializers.py`, `reject_overlapping_attachments()` |
| `variant_of` restreint aux fiches lisibles par l'appelant | `mythology/serializers.py`, `validate_variant_of()` |
| Le propriétaire, le brouillon et la transaction unique | `mythology/serializers.py`, `create()` |
| Le couple entité/profil garanti, réutilisé tel quel | `mythology/services.py`, `create_entity_with_profile()` |
| La création ajoutée seule, sans ModelViewSet complet | `mythology/views.py`, `PrivateEntityViewSet` |
| Les textes publics du schéma | `mythology/schema.py`, section *Private editorial creation* |
| Le contrat côté client | `README.md`, section *Create an entity and its profile* |

Deux points méritent un mot.

**Pourquoi refuser un champ serveur au lieu de l'ignorer.** DRF laisse tomber
silencieusement une clé inconnue. Un client qui envoie `"status": "published"`
recevrait alors `201` et croirait avoir publié. Le refus nommé est ce qui
l'empêche de se tromper sur l'état de sa fiche.

**Pourquoi une transaction autour du service.** `create_entity_with_profile()`
garantit déjà le couple entité/profil. Les rattachements plusieurs-à-plusieurs
exigent une fiche déjà enregistrée, donc ils viennent après : sans transaction
englobante, un échec de rattachement laisserait une fiche créée à moitié
rattachée.
