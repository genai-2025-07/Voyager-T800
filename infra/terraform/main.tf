terraform {
  required_version = ">= 1.5.0"
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = ">= 5.0"
    }
  }
  backend "s3" {
    bucket         = "voyager-terraform-backend"
    key            = "terraform/voyager/terraform.tfstate"
    region         = "us-east-2"
  }
}

provider "aws" {
  region = var.aws_region
}

# Get AZs available in the region
data "aws_availability_zones" "available" {}

# CREATE: project VPC
resource "aws_vpc" "this" {
  cidr_block           = var.vpc_cidr
  enable_dns_support   = true
  enable_dns_hostnames = true

  tags = {
    Name = "${var.project_name}-vpc"
  }
}

# Internet gateway so public subnets can reach the internet
resource "aws_internet_gateway" "igw" {
  vpc_id = aws_vpc.this.id
  tags = { Name = "${var.project_name}-igw" }
}

# Create N public subnets (one per AZ up to 3 by default)
resource "aws_subnet" "public" {
  count = min(var.public_subnet_count, length(data.aws_availability_zones.available.names))

  vpc_id                  = aws_vpc.this.id
  cidr_block              = cidrsubnet(aws_vpc.this.cidr_block, 8, count.index) # splits /16 -> /24s
  availability_zone       = data.aws_availability_zones.available.names[count.index]
  map_public_ip_on_launch = true

  tags = {
    Name = "${var.project_name}-public-${count.index}"
  }
}

# Public route table with default route to the IGW
resource "aws_route_table" "public" {
  vpc_id = aws_vpc.this.id

  route {
    cidr_block = "0.0.0.0/0"
    gateway_id = aws_internet_gateway.igw.id
  }

  tags = { Name = "${var.project_name}-public-rt" }
}

# Associate each public subnet with the public route table
resource "aws_route_table_association" "public" {
  count          = length(aws_subnet.public)
  subnet_id      = aws_subnet.public[count.index].id
  route_table_id = aws_route_table.public.id
}

# Local convenience values
locals {
  public_subnet_ids = aws_subnet.public[*].id
}


data "aws_subnets" "public" {
  filter {
    name   = "vpc-id"
    values = [aws_vpc.this.id]
  }
}

data "aws_caller_identity" "current" {}

# ECR repositories
resource "aws_ecr_repository" "api" {
  name = "${var.project_name}-api"
  image_scanning_configuration { scan_on_push = true }
  force_delete = true
}

resource "aws_ecr_repository" "frontend" {
  name = "${var.project_name}-frontend"
  image_scanning_configuration { scan_on_push = true }
  force_delete = true
}

# S3 bucket for thumbnails
resource "aws_s3_bucket" "thumbnails" {
  bucket = var.s3_thumbnail_bucket
}

resource "aws_s3_bucket_public_access_block" "thumbnails" {
  bucket = aws_s3_bucket.thumbnails.id
  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

# DynamoDB table for session metadata
resource "aws_dynamodb_table" "sessions" {
  name         = var.dynamodb_table
  billing_mode = "PAY_PER_REQUEST"
  hash_key     = "user_id"
  range_key    = "session_id"

  attribute {
    name = "user_id"
    type = "S"
  }
  attribute {
    name = "session_id"
    type = "S"
  }
}

# # IAM roles
# data "aws_iam_policy_document" "ecs_task_assume" {
#   statement {
#     actions = ["sts:AssumeRole"]
#     principals {
#       type        = "Service"
#       identifiers = ["ecs-tasks.amazonaws.com"]
#     }
#   }
# }

# resource "aws_iam_role" "task_execution" {
#   name               = "${var.project_name}-execution-role"
#   assume_role_policy = data.aws_iam_policy_document.ecs_task_assume.json
# }

# resource "aws_iam_role_policy_attachment" "execution" {
#   role       = aws_iam_role.task_execution.name
#   policy_arn = "arn:aws:iam::aws:policy/service-role/AmazonECSTaskExecutionRolePolicy"
# }

# resource "aws_iam_role" "task" {
#   name               = "${var.project_name}-task-role"
#   assume_role_policy = data.aws_iam_policy_document.ecs_task_assume.json
# }

# data "aws_iam_policy_document" "task_access" {
#   statement {
#     effect = "Allow"
#     actions = [
#       "dynamodb:PutItem",
#       "dynamodb:GetItem",
#       "dynamodb:UpdateItem",
#       "dynamodb:Query",
#       "dynamodb:Scan",
#       "dynamodb:DeleteItem"
#     ]
#     resources = [aws_dynamodb_table.sessions.arn]
#   }

#   statement {
#     effect = "Allow"
#     actions = [
#       "s3:PutObject",
#       "s3:GetObject",
#       "s3:DeleteObject",
#       "s3:HeadObject"
#     ]
#     resources = ["${aws_s3_bucket.thumbnails.arn}/*"]
#   }
# }

# resource "aws_iam_policy" "task_access" {
#   name   = "${var.project_name}-task-access"
#   policy = data.aws_iam_policy_document.task_access.json
# }

# resource "aws_iam_role_policy_attachment" "task_attach" {
#   role       = aws_iam_role.task.name
#   policy_arn = aws_iam_policy.task_access.arn
# }

# Logs
resource "aws_cloudwatch_log_group" "api" {
  name              = "/ecs/${var.project_name}-api"
  retention_in_days = 3
}

resource "aws_cloudwatch_log_group" "frontend" {
  name              = "/ecs/${var.project_name}-frontend"
  retention_in_days = 3
}

# ECS cluster
resource "aws_ecs_cluster" "this" {
  name = "${var.project_name}-cluster"
}

# Security groups
resource "aws_security_group" "alb" {
  name        = "${var.project_name}-alb-sg"
  description = "ALB SG"
  vpc_id      = aws_vpc.this.id

  ingress {
    from_port   = 80
    to_port     = 80
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }
}

resource "aws_security_group" "ecs_service" {
  name        = "${var.project_name}-svc-sg"
  description = "ECS service SG"
  vpc_id      = aws_vpc.this.id

  ingress {
    from_port       = 0
    to_port         = 65535
    protocol        = "tcp"
    security_groups = [aws_security_group.alb.id]
  }

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }
}

# ALB and target groups
resource "aws_lb" "this" {
  name               = "${var.project_name}-alb"
  load_balancer_type = "application"
  internal           = false
  security_groups    = [aws_security_group.alb.id]
  subnets            = local.public_subnet_ids
}

resource "aws_lb_target_group" "api" {
  name        = "${var.project_name}-api-tg"
  port        = 8000
  protocol    = "HTTP"
  vpc_id      = aws_vpc.this.id
  target_type = "ip"
  health_check {
    path = "/healthz"
  }
}

resource "aws_lb_target_group" "frontend" {
  name        = "${var.project_name}-fe-tg"
  port        = 80
  protocol    = "HTTP"
  vpc_id      = aws_vpc.this.id
  target_type = "ip"
  health_check {
    path = "/"
  }
}

resource "aws_lb_listener" "http" {
  load_balancer_arn = aws_lb.this.arn
  port              = 80
  protocol          = "HTTP"

  default_action {
    type             = "forward"
    target_group_arn = aws_lb_target_group.frontend.arn
  }
}

resource "aws_lb_listener_rule" "api_path" {
  listener_arn = aws_lb_listener.http.arn
  priority     = 10

  action {
    type             = "forward"
    target_group_arn = aws_lb_target_group.api.arn
  }

  condition {
    path_pattern { values = ["/api*", "/healthz", "/readyz"] }
  }
}

# Task definitions
resource "aws_ecs_task_definition" "api" {
  family                   = "${var.project_name}-api"
  network_mode             = "awsvpc"
  requires_compatibilities = ["FARGATE"]
  cpu                      = var.api_cpu
  memory                   = var.api_memory
  # execution_role_arn       = aws_iam_role.task_execution.arn
  # task_role_arn            = aws_iam_role.task.arn
  execution_role_arn       = var.ecs_task_execution_role_arn
  task_role_arn            = var.ecs_task_role_arn


  container_definitions = jsonencode([
    {
      name      = "api"
      image     = "${aws_ecr_repository.api.repository_url}:latest"
      essential = true
      portMappings = [{ containerPort = 8000, protocol = "tcp" }]
      environment = [
        { name = "CONTAINER_PORT", value = "8000" },
        { name = "USE_LOCAL_DYNAMODB", value = "false" },
        { name = "DYNAMODB_TABLE", value = var.dynamodb_table },
        { name = "S3_THUMBNAIL_BUCKET", value = var.s3_thumbnail_bucket },
        { name = "HOST", value = "0.0.0.0" },
        { name = "AWS_REGION", value = var.aws_region }
      ]
      logConfiguration = {
        logDriver = "awslogs"
        options = {
          awslogs-group         = aws_cloudwatch_log_group.api.name
          awslogs-region        = var.aws_region
          awslogs-stream-prefix = "ecs"
        }
      }
    }
  ])
}

resource "aws_ecs_task_definition" "frontend" {
  family                   = "${var.project_name}-frontend"
  network_mode             = "awsvpc"
  requires_compatibilities = ["FARGATE"]
  cpu                      = var.frontend_cpu
  memory                   = var.frontend_memory
  # execution_role_arn       = aws_iam_role.task_execution.arn
  execution_role_arn       = var.ecs_task_execution_role_arn

  container_definitions = jsonencode([
    {
      name         = "frontend"
      image        = "${aws_ecr_repository.frontend.repository_url}:latest"
      essential    = true
      portMappings = [{ containerPort = 80, protocol = "tcp" }]
      environment  = [{ name = "API_BASE_URL", value = aws_lb.this.dns_name }]
      logConfiguration = {
        logDriver = "awslogs"
        options = {
          awslogs-group         = aws_cloudwatch_log_group.frontend.name
          awslogs-region        = var.aws_region
          awslogs-stream-prefix = "ecs"
        }
      }
    }
  ])
}

# ECS services
resource "aws_ecs_service" "api" {
  name            = "${var.project_name}-api"
  cluster         = aws_ecs_cluster.this.id
  task_definition = aws_ecs_task_definition.api.arn
  desired_count   = var.api_desired_count
  launch_type     = "FARGATE"

  network_configuration {
    assign_public_ip = true
    subnets          = local.public_subnet_ids
    security_groups  = [aws_security_group.ecs_service.id]
  }

  load_balancer {
    target_group_arn = aws_lb_target_group.api.arn
    container_name   = "api"
    container_port   = 8000
  }

  depends_on = [aws_lb_listener.http]
}

resource "aws_ecs_service" "frontend" {
  name            = "${var.project_name}-frontend"
  cluster         = aws_ecs_cluster.this.id
  task_definition = aws_ecs_task_definition.frontend.arn
  desired_count   = var.frontend_desired_count
  launch_type     = "FARGATE"

  network_configuration {
    assign_public_ip = true
    subnets          = local.public_subnet_ids
    security_groups  = [aws_security_group.ecs_service.id]
  }

  load_balancer {
    target_group_arn = aws_lb_target_group.frontend.arn
    container_name   = "frontend"
    container_port   = 80
  }

  depends_on = [aws_lb_listener.http]
}


