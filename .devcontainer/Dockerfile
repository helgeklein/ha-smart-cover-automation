FROM mcr.microsoft.com/devcontainers/python:3.14

USER root

RUN apt-get update && apt-get install -y --no-install-recommends build-essential zlib1g-dev \
    && rm -rf /var/lib/apt/lists/*

COPY requirements-lock.txt requirements-test-lock.txt requirements-ruff.txt requirements-devtools.txt /tmp/requirements/

ENV PIP_DISABLE_PIP_VERSION_CHECK=1 \
    SMART_COVER_TEST_LOCK_CHECKSUMS=/usr/local/share/smart-cover-test-locks.sha256
RUN python3 -m pip install --require-hashes --requirement /tmp/requirements/requirements-lock.txt \
    && python3 -m pip install --require-hashes --requirement /tmp/requirements/requirements-test-lock.txt \
    && python3 -m pip install --requirement /tmp/requirements/requirements-ruff.txt \
    && python3 -m pip install --requirement /tmp/requirements/requirements-devtools.txt \
    && (cd /tmp/requirements && sha256sum requirements-lock.txt requirements-test-lock.txt) > "$SMART_COVER_TEST_LOCK_CHECKSUMS" \
    && rm -rf /tmp/requirements

ENV SMART_COVER_DEPS_BAKED=1 PYTHONNOUSERSITE=1

USER vscode