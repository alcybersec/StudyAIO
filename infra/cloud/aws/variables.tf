# StudyAIO — AWS Infrastructure Variables

variable "project" {
  description = "Project name used for resource tagging"
  type        = string
  default     = "studyaio"
}

variable "environment" {
  description = "Environment (dev, staging, prod)"
  type        = string
  default     = "prod"
}

variable "aws_region" {
  description = "AWS region"
  type        = string
  default     = "us-east-1"
}

# ── Networking ────────────────────────────────────────────────────

variable "vpc_cidr" {
  description = "CIDR block for the VPC"
  type        = string
  default     = "10.0.0.0/16"
}

variable "availability_zones" {
  description = "Availability zones (minimum 2 for RDS)"
  type        = list(string)
  default     = ["us-east-1a", "us-east-1b"]
}

# ── Database ──────────────────────────────────────────────────────

variable "db_instance_class" {
  description = "RDS instance type"
  type        = string
  default     = "db.t4g.micro"
}

variable "db_allocated_storage" {
  description = "RDS storage in GB"
  type        = number
  default     = 20
}

variable "db_password" {
  description = "Postgres master password"
  type        = string
  sensitive   = true
}

# ── Cache ─────────────────────────────────────────────────────────

variable "redis_node_type" {
  description = "ElastiCache node type"
  type        = string
  default     = "cache.t4g.micro"
}

# ── ECS ───────────────────────────────────────────────────────────

variable "api_cpu" {
  description = "API task CPU units (1024 = 1 vCPU)"
  type        = number
  default     = 512
}

variable "api_memory" {
  description = "API task memory in MiB"
  type        = number
  default     = 1024
}

variable "worker_cpu" {
  description = "Worker task CPU units"
  type        = number
  default     = 512
}

variable "worker_memory" {
  description = "Worker task memory in MiB"
  type        = number
  default     = 1024
}

variable "api_desired_count" {
  description = "Number of API task replicas"
  type        = number
  default     = 1
}

variable "worker_desired_count" {
  description = "Number of worker task replicas"
  type        = number
  default     = 1
}

# ── Container images ──────────────────────────────────────────────

variable "api_image" {
  description = "API container image (GHCR)"
  type        = string
  default     = "ghcr.io/alcybersec/studyaio-api:latest"
}

variable "ui_image" {
  description = "UI container image (GHCR)"
  type        = string
  default     = "ghcr.io/alcybersec/studyaio-ui:latest"
}

# ── Domain ────────────────────────────────────────────────────────

variable "domain" {
  description = "Domain name for the ALB (must have Route53 zone)"
  type        = string
  default     = ""
}

variable "certificate_arn" {
  description = "ACM certificate ARN for HTTPS"
  type        = string
  default     = ""
}

# ── Auth ──────────────────────────────────────────────────────────

variable "jwt_secret_key" {
  description = "JWT signing secret"
  type        = string
  sensitive   = true
}
