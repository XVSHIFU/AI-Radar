# Supply a reviewed python:3.12-slim-bookworm@sha256:... reference at build time.
ARG PYTHON_BASE
FROM ${PYTHON_BASE} AS build
WORKDIR /build
COPY requirements.lock ./requirements.lock
RUN python -m pip install --no-cache-dir --require-hashes --target=/opt/analysis -r requirements.lock

FROM ${PYTHON_BASE}
# Runtime has no package installer; network isolation is enforced externally.
RUN python -m pip uninstall --yes pip setuptools wheel \
    && python -c "import pathlib, shutil, sysconfig; shutil.rmtree(pathlib.Path(sysconfig.get_path('stdlib')) / 'ensurepip', ignore_errors=True)"
COPY --from=build /opt/analysis /opt/analysis
COPY worker.py /opt/worker.py
ENV PYTHONPATH=/opt/analysis PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 \
    MPLBACKEND=Agg MPLCONFIGDIR=/tmp/matplotlib OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1
USER 65532:65532
WORKDIR /tmp
ENTRYPOINT ["python", "-B", "/opt/worker.py"]
