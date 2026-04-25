variable "aws_region" {
  description = "AWS region where the infrastructure will be created."
  type        = string
  default     = "us-east-1"
}

variable "project_name" {
  description = "Short project name used in resource naming."
  type        = string
  default     = "ai-face-swap"
}

variable "environment" {
  description = "Deployment environment name."
  type        = string
  default     = "dev"
}

variable "vpc_cidr" {
  description = "CIDR block for the VPC."
  type        = string
  default     = "10.20.0.0/16"
}

variable "public_subnet_cidrs" {
  description = "Two public subnet CIDR blocks for the ALB and NAT gateway."
  type        = list(string)
  default     = ["10.20.1.0/24", "10.20.2.0/24"]

  validation {
    condition     = length(var.public_subnet_cidrs) >= 2
    error_message = "Provide at least two public subnet CIDRs."
  }
}

variable "private_app_subnet_cidrs" {
  description = "Two private application subnet CIDR blocks."
  type        = list(string)
  default     = ["10.20.11.0/24", "10.20.12.0/24"]

  validation {
    condition     = length(var.private_app_subnet_cidrs) >= 2
    error_message = "Provide at least two private app subnet CIDRs."
  }
}

variable "private_data_subnet_cidrs" {
  description = "Two private data subnet CIDR blocks for Redis and future internal data services."
  type        = list(string)
  default     = ["10.20.21.0/24", "10.20.22.0/24"]

  validation {
    condition     = length(var.private_data_subnet_cidrs) >= 2
    error_message = "Provide at least two private data subnet CIDRs."
  }
}

variable "app_instance_type" {
  description = "EC2 instance type for the private application tier."
  type        = string
  default     = "t3.micro"
}

variable "app_root_volume_size" {
  description = "Root EBS volume size in GiB for application instances."
  type        = number
  default     = 50
}

variable "frontend_container_port" {
  description = "Frontend container port."
  type        = number
  default     = 3000
}

variable "backend_container_port" {
  description = "Backend container port."
  type        = number
  default     = 8000
}

variable "redis_port" {
  description = "Redis port."
  type        = number
  default     = 6379
}

variable "redis_node_type" {
  description = "ElastiCache Redis node type."
  type        = string
  default     = "cache.t4g.micro"
}

variable "redis_engine_version" {
  description = "ElastiCache Redis engine version."
  type        = string
  default     = "7.1"
}

variable "redis_use_tls" {
  description = "Enable TLS-in-transit for ElastiCache and generate rediss:// runtime URLs."
  type        = bool
  default     = true
}

variable "app_directory" {
  description = "Directory on the EC2 instances where deployment assets will live."
  type        = string
  default     = "/opt/ai-face-swap"
}

variable "app_repo_url" {
  description = "Public Git repository URL that should be cloned onto app instances."
  type        = string
  default     = null

  validation {
    condition     = var.app_repo_url != null && trimspace(var.app_repo_url) != ""
    error_message = "Provide app_repo_url in tofu.auto.tfvars."
  }
}

variable "app_repo_branch" {
  description = "Git branch to clone on app instances."
  type        = string
  default     = "main"
}

variable "frontend_image_uri" {
  description = "Frontend ECR image URI."
  type        = string
  default     = null

  validation {
    condition     = var.frontend_image_uri != null && trimspace(var.frontend_image_uri) != ""
    error_message = "Provide frontend_image_uri in tofu.auto.tfvars."
  }
}

variable "backend_image_uri" {
  description = "Backend ECR image URI used by both backend and worker."
  type        = string
  default     = null

  validation {
    condition     = var.backend_image_uri != null && trimspace(var.backend_image_uri) != ""
    error_message = "Provide backend_image_uri in tofu.auto.tfvars."
  }
}

variable "execution_provider" {
  description = "Model execution provider passed to backend and worker."
  type        = string
  default     = "CPUExecutionProvider"
}

variable "worker_concurrency" {
  description = "Worker concurrency value."
  type        = number
  default     = 1
}

variable "worker_job_timeout_seconds" {
  description = "Worker job timeout in seconds."
  type        = number
  default     = 900
}

variable "worker_max_retries" {
  description = "Worker maximum retries."
  type        = number
  default     = 2
}

variable "enable_https" {
  description = "Whether to create an HTTPS listener on the ALB."
  type        = bool
  default     = false
}

variable "acm_certificate_arn" {
  description = "ACM certificate ARN for HTTPS."
  type        = string
  default     = null
}

variable "tags" {
  description = "Additional tags applied to all resources."
  type        = map(string)
  default     = {}
}
