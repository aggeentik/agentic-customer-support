# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

An AI-powered customer support automation system. Human support agents click "Generate" in their CRM, which triggers a single API call to a multi-agent AI backend that returns a structured JSON response (suggested reply, workflow actions, citations). The human agent reviews and sends — the AI never communicates directly with end customers.

This is a **pre-implementation repository**. The primary artifact is `solution-design.md` (v2.0, ~1,100 lines), which contains the full architecture, API contracts, agent specs, implementation roadmap, cost model, and security design.

## Architecture

### Multi-Agent System (Agents-as-Tools pattern)

```
CRM → API Gateway + WAF + Cognito JWT
    → AgentCore Runtime (serverless microVMs)
        → SUPERVISOR AGENT (Claude Sonnet 4.5)
              ├── CLASSIFIER AGENT (Claude Haiku 4.5)  — intent classification only, no tools
              ├── INFORMATIONAL AGENT (Claude Sonnet 4.5) — RAG via Bedrock Knowledge Bases
              └── WORKFLOW AGENT (Claude Haiku 4.5)    — action execution via MCP Gateway
```

**Request flow:**
1. CRM POSTs customer context to `/api/v1/process-request`
2. Supervisor calls Classifier → INFORMATIONAL or BUSINESS_WORKFLOW
3. Informational Agent queries Knowledge Bases (Confluence policies, Jira past cases, web-crawled docs) using hybrid semantic+BM25 retrieval
4. Workflow Agent calls Lambda/Step Functions tools via AgentCore Gateway (MCP protocol)
5. Supervisor returns structured JSON to CRM; human reviews before sending

### Technology Stack

| Component | Technology |
|-----------|-----------|
| Agent SDK | Strands Agents (Python) |
| Agent Runtime | Amazon Bedrock AgentCore Runtime |
| Orchestration LLM | `us.anthropic.claude-sonnet-4-5-20250929-v1:0` |
| Classification/Workflow LLM | `us.anthropic.claude-haiku-4-5-20251001-v1:0` |
| RAG | Bedrock Knowledge Bases + OpenSearch Serverless (hybrid semantic+BM25) |
| Embeddings | Amazon Titan Text Embeddings V2 (1024 dims) |
| Tool connectivity | AgentCore Gateway (MCP Protocol) |
| Workflow execution | AWS Lambda + Step Functions |
| Audit/State | DynamoDB |
| Auth | Cognito OAuth 2.0 via AgentCore Identity |
| Data ingestion | AWS Glue ETL (Jira → S3 → KB) |
| Observability | OTEL → CloudWatch via AWS ADOT |
| Guardrails | Bedrock Guardrails (PII redaction, denied topics) |

### Knowledge Bases

- **KB-Confluence**: Internal policies/procedures (sync every 6h, hierarchical chunking 1024/256 tokens)
- **KB-Jira**: Past support cases (sync every 4h via Glue ETL, 512/128 tokens)
- **KB-PublicDocs**: Web-crawled documentation (daily, 768/192 tokens)

## Planned Commands

Once implementation begins, the deployment commands will be (per `solution-design.md`):

```bash
agentcore configure --entrypoint supervisor_agent.py
agentcore deploy --local    # local testing
agentcore deploy            # production deployment
agentcore invoke '{"prompt": "I need a refund for TXN-98765"}'
```

## Key Design Decisions (from solution-design.md)

- **Agents-as-Tools** over full orchestration frameworks — simpler debugging, clear token accounting
- **Haiku for Classifier/Workflow** — cost optimization; classification needs no RAG
- **Non-interactive single-shot** — no agent memory needed; human-in-the-loop design means the AI never directly contacts customers
- **Hybrid retrieval** — semantic + BM25 with Cohere reranking for terminology accuracy
- **AgentCore Gateway** for tool access — avoids direct Lambda ARN coupling in agent code

## MCP Servers Available

Claude Code in this project has access to extensive AWS MCP servers (see `.claude/settings.local.json`), including: `bedrock-agentcore-mcp-server`, `strands-agents`, `aws-api-mcp-server`, `awslabs-terraform-mcp-server`, `aws-diagram-mcp-server`, `awslabs-aws-documentation-mcp-server`, and others for AWS cost, IAM, DynamoDB, S3, CloudWatch, and serverless tooling.

## Implementation Roadmap

- **Phase 1 (Weeks 1–6)**: Infrastructure setup, Knowledge Base creation, data ingestion pipelines, multi-agent skeleton
- **Phase 2 (Weeks 7–14)**: Agent optimization, workflow integrations, security hardening, evaluation framework
- **Phase 3 (Weeks 15–24)**: Production deployment, monitoring, phased rollout

## Reference Files

- `solution-design.md` — Complete solution architecture (start here for any implementation work)
- `data/rds-ug.pdf` — Sample data for Knowledge Base ingestion testing
- `generated-diagrams/` — Architecture diagrams (PNG) generated via MCP
