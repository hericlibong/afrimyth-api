# Authentication

[Back to the README](../README.md)

Three endpoints issue, refresh and verify JSON Web Tokens. They carry
credentials in a request body, and create no content.

| Method | Path | Auth | Purpose |
| --- | --- | --- | --- |
| `POST` | `/api/auth/token/` | none | Exchange credentials for a token pair |
| `POST` | `/api/auth/token/refresh/` | none | Exchange a refresh token for a new access token |
| `GET` | `/api/auth/me/` | access token | Return the caller's own identity |

The access token is also what opens the private editorial routes described
above — together with an editorial group.

## Obtain a token pair

```bash
curl -X POST http://127.0.0.1:8000/api/auth/token/ \
  -H "Content-Type: application/json" \
  -d '{"username": "<username>", "password": "<password>"}'
```

```json
{
  "access": "eyJhbGciOi...",
  "refresh": "eyJhbGciOi..."
}
```

- **`access`** lives 5 minutes outside development and is sent on every request
  that needs authentication. With `DJANGO_DEBUG=True`, its lifetime defaults
  to 20 minutes for exercises, configurable through `JWT_DEV_ACCESS_MINUTES`.
  This override is ignored when debug is disabled.
- **`refresh`** lives 1 day and is sent **only** to the refresh endpoint.

The two are not interchangeable: a refresh token is refused as an access
token, and an access token is refused as a refresh token.

Errors: `400` when `username` or `password` is missing, `401` when the
credentials are refused. The `401` body is identical whether the account does
not exist, the password is wrong, or the account is inactive — it never
reveals which.

## Use the access token

```bash
curl http://127.0.0.1:8000/api/auth/me/ \
  -H "Authorization: Bearer <access token>"
```

```json
{"id": 1, "username": "example-contributor"}
```

The response carries `id` and `username` only. Email address, password hash,
permissions, group membership and administrative flags are deliberately not
exposed.

`401` is returned when no token is sent, or when the token is malformed,
expired, signed with another key, is a refresh token, or belongs to an account
that has since been deactivated or deleted. This endpoint accepts JWT only: an
open administration session is not enough, because its purpose is to prove
that a *token* works.

## Refresh the access token

```bash
curl -X POST http://127.0.0.1:8000/api/auth/token/refresh/ \
  -H "Content-Type: application/json" \
  -d '{"refresh": "<refresh token>"}'
```

```json
{"access": "eyJhbGciOi..."}
```

No `Authorization` header is needed: the refresh token in the body *is* the
credential. The response carries a new `access` and nothing else — rotation is
disabled, so the client keeps the refresh token it already has.

## Authentication is not authorisation

Holding a token proves who the caller is; it does not say what the caller may
do. On the public routes a valid token changes nothing at all: they return
exactly what a stranger sees. Access to the private editorial routes requires
a Django group on top of the token, checked server-side on every request — and
an account with a token but no group is refused with `403`.

Every write is private, and none lets a client choose the owner or the
editorial status, whatever its role. The right to write on one record — its own
fields or one of its children — is checked on that record, not only on the
route.

## Caveats

- **No revocation.** Rotation and token blacklisting are not enabled.
  Refreshing does not invalidate the previous access token, which stays usable
  until it expires on its own, and discarding a token in your client does not
  cancel it server-side. There is no logout endpoint, and none is implied. A
  compromised token therefore stays valid for up to its lifetime — 5 minutes
  for an access token (20 minutes by default in development), 1 day for a
  refresh token.
- **Use HTTPS outside localhost.** Tokens are bearer credentials: anyone
  holding one is the account until it expires. Over plain HTTP they travel in
  clear text and can be captured and replayed. The same applies to the
  password sent to the token endpoint.
- **No brute-force protection.** The token endpoint has no rate limit, no
  attempt counter and no lockout. On a public deployment, throttling has to be
  added — DRF throttling, a reverse proxy, or both.
- **Signing key.** Tokens are signed with HS256 using `DJANGO_SECRET_KEY`.
  Rotating that key invalidates every token in circulation. Use a key of at
  least 32 bytes: a shorter one is accepted but weakens the signature, and
  PyJWT warns about it.
- **An invalid `Authorization` header breaks public reads too.** DRF
  authenticates before it checks permissions, so a stale or mistyped Bearer
  header produces `401` even on an endpoint that needs no authentication at
  all. If a public read suddenly fails, remove the header before suspecting
  the API.
- **No self-service.** There is no registration endpoint and no password
  reset. Accounts are created through the Django administration.
