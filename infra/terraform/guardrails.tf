# ============================================================================
# GUARDRAILS - Budget, Alarms, KMS
# ============================================================================

# KMS Key 
resource "aws_kms_key" "secrets" {
  description             = "KMS key for Voyager secrets"
  deletion_window_in_days = 7
  enable_key_rotation     = true
  tags = { Name = "${var.project_name}-secrets-key" }
}

resource "aws_kms_alias" "secrets" {
  name          = "alias/${var.project_name}-secrets"
  target_key_id = aws_kms_key.secrets.key_id
}

# secret for using KMS
resource "aws_secretsmanager_secret" "api_secrets_kms" {
  name        = "${var.project_name}-api-secrets-v2"
  description = "API secrets with KMS encryption"
  kms_key_id  = aws_kms_key.secrets.id
}

# SNS для алертів
resource "aws_sns_topic" "alerts" {
  name = "${var.project_name}-alerts"
}

resource "aws_sns_topic_subscription" "alerts_email" {
  topic_arn = aws_sns_topic.alerts.arn
  protocol  = "email"
  endpoint  = var.alert_email
}

# CloudWatch Metric Filters
resource "aws_cloudwatch_log_metric_filter" "budget_exceeded" {
  name           = "${var.project_name}-budget-exceeded"
  log_group_name = aws_cloudwatch_log_group.api.name
  pattern        = "{ $.event = \"budget_exceeded\" }"

  metric_transformation {
    name      = "BudgetExceeded"
    namespace = "${var.project_name}/Agent"
    value     = "1"
  }
}

resource "aws_cloudwatch_metric_alarm" "budget_exceeded" {
  alarm_name          = "${var.project_name}-budget-exceeded"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = "1"
  metric_name         = "BudgetExceeded"
  namespace           = "${var.project_name}/Agent"
  period              = "60"
  statistic           = "Sum"
  threshold           = "5"
  alarm_description   = "Agent budget exceeded >5 times in 1 min"
  alarm_actions       = [aws_sns_topic.alerts.arn]
}

# AWS Budget
resource "aws_budgets_budget" "monthly" {
  name              = "${var.project_name}-monthly-budget"
  budget_type       = "COST"
  limit_amount      = var.monthly_budget_usd
  limit_unit        = "USD"
  time_period_start = "2025-01-01_00:00"
  time_unit         = "MONTHLY"

  notification {
    comparison_operator        = "GREATER_THAN"
    threshold                  = 80
    threshold_type             = "PERCENTAGE"
    notification_type          = "ACTUAL"
    subscriber_email_addresses = [var.alert_email]
  }

  notification {
    comparison_operator        = "GREATER_THAN"
    threshold                  = 100
    threshold_type             = "PERCENTAGE"
    notification_type          = "ACTUAL"
    subscriber_email_addresses = [var.alert_email]
  }
}

# Cost Anomaly Detection
resource "aws_ce_anomaly_monitor" "service_monitor" {
  name              = "${var.project_name}-cost-anomaly"
  monitor_type      = "DIMENSIONAL"
  monitor_dimension = "SERVICE"
}

resource "aws_ce_anomaly_subscription" "anomaly_alerts" {
  name      = "${var.project_name}-anomaly-alerts"
  frequency = "DAILY"
  monitor_arn_list = [aws_ce_anomaly_monitor.service_monitor.arn]

  subscriber {
    type    = "EMAIL"
    address = var.alert_email
  }

  threshold_expression {
    dimension {
      key           = "ANOMALY_TOTAL_IMPACT_ABSOLUTE"
      values        = ["10"]
      match_options = ["GREATER_THAN_OR_EQUAL"]
    }
  }
}

# S3 Lifecycle
resource "aws_s3_bucket_lifecycle_configuration" "thumbnails" {
  bucket = aws_s3_bucket.thumbnails.id

  rule {
    id     = "expire-old-thumbnails"
    status = "Enabled"
    expiration { days = 90 }
  }
}

# IAM policy for Secrets + KMS
data "aws_iam_policy_document" "secrets_kms_access" {
  statement {
    effect = "Allow"
    actions = [
      "secretsmanager:GetSecretValue",
      "secretsmanager:DescribeSecret"
    ]
    resources = [aws_secretsmanager_secret.api_secrets.arn]
  }

  statement {
    effect = "Allow"
    actions = ["kms:Decrypt", "kms:DescribeKey"]
    resources = [aws_kms_key.secrets.arn]
  }
}

resource "aws_iam_policy" "secrets_kms_access" {
  name   = "${var.project_name}-secrets-kms-access"
  policy = data.aws_iam_policy_document.secrets_kms_access.json
}

resource "aws_iam_role_policy_attachment" "task_secrets_kms" {
  role       = split("/", var.ecs_task_role_arn)[1]
  policy_arn = aws_iam_policy.secrets_kms_access.arn
}