#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
TF_DIR="$SCRIPT_DIR/../terraform"

echo "Reading Terraform outputs..."
KB_ID=$(terraform -chdir="$TF_DIR" output -raw knowledge_base_id)
DS_ID=$(terraform -chdir="$TF_DIR" output -raw data_source_id)
REGION=$(terraform -chdir="$TF_DIR" output -raw aws_region 2>/dev/null || echo "us-east-1")

echo "Starting ingestion job..."
JOB=$(aws bedrock-agent start-ingestion-job \
  --knowledge-base-id "$KB_ID" \
  --data-source-id   "$DS_ID" \
  --region           "$REGION" \
  --output json)

JOB_ID=$(echo "$JOB" | python3 -c "import json,sys; print(json.load(sys.stdin)['ingestionJob']['ingestionJobId'])")
echo "Job started: $JOB_ID"

echo "Waiting for completion..."
while true; do
  STATUS=$(aws bedrock-agent get-ingestion-job \
    --knowledge-base-id "$KB_ID" \
    --data-source-id    "$DS_ID" \
    --ingestion-job-id  "$JOB_ID" \
    --region            "$REGION" \
    --query "ingestionJob.status" --output text)

  echo "  status: $STATUS"
  case "$STATUS" in
    COMPLETE)  echo "Done."; break ;;
    FAILED)    echo "Ingestion failed."; exit 1 ;;
    *)         sleep 10 ;;
  esac
done
