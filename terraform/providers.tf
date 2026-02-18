terraform {
  required_version = ">= 1.6.0"

  required_providers {
    aws = {
      # aws_bedrockagentcore_agent_runtime requires >= 6.21
      source  = "hashicorp/aws"
      version = "~> 6.21"
    }
    pinecone = {
      source  = "pinecone-io/pinecone"
      version = "~> 2.0"
    }
    archive = {
      source  = "hashicorp/archive"
      version = "~> 2.0"
    }
    null = {
      source  = "hashicorp/null"
      version = "~> 3.0"
    }
  }
}

provider "aws" {
  region = var.aws_region

  default_tags {
    tags = {
      project   = "agentic-customer-support"
      env       = var.environment
      ManagedBy = "terraform"
    }
  }
}

provider "pinecone" {
  api_key = var.pinecone_api_key
}
