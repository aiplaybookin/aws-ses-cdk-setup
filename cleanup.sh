#!/bin/bash

echo "🗑️  Complete AWS SES Infrastructure Cleanup"
echo "==========================================="
echo ""
echo "⚠️  WARNING: This will DELETE everything!"
echo "   - All stacks"
echo "   - DynamoDB tables (with data)"
echo "   - Lambda functions"
echo "   - SNS topics"
echo "   - SQS queues"
echo "   - CloudWatch alarms"
echo "   - DNS records"
echo ""
read -p "Are you sure? Type 'DELETE' to confirm: " confirm

if [ "$confirm" != "DELETE" ]; then
    echo "❌ Cleanup cancelled"
    exit 1
fi

echo ""
echo "🗑️  Step 1: Destroying CDK stacks..."
cdk destroy --all --force

echo ""
echo "🗑️  Step 2: Checking for orphaned resources..."

# Get AWS account info
REGION="us-east-1"
ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)

echo ""
echo "📋 Checking DynamoDB tables..."
aws dynamodb list-tables --region $REGION | grep -E "email-suppression-list|email-campaign-logs"

echo ""
echo "📋 Checking SES identities..."
aws ses list-identities --region $REGION

echo ""
echo "📋 Checking Lambda functions..."
aws lambda list-functions --region $REGION --query 'Functions[?contains(FunctionName, `email`)].FunctionName'

echo ""
echo "📋 Checking SNS topics..."
aws sns list-topics --region $REGION | grep email

echo ""
echo "📋 Checking SQS queues..."
aws sqs list-queues --region $REGION | grep email

echo ""
echo "📋 Checking S3 CDK buckets..."
aws s3 ls | grep cdk

echo ""
echo "✅ Cleanup complete!"
echo ""
echo "⚠️  Manual cleanup may be needed for:"
echo "   1. DynamoDB tables (if RETAIN policy)"
echo "   2. Route 53 DNS records (check manually)"
echo "   3. S3 CDK staging buckets"