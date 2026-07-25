#!/bin/bash
set -e

PROJECT_ID="primer-proyecto-103"
REGION="us-central1"
SERVICE_NAME="apod-pipeline"
SERVICE_ACCOUNT="apod-pipeline-sa@${PROJECT_ID}.iam.gserviceaccount.com"

echo "🔨 Building and pushing Docker image..."
gcloud builds submit --tag "gcr.io/${PROJECT_ID}/${SERVICE_NAME}" --region=global .

echo "🚀 Deploying to Cloud Run..."
gcloud run deploy "${SERVICE_NAME}" \
  --image "gcr.io/${PROJECT_ID}/${SERVICE_NAME}" \
  --region "${REGION}" \
  --platform managed \
  --allow-unauthenticated \
  --memory 512Mi \
  --timeout 900 \
  --set-secrets="NASA_API_KEY=nasa-api-key:latest,SLACK_WEBHOOK_URL=slack-webhook-url:latest" \
  --service-account="${SERVICE_ACCOUNT}"

echo "🌐 Deploying frontend to Firebase Hosting..."
firebase deploy --only hosting

echo "✅ Deploy complete!"
echo "🔗 Pipeline URL: https://${SERVICE_NAME}-441860274924.${REGION}.run.app"
echo "🔗 Frontend: https://apod-pipeline.web.app"