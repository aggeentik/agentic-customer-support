variable "aws_region" {
  description = "AWS region for all resources"
  type        = string
  default     = "us-east-1"
}

variable "environment" {
  description = "Deployment environment (dev / staging / prod)"
  type        = string
  default     = "demo"
}

variable "pinecone_api_key" {
  description = "Pinecone API key — retrieve from https://app.pinecone.io → API Keys. Treat as sensitive."
  type        = string
  sensitive   = true
}

variable "pinecone_cloud" {
  description = "Cloud provider for the Pinecone serverless index. Must match the AWS region family."
  type        = string
  default     = "aws"
}

variable "pinecone_region" {
  description = "Region for the Pinecone serverless index. aws: us-east-1 | us-west-2 | eu-west-1."
  type        = string
  default     = "us-east-1"
}

variable "kb_name" {
  description = "Name for the Bedrock Knowledge Base"
  type        = string
  default     = "customer-support-public-docs"
}

variable "index_name" {
  description = "Name of the Pinecone index (must be lowercase, alphanumeric, hyphens only)"
  type        = string
  default     = "customer-support-kb"
}

variable "pinecone_namespace" {
  description = "Pinecone namespace to use for knowledge base records"
  type        = string
  default     = "public-docs"
}

# Embedding model
# Titan Text Embeddings V2 — 1 024 dims.
# Cross-region inference prefix (us.) is required for on-demand throughput in us-east-1.
variable "embedding_model_id" {
  description = "Bedrock embedding model ID"
  type        = string
  default     = "amazon.titan-embed-text-v2:0"
}

variable "embedding_dimensions" {
  description = "Vector dimension that matches the chosen embedding model (Titan V2 → 1024)"
  type        = number
  default     = 1024
}

variable "data_pdf_path" {
  description = "Relative path (from terraform/) to the source PDF file"
  type        = string
  default     = "../data/2022-bmw-5-series.pdf"
}

# ---------------------------------------------------------------------------
# AgentCore Runtime variables
# ---------------------------------------------------------------------------

variable "agent_image_tag" {
  description = "Docker image tag pushed to ECR and used by the AgentCore Runtime"
  type        = string
  default     = "latest"
}

variable "network_mode" {
  description = "Network mode for the AgentCore Runtime (PUBLIC or PRIVATE)"
  type        = string
  default     = "PUBLIC"

  validation {
    condition     = contains(["PUBLIC", "PRIVATE"], var.network_mode)
    error_message = "network_mode must be PUBLIC or PRIVATE."
  }
}

variable "log_level" {
  description = "LOG_LEVEL environment variable injected into the agent container"
  type        = string
  default     = "INFO"

  validation {
    condition     = contains(["DEBUG", "INFO", "WARNING", "ERROR"], var.log_level)
    error_message = "log_level must be one of DEBUG, INFO, WARNING, ERROR."
  }
}
