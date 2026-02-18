terraform {
  required_version = ">= 1.5.0"

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.80"
    }
    pinecone = {
      source  = "pinecone-io/pinecone"
      version = "~> 2.0"
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
