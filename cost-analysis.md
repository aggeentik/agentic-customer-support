# Agentic Customer Support - Multi-Agent AI Backend Cost Analysis Estimate Report

## Service Overview

Agentic Customer Support - Multi-Agent AI Backend is a fully managed, serverless service that allows you to This project uses multiple AWS services.. This service follows a pay-as-you-go pricing model, making it cost-effective for various workloads.

## Pricing Model

This cost analysis estimate is based on the following pricing model:
- **ON DEMAND** pricing (pay-as-you-go) unless otherwise specified
- Standard service configurations without reserved capacity or savings plans
- No caching or optimization techniques applied

## Assumptions

- 30,000 support tickets per month (1,000/day, business hours) as baseline scenario
- Each ticket triggers 3 LLM calls: Supervisor (always) + Classifier (always) + Informational Agent (70%) or Workflow Agent (30%)
- Supervisor (Claude Sonnet 4.5): 2,000 input tokens + 500 output tokens per call
- Classifier (Claude Haiku 4.5): 1,500 input tokens + 200 output tokens per call
- Informational Agent (Claude Sonnet 4.5): 3,000 input tokens (including RAG context) + 1,000 output tokens per call
- Workflow Agent (Claude Haiku 4.5): 1,500 input tokens + 300 output tokens per call
- Claude Sonnet 4.5 on-demand priced at Claude Sonnet 4 rates ($3.00/MTok input, $15.00/MTok output) as per cross-region inference pricing in API data
- Claude Haiku 4.5 on-demand priced at $0.80/MTok input, $4.00/MTok output based on published Anthropic pricing
- 3 Knowledge Bases (KB-Confluence, KB-Jira, KB-PublicDocs) share a single OpenSearch Serverless collection with separate indices
- AgentCore Runtime: average 10 seconds per request, 2 vCPUs, 4 GB RAM per microVM
- Workflow Agent executes ~5 tool calls per workflow request via AgentCore Gateway
- Glue ETL: 3 sync jobs running daily (6h for Confluence, 4h for Jira, 24h for PublicDocs), averaging 2 DPU × 0.5 hrs per run = 90 DPU-hours/month
- Bedrock Guardrails applied to all inputs and outputs: ~5,000 chars input + 2,000 chars output = 7 text units per request
- CloudWatch OTEL observability estimated at $75/month for custom metrics and log ingestion
- Cognito M2M tokens are cached; ~100 token refreshes/month for CRM integration
- Standard ON DEMAND pricing; no Provisioned Throughput or Reserved Capacity
- Region: us-east-1

## Limitations and Exclusions

- S3 storage costs for Knowledge Base source documents (typically <$5/month)
- Data transfer costs between services in same region
- VPC endpoint costs
- CloudWatch alarms and dashboards beyond basic metric ingestion
- AWS Shield Advanced (standard WAF only)
- Custom model training or fine-tuning
- Development, testing, and staging environment costs
- Human agent CRM licensing costs
- Bedrock model evaluation costs
- Cross-region data transfer if using multi-region deployment
- AWS Support plan costs
- Bedrock Titan Embeddings for document re-ingestion (one-time cost per KB sync, negligible at ~$0.02/1M tokens)

## Cost Breakdown

### Unit Pricing Details

| Service | Resource Type | Unit | Price | Free Tier |
|---------|--------------|------|-------|------------|
| Claude Sonnet 4.5 - Supervisor Agent | Input Tokens | 1,000,000 tokens (cross-region) | $3.00 | No free tier for Bedrock foundation models |
| Claude Sonnet 4.5 - Supervisor Agent | Output Tokens | 1,000,000 tokens (cross-region) | $15.00 | No free tier for Bedrock foundation models |
| Claude Haiku 4.5 - Classifier Agent | Input Tokens | 1,000,000 tokens | $0.80 | No free tier |
| Claude Haiku 4.5 - Classifier Agent | Output Tokens | 1,000,000 tokens | $4.00 | No free tier |
| Claude Sonnet 4.5 - Informational Agent (RAG) | Input Tokens | 1,000,000 tokens (cross-region) | $3.00 | No free tier |
| Claude Sonnet 4.5 - Informational Agent (RAG) | Output Tokens | 1,000,000 tokens (cross-region) | $15.00 | No free tier |
| Claude Haiku 4.5 - Workflow Agent | Input Tokens | 1,000,000 tokens | $0.80 | No free tier |
| Claude Haiku 4.5 - Workflow Agent | Output Tokens | 1,000,000 tokens | $4.00 | No free tier |
| OpenSearch Serverless (Vector Store for 3 KBs) | Ocu | OCU-hour | $0.24 | No free tier; minimum 2 OCUs required |
| AgentCore Runtime (serverless microVMs) | Vcpu | vCPU-hour | $0.0895 | No free tier |
| AgentCore Runtime (serverless microVMs) | Memory | GB-hour | $0.00945 | No free tier |
| AgentCore Gateway (MCP tool invocations) | Api Invocations | invocation | $0.000005 | No free tier |
| AgentCore Gateway (MCP tool invocations) | Search Api | invocation | $0.000025 | No free tier |
| Bedrock Guardrails (PII redaction + denied topics) | Text Units | 1,000 text text units processed (1 text unit = 1,000 chars) | $0.75 | No free tier |
| AWS Glue ETL (Jira KB sync pipeline) | Dpu Hour | DPU-Hour | $0.44 | No free tier for production jobs |
| AWS WAF | Web Acl | 1 unit | $5.00/month | No free tier |
| AWS WAF | Rule | rule | $1.00/month | No free tier |
| AWS WAF | Requests | 1,000,000 requests | $0.60 | No free tier |
| CloudWatch (OTEL observability via ADOT) | Custom Metrics | metric (first 10K) | $0.30 | First 10 metrics free, basic logs free tier |
| CloudWatch (OTEL observability via ADOT) | Log Ingestion | GB | $0.50 | First 10 metrics free, basic logs free tier |
| Amazon DynamoDB (audit/state store) | Writes | 1,000,000 write request writes | $0.625 | 25 GB storage free forever, 25 RCU/WCU free |
| Amazon DynamoDB (audit/state store) | Reads | 1,000,000 read request reads | $0.125 | 25 GB storage free forever, 25 RCU/WCU free |
| Amazon DynamoDB (audit/state store) | Storage | GB-month | $0.25 | 25 GB storage free forever, 25 RCU/WCU free |
| AWS Lambda (workflow action execution) | Requests | 1,000,000 requests | $0.20 | 1M requests/month free (12 months), 400K GB-s/month free |
| AWS Lambda (workflow action execution) | Compute | GB-second | $0.0000166667 | 1M requests/month free (12 months), 400K GB-s/month free |
| AWS Step Functions (workflow orchestration) | State Transitions | state transition | $0.000025 | 4,000 state transitions/month free (12 months) |
| Amazon API Gateway (REST API entry point) | Requests | 1,000,000 requests (first 333M) | $3.50 | 1M API calls/month free (12 months) |
| Amazon Cognito (OAuth 2.0 / M2M auth) | M2M Tokens | token (tier 1) | $0.00225 | No free tier for M2M |

### Cost Calculation

| Service | Usage | Calculation | Monthly Cost |
|---------|-------|-------------|-------------|
| Claude Sonnet 4.5 - Supervisor Agent | 30,000 requests/month × (2,000 input + 500 output tokens) (Input Tokens: 60,000,000 tokens/month, Output Tokens: 15,000,000 tokens/month) | 60M input × $3.00/MTok + 15M output × $15.00/MTok = $180 + $225 = $405.00 | $405.00 |
| Claude Haiku 4.5 - Classifier Agent | 30,000 requests/month × (1,500 input + 200 output tokens) (Input Tokens: 45,000,000 tokens/month, Output Tokens: 6,000,000 tokens/month) | 45M input × $0.80/MTok + 6M output × $4.00/MTok = $36 + $24 = $60.00 | $60.00 |
| Claude Sonnet 4.5 - Informational Agent (RAG) | 21,000 requests/month (70% of tickets) × (3,000 input + 1,000 output tokens) (Input Tokens: 63,000,000 tokens/month, Output Tokens: 21,000,000 tokens/month) | 63M input × $3.00/MTok + 21M output × $15.00/MTok = $189 + $315 = $504.00 | $504.00 |
| Claude Haiku 4.5 - Workflow Agent | 9,000 requests/month (30% of tickets) × (1,500 input + 300 output tokens) (Input Tokens: 13,500,000 tokens/month, Output Tokens: 2,700,000 tokens/month) | 13.5M input × $0.80/MTok + 2.7M output × $4.00/MTok = $10.80 + $10.80 = $21.60 | $21.60 |
| OpenSearch Serverless (Vector Store for 3 KBs) | 1 shared collection, 2 OCUs minimum (24×7) (Ocus: 2 OCUs × 720 hours/month = 1,440 OCU-hours) | $0.24/OCU-hr × 1,440 OCU-hours = $345.60/month. NOTE: 3 separate collections would cost 3× = $1,036.80/month | $345.60 |
| AgentCore Runtime (serverless microVMs) | 30,000 requests × 10 seconds × 2 vCPU × 4 GB RAM (Compute Hours: 30,000 × 10s / 3600 = 83.3 hours, Vcpu Hours: 83.3 × 2 = 166.6 vCPU-hours, Gb Hours: 83.3 × 4 = 333.2 GB-hours) | 166.6 vCPU-hrs × $0.0895 + 333.2 GB-hrs × $0.00945 = $14.91 + $3.15 = $18.07 | $18.07 |
| AgentCore Gateway (MCP tool invocations) | 9,000 workflow requests × 5 tool calls each = 45,000 calls/month (Gateway Calls: 45,000 invocations/month) | 45,000 × $0.000025 (search-type calls) = $1.13 | $1.13 |
| Bedrock Guardrails (PII redaction + denied topics) | 30,000 requests × 7 text units (7,000 chars per request) (Text Units: 30,000 × 7 = 210,000 text units/month) | 210,000 / 1,000 × $0.75 = $157.50/month | $157.50 |
| AWS Glue ETL (Jira KB sync pipeline) | ~90 ETL job runs/month (Confluence 6h sync + Jira 4h sync + PublicDocs 24h crawl daily/weekly) (Dpu Hours: 90 runs × 2 DPU × 0.5 hrs = 90 DPU-hours/month) | 90 DPU-hours × $0.44 = $39.60/month | $39.60 |
| AWS WAF | 1 Web ACL + 10 custom rules + 30,000 requests/month (Web Acls: 1, Rules: 10, Requests: 30,000) | $5 (WebACL) + $10 (10 rules) + 0.03M × $0.60 = $15.02 | $15.02 |
| CloudWatch (OTEL observability via ADOT) | Custom metrics, traces, and log groups from all agents (Estimated: ~50 custom metrics + ~5 GB logs/month) | Estimated $75/month based on typical multi-agent observability workload | $75.00 |
| Amazon DynamoDB (audit/state store) | 30,000 writes + 30,000 reads/month, ~1 GB storage (Writes: 30,000 WRU/month, Reads: 30,000 RRU/month) | 30K WRU × $0.625/1M + 30K RRU × $0.125/1M + 1 GB × $0.25 = $0.02 + $0.004 + $0.25 = $0.27 | $0.27 |
| AWS Lambda (workflow action execution) | 27,000 invocations/month (9,000 workflows × 3 Lambda calls each), 2 sec avg, 512 MB (Requests: 27,000, Gb Seconds: 27,000 × 2s × 0.5GB = 27,000 GB-s) | 27K/1M × $0.20 + 27,000 GB-s × $0.0000166667 = $0.005 + $0.45 = $0.47 | $0.47 |
| AWS Step Functions (workflow orchestration) | 9,000 workflow executions × 10 state transitions each (Transitions: 90,000 state transitions/month) | 90,000 × $0.000025 = $2.25 | $2.25 |
| Amazon API Gateway (REST API entry point) | 30,000 requests/month from CRM (Requests: 30,000) | 0.03M × $3.50 = $0.11 | $0.11 |
| Amazon Cognito (OAuth 2.0 / M2M auth) | ~100 M2M token refreshes/month (tokens cached per CRM session) (Tokens: ~100/month) | 100 × $0.00225 = $0.23 | $0.23 |
| **Total** | **All services** | **Sum of all calculations** | **$1645.85/month** |

### Free Tier

Free tier information by service:
- **Claude Sonnet 4.5 - Supervisor Agent**: No free tier for Bedrock foundation models
- **Claude Haiku 4.5 - Classifier Agent**: No free tier
- **Claude Sonnet 4.5 - Informational Agent (RAG)**: No free tier
- **Claude Haiku 4.5 - Workflow Agent**: No free tier
- **OpenSearch Serverless (Vector Store for 3 KBs)**: No free tier; minimum 2 OCUs required
- **AgentCore Runtime (serverless microVMs)**: No free tier
- **AgentCore Gateway (MCP tool invocations)**: No free tier
- **Bedrock Guardrails (PII redaction + denied topics)**: No free tier
- **AWS Glue ETL (Jira KB sync pipeline)**: No free tier for production jobs
- **AWS WAF**: No free tier
- **CloudWatch (OTEL observability via ADOT)**: First 10 metrics free, basic logs free tier
- **Amazon DynamoDB (audit/state store)**: 25 GB storage free forever, 25 RCU/WCU free
- **AWS Lambda (workflow action execution)**: 1M requests/month free (12 months), 400K GB-s/month free
- **AWS Step Functions (workflow orchestration)**: 4,000 state transitions/month free (12 months)
- **Amazon API Gateway (REST API entry point)**: 1M API calls/month free (12 months)
- **Amazon Cognito (OAuth 2.0 / M2M auth)**: No free tier for M2M

## Cost Scaling with Usage

The following table illustrates how cost estimates scale with different usage levels:

| Service | Low Usage | Medium Usage | High Usage |
|---------|-----------|--------------|------------|
| Claude Sonnet 4.5 - Supervisor Agent | $202/month | $405/month | $810/month |
| Claude Haiku 4.5 - Classifier Agent | $30/month | $60/month | $120/month |
| Claude Sonnet 4.5 - Informational Agent (RAG) | $252/month | $504/month | $1008/month |
| Claude Haiku 4.5 - Workflow Agent | $10/month | $21/month | $43/month |
| OpenSearch Serverless (Vector Store for 3 KBs) | $172/month | $345/month | $691/month |
| AgentCore Runtime (serverless microVMs) | $9/month | $18/month | $36/month |
| AgentCore Gateway (MCP tool invocations) | $0/month | $1/month | $2/month |
| Bedrock Guardrails (PII redaction + denied topics) | $78/month | $157/month | $315/month |
| AWS Glue ETL (Jira KB sync pipeline) | $19/month | $39/month | $79/month |
| AWS WAF | $7/month | $15/month | $30/month |
| CloudWatch (OTEL observability via ADOT) | $37/month | $75/month | $150/month |
| Amazon DynamoDB (audit/state store) | $0/month | $0/month | $0/month |
| AWS Lambda (workflow action execution) | $0/month | $0/month | $0/month |
| AWS Step Functions (workflow orchestration) | $1/month | $2/month | $4/month |
| Amazon API Gateway (REST API entry point) | $0/month | $0/month | $0/month |
| Amazon Cognito (OAuth 2.0 / M2M auth) | $0/month | $0/month | $0/month |

### Key Cost Factors

- **Claude Sonnet 4.5 - Supervisor Agent**: 30,000 requests/month × (2,000 input + 500 output tokens)
- **Claude Haiku 4.5 - Classifier Agent**: 30,000 requests/month × (1,500 input + 200 output tokens)
- **Claude Sonnet 4.5 - Informational Agent (RAG)**: 21,000 requests/month (70% of tickets) × (3,000 input + 1,000 output tokens)
- **Claude Haiku 4.5 - Workflow Agent**: 9,000 requests/month (30% of tickets) × (1,500 input + 300 output tokens)
- **OpenSearch Serverless (Vector Store for 3 KBs)**: 1 shared collection, 2 OCUs minimum (24×7)
- **AgentCore Runtime (serverless microVMs)**: 30,000 requests × 10 seconds × 2 vCPU × 4 GB RAM
- **AgentCore Gateway (MCP tool invocations)**: 9,000 workflow requests × 5 tool calls each = 45,000 calls/month
- **Bedrock Guardrails (PII redaction + denied topics)**: 30,000 requests × 7 text units (7,000 chars per request)
- **AWS Glue ETL (Jira KB sync pipeline)**: ~90 ETL job runs/month (Confluence 6h sync + Jira 4h sync + PublicDocs 24h crawl daily/weekly)
- **AWS WAF**: 1 Web ACL + 10 custom rules + 30,000 requests/month
- **CloudWatch (OTEL observability via ADOT)**: Custom metrics, traces, and log groups from all agents
- **Amazon DynamoDB (audit/state store)**: 30,000 writes + 30,000 reads/month, ~1 GB storage
- **AWS Lambda (workflow action execution)**: 27,000 invocations/month (9,000 workflows × 3 Lambda calls each), 2 sec avg, 512 MB
- **AWS Step Functions (workflow orchestration)**: 9,000 workflow executions × 10 state transitions each
- **Amazon API Gateway (REST API entry point)**: 30,000 requests/month from CRM
- **Amazon Cognito (OAuth 2.0 / M2M auth)**: ~100 M2M token refreshes/month (tokens cached per CRM session)

## Projected Costs Over Time

The following projections show estimated monthly costs over a 12-month period based on different growth patterns:

Base monthly cost calculation:

| Service | Monthly Cost |
|---------|-------------|
| Claude Sonnet 4.5 - Supervisor Agent | $405.00 |
| Claude Haiku 4.5 - Classifier Agent | $60.00 |
| Claude Sonnet 4.5 - Informational Agent (RAG) | $504.00 |
| Claude Haiku 4.5 - Workflow Agent | $21.60 |
| OpenSearch Serverless (Vector Store for 3 KBs) | $345.60 |
| AgentCore Runtime (serverless microVMs) | $18.07 |
| AgentCore Gateway (MCP tool invocations) | $1.13 |
| Bedrock Guardrails (PII redaction + denied topics) | $157.50 |
| AWS Glue ETL (Jira KB sync pipeline) | $39.60 |
| AWS WAF | $15.02 |
| CloudWatch (OTEL observability via ADOT) | $75.00 |
| Amazon DynamoDB (audit/state store) | $0.27 |
| AWS Lambda (workflow action execution) | $0.47 |
| AWS Step Functions (workflow orchestration) | $2.25 |
| Amazon API Gateway (REST API entry point) | $0.11 |
| Amazon Cognito (OAuth 2.0 / M2M auth) | $0.23 |
| **Total Monthly Cost** | **$1645** |

| Growth Pattern | Month 1 | Month 3 | Month 6 | Month 12 |
|---------------|---------|---------|---------|----------|
| Steady | $1645/mo | $1645/mo | $1645/mo | $1645/mo |
| Moderate | $1645/mo | $1814/mo | $2100/mo | $2814/mo |
| Rapid | $1645/mo | $1991/mo | $2650/mo | $4695/mo |

* Steady: No monthly growth (1.0x)
* Moderate: 5% monthly growth (1.05x)
* Rapid: 10% monthly growth (1.1x)

## Detailed Cost Analysis

### Pricing Model

ON DEMAND


### Exclusions

- S3 storage costs for Knowledge Base source documents (typically <$5/month)
- Data transfer costs between services in same region
- VPC endpoint costs
- CloudWatch alarms and dashboards beyond basic metric ingestion
- AWS Shield Advanced (standard WAF only)
- Custom model training or fine-tuning
- Development, testing, and staging environment costs
- Human agent CRM licensing costs
- Bedrock model evaluation costs
- Cross-region data transfer if using multi-region deployment
- AWS Support plan costs
- Bedrock Titan Embeddings for document re-ingestion (one-time cost per KB sync, negligible at ~$0.02/1M tokens)

### Recommendations

#### Immediate Actions

- Use a single OpenSearch Serverless collection with 3 vector indices to avoid paying 3× minimum OCU cost ($345.60 vs $1,036.80)
- Implement prompt caching for Supervisor agent's system prompt (repeated every call) — could reduce Sonnet 4.5 input token costs by 30-50%, saving ~$100-$200/month
- Consider Glue Flex jobs ($0.29/DPU-hr) instead of standard jobs for the non-time-critical PublicDocs sync, saving ~30% on ETL costs
#### Best Practices

- Scale OpenSearch Serverless OCUs based on actual query patterns — 2 OCUs handles ~50 queries/sec; increase if KB retrieval latency degrades
- Monitor AgentCore Runtime duration per request — the 10-second estimate may be optimistic if Informational Agent requires multiple KB retrievals
- Set up CloudWatch alarms on per-token costs to detect prompt injection attacks or runaway loops that could significantly inflate LLM costs
- Consider enabling Bedrock Prompt Caching for Knowledge Base context chunks that are retrieved repeatedly across tickets



## Cost Optimization Recommendations

### Immediate Actions

- Use a single OpenSearch Serverless collection with 3 vector indices to avoid paying 3× minimum OCU cost ($345.60 vs $1,036.80)
- Implement prompt caching for Supervisor agent's system prompt (repeated every call) — could reduce Sonnet 4.5 input token costs by 30-50%, saving ~$100-$200/month
- Consider Glue Flex jobs ($0.29/DPU-hr) instead of standard jobs for the non-time-critical PublicDocs sync, saving ~30% on ETL costs

### Best Practices

- Scale OpenSearch Serverless OCUs based on actual query patterns — 2 OCUs handles ~50 queries/sec; increase if KB retrieval latency degrades
- Monitor AgentCore Runtime duration per request — the 10-second estimate may be optimistic if Informational Agent requires multiple KB retrievals
- Set up CloudWatch alarms on per-token costs to detect prompt injection attacks or runaway loops that could significantly inflate LLM costs

## Conclusion

By following the recommendations in this report, you can optimize your Agentic Customer Support - Multi-Agent AI Backend costs while maintaining performance and reliability. Regular monitoring and adjustment of your usage patterns will help ensure cost efficiency as your workload evolves.
