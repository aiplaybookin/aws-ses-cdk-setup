# AWS SES Email Infrastructure

Complete AWS SES setup with Route 53 DNS configuration.

## Prerequisites

- AWS Account
- Domain registered and using Route 53 for DNS
- AWS CLI configured
- Python 3.11+
- Node.js 18+ (for CDK)

## Quick Start

1. **Install dependencies:**
```bash
   cd cdk
   pip install -r requirements.txt
   npm install -g aws-cdk
```

2. **Configure environment:**
```bash
   cp .env.example .env
   # Edit .env with your domain and AWS account
```

3. **Deploy:**
```bash
   chmod +x deployment.sh
   ./deployment.sh
```

4. **Verify:**
```bash
   python tests/verify_setup.py yourdomain.com
```

## What Gets Created

### Email Identity Stack
- ✅ SES Email Identity
- ✅ Automatic Route 53 DNS records (TXT, CNAME, MX)
- ✅ DKIM signing configuration
- ✅ SPF and DMARC records
- ✅ Custom MAIL FROM domain
- ✅ Email templates
- ✅ IAM roles for sending

### Notification Stack
- ✅ SNS topics for bounces/complaints/deliveries
- ✅ SQS queues for processing
- ✅ Lambda functions for handling notifications
- ✅ DynamoDB suppression list
- ✅ DynamoDB email logs

### Monitoring Stack
- ✅ CloudWatch dashboard
- ✅ Bounce rate alarms
- ✅ Complaint rate alarms

## DNS Records Created

All automatically added to Route 53:

1. **Domain Verification** - TXT record
2. **DKIM (3 records)** - CNAME records
3. **SPF** - TXT record
4. **DMARC** - TXT record
5. **Custom MAIL FROM** - MX and TXT records

## Production Access

After deployment, request production access:

1. Go to AWS SES Console
2. Click "Account dashboard"
3. Click "Request production access"
4. Fill out the form
5. Wait 24-48 hours for approval

## Testing

Send a test email:
```bash
aws ses send-email \
  --from "noreply@yourdomain.com" \
  --destination "ToAddresses=test@example.com" \
  --message "Subject={Data='Test'},Body={Text={Data='Hello!'}}" \
  --configuration-set-name email-campaign-tracking
```

## Costs

Estimated monthly costs (100K emails):
- SES: $10
- Lambda: $1
- DynamoDB: $5
- CloudWatch: $2
**Total: ~$18/month**

## Support

For issues, check:
1. CloudWatch Logs
2. SES Console verification status
3. Route 53 DNS records