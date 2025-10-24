variable "ecs_task_execution_role_arn" {
  type        = string
  description = "ARN of an existing ECS task execution role (must have AmazonECSTaskExecutionRolePolicy attached)"
}

variable "ecs_task_role_arn" {
  type        = string
  description = "ARN of an existing ECS task role (must have permissions to access DynamoDB and S3 as required by the app)"
}

variable "project_name" {
  type        = string
  description = "Project name prefix"
  default     = "voyager"
}

variable "vpc_cidr" {
  type        = string
  description = "CIDR block for the VPC"
  default     = "10.0.0.0/16"
}

variable "public_subnet_count" {
  type        = number
  description = "How many public subnets to create (1-3 recommended)"
  default     = 2
}


variable "aws_region" {
  type        = string
  description = "AWS region"
  default     = "us-east-2"
}

variable "s3_thumbnail_bucket" {
  type        = string
  description = "S3 bucket for thumbnails"
}

variable "dynamodb_table" {
  type        = string
  description = "DynamoDB table name"
  default     = "session_metadata"
}

variable "api_cpu" {
  type        = string
  default     = "512"
}

variable "api_memory" {
  type        = string
  default     = "1024"
}

variable "api_desired_count" {
  type        = number
  default     = 1
}

variable "frontend_cpu" {
  type        = string
  default     = "256"
}

variable "frontend_memory" {
  type        = string
  default     = "512"
}

variable "frontend_desired_count" {
  type        = number
  default     = 1
}

variable "openweather_api_key" {
  type        = string
  description = "OpenWeather API key"
  sensitive   = true
}

variable "map_api_key" {
  type        = string
  description = "Map API key"
  sensitive   = true
}

variable "tavily_api_key" {
  type        = string
  description = "Tavily API key"
  sensitive   = true
}

variable "cognito_user_pool_id" {
  type        = string
  description = "Cognito User Pool ID"
  sensitive   = true
}

variable "cognito_client_id" {
  type        = string
  description = "Cognito Client ID"
  sensitive   = true
}

variable "cognito_client_secret" {
  type        = string
  description = "Cognito Client Secret"
  sensitive   = true
}
variable "alert_email" {
  type        = string
  description = "Email for budget/alarm alerts"
}

variable "monthly_budget_usd" {
  type        = number
  description = "Monthly budget in USD"
  default     = 100
}