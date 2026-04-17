# AWS Infrastructure Setup Guide

This guide provides step-by-step instructions for setting up the AWS infrastructure required for the Cloud Architecture Diagram Generator application.

## Prerequisites

- AWS Account with appropriate permissions
- AWS CLI installed and configured (`aws configure`)
- Docker installed (for local testing)
- Basic understanding of AWS services

## Overview

The application uses the following AWS services:
- **Amazon DynamoDB**: NoSQL database for storing diagram data
- **Amazon Bedrock**: AI service for diagram generation (Claude model)
- **AWS App Runner**: Container-based backend service
- **Amazon ECR**: Docker image registry
- **Amazon S3**: Static file storage for frontend
- **Amazon CloudFront**: CDN for frontend distribution
- **AWS CodeBuild**: CI/CD pipeline for automated deployments
- **IAM**: Identity and access management

---

## Step 1: Create DynamoDB Table

### 1.1 Create Table

```bash
aws dynamodb create-table \
    --table-name cloud-diagrams \
    --attribute-definitions \
        AttributeName=diagram_id,AttributeType=S \
        AttributeName=created_at,AttributeType=S \
        AttributeName=cloud_provider,AttributeType=S \
    --key-schema \
        AttributeName=diagram_id,KeyType=HASH \
    --billing-mode PAY_PER_REQUEST \
    --region us-east-1
```

### 1.2 Create Global Secondary Index (GSI)

```bash
aws dynamodb update-table \
    --table-name cloud-diagrams \
    --attribute-definitions \
        AttributeName=cloud_provider,AttributeType=S \
        AttributeName=created_at,AttributeType=S \
    --global-secondary-index-updates \
        "[{\"Create\":{\"IndexName\":\"created_at-index\",\"KeySchema\":[{\"AttributeName\":\"cloud_provider\",\"KeyType\":\"HASH\"},{\"AttributeName\":\"created_at\",\"KeyType\":\"RANGE\"}],\"Projection\":{\"ProjectionType\":\"ALL\"}}}]" \
    --region us-east-1
```

### 1.3 Verify Table Creation

```bash
aws dynamodb describe-table \
    --table-name cloud-diagrams \
    --region us-east-1
```

---

## Step 2: Create ECR Repository

### 2.1 Create Repository

```bash
aws ecr create-repository \
    --repository-name cloud-diagram-generator \
    --region us-east-1
```

### 2.2 Get Repository URI

```bash
aws ecr describe-repositories \
    --repository-names cloud-diagram-generator \
    --region us-east-1 \
    --query 'repositories[0].repositoryUri' \
    --output text
```

Save this URI for later use in your `.env` file.

---

## Step 3: Create S3 Bucket for Frontend

### 3.1 Create Bucket

```bash
aws s3 mb s3://cloud-architecture-frontend --region us-east-1
```

### 3.2 Block Public Access

```bash
aws s3api put-public-access-block \
    --bucket cloud-architecture-frontend \
    --public-access-block-configuration \
        "BlockPublicAcls=true,IgnorePublicAcls=true,BlockPublicPolicy=true,RestrictPublicBuckets=true"
```

### 3.3 Enable Versioning (Optional but Recommended)

```bash
aws s3api put-bucket-versioning \
    --bucket cloud-architecture-frontend \
    --versioning-configuration Status=Enabled
```

---

## Step 4: Create CloudFront Distribution with OAC

### 4.1 Create Origin Access Control (OAC)

Create a file named `oac-config.json`:

```json
{
    "Name": "cloud-architecture-oac",
    "Description": "OAC for cloud architecture frontend",
    "SigningProtocol": "sigv4",
    "SigningBehavior": "always",
    "OriginAccessControlOriginType": "s3"
}
```

Create the OAC:

```bash
aws cloudfront create-origin-access-control \
    --origin-access-control-config file://oac-config.json \
    --region us-east-1
```

Save the OAC ID from the output.

### 4.2 Create CloudFront Distribution

Create a file named `cloudfront-config.json` (replace `YOUR_BUCKET_NAME` and `YOUR_OAC_ID`):

```json
{
    "CallerReference": "cloud-architecture-frontend-2024",
    "Comment": "CloudFront distribution for Cloud Architecture Diagram Generator",
    "Enabled": true,
    "DefaultRootObject": "index.html",
    "Origins": {
        "Quantity": 1,
        "Items": [
            {
                "Id": "S3-cloud-architecture-frontend",
                "DomainName": "cloud-architecture-frontend.s3.us-east-1.amazonaws.com",
                "OriginAccessControlId": "YOUR_OAC_ID",
                "S3OriginConfig": {
                    "OriginAccessIdentity": ""
                }
            }
        ]
    },
    "DefaultCacheBehavior": {
        "TargetOriginId": "S3-cloud-architecture-frontend",
        "ViewerProtocolPolicy": "redirect-to-https",
        "AllowedMethods": {
            "Quantity": 2,
            "Items": ["GET", "HEAD"],
            "CachedMethods": {
                "Quantity": 2,
                "Items": ["GET", "HEAD"]
            }
        },
        "Compress": true,
        "CachePolicyId": "658327ea-f89d-4fab-a63d-7e88639e58f6",
        "ResponseHeadersPolicyId": "67f7725c-6f97-4210-82d7-5512b31e9d03"
    },
    "CustomErrorResponses": {
        "Quantity": 1,
        "Items": [
            {
                "ErrorCode": 404,
                "ResponsePagePath": "/404.html",
                "ResponseCode": "404",
                "ErrorCachingMinTTL": 300
            }
        ]
    }
}
```

Create the distribution:

```bash
aws cloudfront create-distribution \
    --distribution-config file://cloudfront-config.json
```

Save the Distribution ID and Domain Name from the output.

### 4.3 Update S3 Bucket Policy for OAC

Create a file named `s3-bucket-policy.json` (replace `YOUR_BUCKET_NAME`, `YOUR_DISTRIBUTION_ARN`):

```json
{
    "Version": "2012-10-17",
    "Statement": [
        {
            "Sid": "AllowCloudFrontServicePrincipal",
            "Effect": "Allow",
            "Principal": {
                "Service": "cloudfront.amazonaws.com"
            },
            "Action": "s3:GetObject",
            "Resource": "arn:aws:s3:::YOUR_BUCKET_NAME/*",
            "Condition": {
                "StringEquals": {
                    "AWS:SourceArn": "YOUR_DISTRIBUTION_ARN"
                }
            }
        }
    ]
}
```

Apply the policy:

```bash
aws s3api put-bucket-policy \
    --bucket cloud-architecture-frontend \
    --policy file://s3-bucket-policy.json
```

---

## Step 5: Enable Amazon Bedrock Model Access

### 5.1 Request Model Access

1. Go to AWS Console → Amazon Bedrock → Model access
2. Click "Manage model access"
3. Select "Anthropic Claude 3 Sonnet"
4. Click "Request model access"
5. Wait for approval (usually instant for Claude models)

### 5.2 Verify Access via CLI

```bash
aws bedrock list-foundation-models \
    --region us-east-1 \
    --query 'modelSummaries[?contains(modelId, `claude`)].modelId'
```

---

## Step 6: Create IAM Roles

### 6.1 App Runner IAM Role

Create a file named `apprunner-trust-policy.json`:

```json
{
    "Version": "2012-10-17",
    "Statement": [
        {
            "Effect": "Allow",
            "Principal": {
                "Service": "tasks.apprunner.amazonaws.com"
            },
            "Action": "sts:AssumeRole"
        }
    ]
}
```

Create the role:

```bash
aws iam create-role \
    --role-name AppRunnerDiagramGeneratorRole \
    --assume-role-policy-document file://apprunner-trust-policy.json
```

Create a file named `apprunner-permissions.json`:

```json
{
    "Version": "2012-10-17",
    "Statement": [
        {
            "Effect": "Allow",
            "Action": [
                "dynamodb:PutItem",
                "dynamodb:GetItem",
                "dynamodb:Query",
                "dynamodb:Scan",
                "dynamodb:UpdateItem",
                "dynamodb:DeleteItem",
                "dynamodb:DescribeTable"
            ],
            "Resource": [
                "arn:aws:dynamodb:*:*:table/cloud-diagrams",
                "arn:aws:dynamodb:*:*:table/cloud-diagrams/index/*"
            ]
        },
        {
            "Effect": "Allow",
            "Action": [
                "bedrock:InvokeModel",
                "bedrock:ListFoundationModels"
            ],
            "Resource": "*"
        }
    ]
}
```

Attach the policy:

```bash
aws iam put-role-policy \
    --role-name AppRunnerDiagramGeneratorRole \
    --policy-name AppRunnerPermissions \
    --policy-document file://apprunner-permissions.json
```

### 6.2 CodeBuild IAM Role

Create a file named `codebuild-trust-policy.json`:

```json
{
    "Version": "2012-10-17",
    "Statement": [
        {
            "Effect": "Allow",
            "Principal": {
                "Service": "codebuild.amazonaws.com"
            },
            "Action": "sts:AssumeRole"
        }
    ]
}
```

Create the role:

```bash
aws iam create-role \
    --role-name CodeBuildDiagramGeneratorRole \
    --assume-role-policy-document file://codebuild-trust-policy.json
```

Attach AWS managed policies:

```bash
aws iam attach-role-policy \
    --role-name CodeBuildDiagramGeneratorRole \
    --policy-arn arn:aws:iam::aws:policy/AmazonEC2ContainerRegistryPowerUser

aws iam attach-role-policy \
    --role-name CodeBuildDiagramGeneratorRole \
    --policy-arn arn:aws:iam::aws:policy/CloudWatchLogsFullAccess
```

Create a file named `codebuild-apprunner-permissions.json`:

```json
{
    "Version": "2012-10-17",
    "Statement": [
        {
            "Effect": "Allow",
            "Action": [
                "apprunner:StartDeployment",
                "apprunner:DescribeService"
            ],
            "Resource": "*"
        }
    ]
}
```

Attach the policy:

```bash
aws iam put-role-policy \
    --role-name CodeBuildDiagramGeneratorRole \
    --policy-name CodeBuildAppRunnerPermissions \
    --policy-document file://codebuild-apprunner-permissions.json
```

---

## Step 7: Create App Runner Service

### 7.1 Build and Push Initial Docker Image

First, build and push an initial image to ECR:

```bash
# Login to ECR
aws ecr get-login-password --region us-east-1 | \
    docker login --username AWS --password-stdin YOUR_ACCOUNT_ID.dkr.ecr.us-east-1.amazonaws.com

# Build image
cd backend
docker build -t cloud-diagram-generator:latest .

# Tag and push
docker tag cloud-diagram-generator:latest YOUR_ECR_URI:latest
docker push YOUR_ECR_URI:latest
cd ..
```

### 7.2 Create App Runner Service

Create a file named `apprunner-service.json` (replace placeholders):

```json
{
    "ServiceName": "cloud-diagram-generator",
    "SourceConfiguration": {
        "ImageRepository": {
            "ImageIdentifier": "YOUR_ECR_URI:latest",
            "ImageRepositoryType": "ECR",
            "ImageConfiguration": {
                "Port": "8080",
                "RuntimeEnvironmentVariables": {
                    "AWS_REGION": "us-east-1",
                    "DYNAMODB_TABLE_NAME": "cloud-diagrams",
                    "BEDROCK_MODEL_ID": "anthropic.claude-3-sonnet-20240229-v1:0"
                }
            }
        },
        "AutoDeploymentsEnabled": false
    },
    "InstanceConfiguration": {
        "Cpu": "1 vCPU",
        "Memory": "2 GB",
        "InstanceRoleArn": "arn:aws:iam::YOUR_ACCOUNT_ID:role/AppRunnerDiagramGeneratorRole"
    },
    "HealthCheckConfiguration": {
        "Protocol": "HTTP",
        "Path": "/health",
        "Interval": 10,
        "Timeout": 5,
        "HealthyThreshold": 1,
        "UnhealthyThreshold": 5
    }
}
```

Create the service:

```bash
aws apprunner create-service \
    --cli-input-json file://apprunner-service.json \
    --region us-east-1
```

Save the Service ARN from the output.

### 7.3 Wait for Service to be Running

```bash
aws apprunner describe-service \
    --service-arn YOUR_SERVICE_ARN \
    --region us-east-1 \
    --query 'Service.Status'
```

---

## Step 8: Create CodeBuild Project

Create a file named `codebuild-project.json` (replace placeholders):

```json
{
    "name": "cloud-diagram-generator-build",
    "source": {
        "type": "GITHUB",
        "location": "https://github.com/YOUR_USERNAME/YOUR_REPO.git",
        "buildspec": "backend/buildspec.yml"
    },
    "artifacts": {
        "type": "NO_ARTIFACTS"
    },
    "environment": {
        "type": "LINUX_CONTAINER",
        "image": "aws/codebuild/standard:7.0",
        "computeType": "BUILD_GENERAL1_SMALL",
        "privilegedMode": true,
        "environmentVariables": [
            {
                "name": "AWS_REGION",
                "value": "us-east-1"
            },
            {
                "name": "ECR_REPOSITORY_URI",
                "value": "YOUR_ECR_URI"
            },
            {
                "name": "IMAGE_REPO_NAME",
                "value": "cloud-diagram-generator"
            },
            {
                "name": "IMAGE_TAG",
                "value": "latest"
            },
            {
                "name": "APP_RUNNER_SERVICE_ARN",
                "value": "YOUR_APP_RUNNER_ARN"
            }
        ]
    },
    "serviceRole": "arn:aws:iam::YOUR_ACCOUNT_ID:role/CodeBuildDiagramGeneratorRole"
}
```

Create the project:

```bash
aws codebuild create-project \
    --cli-input-json file://codebuild-project.json
```

---

## Step 9: Configure Environment Variables

Create a `.env` file in your project root:

```bash
# AWS Account Configuration
AWS_ACCOUNT_ID=123456789012
AWS_REGION=us-east-1

# ECR (Elastic Container Registry)
ECR_REPOSITORY_NAME=cloud-diagram-generator
ECR_REPOSITORY_URI=123456789012.dkr.ecr.us-east-1.amazonaws.com/cloud-diagram-generator
IMAGE_REPO_NAME=cloud-diagram-generator

# App Runner
APP_RUNNER_SERVICE_ARN=arn:aws:apprunner:us-east-1:123456789012:service/cloud-diagram-generator/abc123

# S3 and CloudFront
S3_BUCKET_NAME=cloud-architecture-frontend
CLOUDFRONT_DISTRIBUTION_ID=E1234567890ABC
CLOUDFRONT_DOMAIN=d1234567890abc.cloudfront.net

# DynamoDB
DYNAMODB_TABLE_NAME=cloud-diagrams

# Amazon Bedrock
BEDROCK_MODEL_ID=anthropic.claude-3-sonnet-20240229-v1:0
```

---

## Step 10: Test Deployment

### 10.1 Deploy Backend

```bash
./deploy-backend.sh
```

### 10.2 Deploy Frontend

```bash
./deploy-frontend.sh
```

### 10.3 Verify Deployment

Test the backend health endpoint:

```bash
curl https://YOUR_APP_RUNNER_URL/health
```

Test the frontend:

```bash
open https://YOUR_CLOUDFRONT_DOMAIN
```

---

## Troubleshooting

### DynamoDB Connection Issues

- Verify IAM role has correct permissions
- Check table name matches environment variable
- Verify table exists in the correct region

### Bedrock Access Denied

- Ensure model access is enabled in Bedrock console
- Verify IAM role has `bedrock:InvokeModel` permission
- Check model ID is correct

### App Runner Deployment Fails

- Check CloudWatch Logs for error messages
- Verify ECR image exists and is accessible
- Ensure environment variables are set correctly

### CloudFront Not Serving Files

- Verify S3 bucket policy allows CloudFront OAC
- Check CloudFront distribution is enabled
- Wait for distribution to fully deploy (can take 15-20 minutes)

---

## Cost Estimation

Approximate monthly costs for low to moderate traffic:

- **DynamoDB**: $5-10 (on-demand pricing)
- **App Runner**: $20-50 (1 vCPU, 2GB RAM)
- **S3**: $1-5 (static files)
- **CloudFront**: $10-30 (depends on traffic)
- **Bedrock**: $10-50 (depends on usage, ~$0.003 per 1K input tokens)
- **ECR**: $1 (Docker images)

**Total**: ~$50-150/month

---

## Security Best Practices

1. **Use IAM roles** instead of access keys where possible
2. **Enable CloudTrail** for audit logging
3. **Use AWS Secrets Manager** for sensitive configuration
4. **Enable S3 versioning** for rollback capability
5. **Set up CloudWatch alarms** for error rates and latency
6. **Use VPC endpoints** for DynamoDB (optional, for enhanced security)
7. **Enable AWS WAF** on CloudFront (optional, for DDoS protection)

---

## Next Steps

1. Set up CI/CD pipeline with GitHub Actions or AWS CodePipeline
2. Configure custom domain with Route 53
3. Set up monitoring and alerting with CloudWatch
4. Implement backup strategy for DynamoDB
5. Configure auto-scaling for App Runner based on traffic patterns

---

## Additional Resources

- [AWS App Runner Documentation](https://docs.aws.amazon.com/apprunner/)
- [Amazon DynamoDB Developer Guide](https://docs.aws.amazon.com/dynamodb/)
- [Amazon Bedrock User Guide](https://docs.aws.amazon.com/bedrock/)
- [AWS CodeBuild User Guide](https://docs.aws.amazon.com/codebuild/)
- [Amazon CloudFront Developer Guide](https://docs.aws.amazon.com/cloudfront/)
