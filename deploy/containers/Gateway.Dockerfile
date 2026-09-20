FROM node:22.19.0-bookworm-slim@sha256:4a4884e8a44826194dff92ba316264f392056cbe243dcc9fd3551e71cea02b90 AS build
ENV CI=true
RUN npm install -g pnpm@11.22.0 --ignore-scripts
WORKDIR /build/frontend
COPY contracts/prototype-events.json /build/contracts/prototype-events.json
COPY frontend/package.json frontend/pnpm-lock.yaml ./
RUN pnpm install --frozen-lockfile --ignore-scripts
COPY frontend/ ./
RUN pnpm build

FROM caddy:2.10.2-alpine@sha256:4c6e91c6ed0e2fa03efd5b44747b625fec79bc9cd06ac5235a779726618e530d
RUN set -eu; command -v getcap >/dev/null; command -v setcap >/dev/null; \
    if [ -n "$(getcap /usr/bin/caddy)" ]; then setcap -r /usr/bin/caddy; fi
RUN mkdir -p /data /config && chown -R 10001:10001 /data /config
COPY --from=build /build/frontend/dist /srv
COPY deploy/containers/Caddyfile /etc/caddy/Caddyfile
LABEL org.opencontainers.image.licenses="Apache-2.0"
COPY LICENSE THIRD_PARTY_NOTICES.md /usr/share/doc/ai-radar/
USER 10001:10001
