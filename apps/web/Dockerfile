FROM node:24.18.0-bookworm-slim@sha256:6f7b03f7c2c8e2e784dcf9295400527b9b1270fd37b7e9a7285cf83b6951452d

ENV NEXT_TELEMETRY_DISABLED=1
RUN mkdir -p /opt/gamelens-web-dependencies /workspace \
    && chown -R node:node /opt/gamelens-web-dependencies /workspace

WORKDIR /opt/gamelens-web-dependencies
COPY --chown=node:node package.json package-lock.json ./
USER node
RUN npm ci
COPY --chown=node:node scripts/docker-dev-entrypoint.mjs ./docker-dev-entrypoint.mjs

WORKDIR /workspace
COPY --chown=node:node . .
RUN mkdir -p .next node_modules

USER root

EXPOSE 3000

CMD ["node", "/opt/gamelens-web-dependencies/docker-dev-entrypoint.mjs"]
