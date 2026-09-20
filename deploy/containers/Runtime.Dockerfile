FROM node:22.19.0-bookworm-slim@sha256:4a4884e8a44826194dff92ba316264f392056cbe243dcc9fd3551e71cea02b90 AS build
ENV CI=true
RUN npm install -g pnpm@11.22.0 --ignore-scripts
WORKDIR /app/agent/runtime
COPY agent/runtime/package.json agent/runtime/pnpm-lock.yaml ./
RUN pnpm install --frozen-lockfile --ignore-scripts
COPY agent/runtime/tsconfig.json ./
COPY agent/runtime/src ./src
RUN pnpm build && pnpm prune --prod

FROM node:22.19.0-bookworm-slim@sha256:4a4884e8a44826194dff92ba316264f392056cbe243dcc9fd3551e71cea02b90
ENV NODE_ENV=production HOME=/nonexistent
WORKDIR /app/agent/runtime
COPY --from=build /app/agent/runtime/node_modules ./node_modules
COPY --from=build /app/agent/runtime/dist ./dist
COPY agent/runtime/package.json ./package.json
COPY agent/research /app/agent/research
COPY deploy/containers/runtime-entry.mjs ./container.mjs
LABEL org.opencontainers.image.licenses="Apache-2.0"
COPY LICENSE THIRD_PARTY_NOTICES.md /usr/share/doc/ai-radar/
USER 10001:10001
ENTRYPOINT ["node", "container.mjs"]
