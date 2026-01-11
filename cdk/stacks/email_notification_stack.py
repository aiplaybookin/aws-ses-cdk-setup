from aws_cdk import (
    Stack,
    Duration,
    RemovalPolicy,
    CfnOutput,
    aws_sns as sns,
    aws_sqs as sqs,
    aws_lambda as lambda_,
    aws_dynamodb as dynamodb,
    aws_ses as ses,
    aws_iam as iam,
    aws_lambda_event_sources as lambda_event_sources,
)
from constructs import Construct
import aws_cdk.aws_sns_subscriptions as sns_subs

class EmailNotificationStack(Stack):
    def __init__(self, scope: Construct, id: str, configuration_set_name: str, **kwargs):
        super().__init__(scope, id, **kwargs)
        
        # ============================================
        # 1. DYNAMODB TABLE FOR SUPPRESSION LIST
        # ============================================
        
        self.suppression_table = dynamodb.Table(
            self, "SuppressionList",
            table_name="email-suppression-list",
            partition_key=dynamodb.Attribute(
                name="email",
                type=dynamodb.AttributeType.STRING
            ),
            sort_key=dynamodb.Attribute(
                name="reason",
                type=dynamodb.AttributeType.STRING
            ),
            billing_mode=dynamodb.BillingMode.PAY_PER_REQUEST,
            removal_policy=RemovalPolicy.RETAIN,
            point_in_time_recovery=True,
            time_to_live_attribute="ttl",
            stream=dynamodb.StreamViewType.NEW_AND_OLD_IMAGES
        )
        
        # GSI for querying by reason
        self.suppression_table.add_global_secondary_index(
            index_name="reason-index",
            partition_key=dynamodb.Attribute(
                name="reason",
                type=dynamodb.AttributeType.STRING
            ),
            sort_key=dynamodb.Attribute(
                name="suppressed_at",
                type=dynamodb.AttributeType.STRING
            ),
            projection_type=dynamodb.ProjectionType.ALL
        )
        
        # ============================================
        # 2. EMAIL LOGS TABLE
        # ============================================
        
        self.email_logs_table = dynamodb.Table(
            self, "EmailLogs",
            table_name="email-campaign-logs",
            partition_key=dynamodb.Attribute(
                name="campaign_id",
                type=dynamodb.AttributeType.STRING
            ),
            sort_key=dynamodb.Attribute(
                name="email_timestamp",
                type=dynamodb.AttributeType.STRING
            ),
            billing_mode=dynamodb.BillingMode.PAY_PER_REQUEST,
            removal_policy=RemovalPolicy.RETAIN,
            point_in_time_recovery=True,
            stream=dynamodb.StreamViewType.NEW_IMAGE
        )
        
        # GSI for querying by recipient
        self.email_logs_table.add_global_secondary_index(
            index_name="recipient-index",
            partition_key=dynamodb.Attribute(
                name="recipient_email",
                type=dynamodb.AttributeType.STRING
            ),
            sort_key=dynamodb.Attribute(
                name="email_timestamp",
                type=dynamodb.AttributeType.STRING
            ),
            projection_type=dynamodb.ProjectionType.ALL
        )
        
        # ============================================
        # 3. SNS TOPICS FOR NOTIFICATIONS
        # ============================================
        
        self.bounce_topic = sns.Topic(
            self, "BounceNotifications",
            topic_name="email-bounce-notifications",
            display_name="Email Bounce Notifications"
        )
        
        self.complaint_topic = sns.Topic(
            self, "ComplaintNotifications",
            topic_name="email-complaint-notifications",
            display_name="Email Complaint Notifications"
        )
        
        self.delivery_topic = sns.Topic(
            self, "DeliveryNotifications",
            topic_name="email-delivery-notifications",
            display_name="Email Delivery Notifications"
        )
        
        # ============================================
        # 4. SQS QUEUES FOR PROCESSING
        # ============================================
        
        # Dead letter queue
        dlq = sqs.Queue(
            self, "NotificationDLQ",
            queue_name="email-notification-dlq",
            retention_period=Duration.days(14)
        )
        
        # Bounce queue
        self.bounce_queue = sqs.Queue(
            self, "BounceQueue",
            queue_name="email-bounce-queue",
            visibility_timeout=Duration.seconds(300),
            retention_period=Duration.days(14),
            dead_letter_queue=sqs.DeadLetterQueue(
                max_receive_count=3,
                queue=dlq
            )
        )
        
        # Complaint queue
        self.complaint_queue = sqs.Queue(
            self, "ComplaintQueue",
            queue_name="email-complaint-queue",
            visibility_timeout=Duration.seconds(300),
            retention_period=Duration.days(14),
            dead_letter_queue=sqs.DeadLetterQueue(
                max_receive_count=3,
                queue=dlq
            )
        )
        
        # Delivery queue
        self.delivery_queue = sqs.Queue(
            self, "DeliveryQueue",
            queue_name="email-delivery-queue",
            visibility_timeout=Duration.seconds(300),
            retention_period=Duration.days(7),
            dead_letter_queue=sqs.DeadLetterQueue(
                max_receive_count=3,
                queue=dlq
            )
        )
        
        # Subscribe queues to topics
        self.bounce_topic.add_subscription(
            sns_subs.SqsSubscription(self.bounce_queue)
        )
        self.complaint_topic.add_subscription(
            sns_subs.SqsSubscription(self.complaint_queue)
        )
        self.delivery_topic.add_subscription(
            sns_subs.SqsSubscription(self.delivery_queue)
        )
        
        # ============================================
        # 5. LAMBDA FUNCTIONS FOR PROCESSING
        # ============================================
        
        # Bounce processor
        self.bounce_processor = lambda_.Function(
            self, "BounceProcessor",
            function_name="email-bounce-processor",
            runtime=lambda_.Runtime.PYTHON_3_11,
            handler="handler.lambda_handler",
            code=lambda_.Code.from_asset("lambda/bounce_handler"),
            timeout=Duration.seconds(60),
            memory_size=256,
            environment={
                "SUPPRESSION_TABLE": self.suppression_table.table_name,
                "EMAIL_LOGS_TABLE": self.email_logs_table.table_name
            }
        )
        
        # Grant permissions
        self.suppression_table.grant_read_write_data(self.bounce_processor)
        self.email_logs_table.grant_write_data(self.bounce_processor)
        
        # Add SQS trigger
        self.bounce_processor.add_event_source(
            lambda_event_sources.SqsEventSource(
                self.bounce_queue,
                batch_size=10,
                max_batching_window=Duration.seconds(5)
            )
        )
        
        # Complaint processor
        self.complaint_processor = lambda_.Function(
            self, "ComplaintProcessor",
            function_name="email-complaint-processor",
            runtime=lambda_.Runtime.PYTHON_3_11,
            handler="handler.lambda_handler",
            code=lambda_.Code.from_asset("lambda/complaint_handler"),
            timeout=Duration.seconds(60),
            memory_size=256,
            environment={
                "SUPPRESSION_TABLE": self.suppression_table.table_name,
                "EMAIL_LOGS_TABLE": self.email_logs_table.table_name
            }
        )
        
        # Grant permissions
        self.suppression_table.grant_read_write_data(self.complaint_processor)
        self.email_logs_table.grant_write_data(self.complaint_processor)
        
        # Add SQS trigger
        self.complaint_processor.add_event_source(
            lambda_event_sources.SqsEventSource(
                self.complaint_queue,
                batch_size=10,
                max_batching_window=Duration.seconds(5)
            )
        )
        
        # Delivery processor (for tracking)
        self.delivery_processor = lambda_.Function(
            self, "DeliveryProcessor",
            function_name="email-delivery-processor",
            runtime=lambda_.Runtime.PYTHON_3_11,
            handler="handler.lambda_handler",
            code=lambda_.Code.from_asset("lambda/bounce_handler"),  # Reuse same code
            timeout=Duration.seconds(60),
            memory_size=256,
            environment={
                "EMAIL_LOGS_TABLE": self.email_logs_table.table_name
            }
        )
        
        self.email_logs_table.grant_write_data(self.delivery_processor)
        
        self.delivery_processor.add_event_source(
            lambda_event_sources.SqsEventSource(
                self.delivery_queue,
                batch_size=10,
                max_batching_window=Duration.seconds(5)
            )
        )
        
        # ============================================
        # 6. CONFIGURE SES EVENT DESTINATIONS
        # ============================================
        
        # Get configuration set
        config_set = ses.ConfigurationSet.from_configuration_set_name(
            self, "ConfigSet",
            configuration_set_name=configuration_set_name
        )
        
        # Add event destinations (using L1 constructs for SNS)
        ses.CfnConfigurationSetEventDestination(
            self, "BounceEventDestination",
            configuration_set_name=configuration_set_name,
            event_destination=ses.CfnConfigurationSetEventDestination.EventDestinationProperty(
                name="BounceEvents",
                enabled=True,
                matching_event_types=["bounce", "reject"],
                sns_destination=ses.CfnConfigurationSetEventDestination.SnsDestinationProperty(
                    topic_arn=self.bounce_topic.topic_arn
                )
            )
        )
        
        ses.CfnConfigurationSetEventDestination(
            self, "ComplaintEventDestination",
            configuration_set_name=configuration_set_name,
            event_destination=ses.CfnConfigurationSetEventDestination.EventDestinationProperty(
                name="ComplaintEvents",
                enabled=True,
                matching_event_types=["complaint"],
                sns_destination=ses.CfnConfigurationSetEventDestination.SnsDestinationProperty(
                    topic_arn=self.complaint_topic.topic_arn
                )
            )
        )
        
        ses.CfnConfigurationSetEventDestination(
            self, "DeliveryEventDestination",
            configuration_set_name=configuration_set_name,
            event_destination=ses.CfnConfigurationSetEventDestination.EventDestinationProperty(
                name="DeliveryEvents",
                enabled=True,
                matching_event_types=["send", "delivery"],
                sns_destination=ses.CfnConfigurationSetEventDestination.SnsDestinationProperty(
                    topic_arn=self.delivery_topic.topic_arn
                )
            )
        )
        
        # ============================================
        # 7. OUTPUTS
        # ============================================
        
        CfnOutput(
            self, "SuppressionTableName",
            value=self.suppression_table.table_name,
            description="DynamoDB suppression list table",
            export_name="SuppressionTableName"
        )
        
        CfnOutput(
            self, "EmailLogsTableName",
            value=self.email_logs_table.table_name,
            description="DynamoDB email logs table",
            export_name="EmailLogsTableName"
        )
        
        CfnOutput(
            self, "BounceQueueUrl",
            value=self.bounce_queue.queue_url,
            description="Bounce notification queue URL"
        )
        
        CfnOutput(
            self, "ComplaintQueueUrl",
            value=self.complaint_queue.queue_url,
            description="Complaint notification queue URL"
        )