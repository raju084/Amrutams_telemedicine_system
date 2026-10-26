# ==============================================================================
# Terraform Infrastructure as Code: Amrutam Telemedicine Backend
# Provider: AWS (Multi-AZ, High-Availability, 99.95% SLA)
# ==============================================================================

terraform {
  required_version = ">= 1.5.0"
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }
  backend "s3" {
    bucket         = "amrutam-terraform-state-prod"
    key            = "telemedicine/backend/terraform.tfstate"
    region         = "ap-south-1"
    dynamodb_table = "amrutam-tf-locks"
    encrypt        = true
  }
}

provider "aws" {
  region = var.aws_region
  default_tags {
    tags = {
      Project     = "Amrutam Telemedicine"
      Environment = var.environment
      ManagedBy   = "Terraform"
    }
  }
}

# 1. High Availability VPC
resource "aws_vpc" "main" {
  cidr_block           = var.vpc_cidr
  enable_dns_hostnames = true
  enable_dns_support   = true
  tags = {
    Name = "amrutam-telemedicine-vpc-${var.environment}"
  }
}

# 2. Aurora PostgreSQL Serverless v2 Multi-AZ Cluster (Supports 100k Consultations)
resource "aws_rds_cluster" "aurora_postgres" {
  cluster_identifier      = "amrutam-aurora-pg-${var.environment}"
  engine                  = "aurora-postgresql"
  engine_mode             = "provisioned"
  engine_version          = "16.1"
  database_name           = "amrutam_db"
  master_username         = var.db_username
  master_password         = var.db_password
  backup_retention_period = 30
  preferred_backup_window = "02:00-03:00"
  storage_encrypted       = true
  deletion_protection     = true
  skip_final_snapshot     = false

  serverlessv2_scaling_configuration {
    min_capacity = 2.0
    max_capacity = 64.0
  }
}

resource "aws_rds_cluster_instance" "aurora_instances" {
  count               = 2 # Multi-AZ Primary + Replica
  identifier          = "amrutam-aurora-instance-${count.index}"
  cluster_identifier  = aws_rds_cluster.aurora_postgres.id
  instance_class      = "db.serverless"
  engine              = aws_rds_cluster.aurora_postgres.engine
  engine_version      = aws_rds_cluster.aurora_postgres.engine_version
  publicly_accessible = false
}

# 3. AWS ElastiCache Redis Cluster (Multi-AZ with Auto-Failover)
resource "aws_elasticache_replication_group" "redis" {
  replication_group_id          = "amrutam-redis-${var.environment}"
  description                   = "Amrutam distributed cache and distributed locking cluster"
  engine                        = "redis"
  engine_version                = "7.0"
  node_type                     = "cache.m6g.large"
  num_cache_clusters            = 2
  port                          = 6379
  automatic_failover_enabled    = true
  multi_az_enabled              = true
  at_rest_encryption_enabled    = true
  transit_encryption_enabled    = true
  apply_immediately             = true
}

# 4. AWS ECS Fargate Cluster
resource "aws_ecs_cluster" "main" {
  name = "amrutam-ecs-cluster-${var.environment}"

  setting {
    name  = "containerInsights"
    value = "enabled"
  }
}
