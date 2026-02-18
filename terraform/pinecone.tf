# ---------------------------------------------------------------------------
# Pinecone Index
#
# Bedrock handles embedding and sends the 1 024-dim float32 vectors here.
# The index uses the standard (non-integrated-inference) serverless spec so
# Bedrock can upsert pre-computed vectors directly.
# ---------------------------------------------------------------------------

resource "pinecone_index" "kb" {
  name      = var.index_name
  dimension = var.embedding_dimensions
  metric    = "cosine"

  spec = {
    serverless = {
      cloud  = var.pinecone_cloud
      region = var.pinecone_region
    }
  }

  tags = {
    project = "agentic-customer-support"
    env     = var.environment
  }
}
