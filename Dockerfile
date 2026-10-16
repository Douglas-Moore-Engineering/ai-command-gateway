# Supply a reviewed digest with --build-arg PYTHON_IMAGE=python:3.10-slim@sha256:... for promotion.
ARG PYTHON_IMAGE=python:3.10-slim@sha256:6ff506466f8b1e981719b468cc0023b8ef000b983cdec0eafe119d01f379e31d
FROM ${PYTHON_IMAGE}

# Apply the reviewed Debian 13 security fix without changing the base release.
RUN apt-get update \
    && apt-get install --yes --no-install-recommends --only-upgrade liblzma5=5.8.1-1+deb13u2 \
    && rm -rf /var/lib/apt/lists/*

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONPATH=/app/src \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    AI_GATEWAY_WORKSPACE=/tmp/ai-command-gateway \
    AI_GATEWAY_JOB_MODE=demo

WORKDIR /app
COPY requirements-runtime.lock requirements-azure.lock ./
RUN python -m pip install --no-cache-dir -r requirements-runtime.lock -r requirements-azure.lock

COPY pyproject.toml ./
COPY src/ai_command_gateway/ ./src/ai_command_gateway/
RUN python -m pip install --no-cache-dir --no-build-isolation --no-deps . \
    && python -m pip uninstall --yes pip

COPY config/policies/demo-policy.json config/policies/unqualified-policy.json ./config/policies/
COPY data/contracts/ ./data/contracts/
COPY data/lineage/source-inventory.json ./data/lineage/
COPY data/evaluation/advice-cases-v1.json ./data/evaluation/
COPY data/samples/demo-request.json ./data/samples/

RUN useradd --create-home --uid 10001 --user-group appuser
USER 10001:10001
ENTRYPOINT ["python", "-m", "ai_command_gateway.azure_job"]
