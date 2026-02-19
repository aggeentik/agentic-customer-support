# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

An AI-powered customer support automation system. Human support agents click "Generate" in their CRM, which triggers a single API call to a multi-agent AI backend that returns a structured JSON response (suggested reply, workflow actions, citations). The human agent reviews and sends — the AI never communicates directly with end customers.

**Status:** Infrastructure and agent code are implemented and deployed. The current PoV (Proof of Value) phase uses a single Knowledge Base populated with a 2022 BMW 5 Series user guide PDF.

## Architecture

### Multi-Agent System (Agents-as-Tools pattern)

```
CRM / streamlit_demo.py
    → AgentCore Runtime (serverless ARM64 container, ECR image built by CodeBuild)
        → SUPERVISOR AGENT (Claude Sonnet 4.5)
              ├── CLASSIFIER AGENT (Claude Haiku 4.5)  — intent classification only, no tools
              ├── INFORMATIONAL AGENT (Claude Sonnet 4.5) — RAG via custom retrieve_kb tool
              └── WORKFLOW AGENT (Claude Haiku 4.5)    — action execution via AgentCore Gateway (MCP)
```

**Request flow:**
1. CRM POSTs customer context to the AgentCore Runtime (or `streamlit_demo.py` invokes via boto3)
2. Supervisor calls Classifier → `INFORMATIONAL` or `BUSINESS_WORKFLOW`
3. Informational Agent queries the Bedrock Knowledge Base via a custom `retrieve_kb` tool (pure vector search, Pinecone backend)
4. Workflow Agent calls Lambda/Step Functions tools via AgentCore Gateway (MCP Streamable HTTP + Cognito OAuth2)
5. Supervisor returns structured JSON; human reviews before sending

### Technology Stack

| Component | Technology |
|-----------|-----------|
| Agent SDK | Strands Agents (Python), `strands-agents[otel]` |
| Agent Runtime | Amazon Bedrock AgentCore Runtime (ARM64 container) |
| Orchestration LLM | `us.anthropic.claude-sonnet-4-5-20250929-v1:0` |
| Classification/Workflow LLM | `us.anthropic.claude-haiku-4-5-20251001-v1:0` |
| RAG | Bedrock Knowledge Bases + **Pinecone** serverless index (cosine, pure vector search) |
| Embeddings | Amazon Titan Text Embeddings V2 (1024 dims, FLOAT32) |
| Tool connectivity | AgentCore Gateway (MCP Streamable HTTP protocol) |
| Workflow execution | AWS Lambda + Step Functions (via Gateway) |
| Auth (Gateway) | Cognito OAuth2 client credentials (`GATEWAY_TOKEN_ENDPOINT`) |
| Auth (Runtime) | Bedrock AgentCore Identity (workload access tokens) |
| Observability | Strands native OTEL → X-Ray (`OTEL_EXPORTER_OTLP_ENDPOINT`) |
| Guardrails | Bedrock Guardrails (PII redaction + competitor topic denial) |
| Container build | AWS CodeBuild (ARM, `linux/arm64`), source from S3 |
| Container registry | Amazon ECR |
| IaC | Terraform >= 1.6, AWS provider ~> 6.21, pinecone-io/pinecone ~> 2.0 |

### Knowledge Base (PoV phase)

A single Bedrock KB (`customer-support-public-docs`, ID in `KNOWLEDGE_BASE_ID` env var) backed by Pinecone serverless:
- **Data**: `data/2022-bmw-5-series.pdf` — uploaded to S3 by Terraform, ingested via Bedrock data source
- **Chunking**: hierarchical (parent 600 tokens / child 150 tokens, 40-token overlap)
- **Parsing**: `BEDROCK_FOUNDATION_MODEL` for accurate PDF table/layout extraction
- **Search**: pure dense vector (cosine) — **not hybrid/BM25** (Pinecone cosine indexes do not support BM25)
- **Trigger re-sync**: `aws bedrock-agent start-ingestion-job --knowledge-base-id <id> --data-source-id <id>`

## Key Files

| File | Purpose |
|------|---------|
| `agents/supervisor_agent.py` | AgentCore entrypoint; orchestrates sub-agents; parses final JSON |
| `agents/classifier_agent.py` | Haiku classifier; returns `INFORMATIONAL` or `BUSINESS_WORKFLOW` |
| `agents/informational_agent.py` | Sonnet RAG agent; custom `retrieve_kb` tool calls `bedrock-agent-runtime` directly |
| `agents/workflow_agent.py` | Haiku workflow agent; connects to AgentCore Gateway via MCP + Cognito OAuth2 |
| `agents/hooks/guardrail_hook.py` | Strands `HookProvider`; screens tool outputs via `bedrock-runtime:ApplyGuardrail` |
| `agents/models.py` | Pydantic schemas: `CRMRequest`, `SupervisorResponse`, `Source`, `WorkflowAction` |
| `agents/Dockerfile` | ARM64, Python 3.11-slim, non-root user `bedrock_agentcore`, ports 8080/8000 |
| `agents/requirements.txt` | `bedrock-agentcore`, `strands-agents[otel]`, `strands-agents-tools`, `mcp`, `httpx`, `pydantic`, `boto3` |
| `streamlit_demo.py` | Local demo UI; can invoke Cloud (boto3 `InvokeAgentRuntime`) or Local (`localhost:8080`) |
| `terraform/` | Full IaC: KB + Pinecone index + AgentCore Runtime + CodeBuild + ECR + Guardrail |
| `solution-design.md` | Original solution architecture document (reference only; some sections predate current impl) |

## RAG Implementation Detail

The `informational_agent.py` uses a **custom `retrieve_kb` tool** (not `strands_tools.memory`). Reason: `strands_tools.memory` only extracts document IDs from `customDocumentLocation`, which leaves S3-backed KB results with no URI. The custom tool calls `bedrock-agent-runtime.retrieve()` directly and maps `s3Location.uri` → the `uri` field returned to the LLM.

## Runtime Environment Variables

| Variable | Set by | Purpose |
|----------|--------|---------|
| `KNOWLEDGE_BASE_ID` | Terraform | Bedrock KB ID (primary, read by `retrieve_kb`) |
| `STRANDS_KNOWLEDGE_BASE_ID` | Terraform | Same KB ID (fallback for any `strands_tools` usage) |
| `BEDROCK_GUARDRAIL_ID` | Terraform | Guardrail resource ID |
| `BEDROCK_GUARDRAIL_VER` | Terraform | Guardrail version number |
| `AWS_REGION` / `AWS_DEFAULT_REGION` | Terraform | `us-east-1` |
| `LOG_LEVEL` | Terraform | `INFO` (also accepts `DEBUG`, `WARNING`, `ERROR`) |
| `OTEL_EXPORTER_OTLP_ENDPOINT` | Terraform | `https://xray.us-east-1.amazonaws.com` |
| `GATEWAY_MCP_URL` | Runtime config | AgentCore Gateway MCP endpoint |
| `GATEWAY_TOKEN_ENDPOINT` | Runtime config | Cognito token URL |
| `GATEWAY_CLIENT_ID` | Runtime config | Cognito app client ID |
| `GATEWAY_CLIENT_SECRET` | Runtime config | Cognito app client secret |
| `GATEWAY_SCOPE` | Runtime config | OAuth2 scope (default: `gateway/invoke`) |

## Deployment Commands

```bash
# Build infrastructure (first time or after Terraform changes)
cd terraform
terraform init
terraform apply

# Rebuild and redeploy the agent container (after agent code changes)
terraform apply -replace=null_resource.trigger_supervisor_build

# Trigger a KB re-sync (after uploading new documents to S3)
aws bedrock-agent start-ingestion-job \
  --knowledge-base-id <KNOWLEDGE_BASE_ID> \
  --data-source-id <DATA_SOURCE_ID> \
  --region us-east-1

# Local testing (requires agentcore CLI)
agentcore launch --local
agentcore invoke '{"customer_query": "How does adaptive cruise control work?", "metadata": {"model": "BMW 5 Series", "year": "2022"}}'

# Streamlit demo
streamlit run streamlit_demo.py
```

## IAM — AgentCore Execution Role

Managed policies attached to `<prefix>-agentcore-exec-role`:
- `BedrockAgentCoreFullAccess`
- `AWSMarketplaceManageSubscriptions`

Inline policy grants: ECR pull, CloudWatch Logs, X-Ray, CloudWatch Metrics (namespace `bedrock-agentcore`), Bedrock model invocation (Sonnet + Haiku cross-region inference profiles), Bedrock KB Retrieve, Bedrock Guardrail ApplyGuardrail, AgentCore workload access tokens.

## Key Design Decisions

- **Agents-as-Tools** over full orchestration frameworks — simpler debugging, clear token accounting
- **Haiku for Classifier/Workflow** — cost optimization; classification needs no RAG; workflow is parameter extraction + tool call
- **Non-interactive single-shot** — no agent memory; human-in-the-loop design
- **Pure vector search (Pinecone)** — Pinecone cosine indexes do not support BM25/hybrid; `overrideSearchType: "HYBRID"` is only valid for OpenSearch Serverless and Aurora backends
- **Custom `retrieve_kb` tool** — necessary because `strands_tools.memory` does not extract S3 URIs from retrieval results, leaving sources empty
- **Guardrail on tool outputs** — `GuardrailHook` screens sub-agent results via `AfterToolCallEvent` before they reach the Supervisor model; fails open to avoid breaking the pipeline

## MCP Servers Available

Claude Code has access to: `bedrock-agentcore-mcp-server`, `strands-agents`, `awslabs-terraform-mcp-server`, `aws-diagram-mcp-server`, `awslabs-aws-documentation-mcp-server`, `aws-pricing-mcp-server`, `pinecone-mcp`, and others (see `.claude/settings.local.json`).
