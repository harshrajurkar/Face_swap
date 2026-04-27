output "vpc_id" {
  description = "VPC ID for the deployed environment."
  value       = aws_vpc.main.id
}

output "public_subnet_ids" {
  description = "Public subnet IDs used by the ALB and NAT gateway."
  value       = values(aws_subnet.public)[*].id
}

output "private_app_subnet_ids" {
  description = "Private application subnet IDs."
  value       = values(aws_subnet.private_app)[*].id
}

output "private_data_subnet_ids" {
  description = "Private data subnet IDs."
  value       = values(aws_subnet.private_data)[*].id
}

output "alb_dns_name" {
  description = "Public DNS name of the application load balancer."
  value       = aws_lb.app.dns_name
}

output "alb_zone_id" {
  description = "Route53 alias zone ID for the ALB."
  value       = aws_lb.app.zone_id
}

output "frontend_target_group_arn" {
  description = "Target group ARN for the frontend tier on the app instances."
  value       = aws_lb_target_group.frontend.arn
}

output "backend_target_group_arn" {
  description = "Target group ARN for the backend tier on the app instances."
  value       = aws_lb_target_group.backend.arn
}

output "app_instance_profile_name" {
  description = "IAM instance profile attached to app EC2 instances."
  value       = aws_iam_instance_profile.app_ec2.name
}

output "redis_primary_endpoint" {
  description = "ElastiCache Redis primary endpoint."
  value       = aws_elasticache_replication_group.redis.primary_endpoint_address
}

output "redis_url" {
  description = "Runtime Redis URL consumed by backend and worker."
  value       = "${var.redis_use_tls ? "rediss" : "redis"}://${aws_elasticache_replication_group.redis.primary_endpoint_address}:${var.redis_port}/0"
}

output "storage_bucket_name" {
  description = "S3 bucket name for uploads, outputs, or model assets."
  value       = aws_s3_bucket.app_storage.bucket
}

output "storage_bucket_arn" {
  description = "S3 bucket ARN for application storage."
  value       = aws_s3_bucket.app_storage.arn
}

output "app_directory" {
  description = "Directory on the app instances where deployment assets should be placed."
  value       = var.app_directory
}

output "frontend_image_uri" {
  description = "Frontend image URI used by deployment."
  value       = var.frontend_image_uri
}

output "backend_image_uri" {
  description = "Backend image URI used by backend and worker."
  value       = var.backend_image_uri
}

output "app_instance_id" {
  description = "Application EC2 instance ID."
  value       = aws_instance.app_debug.id
}

output "app_instance_private_ip" {
  description = "Application EC2 private IP."
  value       = aws_instance.app_debug.private_ip
}

output "public_base_url" {
  description = "Public base URL served by ALB."
  value       = "${local.https_enabled ? "https" : "http"}://${aws_lb.app.dns_name}"
}

output "grafana_url" {
  description = "Grafana URL routed through ALB."
  value       = "${local.https_enabled ? "https" : "http"}://${aws_lb.app.dns_name}/grafana"
}

output "effective_acm_certificate_arn" {
  description = "Resolved ACM certificate ARN used by ALB HTTPS listener (direct ARN or domain auto-discovery)."
  value       = local.effective_acm_certificate_arn
}

output "ec2_runtime_env_file" {
  description = "Runtime environment file path on EC2."
  value       = "${var.app_directory}/.env.runtime"
}

output "ec2_deploy_script_path" {
  description = "Deployment script path on EC2."
  value       = "/opt/scripts/deploy-ec2-single.sh"
}
