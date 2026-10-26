variable "aws_region" {
  description = "AWS deployment region"
  type        = string
  default     = "ap-south-1" # Mumbai for low latency in India
}

variable "environment" {
  description = "Target environment"
  type        = string
  default     = "production"
}

variable "vpc_cidr" {
  description = "CIDR block for VPC"
  type        = string
  default     = "10.0.0.0/16"
}

variable "db_username" {
  description = "PostgreSQL Master Username"
  type        = string
  default     = "amrutam_admin"
  sensitive   = true
}

variable "db_password" {
  description = "PostgreSQL Master Password"
  type        = string
  sensitive   = true
}
