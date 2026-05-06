# Telegram Crawler

Standalone Python service that discovers public Telegram groups for the matching service, evaluates them with OpenAI, and stores the resulting metadata in the matching service PostgreSQL database.

The crawler is read-only and discovery-only. It does not auto-message users, join private groups, or perform outreach.

## Local Setup

Create a local environment file from the example:

```sh
cp .env.example .env
```

Update `.env` with real values. From inside Docker, PostgreSQL must be reached through the Docker network host `matching-db`, not `127.0.0.1`.

Required variables:

```sh
DATABASE_URL=postgresql://USER:PASSWORD@matching-db:5432/DB_NAME
TELEGRAM_API_ID=CHANGE_ME
TELEGRAM_API_HASH=CHANGE_ME
TELEGRAM_SESSION_NAME=telegram-crawler
OPENAI_API_KEY=CHANGE_ME
OPENAI_MODEL=gpt-4.1-mini
CRAWLER_KEYWORDS=помощь в Германии,жизнь в Германии,вопросы Германия,expats germany,life in germany,moving to germany
CRAWLER_INTERVAL_SECONDS=1800
LOG_LEVEL=INFO
```

Get `TELEGRAM_API_ID` and `TELEGRAM_API_HASH` from [my.telegram.org](https://my.telegram.org) by creating an application. The crawler needs an authorized Telethon session. You can persist a file session in the Docker volume with:

```sh
docker compose run --rm telegram-crawler python -m app.main --login
```

Alternatively, set `TELEGRAM_SESSION` to a Telethon string session if you manage sessions outside the container.

## Docker Compose

Build and start the crawler:

```sh
docker compose build
docker compose up -d
```

View logs:

```sh
docker logs -f matching-telegram-crawler
```

Stop the crawler:

```sh
docker compose down
```

This compose file runs only the crawler. It attaches to the external `matching-service_default` network and expects the existing PostgreSQL container to be available as `matching-db`.

## Production Deployment

Production deploys to:

```sh
/srv/telegram-crawler
```

The server must have a production `.env` file at:

```sh
/srv/telegram-crawler/.env
```

On first deployment, the workflow may create `/srv/telegram-crawler/.env` from `.env.example` and fail intentionally. SSH into the server, edit the generated file, fill in real production values, then re-run GitHub Actions or push again:

```sh
ssh root@46.224.91.140
nano /srv/telegram-crawler/.env
```

Fill real values for:

```sh
DATABASE_URL
TELEGRAM_API_ID
TELEGRAM_API_HASH
OPENAI_API_KEY
```

`.env.example` contains only placeholders/defaults and is safe to commit. `.env` contains real secrets and must never be committed.

Every push to `main` runs the GitHub Actions workflow, SSHes into the server, updates only this repository in `/srv/telegram-crawler`, rebuilds the `telegram-crawler` image, and restarts only the `matching-telegram-crawler` container.

The deployment does not restart or modify the Symfony app, PostgreSQL container, or any `matching-service` containers.
//