output "alb_dns_name" {
  value = aws_lb.this.dns_name
}

output "api_ecr_repository_url" {
  value = aws_ecr_repository.api.repository_url
}

output "frontend_ecr_repository_url" {
  value = aws_ecr_repository.frontend.repository_url
}

output "cluster_name" {
  value = aws_ecs_cluster.this.name
}

output "api_service_name" {
  value = aws_ecs_service.api.name
}

output "frontend_service_name" {
  value = aws_ecs_service.frontend.name
}

output "secrets_manager_secret_arn" {
  value       = aws_secretsmanager_secret.api_secrets.arn
  description = "ARN of the Secrets Manager secret"
}
output "kms_key_id" {
  value       = aws_kms_key.secrets.id
  description = "KMS key ID"
}

output "sns_topic_arn" {
  value       = aws_sns_topic.alerts.arn
  description = "SNS alerts topic"
}