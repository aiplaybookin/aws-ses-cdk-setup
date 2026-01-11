# cdk/lambda/bounce_handler/handler.py
import json
import boto3
import os
from datetime import datetime, timedelta
from decimal import Decimal

dynamodb = boto3.resource('dynamodb')
suppression_table = dynamodb.Table(os.environ['SUPPRESSION_TABLE'])
logs_table = dynamodb.Table(os.environ['EMAIL_LOGS_TABLE'])

def lambda_handler(event, context):
    """
    Process SES bounce notifications
    Add permanent bounces to suppression list
    """
    
    processed = 0
    errors = 0
    
    for record in event['Records']:
        try:
            # Parse SQS message
            message = json.loads(record['body'])
            sns_message = json.loads(message['Message'])
            
            notification_type = sns_message['notificationType']
            
            if notification_type == 'Bounce':
                handle_bounce(sns_message)
                processed += 1
            elif notification_type == 'Delivery':
                handle_delivery(sns_message)
                processed += 1
                
        except Exception as e:
            print(f"Error processing record: {e}")
            errors += 1
    
    return {
        'statusCode': 200,
        'body': json.dumps({
            'processed': processed,
            'errors': errors
        })
    }

def handle_bounce(message):
    """Process bounce notification"""
    bounce = message['bounce']
    mail = message['mail']
    
    bounce_type = bounce['bounceType']  # Permanent or Transient
    timestamp = bounce['timestamp']
    
    for recipient in bounce['bouncedRecipients']:
        email = recipient['emailAddress'].lower()
        
        # Log the bounce
        log_email_event(
            recipient_email=email,
            event_type='bounce',
            bounce_type=bounce_type,
            diagnostic_code=recipient.get('diagnosticCode', ''),
            timestamp=timestamp,
            message_id=mail.get('messageId')
        )
        
        # Only suppress permanent bounces
        if bounce_type == 'Permanent':
            add_to_suppression_list(
                email=email,
                reason='bounce',
                bounce_type=bounce_type,
                details=recipient.get('diagnosticCode', 'Permanent bounce'),
                timestamp=timestamp
            )
            print(f"Added {email} to suppression list (permanent bounce)")
        else:
            print(f"Logged transient bounce for {email}")

def handle_delivery(message):
    """Process delivery notification"""
    mail = message['mail']
    delivery = message['delivery']
    
    for recipient in delivery['recipients']:
        log_email_event(
            recipient_email=recipient.lower(),
            event_type='delivery',
            timestamp=delivery['timestamp'],
            message_id=mail.get('messageId'),
            processing_time_ms=delivery.get('processingTimeMillis')
        )

def add_to_suppression_list(email, reason, bounce_type='', details='', timestamp=None):
    """Add email to suppression list in DynamoDB"""
    
    if not timestamp:
        timestamp = datetime.utcnow().isoformat()
    
    # TTL: 1 year from now
    ttl = int((datetime.utcnow() + timedelta(days=365)).timestamp())
    
    suppression_table.put_item(
        Item={
            'email': email,
            'reason': reason,
            'bounce_type': bounce_type,
            'details': details,
            'suppressed_at': timestamp,
            'ttl': ttl,
            'active': True
        }
    )

def log_email_event(recipient_email, event_type, timestamp, message_id=None, **kwargs):
    """Log email event to DynamoDB"""
    
    item = {
        'campaign_id': kwargs.get('campaign_id', 'system'),
        'email_timestamp': f"{timestamp}#{recipient_email}",
        'recipient_email': recipient_email,
        'event_type': event_type,
        'timestamp': timestamp,
        'logged_at': datetime.utcnow().isoformat()
    }
    
    if message_id:
        item['message_id'] = message_id
    
    # Add any additional fields
    for key, value in kwargs.items():
        if value is not None:
            item[key] = value
    
    logs_table.put_item(Item=item)