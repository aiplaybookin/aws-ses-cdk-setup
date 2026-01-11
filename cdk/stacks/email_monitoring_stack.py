from aws_cdk import (
    Stack,
    Duration,
    CfnOutput,
    aws_cloudwatch as cloudwatch,
    aws_sns as sns,
    aws_cloudwatch_actions as cw_actions,
)
from constructs import Construct

class EmailMonitoringStack(Stack):
    def __init__(self, scope: Construct, id: str, configuration_set_name: str, **kwargs):
        super().__init__(scope, id, **kwargs)
        
        # ============================================
        # 1. CLOUDWATCH DASHBOARD
        # ============================================
        
        dashboard = cloudwatch.Dashboard(
            self, "EmailCampaignDashboard",
            dashboard_name="email-campaign-metrics"
        )
        
        # Metrics
        sends_metric = cloudwatch.Metric(
            namespace="AWS/SES",
            metric_name="Send",
            dimensions_map={"ConfigurationSet": configuration_set_name},
            statistic="Sum",
            period=Duration.minutes(5)
        )
        
        bounces_metric = cloudwatch.Metric(
            namespace="AWS/SES",
            metric_name="Reputation.BounceRate",
            dimensions_map={"ConfigurationSet": configuration_set_name},
            statistic="Average",
            period=Duration.minutes(5)
        )
        
        complaints_metric = cloudwatch.Metric(
            namespace="AWS/SES",
            metric_name="Reputation.ComplaintRate",
            dimensions_map={"ConfigurationSet": configuration_set_name},
            statistic="Average",
            period=Duration.minutes(5)
        )
        
        # Add widgets
        dashboard.add_widgets(
            cloudwatch.GraphWidget(
                title="Email Sends",
                left=[sends_metric],
                width=12
            ),
            cloudwatch.GraphWidget(
                title="Bounce Rate",
                left=[bounces_metric],
                width=12
            )
        )
        
        dashboard.add_widgets(
            cloudwatch.GraphWidget(
                title="Complaint Rate",
                left=[complaints_metric],
                width=24
            )
        )
        
        # ============================================
        # 2. ALARMS
        # ============================================
        
        # SNS topic for alerts
        alert_topic = sns.Topic(
            self, "EmailAlerts",
            topic_name="email-campaign-alerts",
            display_name="Email Campaign Alerts"
        )
        
        # High bounce rate alarm
        bounce_alarm = cloudwatch.Alarm(
            self, "HighBounceRateAlarm",
            alarm_name="email-high-bounce-rate",
            alarm_description="Alert when bounce rate exceeds 5%",
            metric=bounces_metric,
            threshold=0.05,
            evaluation_periods=2,
            comparison_operator=cloudwatch.ComparisonOperator.GREATER_THAN_THRESHOLD,
            treat_missing_data=cloudwatch.TreatMissingData.NOT_BREACHING
        )
        bounce_alarm.add_alarm_action(cw_actions.SnsAction(alert_topic))
        
        # High complaint rate alarm
        complaint_alarm = cloudwatch.Alarm(
            self, "HighComplaintRateAlarm",
            alarm_name="email-high-complaint-rate",
            alarm_description="Alert when complaint rate exceeds 0.1%",
            metric=complaints_metric,
            threshold=0.001,
            evaluation_periods=2,
            comparison_operator=cloudwatch.ComparisonOperator.GREATER_THAN_THRESHOLD,
            treat_missing_data=cloudwatch.TreatMissingData.NOT_BREACHING
        )
        complaint_alarm.add_alarm_action(cw_actions.SnsAction(alert_topic))
        
        # ============================================
        # 3. OUTPUTS
        # ============================================
        
        CfnOutput(
            self, "DashboardUrl",
            value=f"https://console.aws.amazon.com/cloudwatch/home?region={self.region}#dashboards:name=email-campaign-metrics",
            description="CloudWatch Dashboard URL"
        )
        
        CfnOutput(
            self, "AlertTopicArn",
            value=alert_topic.topic_arn,
            description="SNS topic for email alerts"
        )