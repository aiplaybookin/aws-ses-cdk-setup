# send_campaign.py
import boto3
import csv
import time
import datetime 
from botocore.exceptions import ClientError

# ==========================================
# CONFIGURATION - UPDATE THESE
# ==========================================
SENDER_EMAIL = "noreply@aiplaybook.in"  # Must be verified in SES
SENDER_NAME = "AI Playbook"
SUBJECT = "🚀 Exciting Updates from AI Playbook"
REGION = "us-east-1"
CONFIGURATION_SET = "email-campaign-tracking"  # From your CDK deployment

# Files
CUSTOMER_LIST = "customers.csv"
EMAIL_TEMPLATE = "email_template.html"

# Rate limiting (SES default: 14 emails/second)
EMAILS_PER_SECOND = 1
DELAY_BETWEEN_EMAILS = 1.0 / EMAILS_PER_SECOND

# ==========================================
# SCRIPT
# ==========================================

def load_template(template_file):
    """Load HTML email template"""
    with open(template_file, 'r', encoding='utf-8') as f:
        return f.read()

def load_customers(csv_file):
    """Load customer list from CSV"""
    customers = []
    with open(csv_file, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            customers.append({
                'email': row['email'].strip().lower(),
                'first_name': row['first_name'].strip(),
                'last_name': row['last_name'].strip()
            })
    return customers

def personalize_template(template, customer):
    """Replace placeholders in template with customer data"""
    personalized = template
    personalized = personalized.replace('{{first_name}}', customer['first_name'])
    personalized = personalized.replace('{{last_name}}', customer['last_name'])
    personalized = personalized.replace('{{email}}', customer['email'])
    return personalized

def create_text_version(html_content):
    """Create simple text version from HTML"""
    # Basic HTML stripping for text version
    import re
    text = re.sub('<[^<]+?>', '', html_content)
    text = re.sub(r'\s+', ' ', text)
    return text.strip()

def send_email(ses_client, customer, html_body, text_body, subject, sender_email, sender_name):
    """Send email to one customer"""
    
    from_address = f"{sender_name} <{sender_email}>"
    
    try:
        response = ses_client.send_email(
            Source=from_address,
            Destination={
                'ToAddresses': [customer['email']]
            },
            Message={
                'Subject': {
                    'Data': subject,
                    'Charset': 'UTF-8'
                },
                'Body': {
                    'Html': {
                        'Data': html_body,
                        'Charset': 'UTF-8'
                    },
                    'Text': {
                        'Data': text_body,
                        'Charset': 'UTF-8'
                    }
                }
            },
            ConfigurationSetName=CONFIGURATION_SET,
            Tags=[
                {
                    'Name': 'campaign',
                    'Value': 'test_campaign'
                },
                {
                    'Name': 'sent_at',
                    'Value': str(datetime.datetime.now(datetime.UTC).strftime('%Y%m%d-%H%M%S'))
                }
            ]
        )
        
        return {
            'success': True,
            'message_id': response['MessageId'],
            'email': customer['email']
        }
        
    except ClientError as e:
        error_code = e.response['Error']['Code']
        error_message = e.response['Error']['Message']
        
        return {
            'success': False,
            'error_code': error_code,
            'error_message': error_message,
            'email': customer['email']
        }

def main():
    """Main function to send campaign"""
    
    print("=" * 60)
    print("AWS SES Email Campaign Sender")
    print("=" * 60)
    print()
    
    # Initialize SES client
    print(f"🔧 Connecting to AWS SES ({REGION})...")
    ses_client = boto3.client('ses', region_name=REGION)
    
    # Check send quota
    print("📊 Checking send quota...")
    try:
        quota = ses_client.get_send_quota()
        print(f"   Max 24hr Send: {quota['Max24HourSend']:,.0f}")
        print(f"   Sent Last 24hr: {quota['SentLast24Hours']:,.0f}")
        print(f"   Remaining: {quota['Max24HourSend'] - quota['SentLast24Hours']:,.0f}")
        print(f"   Max Send Rate: {quota['MaxSendRate']:.0f}/second")
        print()
        
        # Check if in sandbox mode
        if quota['Max24HourSend'] == 200:
            print("⚠️  WARNING: Account is in SANDBOX mode")
            print("   You can only send to verified email addresses")
            print("   Request production access in SES console")
            print()
            
            response = input("Continue anyway? (yes/no): ")
            if response.lower() != 'yes':
                print("Aborted.")
                return
    except ClientError as e:
        print(f"❌ Error checking quota: {e}")
        return
    
    # Load template
    print(f"📧 Loading email template: {EMAIL_TEMPLATE}")
    try:
        template = load_template(EMAIL_TEMPLATE)
        print(f"   ✓ Template loaded ({len(template)} characters)")
    except FileNotFoundError:
        print(f"   ❌ Template file not found: {EMAIL_TEMPLATE}")
        return
    
    # Load customers
    print(f"👥 Loading customer list: {CUSTOMER_LIST}")
    try:
        customers = load_customers(CUSTOMER_LIST)
        print(f"   ✓ Loaded {len(customers)} customers")
    except FileNotFoundError:
        print(f"   ❌ Customer file not found: {CUSTOMER_LIST}")
        return
    
    if len(customers) == 0:
        print("   ❌ No customers found in CSV")
        return
    
    print()
    print(f"📤 Ready to send {len(customers)} emails")
    print(f"   From: {SENDER_NAME} <{SENDER_EMAIL}>")
    print(f"   Subject: {SUBJECT}")
    print()
    
    # Confirm before sending
    response = input("Send emails? (yes/no): ")
    if response.lower() != 'yes':
        print("Aborted.")
        return
    
    print()
    print("🚀 Sending emails...")
    print("-" * 60)
    
    # Send emails
    results = {
        'sent': [],
        'failed': []
    }
    
    start_time = time.time()
    
    for i, customer in enumerate(customers, 1):
        # Personalize template
        html_body = personalize_template(template, customer)
        text_body = create_text_version(html_body)
        
        # Send email
        result = send_email(
            ses_client=ses_client,
            customer=customer,
            html_body=html_body,
            text_body=text_body,
            subject=SUBJECT,
            sender_email=SENDER_EMAIL,
            sender_name=SENDER_NAME
        )
        
        # Log result
        if result['success']:
            print(f"✓ [{i}/{len(customers)}] Sent to {customer['email']}")
            print(f"  Message ID: {result['message_id']}")
            results['sent'].append(result)
        else:
            print(f"✗ [{i}/{len(customers)}] Failed: {customer['email']}")
            print(f"  Error: {result['error_code']} - {result['error_message']}")
            results['failed'].append(result)
        
        # Rate limiting
        if i < len(customers):
            time.sleep(DELAY_BETWEEN_EMAILS)
    
    # Summary
    elapsed_time = time.time() - start_time
    
    print()
    print("-" * 60)
    print("📊 Campaign Summary")
    print("-" * 60)
    print(f"Total emails: {len(customers)}")
    print(f"✓ Sent: {len(results['sent'])}")
    print(f"✗ Failed: {len(results['failed'])}")
    print(f"Time elapsed: {elapsed_time:.2f} seconds")
    print(f"Rate: {len(customers)/elapsed_time:.2f} emails/second")
    print()
    
    # Show failed emails
    if results['failed']:
        print("Failed emails:")
        for failure in results['failed']:
            print(f"  • {failure['email']}: {failure['error_code']}")
        print()
    
    print("✅ Campaign complete!")
    print()
    print("Next steps:")
    print("1. Check CloudWatch Dashboard for delivery metrics")
    print("2. Monitor bounce/complaint notifications")
    print("3. View logs in DynamoDB email-campaign-logs table")

if __name__ == "__main__":
    main()