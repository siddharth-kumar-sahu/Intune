# Intune

[![Python](https://img.shields.io/badge/python-3.11+-blue.svg)]()
[![Django](https://img.shields.io/badge/django-5.x-green.svg)]()

## Table of Contents

- [Project Overview](#project-overview)
- [Tech Stack](#tech-stack)
- [Features](#features)
- [Prerequisites](#prerequisites)
- [Environment & Configuration](#environment--configuration)
- [Postgres + pgvector setup](#postgres--pgvector-setup)
- [Install & Run (beginner-friendly)](#install--run-beginner-friendly)
  - [1. Clone the repo](#1-clone-the-repo)
  - [2. Install `uv` (recommended) and project dependencies](#2-install-uv-recommended-and-project-dependencies)
  - [3. Configure environment variables](#3-configure-environment-variables)
  - [4. Initialize the database and extensions](#4-initialize-the-database-and-extensions)
  - [5. Create an initial user (manual) — required on first clone](#5-create-an-initial-user-manual--required-on-first-clone)
  - [6. Run Redis and Celery](#6-run-redis-and-celery)
  - [7. Start the development server](#7-start-the-development-server)

- [Embedding storage & pgvector notes](#embedding-storage--pgvector-notes)
- [Troubleshooting](#troubleshooting)
- [Development tips](#development-tips)

---

## Project Overview

**Intune** is a conversational AI assistant for internal teams that lets users query and summarize company documentation, Slack threads, and meeting notes. The assistant is built with Django and stores embeddings in PostgreSQL using `pgvector`. Background processing (embedding generation, text ingestion, scheduled tasks) runs through Celery with Redis as the broker.

This README contains step-by-step instructions so a beginner can clone and run the project locally.

## Tech Stack

- Python (3.11+ recommended)
- Django (project: `intune`)
- Postgres (with `pgvector` extension)
- Redis (Celery broker & cache)
- Celery (task queue)
- `uv` — package/project manager (recommended for installing dependencies)
- pgvector — to store embeddings inside Postgres

## Features

- Conversational query interface over internal docs and notes
- Persistent storage with PostgreSQL
- Embeddings stored in pgvector for similarity search
- Background jobs (ingestion, embedding creation) via Celery + Redis
- Admin pages to view documents and ingestion status

## Prerequisites

- Git
- Python 3.11+ installed
- PostgreSQL (13+) running locally or accessible remotely
- Redis server (local or Docker)
- `uv` (recommended) or `pip`/`venv` for dependency management

## Environment & Configuration

Copy `.env.example` to `.env` (or create your own). Example variables (update values):

> **Tip:** Keep secrets out of version control. Use `.env` + `django-environ` (or similar) to load environment variables.

## Postgres + pgvector setup

1. Install PostgreSQL and create the database (example using psql):

```bash
# create DB and user (example)
CREATE ROLE intune WITH LOGIN SUPERUSER;
ALTER ROLE intune WITH PASSWORD 'intune';
CREATE DATABASE intune WITH OWNER intune
```

2. Install the `pgvector` on your Postgres instance. Checkout this page[https://github.com/pgvector/pgvector] for doing necessary installation according to operating system.

_References:_ pgvector is the extension used to store and query embeddings inside Postgres. Make sure the extension is available in your DB server.

## Install & Run (beginner-friendly)

All commands assume your shell is at the project root.

### 1. Clone the repo

```bash
git clone <repo_url>
cd intune
```

### 2. Install `uv` (recommended) and project dependencies

`uv` is a modern, fast Python package/project manager (recommended). If you want to use `uv`, install it following [https://astral.sh/uv](https://astral.sh/uv) (or use pip/venv).

Using `uv`:

```bash
uv sync
```

If you prefer `venv` + `pip`:

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### 3. Configure environment variables

Copy the environment variable from .env.example to .env

### 4. Initialize the database and extensions

```bash
# make migrations & migrate
python manage.py migrate

```

### 5. Create an initial user (manual) — required on first clone

You mentioned that the first person cloning the repo must create a user manually. Here are explicit steps a beginner can follow.

```bash
# open Django shell
python manage.py shell
```

Then run these Python commands inside the shell (replace credentials):

```py
user = User(email="team@intune.com", full_name="Intune Admin")
user.set_password('1234')
user.save()
```

Exit the shell. You should now be able to log in to the admin and the app with that user.

### 6. Run Redis and Celery

**Start Redis** (local install or via Docker):

```bash
# using docker
docker run -d --name redis -p 6379:6379 redis:7

# or if installed locally
redis-server &
```

**Start Celery worker (from project root)** — replace `intune` with your Django project module if different:

```bash
celery -A intune worker -l info

```

You may want to run the worker in a separate terminal or use a process manager (tmux, systemd, or Docker Compose) for production.

### 7. Start the development server

```bash
# runserver
python manage.py runserver
```

Open `http://127.0.0.1:8000` in your browser.

## Troubleshooting

- **Cannot create extension `vector`:** the Postgres server may not have pgvector installed. Use a Docker image that includes pgvector or install the extension on the server following the pgvector README.
- **Celery cannot connect to Redis:** verify `REDIS_URL` and that Redis is running on the expected port.
- **Dependency errors with `uv`:** ensure `uv` is installed correctly (see uv docs). Alternatively use `venv` + `pip`.
- **Migrations fail:** check `DATABASE_URL`, run migrations, and verify Postgres user permissions.

## Development tips

- Use separate Docker Compose for local development (web, postgres with pgvector image, redis, worker) to mirror production.
- Keep the `.env` out of git. Add `.env` to `.gitignore`.
- Add a management command to programmatically create a default user or to seed demo data so new developers don’t have to open the shell manually.

---

If you want, I can:

- Add a `docker-compose.yml` example (Postgres + pgvector image, Redis, web, worker) for one-command local dev.
- Add a management command to create the initial user automatically.
- Convert the env examples to a sample `.env.example` file.