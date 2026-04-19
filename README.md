# AI Face Swap Platform

This repository is now organized as a single monorepo for both the product code and the AWS/OpenTofu infrastructure.

## Structure

```text
ai-face-swap-platform/
├── app/
│   ├── backend/
│   ├── frontend/
│   ├── docker-compose.yml
│   ├── docker-compose.aws.yml
│   ├── deploy-aws-stack.sh
│   └── README.md
└── infra/
    ├── main.tf
    ├── variables.tf
    ├── output.tf
    ├── terraform.tfvars.example
    ├── .terraform.lock.hcl
    └── templates/
```

## What goes where

- `app/`: actual application source code, local Docker Compose setup, and the AWS deployment compose/script
- `infra/`: OpenTofu code for AWS networking, ALB, EC2, Redis, S3, IAM, and bootstrapping

## How to use it

### Work on the application

Use the app folder:

```bash
cd app
docker compose up --build
```

### Work on the infrastructure

Use the infra folder:

```bash
cd infra
tofu init
tofu plan
tofu apply
```

## Deployment flow

1. Push app changes from `app/` to GitHub
2. Rebuild and push the Docker images from `app/`
3. Run OpenTofu from `infra/`
4. Connect to the EC2 instance with SSM
5. Run `app/deploy-aws-stack.sh` on the instance

## Why this layout is good

- one repository for the complete project story
- clearer separation between product code and infrastructure
- easier CI/CD later
- easier to explain in interviews
