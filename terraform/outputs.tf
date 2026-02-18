output "knowledge_base_id" {
  description = "ID of the Bedrock Knowledge Base — use in agent configuration and SDK calls"
  value       = aws_bedrockagent_knowledge_base.this.id
}

output "knowledge_base_arn" {
  description = "ARN of the Bedrock Knowledge Base"
  value       = aws_bedrockagent_knowledge_base.this.arn
}

output "data_source_id" {
  description = "ID of the S3 data source — use with StartIngestionJob to trigger re-sync"
  value       = aws_bedrockagent_data_source.bmw_ug.data_source_id
}

output "s3_bucket_name" {
  description = "Name of the S3 bucket containing knowledge base documents"
  value       = aws_s3_bucket.kb_data.bucket
}

output "s3_bucket_arn" {
  description = "ARN of the S3 data bucket"
  value       = aws_s3_bucket.kb_data.arn
}

output "pinecone_index_name" {
  description = "Name of the Pinecone index"
  value       = pinecone_index.kb.name
}

output "pinecone_index_host" {
  description = "Host URL of the Pinecone index (used as the KB connection_string)"
  value       = pinecone_index.kb.host
}

output "kb_iam_role_arn" {
  description = "ARN of the IAM role assumed by the Bedrock Knowledge Base"
  value       = aws_iam_role.kb.arn
}

output "pinecone_secret_arn" {
  description = "ARN of the Secrets Manager secret holding the Pinecone API key"
  value       = aws_secretsmanager_secret.pinecone_api_key.arn
  sensitive   = true
}

output "ingestion_command" {
  description = "AWS CLI command to trigger a full sync of the data source"
  value       = <<-EOT
    aws bedrock-agent start-ingestion-job \
      --knowledge-base-id ${aws_bedrockagent_knowledge_base.this.id} \
      --data-source-id ${aws_bedrockagent_data_source.bmw_ug.data_source_id} \
      --region ${var.aws_region}
  EOT
}
