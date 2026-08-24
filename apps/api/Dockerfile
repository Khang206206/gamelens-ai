FROM python:3.12-slim@sha256:57cd7c3a7a273101a6485ba99423ee568157882804b1124b4dd04266317710de

ARG PIP_VERSION=26.1.2
ARG APP_UID=1000
ARG APP_GID=1000

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_ROOT_USER_ACTION=ignore

WORKDIR /workspace/apps/api

RUN test "${APP_UID}" -ne 0 \
    && test "${APP_GID}" -ne 0 \
    && groupadd --non-unique --gid "${APP_GID}" gamelens \
    && useradd --non-unique --uid "${APP_UID}" --gid gamelens --create-home \
        --shell /usr/sbin/nologin gamelens

COPY apps/api/requirements.lock ./

RUN python -m pip install --upgrade "pip==${PIP_VERSION}" \
    && python -m pip install -r requirements.lock

COPY --chown=gamelens:gamelens ml/pyproject.toml ml/README.md /workspace/ml/
COPY --chown=gamelens:gamelens ml/src /workspace/ml/src

RUN python -m pip install --no-deps --no-build-isolation /workspace/ml

COPY --chown=gamelens:gamelens apps/api/pyproject.toml apps/api/README.md ./
COPY --chown=gamelens:gamelens apps/api/app ./app
COPY --chown=gamelens:gamelens apps/api/alembic.ini ./
COPY --chown=gamelens:gamelens apps/api/alembic ./alembic
COPY --chown=gamelens:gamelens apps/api/tests ./tests
COPY --chown=gamelens:gamelens data/catalog /workspace/data/catalog

RUN python -m pip install --no-deps --no-build-isolation .

# The application and its Python runtime do not use Perl. Remove the base-image
# package only after every install/user-management step, then fail the build if
# the package remains, dpkg reports damage, Python requirements break, or the
# application runtime can no longer import.
RUN dpkg --purge --force-remove-essential perl-base \
    && ! dpkg-query --show perl-base \
    && test -z "$(dpkg --audit)" \
    && python -m pip check \
    && python -c "import app, gamelens_recommender"

USER gamelens

EXPOSE 8000

CMD ["python", "-m", "app"]
