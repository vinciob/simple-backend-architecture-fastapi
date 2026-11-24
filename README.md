# simple-backend-architecture-fastapi

A backend API showcase built with FastAPI, Pydantic, SQLAlchemy and PostgreSQL,
focused on a readable, feature-based architecture and the dependency injection
pattern using FastAPI's `Depends`.

Users register, log in and manage their own tasks. Authentication uses Argon2id
password hashes, short-lived JWT access tokens and rotating refresh tokens stored
in an HttpOnly cookie. Database access is asynchronous through SQLAlchemy and
the asyncpg driver.

## Structure

```text
app/
  main.py                       Application factory, lifespan, middleware and routers
  cleanup.py                    Expired-session cleanup entry point
  core/
    config.py                   Environment validation with Pydantic Settings
    database.py                 Async engine, connection pool and session dependency
    errors.py                   Shared errors and HTTP exception handlers
    identifiers.py              Public 24-character hexadecimal IDs
    schemas.py                  Shared Pydantic configuration and camelCase aliases
    security.py                 Password hashing, tokens and authentication dependencies
  modules/
    users/
      routes.py                 Registration, current user and service dependency
      service.py                User registration and retrieval logic
      repository.py             User database operations
      schemas.py                Registration inputs and user responses
      models.py                 SQLAlchemy user model
    auth/
      routes.py                 Login, refresh, logout, origin checks and cookies
      service.py                Authentication and session lifecycle
      repository.py             Session persistence, rotation and replay detection
      schemas.py                Login input and token response
      models.py                 Session and used-refresh-token models
    tasks/
      routes.py                 Task CRUD, pagination and service dependency
      service.py                Task operations and response mapping
      repository.py             Owner-scoped queries and writes
      schemas.py                Task inputs, validation and responses
      models.py                 SQLAlchemy task model
migrations/
  env.py                        Async Alembic configuration and model metadata
  versions/                     Versioned database migrations
```

Each feature groups its routes, services, repositories, schemas and models in
one module. Routes handle HTTP concerns, services coordinate application logic,
and repositories handle database queries and commits. Pydantic schemas validate
inputs and define responses separately from SQLAlchemy models.

### Dependency injection

Dependencies are declared with `Annotated` and `Depends`. Each module's
`get_service` function composes its service and repositories explicitly:

```python
def get_service(database: Annotated[AsyncSession, Depends(get_database)]) -> TaskService:
    return TaskService(TaskRepository(database))


Service = Annotated[TaskService, Depends(get_service)]
```

FastAPI resolves this dependency graph for each request. `get_database` yields
an isolated `AsyncSession` and closes it after the request; repositories commit
complete writes explicitly. Services and repositories receive their dependencies
through their constructors. The shared `UserId` dependency validates the Bearer
token and supplies the authenticated user ID to protected routes.

The `create_app` factory accepts optional settings. Its lifespan creates one
database engine and connection pool per worker, initializes the shared `Security`
instance, and disposes of the engine on shutdown. Dependencies retrieve these
resources from `app.state`.

Alembic migrations create the database schema, including:

- A unique constraint on user email.
- A task owner and ID index for cursor pagination.
- Session user and expiry indexes.
- A used-refresh-token history table for replay detection.
- Foreign keys with cascading deletion and a task-status check constraint.

## Run locally

Requires Python 3.12+, `uv` and PostgreSQL (PostgreSQL 17 is used in Docker
Compose). Docker Compose can supply PostgreSQL while the API runs locally.

```sh
uv sync --frozen
cp .env.example .env
```

Before starting, replace `JWT_SECRET` and `POSTGRES_PASSWORD` in `.env` with
random values. Run the following command once for each value:

```sh
openssl rand -hex 32
```

Set `DATABASE_URL` to your PostgreSQL connection string using the
`postgresql+asyncpg://` scheme. When using the Compose database locally, put the
same password in `POSTGRES_PASSWORD` and the password component of `DATABASE_URL`:

```text
postgresql+asyncpg://showcase:<POSTGRES_PASSWORD>@localhost:5432/showcase
```

| Variable               | Default                    | Description                                               |
| ---------------------- | -------------------------- | --------------------------------------------------------- |
| `ENVIRONMENT`          | `development`              | `development`, `test` or `production`                     |
| `DATABASE_URL`         | Local `showcase` database¹ | PostgreSQL URL using the asyncpg driver                   |
| `DATABASE_POOL_SIZE`   | `20`                       | Connections per worker, from 1 to 200; no pool overflow   |
| `POSTGRES_PASSWORD`    | Required by Compose        | Password for the Compose PostgreSQL service               |
| `JWT_SECRET`           | Required                   | HS256 signing secret, at least 32 characters              |
| `JWT_ISSUER`           | `fastapi-showcase`         | Expected JWT issuer                                       |
| `JWT_AUDIENCE`         | `showcase-api`             | Expected JWT audience                                     |
| `ACCESS_TOKEN_TTL`     | `600`                      | Access-token lifetime in seconds, from 60 to 3600         |
| `REFRESH_TOKEN_TTL`    | `604800`                   | Session lifetime in seconds, from 600 to 2592000          |
| `CLIENT_ORIGIN`        | `http://localhost:5173`    | Allowed frontend origin, matched exactly                  |
| `PASSWORD_CONCURRENCY` | `4`                        | Concurrent password-hashing jobs per worker, from 1 to 16 |

¹ The code default is
`postgresql+asyncpg://showcase:showcase@localhost:5432/showcase`. Configure `.env`
to match your database credentials. Settings are read from `.env` and can be
overridden by environment variables.

Start PostgreSQL, apply migrations and launch the development server:

```sh
docker compose up -d --wait postgres
uv run alembic upgrade head
uv run uvicorn app.main:create_app --factory --reload --host 0.0.0.0 --port 3000
```

If PostgreSQL is already running separately, skip the Compose command. The API
is available at `http://localhost:3000`, with Swagger UI at `/docs`, ReDoc at
`/redoc` and the OpenAPI schema at `/openapi.json`.

Lint, check types and run without automatic reload:

```sh
uv run ruff check app migrations
uv run mypy app
uv run uvicorn app.main:create_app --factory --host 0.0.0.0 --port 3000
```

To run both the backend and PostgreSQL with Docker:

```sh
docker compose up --build
```

Compose reads configuration from `.env` and sets the backend's `DATABASE_URL`
using the `postgres` service hostname and `POSTGRES_PASSWORD`. PostgreSQL must
be healthy before the migration service runs; the backend starts after migrations
complete successfully. The API listens on port `3000`, and database data is kept
in the `postgres_data` volume. PostgreSQL is exposed only on `127.0.0.1:5432`.

The development default supports local HTTP. In production, set
`ENVIRONMENT=production` and serve the API over HTTPS so browsers can send the
Secure refresh cookie.

Expired sessions are rejected during refresh. To also remove their database rows
and associated replay history, run this command periodically through an external
scheduler:

```sh
uv run python -m app.cleanup
```

For a Compose deployment, the equivalent command is
`docker compose run --rm backend python -m app.cleanup`.

## API

The API exposes user registration, authentication, task management and health
checks at the following endpoints. JSON responses use camelCase field names.

| Method | Path               | Auth             | Success response                                  |
| ------ | ------------------ | ---------------- | ------------------------------------------------- |
| GET    | `/health`          | Public           | `200 { status, timestamp }`                       |
| GET    | `/health/db`       | Public           | `200 { status, database }` after PostgreSQL check |
| POST   | `/users`           | Public           | `201 { user }`                                    |
| GET    | `/users/me`        | Bearer           | `200` user object                                 |
| POST   | `/auth/login`      | Public           | `200 { accessToken, tokenType }` + refresh cookie |
| POST   | `/auth/refresh`    | Cookie           | `200 { accessToken, tokenType }` + rotated cookie |
| POST   | `/auth/logout`     | Cookie, optional | `204`, clears cookie                              |
| POST   | `/tasks`           | Bearer           | `201` task object                                 |
| GET    | `/tasks`           | Bearer           | `200` array of task list items                    |
| GET    | `/tasks/{task_id}` | Bearer           | `200` task object                                 |
| PATCH  | `/tasks/{task_id}` | Bearer           | `200` updated task object                         |
| DELETE | `/tasks/{task_id}` | Bearer           | `204`                                             |

`/health` checks the process independently of database availability.
`/health/db` executes a database query and returns `503` when it fails.

### Users

Register with `POST /users`:

```json
{
  "name": "Mario Rossi",
  "email": "mario@example.com",
  "password": "a-long-password-123"
}
```

`name` is trimmed and must be 2–100 characters, email is at most 254 characters,
and password is 12–128 characters. Email is trimmed and lowercased. Registration
returns `{ "user": ... }` and does not create a session. User responses contain
only `id`, `name`, `email` and ISO `createdAt`; password hashes are never returned.

### Login and sessions

`POST /auth/login` accepts `email` and `password`. The response contains an HS256
JWT with `sub` (user ID), `sid` (session ID), issuer, audience and a **10-minute**
lifetime by default:

```json
{
  "accessToken": "<jwt>",
  "tokenType": "Bearer"
}
```

Send it as `Authorization: Bearer <jwt>` on protected routes. In a browser, use
`credentials: 'include'` for login, refresh and logout so the cookie is stored and
sent. CORS permits the frontend origin configured with `CLIENT_ORIGIN`. Auth
routes also reject an `Origin` header that does not match this value; CLI clients
may omit the header.

Refresh tokens expire **7 days after login** by default and are stored only as
SHA-256 hashes in PostgreSQL. Every refresh rotates the token atomically without
extending the original session expiry. Previously used token hashes are kept in
a separate table; reusing one revokes that session. The `refreshToken` cookie is
HttpOnly, SameSite=Lax, restricted to `/auth`, and Secure in production. Logout
revokes the session and clears the cookie, even if the cookie is missing or invalid.

Protected routes verify JWT signatures and claims without looking up the session
on each request. **Logout or refresh-token replay revokes refresh access; an
already issued access token remains valid until its expiry.** Token lifetimes
are configurable with `ACCESS_TOKEN_TTL` and `REFRESH_TOKEN_TTL`.

### Tasks

Create with `POST /tasks`:

```json
{
  "name": "Study FastAPI dependency injection",
  "description": "Follow the route, service and repository dependencies",
  "status": "created",
  "dueDate": "2027-01-30T10:00:00.000Z"
}
```

- `name`: required, 1–120 characters after trimming.
- `description`: optional, at most 2000 characters, defaults to `null`.
- `status`: `created`, `in_progress` or `completed`; defaults to `created`.
- `dueDate`: optional ISO date-time with a timezone, defaults to `null`.

Single-task responses contain `id`, `name`, `description`, `status`, `dueDate`,
`createdAt`, `updatedAt` and `createdBy`. All dates are ISO strings. Public IDs
are 24-character hexadecimal strings.

`GET /tasks` returns an array with only `_id`, `name`, `dueDate` and `status`,
ordered by descending ID. IDs include a time prefix for approximate chronological
ordering. Pagination accepts `limit` (1–100, default 50) and an optional `before`
ID. When more results exist, the response includes `X-Next-Cursor`; send its value
as `before` on the next request, for example
`GET /tasks?limit=20&before=<cursor>`. CORS exposes this header to browser clients.

`PATCH /tasks/{task_id}` accepts any nonempty subset of the create fields.
Omitted fields remain unchanged; `null` clears `description` or `dueDate`.
Whitespace-only names, null names or statuses, empty updates and unexpected
input properties are rejected with `422`.

All task queries include the authenticated owner. Reading, changing or deleting
another user's task returns `404`. Complete or reopen a task with PATCH and the
appropriate `status`.

### Errors

Errors have `code` and `message`. Pydantic request-validation errors also include
an `errors` array with `location` and `code` for each invalid field:

```json
{
  "code": "VALIDATION_ERROR",
  "message": "Validation failed",
  "errors": [{ "location": ["body", "name"], "code": "missing" }]
}
```

Invalid inputs return `422`, authentication failures `401`, disallowed auth
origins `403`, missing resources `404`, and duplicate emails `409`. Database pool
timeouts return `503`. Unexpected errors return a generic `500` response and are
logged on the server.

## Author

Created by Vincenzo Brasca.
