# ---------------------------------------------------------------------------
# AgentCore Runtime — Supervisor Agent Scaffold
#
# Creates the full container build pipeline (ECR + CodeBuild + S3) and the
# AgentCore Runtime resource that runs the multi-agent supervisor.
#
# Dependency graph:
#   agents/ source code
#     → S3 (zip archive)
#     → CodeBuild (docker build + ECR push)
#     → aws_bedrockagentcore_agent_runtime (references ECR image URI)
#
# Prerequisites:
#   - aws provider >= 6.21 (aws_bedrockagentcore_agent_runtime)
#   - archive + null providers (see providers.tf)
#   - Bedrock Knowledge Base from kb.tf must be applied first
#
# After `terraform apply`, deploy a new version with:
#   terraform apply -replace=null_resource.trigger_supervisor_build
# ---------------------------------------------------------------------------

locals {
  agent_prefix = "${var.kb_name}-${var.environment}"

  # Cross-region inference profile ARNs for cost-optimised on-demand throughput
  sonnet_model_arns = [
    "arn:${local.partition}:bedrock:${var.aws_region}::foundation-model/anthropic.claude-sonnet-4-5-20250929-v1:0",
    "arn:${local.partition}:bedrock:${var.aws_region}:${local.account_id}:inference-profile/us.anthropic.claude-sonnet-4-5-20250929-v1:0",
  ]
  haiku_model_arns = [
    "arn:${local.partition}:bedrock:${var.aws_region}::foundation-model/anthropic.claude-haiku-4-5-20251001-v1:0",
    "arn:${local.partition}:bedrock:${var.aws_region}:${local.account_id}:inference-profile/us.anthropic.claude-haiku-4-5-20251001-v1:0",
  ]
}

# ---------------------------------------------------------------------------
# ECR — supervisor agent container registry
# ---------------------------------------------------------------------------

resource "aws_ecr_repository" "supervisor_agent" {
  name                 = "${local.agent_prefix}-supervisor"
  image_tag_mutability = "MUTABLE"
  force_delete         = true

  image_scanning_configuration {
    scan_on_push = true
  }
}

resource "aws_ecr_repository_policy" "supervisor_agent" {
  repository = aws_ecr_repository.supervisor_agent.name

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Sid    = "AllowPullFromAccount"
      Effect = "Allow"
      Principal = {
        AWS = "arn:${local.partition}:iam::${local.account_id}:root"
      }
      Action = ["ecr:BatchGetImage", "ecr:GetDownloadUrlForLayer"]
    }]
  })
}

resource "aws_ecr_lifecycle_policy" "supervisor_agent" {
  repository = aws_ecr_repository.supervisor_agent.name

  policy = jsonencode({
    rules = [{
      rulePriority = 1
      description  = "Expire images beyond the last 5"
      selection = {
        tagStatus   = "any"
        countType   = "imageCountMoreThan"
        countNumber = 5
      }
      action = { type = "expire" }
    }]
  })
}

# ---------------------------------------------------------------------------
# S3 — agent source code bucket (CodeBuild input)
# ---------------------------------------------------------------------------

resource "aws_s3_bucket" "agent_source" {
  # bucket_prefix max = 37 chars; keep short, account-ID suffix ensures global uniqueness
  bucket_prefix = "cs-agent-src-${var.environment}-"
  force_destroy = true
}

resource "aws_s3_bucket_public_access_block" "agent_source" {
  bucket                  = aws_s3_bucket.agent_source.id
  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

resource "aws_s3_bucket_versioning" "agent_source" {
  bucket = aws_s3_bucket.agent_source.id
  versioning_configuration { status = "Enabled" }
}

resource "aws_s3_bucket_server_side_encryption_configuration" "agent_source" {
  bucket = aws_s3_bucket.agent_source.id
  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm = "AES256"
    }
  }
}

# Zip the entire agents/ directory — re-uploads automatically when any file changes.
data "archive_file" "agent_source" {
  type        = "zip"
  source_dir  = "${path.module}/../agents"
  output_path = "${path.module}/.terraform/agent-source.zip"
}

resource "aws_s3_object" "agent_source" {
  bucket = aws_s3_bucket.agent_source.id
  key    = "agent-source-${data.archive_file.agent_source.output_md5}.zip"
  source = data.archive_file.agent_source.output_path
  etag   = data.archive_file.agent_source.output_md5
}

# ---------------------------------------------------------------------------
# IAM — CodeBuild service role (image build only)
# ---------------------------------------------------------------------------

resource "aws_iam_role" "codebuild" {
  name        = "${local.agent_prefix}-codebuild-role"
  description = "CodeBuild role for building the supervisor agent Docker image"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect    = "Allow"
      Principal = { Service = "codebuild.amazonaws.com" }
      Action    = "sts:AssumeRole"
    }]
  })
}

resource "aws_iam_role_policy" "codebuild" {
  name = "${local.agent_prefix}-codebuild-policy"
  role = aws_iam_role.codebuild.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid    = "CloudWatchLogs"
        Effect = "Allow"
        Action = ["logs:CreateLogGroup", "logs:CreateLogStream", "logs:PutLogEvents"]
        Resource = [
          "arn:${local.partition}:logs:${var.aws_region}:${local.account_id}:log-group:/aws/codebuild/*",
          "arn:${local.partition}:logs:${var.aws_region}:${local.account_id}:log-group:/aws/codebuild/*:log-stream:*",
        ]
      },
      {
        Sid    = "ECRPush"
        Effect = "Allow"
        Action = [
          "ecr:BatchCheckLayerAvailability",
          "ecr:GetDownloadUrlForLayer",
          "ecr:BatchGetImage",
          "ecr:PutImage",
          "ecr:InitiateLayerUpload",
          "ecr:UploadLayerPart",
          "ecr:CompleteLayerUpload",
        ]
        Resource = aws_ecr_repository.supervisor_agent.arn
      },
      {
        Sid      = "ECRToken"
        Effect   = "Allow"
        Action   = ["ecr:GetAuthorizationToken"]
        Resource = "*"
      },
      {
        Sid    = "S3ReadSource"
        Effect = "Allow"
        Action = ["s3:GetObject", "s3:GetObjectVersion"]
        Resource = "${aws_s3_bucket.agent_source.arn}/*"
      },
      {
        Sid    = "S3ListSource"
        Effect = "Allow"
        Action = ["s3:ListBucket", "s3:GetBucketLocation"]
        Resource = aws_s3_bucket.agent_source.arn
      },
    ]
  })
}

# ---------------------------------------------------------------------------
# CodeBuild — build and push supervisor agent Docker image
# ---------------------------------------------------------------------------

resource "aws_codebuild_project" "supervisor_agent" {
  name          = "${local.agent_prefix}-supervisor-build"
  description   = "Build the supervisor agent Docker image and push it to ECR"
  service_role  = aws_iam_role.codebuild.arn
  build_timeout = 60 # minutes

  artifacts { type = "NO_ARTIFACTS" }

  environment {
    # ARM_CONTAINER matches the ARM64 Dockerfile platform target — cheaper and faster
    compute_type                = "BUILD_GENERAL1_LARGE"
    image                       = "aws/codebuild/amazonlinux2-aarch64-standard:3.0"
    type                        = "ARM_CONTAINER"
    privileged_mode             = true
    image_pull_credentials_type = "CODEBUILD"

    environment_variable {
      name  = "AWS_DEFAULT_REGION"
      value = var.aws_region
    }
    environment_variable {
      name  = "AWS_ACCOUNT_ID"
      value = local.account_id
    }
    environment_variable {
      name  = "IMAGE_REPO_NAME"
      value = aws_ecr_repository.supervisor_agent.name
    }
    environment_variable {
      name  = "IMAGE_TAG"
      value = var.agent_image_tag
    }
  }

  source {
    type     = "S3"
    location = "${aws_s3_bucket.agent_source.id}/${aws_s3_object.agent_source.key}"

    buildspec = <<-BUILDSPEC
      version: 0.2
      phases:
        pre_build:
          commands:
            - echo Logging in to Amazon ECR...
            - aws ecr get-login-password --region $AWS_DEFAULT_REGION | docker login --username AWS --password-stdin $AWS_ACCOUNT_ID.dkr.ecr.$AWS_DEFAULT_REGION.amazonaws.com
        build:
          commands:
            - echo Build started on $(date)
            - docker build --platform linux/arm64 -t $IMAGE_REPO_NAME:$IMAGE_TAG .
            - docker tag $IMAGE_REPO_NAME:$IMAGE_TAG $AWS_ACCOUNT_ID.dkr.ecr.$AWS_DEFAULT_REGION.amazonaws.com/$IMAGE_REPO_NAME:$IMAGE_TAG
        post_build:
          commands:
            - echo Pushing image...
            - docker push $AWS_ACCOUNT_ID.dkr.ecr.$AWS_DEFAULT_REGION.amazonaws.com/$IMAGE_REPO_NAME:$IMAGE_TAG
            - echo Build completed on $(date)
    BUILDSPEC
  }

  logs_config {
    cloudwatch_logs {
      group_name = "/aws/codebuild/${local.agent_prefix}-supervisor-build"
    }
  }
}

# Trigger a CodeBuild run and wait for SUCCEEDED before creating the runtime.
# Replace this resource to rebuild: terraform apply -replace=null_resource.trigger_supervisor_build
resource "null_resource" "trigger_supervisor_build" {
  triggers = {
    codebuild_project = aws_codebuild_project.supervisor_agent.id
    image_tag         = var.agent_image_tag
    # Rebuild whenever the agent source code changes
    source_code_md5   = data.archive_file.agent_source.output_md5
  }

  provisioner "local-exec" {
    command = <<-SH
      set -e
      BUILD_ID=$(aws codebuild start-build \
        --project-name "${aws_codebuild_project.supervisor_agent.name}" \
        --region "${var.aws_region}" \
        --query 'build.id' --output text)
      echo "CodeBuild started: $BUILD_ID"
      while true; do
        STATUS=$(aws codebuild batch-get-builds \
          --ids "$BUILD_ID" --region "${var.aws_region}" \
          --query 'builds[0].buildStatus' --output text)
        echo "Status: $STATUS"
        case $STATUS in
          SUCCEEDED) echo "Build succeeded!"; break ;;
          FAILED|FAULT|STOPPED|TIMED_OUT)
            echo "Build failed with status: $STATUS"; exit 1 ;;
        esac
        sleep 15
      done
    SH
  }

  depends_on = [
    aws_codebuild_project.supervisor_agent,
    aws_ecr_repository.supervisor_agent,
    aws_iam_role_policy.codebuild,
    aws_s3_object.agent_source,
  ]
}

# ---------------------------------------------------------------------------
# IAM — AgentCore Runtime execution role
# ---------------------------------------------------------------------------

resource "aws_iam_role" "agentcore_execution" {
  name        = "${local.agent_prefix}-agentcore-exec-role"
  description = "AgentCore Runtime execution role for the supervisor agent"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Sid    = "AgentCoreTrust"
      Effect = "Allow"
      Principal = { Service = "bedrock-agentcore.amazonaws.com" }
      Action = "sts:AssumeRole"
      Condition = {
        StringEquals = { "aws:SourceAccount" = local.account_id }
        ArnLike      = { "aws:SourceArn" = "arn:${local.partition}:bedrock-agentcore:${var.aws_region}:${local.account_id}:*" }
      }
    }]
  })
}

# AWS managed policy for broad AgentCore access
resource "aws_iam_role_policy_attachment" "agentcore_full_access" {
  role       = aws_iam_role.agentcore_execution.name
  policy_arn = "arn:aws:iam::aws:policy/BedrockAgentCoreFullAccess"
}

resource "aws_iam_role_policy" "agentcore_execution" {
  name = "${local.agent_prefix}-agentcore-exec-policy"
  role = aws_iam_role.agentcore_execution.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [

      # ECR — pull agent container image
      {
        Sid    = "ECRImageAccess"
        Effect = "Allow"
        Action = ["ecr:BatchGetImage", "ecr:GetDownloadUrlForLayer", "ecr:BatchCheckLayerAvailability"]
        Resource = aws_ecr_repository.supervisor_agent.arn
      },
      {
        Sid      = "ECRTokenAccess"
        Effect   = "Allow"
        Action   = ["ecr:GetAuthorizationToken"]
        Resource = "*"
      },

      # CloudWatch Logs — runtime logs
      {
        Sid    = "CloudWatchLogs"
        Effect = "Allow"
        Action = [
          "logs:CreateLogGroup", "logs:CreateLogStream",
          "logs:DescribeLogGroups", "logs:DescribeLogStreams",
          "logs:PutLogEvents",
        ]
        Resource = "arn:${local.partition}:logs:${var.aws_region}:${local.account_id}:log-group:/aws/bedrock-agentcore/runtimes/*"
      },

      # X-Ray — distributed tracing via OTEL/ADOT
      {
        Sid    = "XRayTracing"
        Effect = "Allow"
        Action = [
          "xray:PutTraceSegments", "xray:PutTelemetryRecords",
          "xray:GetSamplingRules", "xray:GetSamplingTargets",
        ]
        Resource = "*"
      },

      # CloudWatch Metrics — custom namespace from OTEL
      {
        Sid      = "CloudWatchMetrics"
        Effect   = "Allow"
        Action   = ["cloudwatch:PutMetricData"]
        Resource = "*"
        Condition = {
          StringEquals = { "cloudwatch:namespace" = "bedrock-agentcore" }
        }
      },

      # Bedrock — model invocation (Sonnet 4.5 supervisor + Haiku 4.5 classifier/workflow)
      # Cross-region inference profiles required for on-demand throughput in us-east-1
      {
        Sid    = "BedrockModelInvocation"
        Effect = "Allow"
        Action = ["bedrock:InvokeModel", "bedrock:InvokeModelWithResponseStream"]
        Resource = concat(local.sonnet_model_arns, local.haiku_model_arns)
      },

      # Bedrock Knowledge Base — retrieval for Informational Agent
      {
        Sid    = "BedrockKBRetrieve"
        Effect = "Allow"
        Action = ["bedrock:Retrieve", "bedrock:RetrieveAndGenerate"]
        Resource = aws_bedrockagent_knowledge_base.this.arn
      },

      # Bedrock Guardrails — apply during invocation (GuardrailHook)
      {
        Sid    = "BedrockGuardrails"
        Effect = "Allow"
        Action = ["bedrock:ApplyGuardrail"]
        Resource = aws_bedrock_guardrail.supervisor.guardrail_arn
      },

      # AgentCore — workload access tokens (for Gateway OAuth)
      {
        Sid    = "GetAgentAccessToken"
        Effect = "Allow"
        Action = [
          "bedrock-agentcore:GetWorkloadAccessToken",
          "bedrock-agentcore:GetWorkloadAccessTokenForJWT",
          "bedrock-agentcore:GetWorkloadAccessTokenForUserId",
        ]
        Resource = [
          "arn:${local.partition}:bedrock-agentcore:${var.aws_region}:${local.account_id}:workload-identity-directory/default",
          "arn:${local.partition}:bedrock-agentcore:${var.aws_region}:${local.account_id}:workload-identity-directory/default/workload-identity/*",
        ]
      },
    ]
  })
}

# ---------------------------------------------------------------------------
# Bedrock Guardrail — PII redaction + denied topics
# Per solution-design.md §Security: PII redaction, no investment advice
# ---------------------------------------------------------------------------

resource "aws_bedrock_guardrail" "supervisor" {
  name                      = "${local.agent_prefix}-guardrail"
  description               = "PII redaction and denied-topic controls for the automotive customer support supervisor"
  blocked_input_messaging   = "I cannot process this request. Please contact support directly."
  blocked_outputs_messaging = "I cannot provide this information. A human agent will assist you."

  sensitive_information_policy_config {
    pii_entities_config {
      action = "ANONYMIZE"
      type   = "EMAIL"
    }
    pii_entities_config {
      action = "ANONYMIZE"
      type   = "PHONE"
    }
    pii_entities_config {
      action = "ANONYMIZE"
      type   = "NAME"
    }
    pii_entities_config {
      action = "ANONYMIZE"
      type   = "US_SOCIAL_SECURITY_NUMBER"
    }
    pii_entities_config {
      action = "ANONYMIZE"
      type   = "CREDIT_DEBIT_CARD_NUMBER"
    }
    pii_entities_config {
      action = "ANONYMIZE"
      type   = "DRIVER_ID"
    }
    pii_entities_config {
      action = "ANONYMIZE"
      type   = "ADDRESS"
    }
  }

  topic_policy_config {
    topics_config {
      name       = "competitor-promotion"
      type       = "DENY"
      definition = "Any request to recommend, compare favourably, or promote a competitor automotive brand over ours."
      examples   = [
        "Which other car brand should I switch to?",
        "Tell me why competitor X is better",
      ]
    }
  }
}

resource "aws_bedrock_guardrail_version" "supervisor" {
  guardrail_arn = aws_bedrock_guardrail.supervisor.guardrail_arn
  description   = "v1 — initial production guardrail"

  depends_on = [aws_bedrock_guardrail.supervisor]
}

# ---------------------------------------------------------------------------
# CloudWatch Log Group — pre-create so the runtime can write immediately
# ---------------------------------------------------------------------------

resource "aws_cloudwatch_log_group" "agentcore_runtime" {
  name              = "/aws/bedrock-agentcore/runtimes/${local.agent_prefix}-supervisor"
  retention_in_days = 30
}

# ---------------------------------------------------------------------------
# AgentCore Runtime — supervisor agent
#
# agent_runtime_name: alphanumeric + underscores only (hyphens → underscores)
# environment_variables: injected into the container at runtime so the agent
#   code reads them via os.environ — no hardcoded IDs in Python.
# ---------------------------------------------------------------------------

resource "aws_bedrockagentcore_agent_runtime" "supervisor" {
  agent_runtime_name = replace("${local.agent_prefix}_supervisor", "-", "_")
  description        = "Automotive customer support — multi-agent supervisor (Strands + Claude Sonnet 4.5)"
  role_arn           = aws_iam_role.agentcore_execution.arn

  agent_runtime_artifact {
    container_configuration {
      container_uri = "${aws_ecr_repository.supervisor_agent.repository_url}:${var.agent_image_tag}"
    }
  }

  network_configuration {
    network_mode = var.network_mode
  }

  environment_variables = {
    AWS_REGION            = var.aws_region
    AWS_DEFAULT_REGION    = var.aws_region
    KNOWLEDGE_BASE_ID     = aws_bedrockagent_knowledge_base.this.id
    BEDROCK_GUARDRAIL_ID  = aws_bedrock_guardrail.supervisor.guardrail_id
    BEDROCK_GUARDRAIL_VER = aws_bedrock_guardrail_version.supervisor.version
    LOG_LEVEL             = var.log_level
    # Strands native OTEL — points to the CloudWatch OTLP endpoint.
    # SigV4 auth is handled automatically via the container's IAM role.
    OTEL_EXPORTER_OTLP_ENDPOINT = "https://xray.${var.aws_region}.amazonaws.com"
  }

  depends_on = [
    null_resource.trigger_supervisor_build,
    aws_iam_role_policy.agentcore_execution,
    aws_iam_role_policy_attachment.agentcore_full_access,
    aws_cloudwatch_log_group.agentcore_runtime,
  ]
}
