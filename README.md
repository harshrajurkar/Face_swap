# AI Face Swap Platform

This repository is organized as a single monorepo for both the app and OpenTofu infrastructure.

## Structure

```text
repo-clean/
+-- app/
¦   +-- backend/
¦   +-- frontend/
¦   +-- docker-compose.yml
¦   +-- docker-compose.aws.yml
¦   +-- docker-compose.aws-build.yml
¦   +-- deploy-ec2-single.sh
¦   +-- README.md
+-- infra/
    +-- main.tf
    +-- variables.tf
    +-- output.tf
    +-- tofu.auto.tfvars.example
    +-- templates/
```

## What Goes Where

- `app/`: application code, compose files, and the single EC2 deployment script
- `infra/`: OpenTofu code for VPC, ALB, EC2, ElastiCache, S3, IAM, and user-data bootstrapping

## Infra Workflow (OpenTofu)

```bash
cd infra
tofu init
tofu plan
tofu apply
```

## EC2 Workflow

After `tofu apply` (or after replacing the instance), connect to EC2 and run:

```bash
sudo bash /opt/scripts/deploy-ec2-single.sh
```

The script installs Docker, builds backend/frontend images from Dockerfiles, starts backend + worker + frontend, and prints:

```text
UI is running on <url>
```
