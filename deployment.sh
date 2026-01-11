#!/bin/bash

echo "🚀 Deploying AWS SES Email Infrastructure"
echo "=========================================="

# 1. Install dependencies
echo "📦 Installing Python dependencies..."
cd cdk
pip install -r requirements.txt

# 2. Install Lambda dependencies
echo "📦 Installing Lambda dependencies..."
cd lambda/bounce_handler
pip install -r requirements.txt -t .
cd ../complaint_handler
pip install -r requirements.txt -t .
cd ../..

# 3. Bootstrap CDK (only needed first time)
echo "🏗️  Bootstrapping CDK..."
cdk bootstrap

# 4. Synthesize CloudFormation
echo "🔨 Synthesizing CloudFormation templates..."
cdk synth

# 5. Deploy stacks
echo "🚀 Deploying stacks..."
cdk deploy --all --require-approval never

echo ""
echo "✅ Deployment complete!"
echo ""
echo "Next steps:"
echo "1. Check SES console for domain verification status"
echo "2. Wait 10-15 minutes for DNS propagation"
echo "3. Request production access (if in sandbox mode)"
echo "4. Test sending emails"