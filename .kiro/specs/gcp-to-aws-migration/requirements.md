# Requirements Document

## Introduction

Cloud Architecture Diagram Generator는 현재 GCP 기반으로 구축된 웹 애플리케이션입니다. 이 프로젝트는 AI를 활용해 클라우드 아키텍처 다이어그램을 자동 생성하며, FastAPI 백엔드와 순수 HTML/JS 프론트엔드로 구성되어 있습니다.

본 마이그레이션의 목표는 GCP 종속 서비스들을 동등한 AWS 서비스로 교체하는 것입니다:
- **데이터베이스**: Firestore → DynamoDB
- **AI 모델**: Vertex AI (Gemini 2.5 Flash) → Amazon Bedrock (Claude)
- **백엔드 실행 환경**: Cloud Run → AWS App Runner
- **프론트엔드 호스팅**: Cloud Storage → S3 + CloudFront
- **CI/CD**: Cloud Build + Artifact Registry → AWS CodeBuild + ECR
- **배포 스크립트**: gcloud/gsutil CLI → AWS CLI

애플리케이션의 기능적 동작(API 엔드포인트, 다이어그램 생성 로직, 프론트엔드 UI)은 변경하지 않습니다.

---

## Glossary

- **Backend**: FastAPI 기반 백엔드 서버 (`backend/main.py`)
- **Frontend**: 순수 HTML/CSS/JS 기반 프론트엔드 (`frontend/`)
- **DynamoDB_Client**: AWS DynamoDB와 통신하는 boto3 기반 클라이언트 모듈
- **Bedrock_Client**: Amazon Bedrock API를 호출하는 boto3 기반 클라이언트 모듈
- **App_Runner**: AWS App Runner 서비스 (백엔드 컨테이너 실행 환경)
- **ECR**: Amazon Elastic Container Registry (Docker 이미지 저장소)
- **CodeBuild**: AWS CodeBuild (CI/CD 빌드 서비스)
- **S3_Bucket**: 프론트엔드 정적 파일을 저장하는 Amazon S3 버킷
- **CloudFront**: 프론트엔드 CDN 배포를 담당하는 Amazon CloudFront 배포
- **Deploy_Script**: AWS CLI 기반 배포 자동화 셸 스크립트
- **Diagram**: Mermaid architecture-beta 형식의 클라우드 아키텍처 다이어그램 데이터
- **IAM_Role**: AWS 서비스 간 권한을 부여하는 IAM 역할

---

## Requirements

### Requirement 1: DynamoDB로 데이터베이스 교체

**User Story:** As a 개발자, I want Firestore 의존성을 DynamoDB로 교체하고 싶다, so that GCP 없이 AWS 환경에서 다이어그램 데이터를 저장하고 조회할 수 있다.

#### Acceptance Criteria

1. THE Backend SHALL `google-cloud-firestore` 패키지 의존성을 제거하고 `boto3` 패키지로 교체한다.
2. WHEN 다이어그램 생성 요청이 수신되면, THE DynamoDB_Client SHALL 생성된 다이어그램 데이터를 DynamoDB 테이블에 저장한다.
3. WHEN 다이어그램 조회 요청이 수신되면, THE DynamoDB_Client SHALL DynamoDB 테이블에서 해당 `diagram_id`로 항목을 조회한다.
4. WHEN 존재하지 않는 `diagram_id`로 조회 요청이 수신되면, THE Backend SHALL HTTP 404 상태 코드를 반환한다.
5. WHEN 다이어그램 목록 조회 요청이 수신되면, THE DynamoDB_Client SHALL DynamoDB 테이블에서 최신순으로 정렬된 다이어그램 목록을 반환한다.
6. WHEN 다이어그램 수정 요청이 수신되면, THE DynamoDB_Client SHALL DynamoDB 테이블의 해당 항목을 업데이트한다.
7. WHEN 다이어그램 삭제 요청이 수신되면, THE DynamoDB_Client SHALL DynamoDB 테이블에서 해당 항목을 삭제한다.
8. THE DynamoDB_Client SHALL `AWS_REGION`, `DYNAMODB_TABLE_NAME` 환경변수를 통해 연결 설정을 읽는다.
9. IF DynamoDB 연결이 실패하면, THE Backend SHALL 오류를 로그에 기록하고 HTTP 503 상태 코드를 반환한다.

---

### Requirement 2: Amazon Bedrock으로 AI 모델 교체

**User Story:** As a 개발자, I want Vertex AI (Gemini) 의존성을 Amazon Bedrock (Claude)으로 교체하고 싶다, so that AWS 환경에서 AI 기반 다이어그램 생성 기능을 유지할 수 있다.

#### Acceptance Criteria

1. THE Backend SHALL `google-cloud-aiplatform` 패키지 의존성을 제거하고 `boto3`의 Bedrock Runtime 클라이언트로 교체한다.
2. WHEN 다이어그램 생성 요청이 수신되면, THE Bedrock_Client SHALL Amazon Bedrock의 Claude 모델을 호출하여 Mermaid 코드를 생성한다.
3. THE Bedrock_Client SHALL `AWS_REGION`, `BEDROCK_MODEL_ID` 환경변수를 통해 모델 설정을 읽는다.
4. THE Bedrock_Client SHALL 기존 Vertex AI 프롬프트 내용을 동일하게 유지하여 Bedrock API 형식으로 전달한다.
5. WHEN Bedrock API 호출이 실패하면, THE Backend SHALL 오류를 로그에 기록하고 HTTP 503 상태 코드를 반환한다.
6. THE Backend SHALL `/health` 엔드포인트 응답에서 `vertex_ai` 항목을 `bedrock`으로 교체하여 Bedrock 연결 상태를 반환한다.

---

### Requirement 3: AWS App Runner로 백엔드 실행 환경 교체

**User Story:** As a 개발자, I want Cloud Run 대신 AWS App Runner에서 백엔드를 실행하고 싶다, so that AWS 인프라 위에서 컨테이너 기반 백엔드를 운영할 수 있다.

#### Acceptance Criteria

1. THE Backend SHALL `GOOGLE_CLOUD_PROJECT` 환경변수 참조를 제거하고 `AWS_REGION` 환경변수를 사용한다.
2. THE Dockerfile SHALL 기존 멀티스테이지 빌드 구조를 유지하며 AWS 환경에서 정상 동작한다.
3. THE App_Runner SHALL 포트 8080에서 백엔드 서비스를 실행한다.
4. THE App_Runner SHALL `AWS_REGION`, `DYNAMODB_TABLE_NAME`, `BEDROCK_MODEL_ID` 환경변수를 주입받아 실행된다.
5. THE App_Runner SHALL IAM_Role을 통해 DynamoDB 및 Bedrock 서비스에 접근 권한을 부여받는다.
6. WHEN App Runner 서비스가 배포되면, THE App_Runner SHALL `/health` 엔드포인트로 헬스체크를 수행한다.

---

### Requirement 4: AWS CodeBuild + ECR로 CI/CD 파이프라인 교체

**User Story:** As a 개발자, I want Cloud Build와 Artifact Registry를 AWS CodeBuild와 ECR로 교체하고 싶다, so that AWS 환경에서 Docker 이미지를 빌드하고 배포할 수 있다.

#### Acceptance Criteria

1. THE Backend SHALL `cloudbuild.yaml` 파일을 제거하고 `buildspec.yml` 파일로 교체한다.
2. THE CodeBuild SHALL `buildspec.yml`에 정의된 단계에 따라 Docker 이미지를 빌드하고 ECR에 푸시한다.
3. THE CodeBuild SHALL ECR 리포지토리 URI를 환경변수 `ECR_REPOSITORY_URI`로 참조한다.
4. THE CodeBuild SHALL 빌드 완료 후 App Runner 서비스를 최신 이미지로 업데이트한다.
5. THE ECR SHALL 빌드된 Docker 이미지를 `latest` 태그와 커밋 해시 태그로 저장한다.

---

### Requirement 5: S3 + CloudFront로 프론트엔드 호스팅 교체

**User Story:** As a 개발자, I want Cloud Storage 정적 호스팅을 S3 + CloudFront로 교체하고 싶다, so that AWS 환경에서 프론트엔드를 글로벌 CDN으로 서빙할 수 있다.

#### Acceptance Criteria

1. THE Frontend SHALL `storage.googleapis.com` URL 참조를 제거하고 CloudFront 도메인 기반 URL을 사용한다.
2. THE Frontend SHALL `getIconUrl()` 함수에서 `storage.googleapis.com` 조건 분기를 제거하고 CloudFront URL 기반으로 아이콘 경로를 반환한다.
3. THE Frontend SHALL `getApiBaseUrl()` 함수에서 `storage.googleapis.com` 조건 분기를 제거하고 App Runner 서비스 URL을 반환한다.
4. THE S3_Bucket SHALL 퍼블릭 액세스를 차단하고 CloudFront OAC(Origin Access Control)를 통해서만 접근을 허용한다.
5. THE CloudFront SHALL S3_Bucket을 오리진으로 설정하고 `index.html`을 기본 루트 객체로 반환한다.
6. THE CloudFront SHALL HTML, CSS, JS 파일에 대해 `Cache-Control: no-cache` 헤더를 적용한다.

---

### Requirement 6: AWS CLI 기반 배포 스크립트 교체

**User Story:** As a 개발자, I want gcloud/gsutil 기반 배포 스크립트를 AWS CLI 기반으로 교체하고 싶다, so that AWS 환경에서 동일한 배포 자동화 워크플로우를 사용할 수 있다.

#### Acceptance Criteria

1. THE Deploy_Script SHALL `deploy-backend.sh`에서 `gcloud` CLI 명령을 제거하고 `aws` CLI 명령으로 교체한다.
2. THE Deploy_Script SHALL `deploy-frontend.sh`에서 `gsutil` CLI 명령을 제거하고 `aws s3` CLI 명령으로 교체한다.
3. THE Deploy_Script SHALL `.env` 파일에서 `AWS_ACCOUNT_ID`, `AWS_REGION`, `ECR_REPOSITORY_NAME`, `APP_RUNNER_SERVICE_ARN`, `S3_BUCKET_NAME`, `CLOUDFRONT_DISTRIBUTION_ID` 환경변수를 읽는다.
4. WHEN 백엔드 배포 스크립트가 실행되면, THE Deploy_Script SHALL ECR 로그인 → Docker 빌드 → ECR 푸시 → App Runner 서비스 업데이트 순서로 실행한다.
5. WHEN 프론트엔드 배포 스크립트가 실행되면, THE Deploy_Script SHALL App Runner URL을 `index.html` 메타 태그에 주입한 후 S3에 업로드하고 CloudFront 캐시를 무효화한다.
6. IF AWS CLI 인증이 설정되지 않은 경우, THE Deploy_Script SHALL 오류 메시지를 출력하고 종료 코드 1로 종료한다.
7. WHEN 배포가 완료되면, THE Deploy_Script SHALL CloudFront 도메인 URL과 App Runner 서비스 URL을 출력한다.

---

### Requirement 7: GCP 의존성 완전 제거

**User Story:** As a 개발자, I want 코드베이스에서 모든 GCP 관련 의존성과 참조를 제거하고 싶다, so that AWS 전환 후 불필요한 GCP 코드가 남지 않는다.

#### Acceptance Criteria

1. THE Backend SHALL `pyproject.toml`에서 `google-cloud-firestore`, `google-cloud-aiplatform` 패키지를 제거한다.
2. THE Backend SHALL `main.py`에서 `google.cloud`, `vertexai` 임포트 구문을 제거한다.
3. THE Backend SHALL `main.py`에서 `get_project_id()` 함수와 GCP 메타데이터 서버 호출 코드를 제거한다.
4. THE Backend SHALL `.gcloudignore` 파일을 제거하고 `.dockerignore`에서 GCP 관련 항목을 정리한다.
5. THE Backend SHALL `cloudbuild.yaml` 파일을 제거한다.
6. THE Frontend SHALL `app.js`의 `CONFIG.PROD_API_URL`에서 `a.run.app` 도메인 하드코딩을 제거한다.
