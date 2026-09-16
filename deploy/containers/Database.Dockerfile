FROM pgvector/pgvector:0.8.6-pg16-bookworm@sha256:ccc6e83d6e35e931dc7c5def2022729d5a6c370318d099181995567ff1fb4d6b
RUN groupmod -g 10001 postgres && usermod -u 10001 -g 10001 postgres \
    && chown -R 10001:10001 /var/lib/postgresql /var/run/postgresql
COPY --chmod=0555 deploy/containers/init-database.sh /docker-entrypoint-initdb.d/10-radar.sh
USER 10001:10001
