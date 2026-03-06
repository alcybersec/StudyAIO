# Outputs

output "vpc_id" {
  description = "VPC ID"
  value       = aws_vpc.main.id
}

output "alb_dns" {
  description = "ALB DNS name (point your domain CNAME here)"
  value       = aws_lb.main.dns_name
}

output "rds_endpoint" {
  description = "RDS PostgreSQL endpoint"
  value       = aws_db_instance.main.endpoint
}

output "redis_endpoint" {
  description = "ElastiCache Redis endpoint"
  value       = aws_elasticache_cluster.main.cache_nodes[0].address
}

output "s3_bucket" {
  description = "S3 bucket name for file storage"
  value       = aws_s3_bucket.data.id
}

output "ecs_cluster" {
  description = "ECS cluster name"
  value       = aws_ecs_cluster.main.name
}

output "api_service" {
  description = "ECS API service name"
  value       = aws_ecs_service.api.name
}

output "worker_service" {
  description = "ECS worker service name"
  value       = aws_ecs_service.worker.name
}
