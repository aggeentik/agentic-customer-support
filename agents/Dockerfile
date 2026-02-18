# ---------------------------------------------------------------------------
# Supervisor Agent — AgentCore Runtime container
#
# Build target: linux/arm64 (matches CodeBuild ARM_CONTAINER + ECR)
# strands-agents[otel] provides native OTEL tracing — no extra distro needed.
# OTEL_EXPORTER_OTLP_ENDPOINT is injected at runtime by the AgentCore Runtime.
# ---------------------------------------------------------------------------

FROM public.ecr.aws/docker/library/python:3.11-slim

WORKDIR /app

# Install dependencies first (layer cache-friendly)
COPY requirements.txt requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

# Non-root user required by AgentCore Runtime security policy
RUN useradd -m -u 1000 bedrock_agentcore
USER bedrock_agentcore

# AgentCore Runtime service ports
# 8080 — HTTP /invocations + /ping (entrypoint)
# 8000 — OTEL metrics exporter
EXPOSE 8080
EXPOSE 8000

COPY . .

HEALTHCHECK --interval=30s --timeout=3s --start-period=10s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8080/ping')" || exit 1

CMD ["python", "-m", "supervisor_agent"]
