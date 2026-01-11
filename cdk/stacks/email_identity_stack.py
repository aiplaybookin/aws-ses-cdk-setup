from aws_cdk import (
    Stack,
    Duration,
    RemovalPolicy,
    CfnOutput,
    aws_route53 as route53,
    aws_ses as ses,
    aws_iam as iam,
)
from constructs import Construct

class EmailIdentityStack(Stack):
    def __init__(self, scope: Construct, id: str, domain_name: str, **kwargs):
        super().__init__(scope, id, **kwargs)
        
        self.domain_name = domain_name
        
        # ============================================
        # 1. GET HOSTED ZONE FROM ROUTE 53
        # ============================================
        
        self.hosted_zone = route53.HostedZone.from_lookup(
            self, "HostedZone",
            domain_name=domain_name
        )
        
        # ============================================
        # 2. CREATE CONFIGURATION SET
        # ============================================
        
        self.config_set = ses.ConfigurationSet(
            self, "EmailConfigurationSet",
            configuration_set_name="email-campaign-tracking",
            reputation_metrics=True,
            sending_enabled=True,
            suppression_reasons=ses.SuppressionReasons.BOUNCES_AND_COMPLAINTS,
            # Track opens and clicks
            tls_policy=ses.ConfigurationSetTlsPolicy.REQUIRE
        )
        
        # ============================================
        # 3. CREATE EMAIL IDENTITY WITH DKIM
        # ============================================
        # This automatically creates:
        # - Domain verification TXT record
        # - 3 DKIM CNAME records
        # - All in Route 53!
        
        self.email_identity = ses.EmailIdentity(
            self, "EmailIdentity",
            identity=ses.Identity.public_hosted_zone(self.hosted_zone),
            # Enable DKIM signing (creates 3 CNAME records automatically)
            dkim_signing=True,
            dkim_identity=ses.DkimIdentity.easy_dkim(
                signing_key_length=ses.EasyDkimSigningKeyLength.RSA_2048_BIT
            ),
            # Custom MAIL FROM domain for better deliverability
            mail_from_domain=f"email.{domain_name}",
            mail_from_behavior_on_mx_failure=ses.MailFromBehaviorOnMxFailure.USE_DEFAULT_VALUE,
            # Feedback forwarding
            feedback_forwarding=False  # We'll use SNS instead
        )
        
        # ============================================
        # 4. ADD SPF RECORD
        # ============================================
        
        spf_record = route53.TxtRecord(
            self, "SPFRecord",
            zone=self.hosted_zone,
            record_name=domain_name,
            values=["v=spf1 include:amazonses.com ~all"],
            ttl=Duration.hours(1),
            comment="SPF record for AWS SES"
        )
        
        # ============================================
        # 5. ADD DMARC RECORD
        # ============================================
        
        dmarc_record = route53.TxtRecord(
            self, "DMARCRecord",
            zone=self.hosted_zone,
            record_name=f"_dmarc.{domain_name}",
            values=[
                f"v=DMARC1; p=quarantine; rua=mailto:dmarc-reports@{domain_name}; "
                f"ruf=mailto:dmarc-forensics@{domain_name}; fo=1; pct=100; "
                f"adkim=s; aspf=s"
            ],
            ttl=Duration.hours(1),
            comment="DMARC policy for email authentication"
        )
        
        # ============================================
        # 6. ADD MX AND TXT RECORDS FOR CUSTOM MAIL FROM
        # ============================================
        
        mail_from_mx = route53.MxRecord(
            self, "MailFromMX",
            zone=self.hosted_zone,
            record_name=f"mail.{domain_name}",
            values=[
                route53.MxRecordValue(
                    host_name=f"feedback-smtp.{self.region}.amazonses.com",
                    priority=10
                )
            ],
            ttl=Duration.hours(1),
            comment="MX record for custom MAIL FROM domain"
        )
        
        mail_from_spf = route53.TxtRecord(
            self, "MailFromSPF",
            zone=self.hosted_zone,
            record_name=f"mail.{domain_name}",
            values=["v=spf1 include:amazonses.com ~all"],
            ttl=Duration.hours(1),
            comment="SPF record for custom MAIL FROM domain"
        )
        
        # ============================================
        # 7. CREATE EMAIL TEMPLATES
        # ============================================
        
        # Welcome email template
        welcome_template = ses.CfnTemplate(
            self, "WelcomeEmailTemplate",
            template=ses.CfnTemplate.TemplateProperty(
                template_name="welcome-email",
                subject_part="Welcome to {{company_name}}!",
                html_part="""
                <!DOCTYPE html>
                <html>
                <head>
                    <meta charset="UTF-8">
                    <meta name="viewport" content="width=device-width, initial-scale=1.0">
                </head>
                <body style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto;">
                    <div style="background-color: #f8f9fa; padding: 20px; text-align: center;">
                        <h1 style="color: #333;">Welcome {{user_name}}!</h1>
                    </div>
                    <div style="padding: 20px;">
                        <p>Hi {{user_name}},</p>
                        <p>We're excited to have you on board at {{company_name}}!</p>
                        <p>Click the button below to get started:</p>
                        <div style="text-align: center; margin: 30px 0;">
                            <a href="{{dashboard_url}}" 
                               style="background-color: #007bff; color: white; padding: 12px 30px; 
                                      text-decoration: none; border-radius: 5px; display: inline-block;">
                                Get Started
                            </a>
                        </div>
                        <p>If you have any questions, feel free to reply to this email.</p>
                        <p>Best regards,<br>The {{company_name}} Team</p>
                    </div>
                    <div style="background-color: #f8f9fa; padding: 20px; text-align: center; 
                                font-size: 12px; color: #666;">
                        <p>© {{current_year}} {{company_name}}. All rights reserved.</p>
                        <p><a href="{{unsubscribe_url}}" style="color: #666;">Unsubscribe</a></p>
                    </div>
                </body>
                </html>
                """,
                text_part="""
                Welcome {{user_name}}!
                
                Hi {{user_name}},
                
                We're excited to have you on board at {{company_name}}!
                
                Get started by visiting: {{dashboard_url}}
                
                If you have any questions, feel free to reply to this email.
                
                Best regards,
                The {{company_name}} Team
                
                © {{current_year}} {{company_name}}. All rights reserved.
                Unsubscribe: {{unsubscribe_url}}
                """
            )
        )
        
        # Campaign template
        campaign_template = ses.CfnTemplate(
            self, "CampaignEmailTemplate",
            template=ses.CfnTemplate.TemplateProperty(
                template_name="campaign-email",
                subject_part="{{subject}}",
                html_part="""
                <!DOCTYPE html>
                <html>
                <head>
                    <meta charset="UTF-8">
                    <meta name="viewport" content="width=device-width, initial-scale=1.0">
                </head>
                <body style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto;">
                    {{body_html}}
                    <div style="background-color: #f8f9fa; padding: 20px; margin-top: 40px; 
                                border-top: 1px solid #ddd; font-size: 12px; color: #666;">
                        <p style="margin: 5px 0;">
                            You're receiving this because you subscribed to our mailing list.
                        </p>
                        <p style="margin: 5px 0;">
                            <a href="{{unsubscribe_url}}" style="color: #666;">Unsubscribe</a> | 
                            <a href="{{preferences_url}}" style="color: #666;">Email Preferences</a>
                        </p>
                        <p style="margin: 5px 0;">{{company_address}}</p>
                    </div>
                </body>
                </html>
                """,
                text_part="{{body_text}}\n\nUnsubscribe: {{unsubscribe_url}}"
            )
        )
        
        # ============================================
        # 8. CREATE IAM ROLE FOR SENDING EMAILS
        # ============================================
        
        self.ses_sending_role = iam.Role(
            self, "SESSendingRole",
            assumed_by=iam.ServicePrincipal("lambda.amazonaws.com"),
            description="Role for Lambda functions to send emails via SES",
            managed_policies=[
                iam.ManagedPolicy.from_aws_managed_policy_name(
                    "service-role/AWSLambdaBasicExecutionRole"
                )
            ]
        )
        
        # Add SES permissions
        self.ses_sending_role.add_to_policy(
            iam.PolicyStatement(
                effect=iam.Effect.ALLOW,
                actions=[
                    "ses:SendEmail",
                    "ses:SendRawEmail",
                    "ses:SendBulkTemplatedEmail",
                    "ses:SendTemplatedEmail"
                ],
                resources=[
                    f"arn:aws:ses:{self.region}:{self.account}:identity/{domain_name}",
                    f"arn:aws:ses:{self.region}:{self.account}:configuration-set/{self.config_set.configuration_set_name}",
                    f"arn:aws:ses:{self.region}:{self.account}:template/*"
                ]
            )
        )
        
        # ============================================
        # 9. OUTPUTS
        # ============================================
        
        self.configuration_set_name = self.config_set.configuration_set_name
        
        CfnOutput(
            self, "DomainName",
            value=domain_name,
            description="Email domain name"
        )
        
        CfnOutput(
            self, "EmailIdentityArn",
            value=self.email_identity.email_identity_arn,
            description="SES Email Identity ARN"
        )
        
        CfnOutput(
            self, "ConfigurationSetName",
            value=self.config_set.configuration_set_name,
            description="SES Configuration Set Name",
            export_name="EmailConfigurationSetName"
        )
        
        CfnOutput(
            self, "HostedZoneId",
            value=self.hosted_zone.hosted_zone_id,
            description="Route 53 Hosted Zone ID"
        )
        
        CfnOutput(
            self, "SESSendingRoleArn",
            value=self.ses_sending_role.role_arn,
            description="IAM Role ARN for sending emails",
            export_name="SESSendingRoleArn"
        )
        
        CfnOutput(
            self, "VerificationInstructions",
            value=f"DNS records automatically created in Route 53. "
                  f"Check SES console for verification status: "
                  f"https://console.aws.amazon.com/ses/home?region={self.region}#/verified-identities",
            description="Next steps"
        )