# cdk/lambda/complaint_handler/handler.py
import json
import boto3
import os
from datetime import datetime, timedelta

dynamodb = boto3.resource('dynamodb')
suppression_table = dynamodb.Table(os.environ['SUPPRESSION_TABLE'])
logs_table = dynamodb.Table(os.environ['EMAIL_LOGS_TABLE'])

def lambda_handler(event, context):
    """
    Process SES complaint notifications
    Add all complaints to suppression list immediately
    """
    
    processed = 0
    errors = 0
    
    for record in event['Records']:
        try:
            message = json.loads(record['body'])
            sns_message = json.loads(message['Message'])
            
            if sns_message['notificationType'] == 'Complaint':
                handle_complaint(sns_message)
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

def handle_complaint(message):
    """Process complaint notification"""
    complaint = message['complaint']
    mail = message['mail']
    
    timestamp = complaint['timestamp']
    complaint_feedback_type = complaint.get('complaintFeedbackType', 'unknown')
    
    for recipient in complaint['complainedRecipients']:
        email = recipient['emailAddress'].lower()
        
        # Log the complaint
        log_complaint(
            recipient_email=email,
            feedback_type=complaint_feedback_type,
            timestamp=timestamp,
            message_id=mail.get('messageId')
        )
        
        # Always suppress complaints
        add_to_suppression_list(
            email=email,
            reason='complaint',
            details=f"Complaint type: {complaint_feedback_type}",
            timestamp=timestamp
        )
        
        print(f"Added {email} to suppression list (complaint: {complaint_feedback_type})")

def add_to_suppression_list(email, reason, details='', timestamp=None):
    """Add email to suppression list"""
    
    if not timestamp:
        timestamp = datetime.utcnow().isoformat()
    
    # TTL: 2 years for complaints (more serious)
    ttl = int((datetime.utcnow() + timedelta(days=730)).timestamp())
    
    suppression_table.put_item(
        Item={
            'email': email,
            'reason': reason,
            'details': details,
            'suppressed_at': timestamp,
            'ttl': ttl,
            'active': True
        }
    )

def log_complaint(recipient_email, feedback_type, timestamp, message_id=None):
    """Log complaint to DynamoDB"""
    
    logs_table.put_item(
        Item={
            'campaign_id': 'system',
            'email_timestamp': f"{timestamp}#{recipient_email}",
            'recipient_email': recipient_email,
            'event_type': 'complaint',
            'feedback_type': feedback_type,
            'timestamp': timestamp,
            'message_id': message_id or 'unknown',
            'logged_at': datetime.utcnow().isoformat()
        }
    )