#!/bin/bash

# 프론트엔드만 배포하는 스크립트 (AWS S3 + CloudFront)
# HTML 파일 수정 후 빠르게 배포하고 싶을 때 사용

set -e  # 에러 발생 시 스크립트 중단

echo "🚀 프론트엔드만 배포 시작..."
echo "📂 현재 작업 디렉토리: $(pwd)"

# 프론트엔드 파일 확인
if [ ! -f "frontend/index.html" ]; then
    echo "❌ frontend/index.html 파일을 찾을 수 없습니다."
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
REQUIRED_VARS=("AWS_REGION" "S3_BUCKET_NAME" "CLOUDFRONT_DISTRIBUTION_ID" "APP_RUNNER_SERVICE_ARN")
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

echo "✅ AWS 리전: $AWS_REGION"
echo "✅ S3 버킷: $S3_BUCKET_NAME"
echo "✅ CloudFront 배포 ID: $CLOUDFRONT_DISTRIBUTION_ID"

# AWS CLI 인증 확인
echo "🔐 AWS CLI 인증 상태 확인..."
if ! aws sts get-caller-identity &>/dev/null; then
    echo "❌ AWS CLI 인증이 설정되지 않았습니다."
    echo "💡 다음 명령어로 AWS CLI를 설정하세요:"
    echo "   aws configure"
    exit 1
fi

AWS_IDENTITY=$(aws sts get-caller-identity --query 'Arn' --output text)
echo "✅ AWS 인증 확인: $AWS_IDENTITY"

# App Runner 서비스 URL 가져오기
echo "🔍 백엔드 서비스 URL 확인 중..."
BACKEND_URL=$(aws apprunner describe-service \
    --service-arn $APP_RUNNER_SERVICE_ARN \
    --region $AWS_REGION \
    --query 'Service.ServiceUrl' \
    --output text 2>/dev/null || echo "")

if [ -z "$BACKEND_URL" ]; then
    echo "⚠️  백엔드 서비스를 찾을 수 없습니다. API URL 설정을 건너뜁니다."
    BACKEND_URL=""
else
    BACKEND_URL="https://$BACKEND_URL"
    echo "🌐 백엔드 서비스 URL: $BACKEND_URL"
fi


# 임시 디렉토리 생성
TEMP_DIR=$(mktemp -d)
echo "📁 임시 빌드 디렉토리: $TEMP_DIR"

# 프론트엔드 파일 복사
echo "📋 프론트엔드 파일 복사 중..."
cp -r frontend/* $TEMP_DIR/ 2>/dev/null || true

# 복사된 파일 목록 표시
echo "✅ 복사된 파일 목록:"
find $TEMP_DIR -type f | sed "s|$TEMP_DIR/|   • |g" | sort

# 메타 태그에 백엔드 URL 설정
if [ -n "$BACKEND_URL" ]; then
    echo "🔧 API URL 자동 설정 중..."
    if [ -f "$TEMP_DIR/index.html" ]; then
        sed -i.bak "s|<meta name=\"api-base-url\" content=\"[^\"]*\">|<meta name=\"api-base-url\" content=\"$BACKEND_URL\">|g" $TEMP_DIR/index.html
        rm -f $TEMP_DIR/index.html.bak
        echo "✅ index.html에 API URL 설정 완료"
    fi
fi

# 타임스탬프 추가 (브라우저 캐시 무효화용)
TIMESTAMP=$(date +%s)
echo "🕐 배포 타임스탬프: $TIMESTAMP"

# S3에 프론트엔드 파일 업로드
echo "📤 S3에 프론트엔드 파일 업로드 중..."

# HTML, CSS, JS 파일은 no-cache로 업로드
aws s3 sync $TEMP_DIR/ s3://$S3_BUCKET_NAME/ \
    --delete \
    --cache-control "no-cache" \
    --exclude "icons/*"

if [ $? -ne 0 ]; then
    echo "❌ S3 업로드 실패"
    rm -rf $TEMP_DIR
    exit 1
fi

echo "✅ 메인 파일 업로드 완료"

# 아이콘 파일은 더 긴 캐시로 업로드
if [ -d "$TEMP_DIR/icons" ]; then
    echo "🎨 아이콘 파일 업로드 중..."
    aws s3 sync $TEMP_DIR/icons/ s3://$S3_BUCKET_NAME/icons/ \
        --cache-control "max-age=3600"
    
    if [ $? -ne 0 ]; then
        echo "⚠️  아이콘 파일 업로드 실패"
    else
        echo "✅ 아이콘 파일 업로드 완료"
    fi
fi

# 임시 디렉토리 정리
rm -rf $TEMP_DIR

# CloudFront 캐시 무효화
echo "🔄 CloudFront 캐시 무효화 중..."
INVALIDATION_ID=$(aws cloudfront create-invalidation \
    --distribution-id $CLOUDFRONT_DISTRIBUTION_ID \
    --paths "/*" \
    --query 'Invalidation.Id' \
    --output text)

if [ $? -ne 0 ]; then
    echo "⚠️  CloudFront 캐시 무효화 실패"
else
    echo "✅ CloudFront 캐시 무효화 시작됨 (ID: $INVALIDATION_ID)"
fi

# CloudFront 도메인 가져오기
CLOUDFRONT_DOMAIN=$(aws cloudfront get-distribution \
    --id $CLOUDFRONT_DISTRIBUTION_ID \
    --query 'Distribution.DomainName' \
    --output text 2>/dev/null || echo "")

echo ""
echo "🎉 프론트엔드 배포 완료!"
echo ""
echo "=== 📋 배포 정보 ==="
echo "🌍 프론트엔드 웹사이트:"
if [ -n "$CLOUDFRONT_DOMAIN" ]; then
    echo "   • CloudFront URL: https://$CLOUDFRONT_DOMAIN"
fi
echo "   • S3 버킷: s3://$S3_BUCKET_NAME"
echo ""
echo "🔗 연결된 백엔드 API: $BACKEND_URL"
echo "🕐 배포 타임스탬프: $TIMESTAMP"
echo "🔄 캐시 무효화 ID: $INVALIDATION_ID"
echo ""
echo "💡 브라우저에서 테스트 방법:"
echo "   1. 시크릿/프라이빗 모드로 열기"
echo "   2. 일반 모드에서 Ctrl+Shift+R (하드 리프레시)"
echo "   3. 개발자 도구(F12) > Network > 'Disable cache' 체크"
echo ""
echo "🔍 배포 상태 확인:"
echo "   aws s3 ls s3://$S3_BUCKET_NAME/"
echo "   aws cloudfront get-invalidation --distribution-id $CLOUDFRONT_DISTRIBUTION_ID --id $INVALIDATION_ID"
echo ""