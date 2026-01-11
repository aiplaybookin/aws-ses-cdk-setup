#!/bin/bash

echo "🔄 Quick Deploy Script"
echo "====================="

# Check what changed
echo ""
echo "📋 Checking changes..."
cdk diff

echo ""
read -p "Deploy these changes? (yes/no): " confirm

if [ "$confirm" = "yes" ]; then
    echo ""
    echo "🚀 Deploying..."
    cdk deploy --all --require-approval never
    
    echo ""
    echo "✅ Deployment complete!"
else
    echo "❌ Deployment cancelled"
fi