output "aurora_endpoint" {
  description = "Writer endpoint for Aurora PostgreSQL cluster"
  value       = aws_rds_cluster.aurora_postgres.endpoint
}

output "aurora_reader_endpoint" {
  description = "Reader endpoint for read-heavy operations"
  value       = aws_rds_cluster.aurora_postgres.reader_endpoint
}

output "redis_primary_endpoint" {
  description = "Primary endpoint for ElastiCache Redis replication group"
  value       = aws_elasticache_replication_group.redis.primary_endpoint_address
}

output "ecs_cluster_name" {
  description = "Name of ECS Fargate cluster"
  value       = aws_ecs_cluster.main.name
}
