# The promoted artifact is the scanned linux/amd64 image, not an unreviewed rebuild.
ARG BASE_IMAGE=cgr.dev/chainguard/wolfi-base@sha256:256c88bb066424045021090932d50be93c8e3f2ce3586707702a401b146f3e43
FROM ${BASE_IMAGE} AS runtime

# Retain the real APK inventory. Pin the complete OS package set, including
# timezone data required by Arrow, and preserve signed-package archive hashes.
COPY containers/wolfi-packages.lock /opt/buildinfo/wolfi-packages.lock
RUN sed '/^#/d; /^$/d' /opt/buildinfo/wolfi-packages.lock > /tmp/package-pins \
    && apk add --no-cache $(cat /tmp/package-pins) \
    && mkdir /tmp/package-archives \
    && apk fetch --no-cache --world --output /tmp/package-archives \
    && sha256sum /tmp/package-archives/*.apk > /opt/buildinfo/apk-sha256.txt \
    && rm -rf /tmp/package-archives /tmp/package-pins

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONPATH=/app/src \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    AI_GATEWAY_WORKSPACE=/tmp/ai-command-gateway \
    AI_GATEWAY_JOB_MODE=demo \
    PATH=/opt/venv/bin:$PATH

WORKDIR /app

FROM runtime AS build
RUN python3.13 -m venv /opt/venv
COPY containers/python-linux-amd64.lock /opt/buildinfo/python-linux-amd64.lock
RUN python -m pip install --no-cache-dir --only-binary=:all: --require-hashes \
    --report /opt/buildinfo/python-downloads.json -r /opt/buildinfo/python-linux-amd64.lock

COPY pyproject.toml ./
COPY src/ai_command_gateway/ ./src/ai_command_gateway/
RUN python -m pip install --no-cache-dir --no-build-isolation --no-deps \
    --report /opt/buildinfo/application-install.json . \
    && python -m pip uninstall --yes pip

FROM runtime AS final
COPY --from=build /opt/venv /opt/venv
COPY --from=build /opt/buildinfo/ /opt/buildinfo/
COPY pyproject.toml requirements-runtime.lock requirements-azure.lock ./
COPY src/ai_command_gateway/ ./src/ai_command_gateway/
COPY config/policies/demo-policy.json config/policies/unqualified-policy.json ./config/policies/
COPY data/contracts/ ./data/contracts/
COPY data/lineage/source-inventory.json ./data/lineage/
COPY data/evaluation/advice-cases-v1.json ./data/evaluation/
COPY data/samples/demo-request.json ./data/samples/

RUN addgroup -g 10001 appuser && adduser -D -u 10001 -G appuser appuser
USER 10001:10001
ENTRYPOINT ["python", "-m", "ai_command_gateway.azure_job"]
