# Create AWS Secrets Manager secret for API keys and credentials
resource "aws_secretsmanager_secret" "api_secrets" {
  name        = "${var.project_name}-api-secrets"
  description = "API keys and credentials for ${var.project_name}"
}

resource "aws_secretsmanager_secret_version" "api_secrets" {
  secret_id = aws_secretsmanager_secret.api_secrets.id
  secret_string = jsonencode({
    OPENWEATHER_API_KEY     = var.openweather_api_key
    MAP_API_KEY             = var.map_api_key
    TAVILY_API_KEY          = var.tavily_api_key
    COGNITO_USER_POOL_ID    = var.cognito_user_pool_id
    COGNITO_CLIENT_ID       = var.cognito_client_id
    COGNITO_CLIENT_SECRET   = var.cognito_client_secret
  })
}
