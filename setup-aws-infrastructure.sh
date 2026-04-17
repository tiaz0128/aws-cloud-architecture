#!/bin/bash

# AWS 인프라 자동 설정 스크립트
# Cloud Architecture Diagram Generator

set -e  # 에러 발생 시 스크립트 중단

echo "🚀 AWS 인프라 자동 설정 시작..."
echo ""

# .env 파일에서 환경변수 로드
if [ -f ".env" ]; then
    echo "📋 .env 파일에서 환경변수를 로드합니다..."
    export $(grep -v '^#' .env | grep -v '^$' | xargs)
    echo "✅ .env 파일 로드 완료"
else
    echo "❌ .env 파일을 찾을 수 없습니다."
    exit 1
fi

# AWS CLI 인증 확인
echo ""
echo "🔐 AWS CLI 인증 상태 확인..."
if ! aws sts get-caller-identity &>/dev/null; then
    echo "❌ AWS CLI 인증이 설정되지 않았습니다."
    exit 1
fi

AWS_ACCOUNT_ID=$(aws sts get-caller-identity --query 'Account' --output text)
echo "✅ AWS 계정 ID: $AWS_ACCOUNT_ID"
echo "✅ AWS 리전: $AWS_REGION"

# 환경변수 업데이트
sed -i.bak "s/AWS_ACCOUNT_ID=.*/AWS_ACCOUNT_ID=$AWS_ACCOUNT_ID/" .env
rm -f .env.bak

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "📦 Step 1/6: DynamoDB 테이블 생성"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

if aws dynamodb describe-table --table-name $DYNAMODB_TABLE_NAME --region $AWS_REGION &>/dev/null; then
    echo "ℹ️  DynamoDB 테이블이 이미 존재합니다: $DYNAMODB_TABLE_NAME"
else
    echo "🔨 DynamoDB 테이블 생성 중..."
    aws dynamodb create-table \
        --table-name $DYNAMODB_TABLE_NAME \
        --attribute-definitions \
            AttributeName=diagram_id,AttributeType=S \
            AttributeName=created_at,AttributeType=S \
            AttributeName=cloud_provider,AttributeType=S \
        --key-schema \
            AttributeName=diagram_id,KeyType=HASH \
        --global-secondary-indexes \
            "[{\"IndexName\":\"created_at-index\",\"KeySchema\":[{\"AttributeName\":\"cloud_provider\",\"KeyType\":\"HASH\"},{\"AttributeName\":\"created_at\",\"KeyType\":\"RANGE\"}],\"Projection\":{\"ProjectionType\":\"ALL\"}}]" \
        --billing-mode PAY_PER_REQUEST \
        --region $AWS_REGION \
        --output json > /dev/null
    
    echo "⏳ 테이블 생성 대기 중..."
    aws dynamodb wait table-exists --table-name $DYNAMODB_TABLE_NAME --region $AWS_REGION
    echo "✅ DynamoDB 테이블 생성 완료: $DYNAMODB_TABLE_NAME"
fi

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "📦 Step 2/6: ECR 리포지토리 생성"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

if aws ecr describe-repositories --repository-names $ECR_REPOSITORY_NAME --region $AWS_REGION &>/dev/null; then
    echo "ℹ️  ECR 리포지토리가 이미 존재합니다: $ECR_REPOSITORY_NAME"
else
    echo "🔨 ECR 리포지토리 생성 중..."
    aws ecr create-repository \
        --repository-name $ECR_REPOSITORY_NAME \
        --region $AWS_REGION \
        --output json > /dev/null
    echo "✅ ECR 리포지토리 생성 완료: $ECR_REPOSITORY_NAME"
fi

# ECR URI 가져오기
ECR_URI=$(aws ecr describe-repositories \
    --repository-names $ECR_REPOSITORY_NAME \
    --region $AWS_REGION \
    --query 'repositories[0].repositoryUri' \
    --output text)

echo "📝 ECR URI: $ECR_URI"

# .env 파일 업데이트
sed -i.bak "s|ECR_REPOSITORY_URI=.*|ECR_REPOSITORY_URI=$ECR_URI|" .env
rm -f .env.bak

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "📦 Step 3/6: S3 버킷 생성"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

if aws s3 ls s3://$S3_BUCKET_NAME &>/dev/null; then
    echo "ℹ️  S3 버킷이 이미 존재합니다: $S3_BUCKET_NAME"
else
    echo "🔨 S3 버킷 생성 중..."
    
    # 리전에 따라 버킷 생성 명령어 다르게 처리
    if [ "$AWS_REGION" = "us-east-1" ]; then
        aws s3 mb s3://$S3_BUCKET_NAME
    else
        aws s3 mb s3://$S3_BUCKET_NAME --region $AWS_REGION
    fi
    
    echo "✅ S3 버킷 생성 완료: $S3_BUCKET_NAME"
fi

# 퍼블릭 액세스 차단
echo "🔒 S3 버킷 퍼블릭 액세스 차단 설정 중..."
aws s3api put-public-access-block \
    --bucket $S3_BUCKET_NAME \
    --public-access-block-configuration \
        "BlockPublicAcls=true,IgnorePublicAcls=true,BlockPublicPolicy=true,RestrictPublicBuckets=true" \
    --region $AWS_REGION

echo "✅ S3 버킷 보안 설정 완료"

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "📦 Step 4/6: IAM 역할 생성"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

# App Runner IAM 역할
APPRUNNER_ROLE_NAME="AppRunnerDiagramGeneratorRole"

if aws iam get-role --role-name $APPRUNNER_ROLE_NAME &>/dev/null; then
    echo "ℹ️  App Runner IAM 역할이 이미 존재합니다: $APPRUNNER_ROLE_NAME"
else
    echo "🔨 App Runner IAM 역할 생성 중..."
    
    # Trust policy 생성
    cat > /tmp/apprunner-trust-policy.json <<EOF
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
EOF

    aws iam create-role \
        --role-name $APPRUNNER_ROLE_NAME \
        --assume-role-policy-document file:///tmp/apprunner-trust-policy.json \
        --output json > /dev/null

    # Permissions policy 생성
    cat > /tmp/apprunner-permissions.json <<EOF
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
                "arn:aws:dynamodb:*:*:table/$DYNAMODB_TABLE_NAME",
                "arn:aws:dynamodb:*:*:table/$DYNAMODB_TABLE_NAME/index/*"
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
EOF

    aws iam put-role-policy \
        --role-name $APPRUNNER_ROLE_NAME \
        --policy-name AppRunnerPermissions \
        --policy-document file:///tmp/apprunner-permissions.json

    echo "✅ App Runner IAM 역할 생성 완료"
    
    # 역할 전파 대기
    echo "⏳ IAM 역할 전파 대기 중 (10초)..."
    sleep 10
fi

APPRUNNER_ROLE_ARN=$(aws iam get-role --role-name $APPRUNNER_ROLE_NAME --query 'Role.Arn' --output text)
echo "📝 App Runner Role ARN: $APPRUNNER_ROLE_ARN"

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "📦 Step 5/6: 초기 Docker 이미지 빌드 및 푸시"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

echo "🔐 ECR 로그인 중..."
aws ecr get-login-password --region $AWS_REGION | \
    docker login --username AWS --password-stdin $ECR_URI

echo "🏗️  Docker 이미지 빌드 중..."
cd backend
docker build -t $ECR_REPOSITORY_NAME:latest .

echo "🏷️  Docker 이미지 태그 지정..."
docker tag $ECR_REPOSITORY_NAME:latest $ECR_URI:latest

echo "📤 ECR에 이미지 푸시 중..."
docker push $ECR_URI:latest

cd ..
echo "✅ Docker 이미지 푸시 완료"

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "📦 Step 6/6: App Runner 서비스 생성"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

SERVICE_NAME="cloud-diagram-generator"

# 서비스가 이미 존재하는지 확인
if aws apprunner list-services --region $AWS_REGION --query "ServiceSummaryList[?ServiceName=='$SERVICE_NAME'].ServiceArn" --output text | grep -q "arn:"; then
    echo "ℹ️  App Runner 서비스가 이미 존재합니다"
    EXISTING_ARN=$(aws apprunner list-services --region $AWS_REGION --query "ServiceSummaryList[?ServiceName=='$SERVICE_NAME'].ServiceArn" --output text)
    echo "📝 기존 서비스 ARN: $EXISTING_ARN"
    
    # .env 파일 업데이트
    sed -i.bak "s|APP_RUNNER_SERVICE_ARN=.*|APP_RUNNER_SERVICE_ARN=$EXISTING_ARN|" .env
    rm -f .env.bak
else
    echo "🔨 App Runner ECR 액세스 역할 생성 중..."
    
    APPRUNNER_ECR_ROLE_NAME="AppRunnerECRAccessRole"
    
    if aws iam get-role --role-name $APPRUNNER_ECR_ROLE_NAME &>/dev/null; then
        echo "ℹ️  ECR 액세스 역할이 이미 존재합니다"
    else
        cat > /tmp/apprunner-ecr-trust.json <<EOF
{
    "Version": "2012-10-17",
    "Statement": [
        {
            "Effect": "Allow",
            "Principal": {
                "Service": "build.apprunner.amazonaws.com"
            },
            "Action": "sts:AssumeRole"
        }
    ]
}
EOF
        aws iam create-role \
            --role-name $APPRUNNER_ECR_ROLE_NAME \
            --assume-role-policy-document file:///tmp/apprunner-ecr-trust.json \
            --output json > /dev/null

        aws iam attach-role-policy \
            --role-name $APPRUNNER_ECR_ROLE_NAME \
            --policy-arn arn:aws:iam::aws:policy/service-role/AWSAppRunnerServicePolicyForECRAccess

        echo "✅ ECR 액세스 역할 생성 완료"
        echo "⏳ IAM 역할 전파 대기 중 (10초)..."
        sleep 10
    fi

    APPRUNNER_ECR_ROLE_ARN=$(aws iam get-role --role-name $APPRUNNER_ECR_ROLE_NAME --query 'Role.Arn' --output text)
    echo "📝 ECR Access Role ARN: $APPRUNNER_ECR_ROLE_ARN"

    echo "🔨 App Runner 서비스 생성 중..."
    
    # 서비스 설정 파일 생성
    cat > /tmp/apprunner-service.json <<EOF
{
    "ServiceName": "$SERVICE_NAME",
    "SourceConfiguration": {
        "AuthenticationConfiguration": {
            "AccessRoleArn": "$APPRUNNER_ECR_ROLE_ARN"
        },
        "ImageRepository": {
            "ImageIdentifier": "$ECR_URI:latest",
            "ImageRepositoryType": "ECR",
            "ImageConfiguration": {
                "Port": "8080",
                "RuntimeEnvironmentVariables": {
                    "AWS_REGION": "$AWS_REGION",
                    "DYNAMODB_TABLE_NAME": "$DYNAMODB_TABLE_NAME",
                    "BEDROCK_MODEL_ID": "$BEDROCK_MODEL_ID"
                }
            }
        },
        "AutoDeploymentsEnabled": false
    },
    "InstanceConfiguration": {
        "Cpu": "1 vCPU",
        "Memory": "2 GB",
        "InstanceRoleArn": "$APPRUNNER_ROLE_ARN"
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
EOF

    SERVICE_ARN=$(aws apprunner create-service \
        --cli-input-json file:///tmp/apprunner-service.json \
        --region $AWS_REGION \
        --query 'Service.ServiceArn' \
        --output text)
    
    echo "✅ App Runner 서비스 생성 시작됨"
    echo "📝 서비스 ARN: $SERVICE_ARN"
    
    # .env 파일 업데이트
    sed -i.bak "s|APP_RUNNER_SERVICE_ARN=.*|APP_RUNNER_SERVICE_ARN=$SERVICE_ARN|" .env
    rm -f .env.bak
    
    echo "⏳ 서비스 배포 대기 중 (약 3-5분 소요)..."
    
    # 서비스 상태 확인
    while true; do
        STATUS=$(aws apprunner describe-service \
            --service-arn $SERVICE_ARN \
            --region $AWS_REGION \
            --query 'Service.Status' \
            --output text)
        
        echo "   현재 상태: $STATUS"
        
        if [ "$STATUS" = "RUNNING" ]; then
            break
        elif [ "$STATUS" = "CREATE_FAILED" ] || [ "$STATUS" = "OPERATION_FAILED" ]; then
            echo "❌ 서비스 생성 실패"
            exit 1
        fi
        
        sleep 15
    done
    
    echo "✅ App Runner 서비스 실행 중"
fi

# 서비스 URL 가져오기
SERVICE_URL=$(aws apprunner describe-service \
    --service-arn $(grep APP_RUNNER_SERVICE_ARN .env | cut -d'=' -f2) \
    --region $AWS_REGION \
    --query 'Service.ServiceUrl' \
    --output text)

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "🎉 AWS 인프라 설정 완료!"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
echo "✅ 생성된 리소스:"
echo "   • DynamoDB 테이블: $DYNAMODB_TABLE_NAME"
echo "   • ECR 리포지토리: $ECR_URI"
echo "   • S3 버킷: $S3_BUCKET_NAME"
echo "   • IAM 역할: $APPRUNNER_ROLE_NAME"
echo "   • App Runner 서비스: $SERVICE_NAME"
echo ""
echo "🌐 백엔드 API URL: https://$SERVICE_URL"
echo ""
echo "📝 다음 단계:"
echo "   1. 백엔드 API 테스트:"
echo "      curl https://$SERVICE_URL/health"
echo ""
echo "   2. CloudFront 배포 설정 (수동):"
echo "      - AWS Console에서 CloudFront 배포 생성"
echo "      - S3 버킷을 오리진으로 설정"
echo "      - OAC(Origin Access Control) 구성"
echo "      - .env 파일에 CLOUDFRONT_DISTRIBUTION_ID와 CLOUDFRONT_DOMAIN 업데이트"
echo ""
echo "   3. 프론트엔드 배포:"
echo "      ./deploy-frontend.sh"
echo ""
echo "💡 CloudFront 설정 가이드: docs/aws-infrastructure-setup.md (Step 4 참조)"
echo ""

# 임시 파일 정리
rm -f /tmp/apprunner-*.json

echo "✨ 설정 완료!"
