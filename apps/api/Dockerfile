FROM python:3.12-slim@sha256:57cd7c3a7a273101a6485ba99423ee568157882804b1124b4dd04266317710de

ARG PIP_VERSION=26.1.2

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_ROOT_USER_ACTION=ignore

WORKDIR /workspace/apps/api

RUN groupadd --system gamelens \
    && useradd --system --gid gamelens --create-home gamelens

COPY apps/api/requirements.lock ./

RUN python -m pip install --upgrade "pip==${PIP_VERSION}" \
    && python -m pip install -r requirements.lock

COPY --chown=gamelens:gamelens apps/api/pyproject.toml apps/api/README.md ./
COPY --chown=gamelens:gamelens apps/api/app ./app
COPY --chown=gamelens:gamelens apps/api/alembic.ini ./
COPY --chown=gamelens:gamelens apps/api/alembic ./alembic
COPY --chown=gamelens:gamelens apps/api/tests ./tests
COPY --chown=gamelens:gamelens data/seed /workspace/data/seed

RUN python -m pip install --no-deps --no-build-isolation .

USER gamelens

EXPOSE 8000

CMD ["python", "-m", "app"]
