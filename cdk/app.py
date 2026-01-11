import os
from aws_cdk import App, Environment
from stacks.email_identity_stack import EmailIdentityStack
from stacks.email_notification_stack import EmailNotificationStack
from stacks.email_monitoring_stack import EmailMonitoringStack
from dotenv import load_dotenv

load_dotenv()

app = App()

# Get configuration from environment or context
account = os.getenv('AWS_ACCOUNT_ID') or app.node.try_get_context('account')
region = os.getenv('AWS_REGION', 'us-east-1')
domain = os.getenv('DOMAIN_NAME') or app.node.try_get_context('domain')

if not domain:
    raise ValueError("DOMAIN_NAME must be set in .env or passed via context")

env = Environment(account=account, region=region)

# Stack 1: Email Identity and DNS Configuration
email_identity_stack = EmailIdentityStack(
    app,
    "EmailIdentityStack",
    domain_name=domain,
    env=env,
    description="SES Email Identity with Route 53 DNS configuration"
)

# Stack 2: Notification Handling (Bounces, Complaints)
notification_stack = EmailNotificationStack(
    app,
    "EmailNotificationStack",
    configuration_set_name=email_identity_stack.configuration_set_name,
    env=env,
    description="SES bounce and complaint notification handling"
)

# Stack 3: Monitoring and Analytics
monitoring_stack = EmailMonitoringStack(
    app,
    "EmailMonitoringStack",
    configuration_set_name=email_identity_stack.configuration_set_name,
    env=env,
    description="SES monitoring, dashboards, and analytics"
)

# Add dependencies
notification_stack.add_dependency(email_identity_stack)
monitoring_stack.add_dependency(email_identity_stack)

app.synth()