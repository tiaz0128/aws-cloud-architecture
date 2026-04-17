# Design Document: GCP to AWS Migration

## Overview

This design document outlines the technical approach for migrating the Cloud Architecture Diagram Generator from Google Cloud Platform (GCP) to Amazon Web Services (AWS). The migration maintains functional parity while replacing all GCP-specific services with AWS equivalents.

### Migration Scope

The application consists of:
- **Backend**: FastAPI-based REST API (`backend/main.py`)
- **Frontend**: Static HTML/CSS/JS application (`frontend/`)
- **Infrastructure**: Container runtime, database, AI services, CI/CD pipeline
- **Deployment**: Automated deployment scripts

### Service Mapping

| Component | GCP Service | AWS Service |
|-----------|-------------|-------------|
| Database | Firestore | DynamoDB |
| AI Model | Vertex AI (Gemini 2.5 Flash) | Amazon Bedrock (Claude) |
| Backend Runtime | Cloud Run | AWS App Runner |
| Container Registry | Artifact Registry | Amazon ECR |
| CI/CD | Cloud Build | AWS CodeBuild |
| Frontend Hosting | Cloud Storage | S3 + CloudFront |
| CLI Tools | gcloud, gsutil | AWS CLI |

### Design Principles

1. **Functional Preservation**: All API endpoints and frontend functionality remain unchanged
2. **Service Equivalence**: AWS services are selected to match GCP capabilities
3. **Minimal Code Changes**: Focus on service client replacement, not application logic
4. **Infrastructure as Code**: Maintain declarative configuration where possible
5. **Deployment Automation**: Preserve script-based deployment workflow

---

## Architecture

### High-Level Architecture

```mermaid
architecture-beta
    group aws(logos:aws)[AWS Cloud]
    
    group frontend_tier[Frontend Tier] in aws
    service s3(aws:amazon_simple_storage_service_s3)[S3 Bucket] in frontend_tier
    service cloudfront(aws:amazon_cloudfront)[CloudFront] in frontend_tier
    
    group backend_tier[Backend Tier] in aws
    service apprunner(aws:aws_app_runner)[App Runner] in backend_tier
    service ecr(aws:amazon_elastic_container_registry)[ECR] in backend_tier
    
    group data_tier[Data Tier] in aws
    service dynamodb(aws:amazon_dynamodb)[DynamoDB] in data_tier
    service bedrock(aws:amazon_bedrock)[Bedrock] in data_tier
    
    group cicd_tier[CI/CD] in aws
    service codebuild(aws:aws_codebuild)[CodeBuild] in cicd_tier
    
    service user(mdi:account)[User]
    
    user:R --> L:cloudfront
    cloudfront:R --> L:s3
    cloudfront:B --> T:apprunner
    apprunner:R --> L:dynamodb
    apprunner:B --> T:bedrock
    codebuild:R --> L:ecr
    ecr:R --> L:apprunner
```

### Component Interactions

1. **User Request Flow**:
   - User accesses CloudFront distribution
   - CloudFront serves static files from S3
   - Frontend JavaScript calls App Runner API

2. **API Request Flow**:
   - App Runner receives HTTP request
   - Backend queries DynamoDB for data operations
   - Backend calls Bedrock for AI diagram generation
   - Response returned to frontend

3. **Deployment Flow**:
   - CodeBuild builds Docker image from source
   - Image pushed to ECR repository
   - App Runner service updated with new image
   - Frontend files uploaded to S3
   - CloudFront cache invalidated

---

## Components and Interfaces

### 1. DynamoDB Client Module

**Purpose**: Replace Firestore client with DynamoDB client for data persistence.

**Interface**:
```python
class DynamoDBClient:
    def __init__(self, table_name: str, region: str):
        """Initialize DynamoDB client with boto3"""
        
    def create_diagram(self, diagram_data: dict) -> str:
        """Create new diagram record, return diagram_id"""
        
    def get_diagram(self, diagram_id: str) -> dict:
        """Retrieve diagram by ID, raise NotFoundError if missing"""
        
    def list_diagrams(self, limit: int = 10) -> list[dict]:
        """List diagrams sorted by created_at descending"""
        
    def update_diagram(self, diagram_id: str, diagram_data: dict) -> None:
        """Update existing diagram"""
        
    def delete_diagram(self, diagram_id: str) -> None:
        """Delete diagram by ID"""
```

**Configuration**:
- Environment variables: `AWS_REGION`, `DYNAMODB_TABLE_NAME`
- IAM permissions: `dynamodb:PutItem`, `dynamodb:GetItem`, `dynamodb:Query`, `dynamodb:UpdateItem`, `dynamodb:DeleteItem`

**Error Handling**:
- Connection failures return HTTP 503
- Missing items return HTTP 404
- Invalid requests return HTTP 400

### 2. Bedrock Client Module

**Purpose**: Replace Vertex AI client with Amazon Bedrock client for AI-powered diagram generation.

**Interface**:
```python
class BedrockClient:
    def __init__(self, model_id: str, region: str):
        """Initialize Bedrock Runtime client with boto3"""
        
    def generate_diagram_code(self, prompt: str) -> str:
        """Call Claude model via Bedrock, return Mermaid code"""
```

**Configuration**:
- Environment variables: `AWS_REGION`, `BEDROCK_MODEL_ID` (e.g., `anthropic.claude-3-sonnet-20240229-v1:0`)
- IAM permissions: `bedrock:InvokeModel`

**Prompt Preservation**:
- Existing Vertex AI prompt content remains identical
- Only API invocation format changes (Bedrock JSON structure)

**Error Handling**:
- Model invocation failures return HTTP 503
- Throttling errors trigger exponential backoff retry (3 attempts)

### 3. FastAPI Backend Modifications

**Changes Required**:

1. **Dependency Replacement**:
   - Remove: `google-cloud-firestore`, `google-cloud-aiplatform`
   - Add: `boto3`, `botocore`

2. **Import Changes**:
   ```python
   # Remove
   from google.cloud import firestore
   import vertexai
   from vertexai.generative_models import GenerativeModel
   
   # Add
   import boto3
   from botocore.exceptions import ClientError
   ```

3. **Initialization Changes**:
   ```python
   # Remove GCP project ID detection
   # Remove Vertex AI initialization
   
   # Add AWS client initialization
   dynamodb_client = DynamoDBClient(
       table_name=os.getenv('DYNAMODB_TABLE_NAME'),
       region=os.getenv('AWS_REGION', 'us-east-1')
   )
   
   bedrock_client = BedrockClient(
       model_id=os.getenv('BEDROCK_MODEL_ID'),
       region=os.getenv('AWS_REGION', 'us-east-1')
   )
   ```

4. **Health Check Endpoint**:
   ```python
   @app.get("/health")
   async def health_check():
       return {
           "status": "healthy",
           "services": {
               "dynamodb": check_dynamodb_connection(),
               "bedrock": check_bedrock_availability()
           }
       }
   ```

### 4. App Runner Service Configuration

**Service Definition**:
- **Source**: ECR image URI
- **Port**: 8080
- **CPU**: 1 vCPU
- **Memory**: 2 GB
- **Auto Scaling**: 1-10 instances
- **Health Check**: `/health` endpoint

**Environment Variables**:
```
AWS_REGION=us-east-1
DYNAMODB_TABLE_NAME=cloud-diagrams
BEDROCK_MODEL_ID=anthropic.claude-3-sonnet-20240229-v1:0
```

**IAM Role Permissions**:
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
        "dynamodb:UpdateItem",
        "dynamodb:DeleteItem"
      ],
      "Resource": "arn:aws:dynamodb:*:*:table/cloud-diagrams"
    },
    {
      "Effect": "Allow",
      "Action": ["bedrock:InvokeModel"],
      "Resource": "arn:aws:bedrock:*::foundation-model/*"
    }
  ]
}
```

### 5. CodeBuild Pipeline

**buildspec.yml Structure**:
```yaml
version: 0.2

phases:
  pre_build:
    commands:
      - echo Logging in to Amazon ECR...
      - aws ecr get-login-password --region $AWS_REGION | docker login --username AWS --password-stdin $ECR_REPOSITORY_URI
  
  build:
    commands:
      - echo Building Docker image...
      - docker build -t $IMAGE_REPO_NAME:$IMAGE_TAG backend/
      - docker tag $IMAGE_REPO_NAME:$IMAGE_TAG $ECR_REPOSITORY_URI:$IMAGE_TAG
      - docker tag $IMAGE_REPO_NAME:$IMAGE_TAG $ECR_REPOSITORY_URI:latest
  
  post_build:
    commands:
      - echo Pushing Docker image to ECR...
      - docker push $ECR_REPOSITORY_URI:$IMAGE_TAG
      - docker push $ECR_REPOSITORY_URI:latest
      - echo Updating App Runner service...
      - aws apprunner start-deployment --service-arn $APP_RUNNER_SERVICE_ARN
```

**Environment Variables**:
- `AWS_REGION`
- `ECR_REPOSITORY_URI`
- `IMAGE_REPO_NAME`
- `IMAGE_TAG` (default: `latest`)
- `APP_RUNNER_SERVICE_ARN`

**IAM Role Permissions**:
- `ecr:GetAuthorizationToken`
- `ecr:BatchCheckLayerAvailability`
- `ecr:PutImage`
- `ecr:InitiateLayerUpload`
- `ecr:UploadLayerPart`
- `ecr:CompleteLayerUpload`
- `apprunner:StartDeployment`

### 6. S3 + CloudFront Frontend Hosting

**S3 Bucket Configuration**:
- **Public Access**: Blocked (CloudFront OAC only)
- **Versioning**: Enabled
- **Encryption**: AES-256 (SSE-S3)

**CloudFront Distribution**:
- **Origin**: S3 bucket with OAC
- **Default Root Object**: `index.html`
- **Error Pages**: 404 → `/404.html`
- **Cache Behavior**:
  - HTML/CSS/JS: `Cache-Control: no-cache`
  - Icons (JSON): `Cache-Control: max-age=3600`

**Frontend Code Changes**:

1. **API URL Configuration** (`app.js`):
   ```javascript
   function getApiBaseUrl() {
       const metaApiUrl = document.querySelector('meta[name="api-base-url"]');
       if (metaApiUrl && metaApiUrl.content) {
           return metaApiUrl.content;
       }
       
       // Remove GCP-specific logic
       return process.env.API_URL || 'https://default-api-url.com';
   }
   ```

2. **Icon URL Resolution** (`app.js`):
   ```javascript
   function getIconUrl(filename) {
       const cloudfrontDomain = window.location.origin;
       return `${cloudfrontDomain}/icons/${filename}`;
   }
   ```

3. **Meta Tag Injection** (`index.html`):
   ```html
   <meta name="api-base-url" content="https://<app-runner-url>">
   ```

### 7. Deployment Scripts

**Backend Deployment** (`deploy-backend.sh`):
```bash
#!/bin/bash
set -e

# Load environment variables
source .env

# ECR login
aws ecr get-login-password --region $AWS_REGION | \
    docker login --username AWS --password-stdin $ECR_REPOSITORY_URI

# Build and push Docker image
cd backend
docker build -t $IMAGE_REPO_NAME:latest .
docker tag $IMAGE_REPO_NAME:latest $ECR_REPOSITORY_URI:latest
docker push $ECR_REPOSITORY_URI:latest

# Trigger App Runner deployment
aws apprunner start-deployment \
    --service-arn $APP_RUNNER_SERVICE_ARN \
    --region $AWS_REGION

echo "Backend deployment initiated"
```

**Frontend Deployment** (`deploy-frontend.sh`):
```bash
#!/bin/bash
set -e

# Load environment variables
source .env

# Get App Runner URL
APP_RUNNER_URL=$(aws apprunner describe-service \
    --service-arn $APP_RUNNER_SERVICE_ARN \
    --query 'Service.ServiceUrl' \
    --output text)

# Inject API URL into index.html
sed -i "s|<meta name=\"api-base-url\" content=\"[^\"]*\">|<meta name=\"api-base-url\" content=\"https://$APP_RUNNER_URL\">|g" frontend/index.html

# Upload to S3
aws s3 sync frontend/ s3://$S3_BUCKET_NAME/ \
    --delete \
    --cache-control "no-cache" \
    --exclude "icons/*"

# Upload icons with longer cache
aws s3 sync frontend/icons/ s3://$S3_BUCKET_NAME/icons/ \
    --cache-control "max-age=3600"

# Invalidate CloudFront cache
aws cloudfront create-invalidation \
    --distribution-id $CLOUDFRONT_DISTRIBUTION_ID \
    --paths "/*"

echo "Frontend deployment complete"
echo "CloudFront URL: https://$CLOUDFRONT_DOMAIN"
```

**Environment Variables** (`.env`):
```bash
AWS_ACCOUNT_ID=123456789012
AWS_REGION=us-east-1
ECR_REPOSITORY_NAME=cloud-diagram-generator
ECR_REPOSITORY_URI=${AWS_ACCOUNT_ID}.dkr.ecr.${AWS_REGION}.amazonaws.com/${ECR_REPOSITORY_NAME}
IMAGE_REPO_NAME=cloud-diagram-generator
APP_RUNNER_SERVICE_ARN=arn:aws:apprunner:us-east-1:123456789012:service/cloud-diagram-generator/abc123
S3_BUCKET_NAME=cloud-architecture-frontend
CLOUDFRONT_DISTRIBUTION_ID=E1234567890ABC
CLOUDFRONT_DOMAIN=d1234567890abc.cloudfront.net
DYNAMODB_TABLE_NAME=cloud-diagrams
BEDROCK_MODEL_ID=anthropic.claude-3-sonnet-20240229-v1:0
```

---

## Data Models

### DynamoDB Table Schema

**Table Name**: `cloud-diagrams`

**Primary Key**:
- Partition Key: `diagram_id` (String) - UUID v4

**Attributes**:
```json
{
  "diagram_id": "550e8400-e29b-41d4-a716-446655440000",
  "mermaid_code": "architecture-beta\n...",
  "description": "FastAPI app with Cloud Run and Firestore",
  "cloud_provider": "gcp",
  "diagram_type": "architecture-beta",
  "created_at": "2025-01-15T10:30:00Z",
  "updated_at": "2025-01-15T11:45:00Z"
}
```

**Global Secondary Index** (for list queries):
- Index Name: `created_at-index`
- Partition Key: `cloud_provider` (String)
- Sort Key: `created_at` (String)
- Projection: ALL

**Capacity Mode**: On-Demand (pay-per-request)

### Bedrock Request/Response Format

**Request to Claude**:
```json
{
  "anthropic_version": "bedrock-2023-05-31",
  "max_tokens": 4096,
  "messages": [
    {
      "role": "user",
      "content": "<prompt from Vertex AI, unchanged>"
    }
  ],
  "temperature": 0.7
}
```

**Response from Claude**:
```json
{
  "id": "msg_01XYZ...",
  "type": "message",
  "role": "assistant",
  "content": [
    {
      "type": "text",
      "text": "architecture-beta\n..."
    }
  ],
  "stop_reason": "end_turn"
}
```

**Code Extraction**:
- Parse `content[0].text` field
- Apply same `clean_mermaid_code()` function as Vertex AI implementation

---

## Error Handling

### Error Categories and Responses

| Error Type | HTTP Status | Response Body | Logging |
|------------|-------------|---------------|---------|
| DynamoDB connection failure | 503 | `{"detail": "Database service unavailable"}` | ERROR with boto3 exception |
| Bedrock invocation failure | 503 | `{"detail": "AI service unavailable"}` | ERROR with model ID and error |
| Diagram not found | 404 | `{"detail": "Diagram not found"}` | INFO with diagram_id |
| Invalid request body | 400 | `{"detail": "Invalid request: <reason>"}` | WARNING with validation error |
| Throttling (Bedrock) | 429 | `{"detail": "Rate limit exceeded, retry after <seconds>"}` | WARNING with retry count |
| Internal server error | 500 | `{"detail": "Internal server error"}` | ERROR with full traceback |

### Retry Logic

**Bedrock API Calls**:
- Retry on: `ThrottlingException`, `ServiceUnavailableException`
- Strategy: Exponential backoff (1s, 2s, 4s)
- Max retries: 3
- Timeout: 30 seconds per attempt

**DynamoDB Operations**:
- Retry on: `ProvisionedThroughputExceededException`, `RequestLimitExceeded`
- Strategy: Exponential backoff with jitter
- Max retries: 3 (boto3 default)

### Health Check Behavior

**Endpoint**: `GET /health`

**Success Response** (200):
```json
{
  "status": "healthy",
  "timestamp": "2025-01-15T10:30:00Z",
  "services": {
    "dynamodb": "healthy",
    "bedrock": "healthy"
  }
}
```

**Degraded Response** (503):
```json
{
  "status": "unhealthy",
  "timestamp": "2025-01-15T10:30:00Z",
  "services": {
    "dynamodb": "unhealthy",
    "bedrock": "healthy"
  },
  "issues": ["DynamoDB connection test failed: <error>"]
}
```

**Health Check Tests**:
- DynamoDB: Attempt `DescribeTable` on configured table
- Bedrock: Check IAM permissions with `ListFoundationModels` (cached for 5 minutes)

---

## Testing Strategy

### Testing Approach

Since this is an **Infrastructure as Code (IaC) migration**, property-based testing is not applicable. The testing strategy focuses on:

1. **Integration Tests**: Verify AWS service interactions
2. **Deployment Validation**: Ensure infrastructure is correctly provisioned
3. **Functional Regression Tests**: Confirm API behavior matches GCP implementation
4. **End-to-End Tests**: Validate complete user workflows

### Test Categories

#### 1. Unit Tests (Backend Logic)

**Scope**: Test business logic independent of cloud services

**Examples**:
- `clean_mermaid_code()` function validation
- Request/response serialization
- Error message formatting

**Tools**: `pytest`, `pytest-asyncio`

**Coverage Target**: 80% for non-infrastructure code

#### 2. Integration Tests (AWS Services)

**Scope**: Test interactions with DynamoDB and Bedrock using real AWS services (test environment)

**Test Cases**:

**DynamoDB Integration**:
- Create diagram → verify item exists in table
- Get diagram by ID → verify correct data returned
- List diagrams → verify sorting and pagination
- Update diagram → verify changes persisted
- Delete diagram → verify item removed
- Get non-existent diagram → verify 404 response

**Bedrock Integration**:
- Generate diagram with valid prompt → verify Mermaid code returned
- Handle Bedrock throttling → verify retry logic
- Handle invalid model ID → verify error handling

**Setup**:
- Use dedicated test DynamoDB table (`cloud-diagrams-test`)
- Use test AWS account or IAM role with limited permissions
- Clean up test data after each test run

**Tools**: `pytest`, `boto3`, `moto` (for local mocking during development)

#### 3. API Functional Tests

**Scope**: Verify API endpoints match GCP implementation behavior

**Test Cases**:
- `POST /generate-diagram` → verify response structure
- `GET /diagrams/{id}` → verify diagram retrieval
- `GET /diagrams` → verify list pagination
- `PUT /diagrams/{id}` → verify update behavior
- `DELETE /diagrams/{id}` → verify deletion
- `GET /health` → verify health check response

**Comparison Strategy**:
- Run same test suite against GCP and AWS deployments
- Assert identical response structures (excluding cloud-specific metadata)

**Tools**: `pytest`, `httpx` or `requests`

#### 4. Deployment Validation Tests

**Scope**: Verify infrastructure is correctly provisioned

**Test Cases**:

**App Runner**:
- Service is running and healthy
- Environment variables are set correctly
- IAM role has required permissions
- Health check endpoint responds

**DynamoDB**:
- Table exists with correct schema
- GSI is configured correctly
- On-demand capacity mode is enabled

**ECR**:
- Repository exists
- Latest image is tagged correctly

**S3 + CloudFront**:
- S3 bucket has correct permissions (OAC only)
- CloudFront distribution is enabled
- Default root object is `index.html`
- Cache behaviors are configured correctly

**Tools**: AWS CLI, `boto3`, shell scripts

**Execution**: Run after each deployment via CI/CD pipeline

#### 5. End-to-End Tests

**Scope**: Validate complete user workflows from frontend to backend

**Test Scenarios**:
1. User loads frontend from CloudFront
2. User submits diagram generation request
3. Backend calls Bedrock and stores result in DynamoDB
4. Frontend displays generated diagram
5. User downloads diagram as SVG/PNG

**Tools**: Playwright or Selenium for browser automation

**Execution**: Run nightly against staging environment

#### 6. Performance Tests

**Scope**: Ensure AWS implementation meets performance requirements

**Metrics**:
- API response time: < 2 seconds (excluding AI generation)
- AI generation time: < 10 seconds (Bedrock)
- Frontend load time: < 1 second (CloudFront)
- DynamoDB query latency: < 100ms

**Tools**: `locust` or `k6` for load testing

**Baseline**: Compare against GCP performance metrics

#### 7. Migration Validation Tests

**Scope**: Verify data migration from Firestore to DynamoDB (if applicable)

**Test Cases**:
- Export all diagrams from Firestore
- Import into DynamoDB
- Verify record count matches
- Verify sample records have identical content
- Verify all fields are correctly mapped

**Tools**: Python migration script with validation checks

### Test Execution Plan

**Pre-Migration**:
1. Run full test suite against GCP deployment (baseline)
2. Document all test results and performance metrics

**During Migration**:
1. Deploy AWS infrastructure to staging environment
2. Run integration tests against AWS services
3. Run API functional tests and compare with GCP baseline
4. Run deployment validation tests
5. Fix any issues before production deployment

**Post-Migration**:
1. Run end-to-end tests against production
2. Run performance tests and compare with baseline
3. Monitor health check endpoint for 24 hours
4. Validate CloudWatch logs and metrics

**Continuous Testing**:
- Run unit tests on every commit (CI)
- Run integration tests on every pull request
- Run end-to-end tests nightly
- Run performance tests weekly

### Test Environment Setup

**AWS Test Account**:
- Separate AWS account for testing (recommended)
- Or use resource tagging to isolate test resources

**Test Data**:
- Use synthetic test data (no production data in tests)
- Clean up test resources after each run

**CI/CD Integration**:
- GitHub Actions or AWS CodePipeline
- Automated test execution on pull requests
- Deployment to staging on merge to `main`
- Manual approval for production deployment

---

## Migration Checklist

### Phase 1: Infrastructure Setup

- [ ] Create DynamoDB table with GSI
- [ ] Create ECR repository
- [ ] Create S3 bucket for frontend
- [ ] Create CloudFront distribution with OAC
- [ ] Create IAM roles for App Runner and CodeBuild
- [ ] Enable Bedrock model access in AWS account
- [ ] Set up CodeBuild project with buildspec.yml

### Phase 2: Code Changes

- [ ] Update `pyproject.toml` dependencies
- [ ] Implement `DynamoDBClient` class
- [ ] Implement `BedrockClient` class
- [ ] Update `main.py` to use new clients
- [ ] Remove GCP imports and initialization code
- [ ] Update `/health` endpoint
- [ ] Update `frontend/app.js` API URL logic
- [ ] Update `frontend/app.js` icon URL logic
- [ ] Create `buildspec.yml` for CodeBuild
- [ ] Update `deploy-backend.sh` for AWS CLI
- [ ] Update `deploy-frontend.sh` for AWS CLI
- [ ] Create `.env.example` with AWS variables

### Phase 3: Testing

- [ ] Run unit tests locally
- [ ] Deploy to AWS staging environment
- [ ] Run integration tests against staging
- [ ] Run API functional tests and compare with GCP
- [ ] Run deployment validation tests
- [ ] Run end-to-end tests
- [ ] Run performance tests and compare with baseline
- [ ] Fix any issues identified

### Phase 4: Production Deployment

- [ ] Deploy backend to App Runner production
- [ ] Deploy frontend to S3/CloudFront production
- [ ] Update DNS (if applicable)
- [ ] Run smoke tests against production
- [ ] Monitor health check endpoint
- [ ] Monitor CloudWatch logs and metrics
- [ ] Verify all API endpoints are functional

### Phase 5: Cleanup

- [ ] Remove `cloudbuild.yaml`
- [ ] Remove `.gcloudignore`
- [ ] Remove GCP-specific documentation
- [ ] Update README.md with AWS instructions
- [ ] Archive GCP deployment (optional)
- [ ] Decommission GCP resources (after validation period)

---

## Rollback Plan

In case of critical issues during migration:

1. **Immediate Rollback**:
   - Revert DNS to GCP Cloud Run URL (if changed)
   - Frontend continues to call GCP backend
   - No data loss (DynamoDB and Firestore can coexist)

2. **Partial Rollback**:
   - Keep frontend on CloudFront
   - Point API URL back to GCP Cloud Run
   - Investigate AWS backend issues

3. **Data Synchronization**:
   - If data was migrated, export DynamoDB data
   - Re-import to Firestore if needed
   - Verify data integrity

4. **Rollback Testing**:
   - Test rollback procedure in staging before production migration
   - Document rollback steps in runbook

---

## Security Considerations

### IAM Least Privilege

- App Runner role: Only DynamoDB and Bedrock permissions
- CodeBuild role: Only ECR and App Runner permissions
- S3 bucket: Block all public access, CloudFront OAC only

### Secrets Management

- No hardcoded credentials in code
- Use AWS Systems Manager Parameter Store or Secrets Manager for sensitive values
- Rotate IAM access keys regularly

### Network Security

- App Runner: Private VPC endpoint (optional, for enhanced security)
- DynamoDB: VPC endpoint (optional)
- CloudFront: Enable AWS WAF for DDoS protection (optional)

### Data Encryption

- DynamoDB: Encryption at rest (AWS managed keys)
- S3: Server-side encryption (SSE-S3)
- App Runner: HTTPS only (TLS 1.2+)

### Monitoring and Logging

- Enable CloudWatch Logs for App Runner
- Enable CloudTrail for API audit logging
- Set up CloudWatch Alarms for error rates and latency
- Enable S3 access logging (optional)

---

## Cost Estimation

### Monthly Cost Breakdown (Estimated)

**Compute**:
- App Runner: ~$20-50 (1 vCPU, 2GB, low traffic)

**Storage**:
- DynamoDB: ~$5-10 (on-demand, low traffic)
- S3: ~$1-5 (static files)
- ECR: ~$1 (Docker images)

**Data Transfer**:
- CloudFront: ~$10-30 (depends on traffic)

**AI Services**:
- Bedrock (Claude): ~$10-50 (depends on usage, ~$0.003 per 1K input tokens)

**Total Estimated**: ~$50-150/month (low to moderate traffic)

**Cost Optimization**:
- Use DynamoDB on-demand pricing (no idle costs)
- Enable CloudFront caching to reduce origin requests
- Use App Runner auto-scaling to scale to zero during idle periods
- Monitor Bedrock usage and optimize prompts

---

## Appendix

### Useful AWS CLI Commands

**Check App Runner service status**:
```bash
aws apprunner describe-service --service-arn $APP_RUNNER_SERVICE_ARN
```

**View DynamoDB table**:
```bash
aws dynamodb describe-table --table-name cloud-diagrams
```

**List ECR images**:
```bash
aws ecr list-images --repository-name cloud-diagram-generator
```

**Invalidate CloudFront cache**:
```bash
aws cloudfront create-invalidation --distribution-id $CLOUDFRONT_DISTRIBUTION_ID --paths "/*"
```

**View CloudWatch logs**:
```bash
aws logs tail /aws/apprunner/cloud-diagram-generator --follow
```

### References

- [AWS App Runner Documentation](https://docs.aws.amazon.com/apprunner/)
- [Amazon DynamoDB Developer Guide](https://docs.aws.amazon.com/dynamodb/)
- [Amazon Bedrock User Guide](https://docs.aws.amazon.com/bedrock/)
- [AWS CodeBuild User Guide](https://docs.aws.amazon.com/codebuild/)
- [Amazon CloudFront Developer Guide](https://docs.aws.amazon.com/cloudfront/)
