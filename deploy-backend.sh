#!/bin/bash

# 백엔드만 배포하는 스크립트 (AWS App Runner)
# API 수정 후 빠르게 백엔드만 다시 배포하고 싶을 때 사용

set -e  # 에러 발생 시 스크립트 중단

echo "🚀 백엔드만 배포 시작..."
echo "📂 현재 작업 디렉토리: $(pwd)"

# 백엔드 디렉토리 확인
if [ ! -d "backend" ]; then
    echo "❌ backend 디렉토리를 찾을 수 없습니다."
    echo "📍 올바른 실행 위치: 프로젝트 최상단"
    exit 1
fi

# 백엔드 필수 파일 확인
if [ ! -f "backend/Dockerfile" ]; then
    echo "❌ backend/Dockerfile 파일을 찾을 수 없습니다."
    exit 1
fi

if [ ! -f "backend/main.py" ]; then
    echo "❌ backend/main.py 파일을 찾을 수 없습니다."
    exit 1
fi

# .env 파일에서 환경변수 로드
if [ -f ".env" ]; then
    echo "📋 .env 파일에서 환경변수를 로드합니다..."
    export $(grep -v '^#' .env | grep -v '^$' | xargs)
    echo "✅ .env 파일 로드 완료"
else
    echo "⚠️  .env 파일을 찾을 수 없습니다."
fi

# 필수 환경변수 확인
REQUIRED_VARS=("AWS_ACCOUNT_ID" "AWS_REGION" "ECR_REPOSITORY_NAME" "APP_RUNNER_SERVICE_ARN")
MISSING_VARS=()

for var in "${REQUIRED_VARS[@]}"; do
    if [ -z "${!var}" ]; then
        MISSING_VARS+=("$var")
    fi
done

if [ ${#MISSING_VARS[@]} -ne 0 ]; then
    echo "❌ 다음 환경변수가 설정되지 않았습니다:"
    for var in "${MISSING_VARS[@]}"; do
        echo "   • $var"
    done
    echo ""
    echo "📝 .env 파일을 생성하거나 환경변수를 설정해주세요."
    echo "💡 .env.example 파일을 참고하세요."
    exit 1
fi

# ECR_REPOSITORY_URI 구성
ECR_REPOSITORY_URI="${AWS_ACCOUNT_ID}.dkr.ecr.${AWS_REGION}.amazonaws.com/${ECR_REPOSITORY_NAME}"

echo "✅ AWS 계정 ID: $AWS_ACCOUNT_ID"
echo "✅ AWS 리전: $AWS_REGION"
echo "✅ ECR 리포지토리: $ECR_REPOSITORY_URI"

# AWS CLI 인증 확인
echo "🔐 AWS CLI 인증 상태 확인..."
if ! aws sts get-caller-identity &>/dev/null; then
    echo "❌ AWS CLI 인증이 설정되지 않았습니다."
    echo "💡 다음 명령어로 AWS CLI를 설정하세요:"
    echo "   aws configure"
    echo "   또는 AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY 환경변수를 설정하세요."
    exit 1
fi

AWS_IDENTITY=$(aws sts get-caller-identity --query 'Arn' --output text)
echo "✅ AWS 인증 확인: $AWS_IDENTITY"

# ECR 로그인
echo "🔐 ECR 로그인 중..."
aws ecr get-login-password --region $AWS_REGION | \
    docker login --username AWS --password-stdin $ECR_REPOSITORY_URI

if [ $? -ne 0 ]; then
    echo "❌ ECR 로그인 실패"
    exit 1
fi

echo "✅ ECR 로그인 완료"

# Docker 이미지 빌드
echo "🏗️  Docker 이미지 빌드 중..."
cd backend

echo "📋 배포할 파일 확인:"
echo "   • main.py: $(ls -lh main.py 2>/dev/null | awk '{print $5}' || echo '없음')"
echo "   • Dockerfile: $(ls -lh Dockerfile 2>/dev/null | awk '{print $5}' || echo '없음')"
echo "   • pyproject.toml: $(ls -lh pyproject.toml 2>/dev/null | awk '{print $5}' || echo '없음')"

IMAGE_TAG="latest"
docker build -t ${ECR_REPOSITORY_NAME}:${IMAGE_TAG} .

if [ $? -ne 0 ]; then
    echo "❌ Docker 이미지 빌드 실패"
    cd ..
    exit 1
fi

echo "✅ Docker 이미지 빌드 완료"

# Docker 이미지 태그 지정
echo "🏷️  Docker 이미지 태그 지정..."
docker tag ${ECR_REPOSITORY_NAME}:${IMAGE_TAG} ${ECR_REPOSITORY_URI}:${IMAGE_TAG}

# ECR에 이미지 푸시
echo "📤 ECR에 이미지 푸시 중..."
docker push ${ECR_REPOSITORY_URI}:${IMAGE_TAG}

if [ $? -ne 0 ]; then
    echo "❌ ECR 이미지 푸시 실패"
    cd ..
    exit 1
fi

echo "✅ ECR 이미지 푸시 완료"

# 프로젝트 루트로 돌아가기
cd ..

# App Runner 서비스 업데이트
echo "🚀 App Runner 서비스 업데이트 중..."
aws apprunner start-deployment \
    --service-arn $APP_RUNNER_SERVICE_ARN \
    --region $AWS_REGION

if [ $? -ne 0 ]; then
    echo "❌ App Runner 서비스 업데이트 실패"
    exit 1
fi

echo "✅ App Runner 배포 시작됨"

# 배포 상태 확인
echo "⏳ 배포 상태 확인 중..."
sleep 5

SERVICE_STATUS=$(aws apprunner describe-service \
    --service-arn $APP_RUNNER_SERVICE_ARN \
    --region $AWS_REGION \
    --query 'Service.Status' \
    --output text)

echo "📊 서비스 상태: $SERVICE_STATUS"

# 서비스 URL 가져오기
BACKEND_URL=$(aws apprunner describe-service \
    --service-arn $APP_RUNNER_SERVICE_ARN \
    --region $AWS_REGION \
    --query 'Service.ServiceUrl' \
    --output text)

if [ -z "$BACKEND_URL" ]; then
    echo "⚠️  서비스 URL을 가져올 수 없습니다."
else
    echo "🌐 백엔드 서비스 URL: https://$BACKEND_URL"
fi

echo ""
echo "🎉 백엔드 배포 완료!"
echo ""
echo "=== 📋 배포 정보 ==="
echo "🏗️  서비스 ARN: $APP_RUNNER_SERVICE_ARN"
echo "🌍 리전: $AWS_REGION"
echo "🌐 API 엔드포인트: https://$BACKEND_URL"
echo "📦 ECR 이미지: $ECR_REPOSITORY_URI:$IMAGE_TAG"
echo ""
echo "✨ API 테스트 방법:"
echo "   curl https://$BACKEND_URL/health"
echo "   curl https://$BACKEND_URL/api/docs (API 문서)"
echo ""
echo "💡 배포 상태 확인:"
echo "   aws apprunner describe-service --service-arn $APP_RUNNER_SERVICE_ARN --region $AWS_REGION"
echo ""
