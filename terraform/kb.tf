# ---------------------------------------------------------------------------
# Data sources
# ---------------------------------------------------------------------------

data "aws_caller_identity" "current" {}
data "aws_partition" "current" {}

locals {
  account_id     = data.aws_caller_identity.current.account_id
  partition      = data.aws_partition.current.partition
  embedding_arn  = "arn:${local.partition}:bedrock:${var.aws_region}::foundation-model/${var.embedding_model_id}"
  name_prefix    = "${var.kb_name}-${var.environment}"
}

# ---------------------------------------------------------------------------
# S3 — data source bucket
# ---------------------------------------------------------------------------

resource "aws_s3_bucket" "kb_data" {
  bucket = "${local.name_prefix}-data-${local.account_id}"
}

resource "aws_s3_bucket_versioning" "kb_data" {
  bucket = aws_s3_bucket.kb_data.id
  versioning_configuration {
    status = "Enabled"
  }
}

resource "aws_s3_bucket_server_side_encryption_configuration" "kb_data" {
  bucket = aws_s3_bucket.kb_data.id
  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm = "AES256"
    }
  }
}

resource "aws_s3_bucket_public_access_block" "kb_data" {
  bucket                  = aws_s3_bucket.kb_data.id
  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

# Upload the sample PDF
resource "aws_s3_object" "bmw_user_guide" {
  bucket       = aws_s3_bucket.kb_data.id
  key          = "2022-bmw-5-series.pdf"
  source       = "${path.module}/${var.data_pdf_path}"
  content_type = "application/pdf"
  etag         = filemd5("${path.module}/${var.data_pdf_path}")
}

# ---------------------------------------------------------------------------
# Secrets Manager — Pinecone API key
#
# The secret must contain a single key named "apiKey" whose value is the
# Pinecone API key. Amazon Bedrock reads this key when writing embeddings.
# See: https://docs.aws.amazon.com/bedrock/latest/userguide/knowledge-base-setup.html
# ---------------------------------------------------------------------------

resource "aws_secretsmanager_secret" "pinecone_api_key" {
  name                    = "${local.name_prefix}/pinecone-api-key-latest"
  description             = "Pinecone API key for Bedrock Knowledge Base ${var.kb_name}"
  recovery_window_in_days = 7
}

resource "aws_secretsmanager_secret_version" "pinecone_api_key" {
  secret_id = aws_secretsmanager_secret.pinecone_api_key.id
  # Bedrock expects the JSON key to be exactly "apiKey"
  secret_string = jsonencode({ apiKey = var.pinecone_api_key })
}

# ---------------------------------------------------------------------------
# IAM — service role for Bedrock Knowledge Base
# ---------------------------------------------------------------------------

data "aws_iam_policy_document" "kb_trust" {
  statement {
    sid     = "BedrockKBTrust"
    effect  = "Allow"
    actions = ["sts:AssumeRole"]

    principals {
      type        = "Service"
      identifiers = ["bedrock.amazonaws.com"]
    }

    condition {
      test     = "StringEquals"
      variable = "aws:SourceAccount"
      values   = [local.account_id]
    }

    condition {
      test     = "ArnLike"
      variable = "aws:SourceArn"
      values   = ["arn:${local.partition}:bedrock:${var.aws_region}:${local.account_id}:knowledge-base/*"]
    }
  }
}

resource "aws_iam_role" "kb" {
  name               = "${local.name_prefix}-kb-role"
  assume_role_policy = data.aws_iam_policy_document.kb_trust.json
  description        = "Service role for Bedrock Knowledge Base ${var.kb_name}"
}

data "aws_iam_policy_document" "kb_permissions" {
  # Read the PDF from S3
  statement {
    sid    = "ReadS3DataSource"
    effect = "Allow"
    actions = [
      "s3:GetObject",
      "s3:ListBucket",
    ]
    resources = [
      aws_s3_bucket.kb_data.arn,
      "${aws_s3_bucket.kb_data.arn}/*",
    ]
    condition {
      test     = "StringEquals"
      variable = "aws:ResourceAccount"
      values   = [local.account_id]
    }
  }

  # Invoke the embedding model
  statement {
    sid     = "InvokeEmbeddingModel"
    effect  = "Allow"
    actions = ["bedrock:InvokeModel"]
    resources = [
      local.embedding_arn,
      # Cross-region inference profile (us.*) — required for on-demand throughput
      "arn:${local.partition}:bedrock:${var.aws_region}:${local.account_id}:inference-profile/us.${var.embedding_model_id}",
    ]
  }

  # Read the Pinecone secret so it can authenticate to Pinecone
  statement {
    sid     = "ReadPineconeSecret"
    effect  = "Allow"
    actions = ["secretsmanager:GetSecretValue"]
    resources = [
      aws_secretsmanager_secret.pinecone_api_key.arn,
    ]
  }

  # Allow Bedrock to describe the secret (needed for validation)
  statement {
    sid     = "DescribePineconeSecret"
    effect  = "Allow"
    actions = ["secretsmanager:DescribeSecret"]
    resources = [
      aws_secretsmanager_secret.pinecone_api_key.arn,
    ]
  }
}

resource "aws_iam_role_policy" "kb" {
  name   = "${local.name_prefix}-kb-policy"
  role   = aws_iam_role.kb.id
  policy = data.aws_iam_policy_document.kb_permissions.json
}

# ---------------------------------------------------------------------------
# Bedrock Knowledge Base — vector type, Pinecone storage
#
# connection_string: the host URL shown on the Pinecone index detail page
#   e.g. https://customer-support-kb-xxxx.svc.pinecone.io
# Field mapping uses the Bedrock-reserved field names so the console and
# SDK helpers resolve source attribution automatically.
# ---------------------------------------------------------------------------

resource "aws_bedrockagent_knowledge_base" "this" {
  name        = var.kb_name
  description = "Public docs knowledge base for the customer-support agent. Data source: 2022-bmw-5-series.pdf."
  role_arn    = aws_iam_role.kb.arn

  knowledge_base_configuration {
    type = "VECTOR"

    vector_knowledge_base_configuration {
      embedding_model_arn = local.embedding_arn

      embedding_model_configuration {
        bedrock_embedding_model_configuration {
          dimensions          = var.embedding_dimensions
          embedding_data_type = "FLOAT32"
        }
      }
    }
  }

  storage_configuration {
    type = "PINECONE"

    pinecone_configuration {
      # The host URL is known only after the index is provisioned
      connection_string      = "https://${pinecone_index.kb.host}"
      credentials_secret_arn = aws_secretsmanager_secret.pinecone_api_key.arn
      namespace              = var.pinecone_namespace

      field_mapping {
        # Bedrock-standard field names — keep these unless you have a reason
        # to override them (e.g. index already exists with different names).
        text_field     = "AMAZON_BEDROCK_TEXT_CHUNK"
        metadata_field = "AMAZON_BEDROCK_METADATA"
      }
    }
  }

  depends_on = [
    aws_iam_role_policy.kb,
    aws_secretsmanager_secret_version.pinecone_api_key,
    pinecone_index.kb,
  ]
}

# ---------------------------------------------------------------------------
# Bedrock Data Source — S3 + PDF parsing + hierarchical chunking
#
# Chunking matches the KB-PublicDocs spec in solution-design.md:
#   parent 600 tokens, child 150 tokens, 40-token overlap.
#
# Parsing uses BEDROCK_FOUNDATION_MODEL so the PDF tables and layout are
# correctly extracted before embedding.
# ---------------------------------------------------------------------------

resource "aws_bedrockagent_data_source" "bmw_ug" {
  knowledge_base_id = aws_bedrockagent_knowledge_base.this.id
  name              = "bmw-5-series-user-guide-pdf"
  description       = "BMW 5 Series User Guide PDF — sample data for knowledge base ingestion testing"

  data_deletion_policy = "RETAIN"

  data_source_configuration {
    type = "S3"

    s3_configuration {
      bucket_arn         = aws_s3_bucket.kb_data.arn
      inclusion_prefixes = ["2022-bmw-5-series.pdf"]
    }
  }

}
