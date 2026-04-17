
# 🏗️ Cloud Architecture Diagram Generator

AI-powered cloud architecture diagram generator that converts natural language descriptions into Mermaid architecture diagrams.

## 🌟 Features

- **AI-Powered Generation**: Uses Amazon Bedrock (Claude) to generate diagrams from text descriptions
- **Multi-Cloud Support**: Supports GCP, AWS, and Azure architectures
- **Interactive Diagrams**: Zoom, pan, and export diagrams as SVG or PNG
- **Manual Code Editor**: Write and render Mermaid code directly
- **Responsive Design**: Works on desktop and mobile devices

## 🏗️ Architecture

### AWS Services

- **Backend**: AWS App Runner (containerized FastAPI application)
- **Database**: Amazon DynamoDB (NoSQL database for diagram storage)
- **AI Model**: Amazon Bedrock with Claude 3 Sonnet
- **Frontend**: Amazon S3 + CloudFront (static website hosting with CDN)
- **Container Registry**: Amazon ECR (Docker image storage)
- **CI/CD**: AWS CodeBuild (automated deployments)

### Architecture Diagram

```
┌─────────────────────────────────────────────────────────────┐
│                         AWS Cloud                            │
│                                                              │
│  ┌──────────────┐      ┌──────────────┐                    │
│  │  CloudFront  │─────▶│      S3      │                    │
│  │     (CDN)    │      │  (Frontend)  │                    │
│  └──────┬───────┘      └──────────────┘                    │
│         │                                                    │
│         │                                                    │
│         ▼                                                    │
│  ┌──────────────┐      ┌──────────────┐                    │
│  │  App Runner  │─────▶│   DynamoDB   │                    │
│  │  (Backend)   │      │  (Database)  │                    │
│  └──────┬───────┘      └──────────────┘                    │
│         │                                                    │
│         ▼                                                    │
│  ┌──────────────┐                                           │
│  │   Bedrock    │                                           │
│  │   (Claude)   │                                           │
│  └──────────────┘                                           │
│                                                              │
│  ┌──────────────┐      ┌──────────────┐                    │
│  │  CodeBuild   │─────▶│     ECR      │                    │
│  │   (CI/CD)    │      │  (Registry)  │                    │
│  └──────────────┘      └──────────────┘                    │
└─────────────────────────────────────────────────────────────┘
```

## 🚀 Quick Start

### Prerequisites

- AWS Account with appropriate permissions
- AWS CLI installed and configured
- Docker installed
- Python 3.12+
- Node.js (for local frontend development, optional)

### 1. Clone Repository

```bash
git clone https://github.com/your-username/cloud-architecture-diagram-generator.git
cd cloud-architecture-diagram-generator
```

### 2. Set Up AWS Infrastructure

Follow the detailed guide in [docs/aws-infrastructure-setup.md](docs/aws-infrastructure-setup.md) to set up:

- DynamoDB table
- ECR repository
- S3 bucket and CloudFront distribution
- IAM roles
- App Runner service
- CodeBuild project
- Bedrock model access

### 3. Configure Environment Variables

Copy `.env.example` to `.env` and fill in your AWS details:

```bash
cp .env.example .env
```

Edit `.env`:

```bash
AWS_ACCOUNT_ID=123456789012
AWS_REGION=us-east-1
ECR_REPOSITORY_NAME=cloud-diagram-generator
ECR_REPOSITORY_URI=123456789012.dkr.ecr.us-east-1.amazonaws.com/cloud-diagram-generator
IMAGE_REPO_NAME=cloud-diagram-generator
APP_RUNNER_SERVICE_ARN=arn:aws:apprunner:us-east-1:123456789012:service/cloud-diagram-generator/abc123
S3_BUCKET_NAME=cloud-architecture-frontend
CLOUDFRONT_DISTRIBUTION_ID=E1234567890ABC
CLOUDFRONT_DOMAIN=d1234567890abc.cloudfront.net
DYNAMODB_TABLE_NAME=cloud-diagrams
BEDROCK_MODEL_ID=anthropic.claude-3-sonnet-20240229-v1:0
```

### 4. Deploy Backend

```bash
./deploy-backend.sh
```

This script will:
1. Login to ECR
2. Build Docker image
3. Push to ECR
4. Trigger App Runner deployment

### 5. Deploy Frontend

```bash
./deploy-frontend.sh
```

This script will:
1. Get App Runner URL
2. Inject API URL into frontend
3. Upload files to S3
4. Invalidate CloudFront cache

### 6. Access Application

Open your CloudFront domain in a browser:

```
https://YOUR_CLOUDFRONT_DOMAIN
```

## 🛠️ Local Development

### Backend

```bash
cd backend

# Install dependencies with uv
uv venv
uv sync

# Set environment variables
export AWS_REGION=us-east-1
export DYNAMODB_TABLE_NAME=cloud-diagrams
export BEDROCK_MODEL_ID=anthropic.claude-3-sonnet-20240229-v1:0

# Run server
uvicorn main:app --reload --port 8080
```

### Frontend

```bash
cd frontend

# Serve with Python
python -m http.server 8000

# Or use any static file server
# npx serve .
```

Open `http://localhost:8000` in your browser.

## 📝 API Documentation

Once the backend is deployed, access the interactive API documentation:

- Swagger UI: `https://YOUR_APP_RUNNER_URL/docs`
- ReDoc: `https://YOUR_APP_RUNNER_URL/redoc`

### Key Endpoints

- `POST /generate-diagram`: Generate diagram from description
- `GET /diagrams/{id}`: Retrieve diagram by ID
- `GET /diagrams`: List all diagrams
- `PUT /diagrams/{id}`: Update diagram
- `DELETE /diagrams/{id}`: Delete diagram
- `GET /health`: Health check endpoint

## 🧪 Testing

### Backend Tests

```bash
cd backend
pytest
```

### API Testing

```bash
# Health check
curl https://YOUR_APP_RUNNER_URL/health

# Generate diagram
curl -X POST https://YOUR_APP_RUNNER_URL/generate-diagram \
  -H "Content-Type: application/json" \
  -d '{
    "description": "FastAPI app with DynamoDB and Bedrock",
    "cloud_provider": "aws",
    "diagram_type": "architecture-beta"
  }'
```

## 📦 Project Structure

```
.
├── backend/
│   ├── main.py                 # FastAPI application
│   ├── dynamodb_client.py      # DynamoDB client
│   ├── bedrock_client.py       # Bedrock client
│   ├── Dockerfile              # Container definition
│   ├── buildspec.yml           # CodeBuild configuration
│   └── pyproject.toml          # Python dependencies
├── frontend/
│   ├── index.html              # Main HTML file
│   ├── app.js                  # JavaScript application
│   ├── styles.css              # Styles
│   └── icons/                  # Cloud provider icons
├── docs/
│   └── aws-infrastructure-setup.md  # Infrastructure guide
├── deploy-backend.sh           # Backend deployment script
├── deploy-frontend.sh          # Frontend deployment script
├── .env.example                # Environment variables template
└── README.md                   # This file
```

## 🔧 Configuration

### Backend Environment Variables

- `AWS_REGION`: AWS region (e.g., `us-east-1`)
- `DYNAMODB_TABLE_NAME`: DynamoDB table name
- `BEDROCK_MODEL_ID`: Bedrock model ID (e.g., `anthropic.claude-3-sonnet-20240229-v1:0`)

### Frontend Configuration

The frontend automatically reads the API URL from a meta tag injected during deployment:

```html
<meta name="api-base-url" content="https://YOUR_APP_RUNNER_URL">
```

## 🐛 Troubleshooting

### Backend Issues

**DynamoDB Connection Error**:
- Verify IAM role has DynamoDB permissions
- Check table name matches environment variable
- Ensure table exists in the correct region

**Bedrock Access Denied**:
- Enable model access in Bedrock console
- Verify IAM role has `bedrock:InvokeModel` permission
- Check model ID is correct

**App Runner Deployment Fails**:
- Check CloudWatch Logs for error messages
- Verify ECR image exists and is accessible
- Ensure environment variables are set correctly

### Frontend Issues

**API Connection Error**:
- Verify App Runner service is running
- Check CORS settings in backend
- Ensure CloudFront is serving the correct files

**CloudFront Not Updating**:
- Wait for cache invalidation to complete (5-10 minutes)
- Try hard refresh (Ctrl+Shift+R)
- Check CloudFront distribution status

## 💰 Cost Estimation

Approximate monthly costs for low to moderate traffic:

- **DynamoDB**: $5-10 (on-demand pricing)
- **App Runner**: $20-50 (1 vCPU, 2GB RAM)
- **S3**: $1-5 (static files)
- **CloudFront**: $10-30 (depends on traffic)
- **Bedrock**: $10-50 (depends on usage)
- **ECR**: $1 (Docker images)

**Total**: ~$50-150/month

## 🔒 Security

- All data encrypted at rest (DynamoDB, S3)
- HTTPS enforced for all connections
- IAM roles with least privilege principle
- S3 bucket blocks public access (CloudFront OAC only)
- No hardcoded credentials in code

## 📄 License

This project is licensed under the MIT License.

## 🤝 Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

## 📧 Contact

For questions or support, please open an issue on GitHub.

---

**Note**: This application was migrated from GCP to AWS. For the original GCP version, see the `gcp-legacy` branch.
