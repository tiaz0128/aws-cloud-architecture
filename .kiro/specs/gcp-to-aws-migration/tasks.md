# Implementation Plan: GCP to AWS Migration

## Overview

이 구현 계획은 Cloud Architecture Diagram Generator를 GCP에서 AWS로 마이그레이션하는 작업을 단계별로 정의합니다. 각 작업은 기존 GCP 서비스를 동등한 AWS 서비스로 교체하며, 애플리케이션의 기능적 동작은 변경하지 않습니다.

**마이그레이션 범위:**
- Firestore → DynamoDB
- Vertex AI (Gemini) → Amazon Bedrock (Claude)
- Cloud Run → AWS App Runner
- Artifact Registry → Amazon ECR
- Cloud Build → AWS CodeBuild
- Cloud Storage → S3 + CloudFront
- gcloud/gsutil CLI → AWS CLI

## Tasks

- [x] 1. 백엔드 의존성 및 클라이언트 모듈 교체
  - [x] 1.1 pyproject.toml 의존성 업데이트
    - `google-cloud-firestore`, `google-cloud-aiplatform` 패키지 제거
    - `boto3`, `botocore` 패키지 추가
    - _Requirements: 1.1, 2.1, 7.1_

  - [x] 1.2 DynamoDB 클라이언트 모듈 구현
    - `backend/dynamodb_client.py` 파일 생성
    - `DynamoDBClient` 클래스 구현 (create_diagram, get_diagram, list_diagrams, update_diagram, delete_diagram 메서드)
    - 환경변수 `AWS_REGION`, `DYNAMODB_TABLE_NAME` 읽기
    - boto3 DynamoDB 클라이언트 초기화 및 에러 핸들링
    - _Requirements: 1.1, 1.2, 1.3, 1.4, 1.5, 1.6, 1.7, 1.8, 1.9_

  - [x] 1.3 Bedrock 클라이언트 모듈 구현
    - `backend/bedrock_client.py` 파일 생성
    - `BedrockClient` 클래스 구현 (generate_diagram_code 메서드)
    - 환경변수 `AWS_REGION`, `BEDROCK_MODEL_ID` 읽기
    - boto3 Bedrock Runtime 클라이언트 초기화
    - Claude 모델 호출 로직 구현 (기존 Vertex AI 프롬프트 유지)
    - Exponential backoff 재시도 로직 구현 (ThrottlingException 처리)
    - _Requirements: 2.1, 2.2, 2.3, 2.4, 2.5_

- [x] 2. FastAPI 백엔드 main.py 수정
  - [x] 2.1 GCP 관련 import 제거 및 AWS import 추가
    - `google.cloud.firestore`, `vertexai` import 제거
    - `boto3`, `botocore.exceptions` import 추가
    - `DynamoDBClient`, `BedrockClient` import 추가
    - _Requirements: 7.2, 7.3_

  - [x] 2.2 GCP 초기화 코드 제거 및 AWS 클라이언트 초기화
    - `get_project_id()` 함수 및 GCP 메타데이터 서버 호출 코드 제거
    - Firestore 및 Vertex AI 초기화 코드 제거
    - DynamoDB 및 Bedrock 클라이언트 초기화 코드 추가
    - 환경변수 `GOOGLE_CLOUD_PROJECT` 참조 제거, `AWS_REGION` 사용
    - _Requirements: 3.1, 7.3_

  - [x] 2.3 API 엔드포인트에서 DynamoDB 클라이언트 사용
    - `/generate-diagram` 엔드포인트: DynamoDB에 다이어그램 저장
    - `/diagrams/{diagram_id}` 엔드포인트: DynamoDB에서 다이어그램 조회
    - `/diagrams` 엔드포인트: DynamoDB에서 다이어그램 목록 조회
    - `/diagrams/{diagram_id}` PUT 엔드포인트: DynamoDB 다이어그램 업데이트
    - `/diagrams/{diagram_id}` DELETE 엔드포인트: DynamoDB 다이어그램 삭제
    - 404, 503 에러 핸들링 구현
    - _Requirements: 1.2, 1.3, 1.4, 1.5, 1.6, 1.7, 1.9_

  - [x] 2.4 API 엔드포인트에서 Bedrock 클라이언트 사용
    - `/generate-diagram` 엔드포인트: Bedrock Claude 모델 호출
    - 기존 Vertex AI 프롬프트 내용 유지
    - Bedrock API 호출 실패 시 503 에러 반환
    - _Requirements: 2.2, 2.4, 2.5_

  - [x] 2.5 /health 엔드포인트 수정
    - `vertex_ai` 항목을 `bedrock`으로 교체
    - DynamoDB 연결 상태 체크 (DescribeTable 호출)
    - Bedrock 가용성 체크 (ListFoundationModels 호출, 5분 캐싱)
    - `project_id` 필드 제거
    - _Requirements: 2.6_

- [x] 3. Checkpoint - 백엔드 코드 변경 검증
  - 로컬에서 코드 구문 오류 확인
  - 환경변수 설정 확인 (AWS_REGION, DYNAMODB_TABLE_NAME, BEDROCK_MODEL_ID)
  - 사용자에게 진행 상황 확인 요청

- [x] 4. Dockerfile 및 빌드 설정 수정
  - [x] 4.1 Dockerfile AWS 환경 호환성 확인
    - 기존 멀티스테이지 빌드 구조 유지
    - 포트 8080 노출 확인
    - 환경변수 설정 확인
    - _Requirements: 3.2_

  - [x] 4.2 cloudbuild.yaml 제거 및 buildspec.yml 생성
    - `backend/cloudbuild.yaml` 파일 삭제
    - `backend/buildspec.yml` 파일 생성
    - ECR 로그인, Docker 빌드, ECR 푸시, App Runner 업데이트 단계 정의
    - 환경변수 `ECR_REPOSITORY_URI`, `IMAGE_REPO_NAME`, `IMAGE_TAG`, `APP_RUNNER_SERVICE_ARN` 사용
    - _Requirements: 4.1, 4.2, 4.3, 4.4, 4.5_

  - [x] 4.3 .gcloudignore 파일 제거
    - `backend/.gcloudignore` 파일 삭제
    - `.dockerignore`에서 GCP 관련 항목 정리
    - _Requirements: 7.4, 7.5_

- [x] 5. 프론트엔드 코드 수정
  - [x] 5.1 app.js API URL 로직 수정
    - `getApiBaseUrl()` 함수에서 `storage.googleapis.com` 조건 분기 제거
    - App Runner 서비스 URL 반환 로직으로 교체
    - `CONFIG.PROD_API_URL`에서 `a.run.app` 도메인 하드코딩 제거
    - _Requirements: 5.2, 5.3, 7.6_

  - [x] 5.2 app.js 아이콘 URL 로직 수정
    - `getIconUrl()` 함수에서 `storage.googleapis.com` 조건 분기 제거
    - CloudFront URL 기반 아이콘 경로 반환 로직으로 교체
    - _Requirements: 5.1, 5.2_

- [x] 6. 배포 스크립트 AWS CLI 기반으로 교체
  - [x] 6.1 deploy-backend.sh AWS CLI 기반으로 재작성
    - gcloud CLI 명령 제거
    - `.env` 파일에서 AWS 환경변수 읽기 (`AWS_ACCOUNT_ID`, `AWS_REGION`, `ECR_REPOSITORY_NAME`, `APP_RUNNER_SERVICE_ARN`)
    - ECR 로그인 → Docker 빌드 → ECR 푸시 → App Runner 서비스 업데이트 순서 구현
    - AWS CLI 인증 확인 로직 추가
    - 배포 완료 후 App Runner 서비스 URL 출력
    - _Requirements: 6.1, 6.3, 6.4, 6.6, 6.7_

  - [x] 6.2 deploy-frontend.sh AWS CLI 기반으로 재작성
    - gsutil CLI 명령 제거
    - `.env` 파일에서 AWS 환경변수 읽기 (`S3_BUCKET_NAME`, `CLOUDFRONT_DISTRIBUTION_ID`)
    - App Runner URL을 `index.html` 메타 태그에 주입
    - S3에 프론트엔드 파일 업로드 (`aws s3 sync`)
    - CloudFront 캐시 무효화 (`aws cloudfront create-invalidation`)
    - AWS CLI 인증 확인 로직 추가
    - 배포 완료 후 CloudFront 도메인 URL 출력
    - _Requirements: 6.2, 6.3, 6.5, 6.6, 6.7_

  - [x] 6.3 .env.example 파일 생성
    - AWS 환경변수 템플릿 작성
    - `AWS_ACCOUNT_ID`, `AWS_REGION`, `ECR_REPOSITORY_NAME`, `ECR_REPOSITORY_URI`, `IMAGE_REPO_NAME`, `APP_RUNNER_SERVICE_ARN`, `S3_BUCKET_NAME`, `CLOUDFRONT_DISTRIBUTION_ID`, `CLOUDFRONT_DOMAIN`, `DYNAMODB_TABLE_NAME`, `BEDROCK_MODEL_ID` 포함
    - _Requirements: 6.3_

- [x] 7. Checkpoint - 코드 변경 완료 확인
  - 모든 GCP 의존성 제거 확인
  - AWS 클라이언트 코드 구현 완료 확인
  - 배포 스크립트 AWS CLI 기반 전환 확인
  - 사용자에게 AWS 인프라 설정 준비 상태 확인 요청

- [x] 8. AWS 인프라 설정 가이드 문서 작성
  - [x] 8.1 인프라 설정 가이드 작성
    - `docs/aws-infrastructure-setup.md` 파일 생성
    - DynamoDB 테이블 생성 방법 (테이블명, 파티션 키, GSI 설정)
    - ECR 리포지토리 생성 방법
    - S3 버킷 생성 및 설정 방법 (퍼블릭 액세스 차단)
    - CloudFront 배포 생성 및 OAC 설정 방법
    - IAM 역할 생성 방법 (App Runner, CodeBuild)
    - Bedrock 모델 액세스 활성화 방법
    - App Runner 서비스 생성 방법 (환경변수, IAM 역할 설정)
    - CodeBuild 프로젝트 생성 방법
    - _Requirements: 모든 요구사항의 인프라 전제조건_

- [x] 9. README.md 업데이트
  - [x] 9.1 README.md AWS 배포 가이드로 업데이트
    - GCP 관련 설명 제거
    - AWS 서비스 아키텍처 설명 추가
    - AWS 인프라 설정 가이드 링크 추가
    - 배포 스크립트 사용 방법 업데이트
    - 환경변수 설정 방법 업데이트
    - _Requirements: 7.x (문서화)_

- [x] 10. 최종 검증 및 배포 테스트
  - [x] 10.1 로컬 환경에서 통합 테스트
    - DynamoDB 로컬 또는 테스트 테이블 사용
    - Bedrock API 호출 테스트 (실제 AWS 계정 필요)
    - 모든 API 엔드포인트 동작 확인
    - _Requirements: 모든 요구사항_

  - [x] 10.2 AWS 스테이징 환경 배포
    - 백엔드 배포 스크립트 실행
    - 프론트엔드 배포 스크립트 실행
    - App Runner 서비스 헬스체크 확인
    - CloudFront 배포 확인
    - _Requirements: 3.x, 4.x, 5.x, 6.x_

  - [x] 10.3 기능 회귀 테스트
    - 다이어그램 생성 기능 테스트
    - 다이어그램 조회 기능 테스트
    - 다이어그램 목록 조회 기능 테스트
    - 다이어그램 수정 기능 테스트
    - 다이어그램 삭제 기능 테스트
    - 프론트엔드 UI 동작 확인
    - _Requirements: 1.x, 2.x, 5.x_

- [x] 11. 최종 Checkpoint - 프로덕션 배포 준비
  - 모든 테스트 통과 확인
  - AWS 인프라 설정 완료 확인
  - 배포 스크립트 정상 동작 확인
  - 사용자에게 프로덕션 배포 승인 요청

## Notes

- 이 마이그레이션은 Infrastructure as Code (IaC) 프로젝트이므로 property-based testing은 적용하지 않습니다
- 각 작업은 기존 GCP 서비스를 AWS 서비스로 1:1 교체하는 것을 목표로 합니다
- 애플리케이션의 기능적 동작(API 엔드포인트, 다이어그램 생성 로직, 프론트엔드 UI)은 변경하지 않습니다
- AWS 인프라는 사전에 설정되어 있어야 하며, 작업 8에서 설정 가이드를 제공합니다
- 배포 스크립트는 `.env` 파일에서 환경변수를 읽어 사용합니다
- Checkpoint 작업에서는 사용자에게 진행 상황을 확인하고 질문이 있는지 물어봅니다
