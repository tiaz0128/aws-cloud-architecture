from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import boto3
from botocore.exceptions import ClientError
from dynamodb_client import DynamoDBClient
from bedrock_client import BedrockClient
import os
import asyncio
from functools import partial
from datetime import datetime
import logging

# 로깅 설정
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def clean_mermaid_code(code: str) -> str:
    """Mermaid 코드를 안전하게 정리하고 검증"""
    lines = code.split("\n")
    cleaned_lines = []

    for line in lines:
        line = line.strip()
        if not line:
            continue

        # 주석 제거
        if line.startswith("%%"):
            continue

        # 대괄호 안의 특수문자 처리 - 예: [Cloud Storage (Static Files)]
        # Mermaid에서 대괄호 안에 특수문자가 있으면 문제가 될 수 있으므로 안전하게 제거
        import re

        # 대괄호 안에 특수문자가 있는 패턴을 찾아서 특수문자를 제거
        def clean_special_chars_in_label(match):
            label_content = match.group(1)
            # 특수문자를 공백으로 변환 후 여러 공백을 하나로 정리
            # 영문자, 숫자, 공백, 언더스코어만 남기고 나머지 제거
            cleaned_content = re.sub(r"[^\w\s]", " ", label_content)
            # 여러 공백을 하나로 정리하고 앞뒤 공백 제거
            cleaned_content = re.sub(r"\s+", " ", cleaned_content).strip()
            return f"[{cleaned_content}]"

        # 패턴: [내용] 형태에서 특수문자가 포함된 경우 정리
        line = re.sub(
            r"\[([^\[\]]*[^\w\s][^\[\]]*)\]", clean_special_chars_in_label, line
        )

        # architecture-beta 구문에서는 기본적으로 안전한 구문 사용
        # 특수문자 처리는 최소화 (architecture-beta는 구조가 더 엄격함)
        cleaned_lines.append(line)

    cleaned_code = "\n".join(cleaned_lines)

    # 기본 구조 검증 - architecture-beta 지원 추가
    if not cleaned_code.strip().startswith(
        ("graph", "flowchart", "sequenceDiagram", "architecture-beta")
    ):
        logger.warning("Mermaid 코드가 올바른 다이어그램 타입으로 시작하지 않습니다")
        # 기본 architecture-beta 추가
        cleaned_code = f"architecture-beta\n{cleaned_code}"

    return cleaned_code


app = FastAPI(title="Cloud Architecture Diagram Generator")

# CORS 설정
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # 프로덕션에서는 특정 도메인으로 제한
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# AWS 클라이언트 초기화
try:
    # DynamoDB 클라이언트 초기화
    dynamodb_client = DynamoDBClient(
        table_name=os.getenv('DYNAMODB_TABLE_NAME'),
        region=os.getenv('AWS_REGION', 'us-east-1')
    )
    logger.info("DynamoDB 클라이언트 초기화 성공")
except Exception as e:
    logger.error(f"DynamoDB 클라이언트 초기화 실패: {e}")
    dynamodb_client = None

# Bedrock 클라이언트 초기화
try:
    bedrock_client = BedrockClient(
        model_id=os.getenv('BEDROCK_MODEL_ID'),
        region=os.getenv('BEDROCK_REGION', os.getenv('AWS_REGION', 'us-east-1'))
    )
    logger.info("Bedrock 클라이언트 초기화 성공")
except Exception as e:
    logger.error(f"Bedrock 클라이언트 초기화 실패: {e}")
    bedrock_client = None


# 데이터 모델
class DiagramRequest(BaseModel):
    description: str
    cloud_provider: str = "gcp"  # gcp, aws, azure
    diagram_type: str = "architecture-beta"  #


class DiagramResponse(BaseModel):
    id: str
    mermaid_code: str
    description: str
    cloud_provider: str
    created_at: str


class IaCExportRequest(BaseModel):
    mermaid_code: str
    description: str = ""
    cloud_provider: str = "aws"
    iac_type: str = "terraform"  # "terraform" | "cloudformation"


@app.post("/generate-diagram", response_model=DiagramResponse)
async def generate_diagram(request: DiagramRequest):
    """AI로 Mermaid 다이어그램 코드 생성"""
    try:
        if bedrock_client is None:
            raise HTTPException(
                status_code=503, detail="Bedrock 서비스를 사용할 수 없습니다"
            )

        if dynamodb_client is None:
            raise HTTPException(
                status_code=503, detail="DynamoDB 서비스를 사용할 수 없습니다"
            )

        # Bedrock (Claude) 프롬프트 생성
        prompt = f"""
        다음 설명을 바탕으로 {request.cloud_provider.upper()} 클라우드 아키텍처 다이어그램을 Mermaid architecture-beta 코드로 생성해주세요.

        사용자 설명: {request.description}
        클라우드 제공자: {request.cloud_provider.upper()}
        다이어그램 타입: architecture-beta

        **중요한 Mermaid architecture-beta 구문 규칙을 반드시 준수하세요:**

        1. **기본 구조**:
           - architecture-beta로 시작
           - 4칸 들여쓰기 사용
           - ( ), [ ] 괄호안에 빈값은 허용하지 않음
           - 주석은 %% 로 시작하지만, 이번에는 사용하지 않음
           - Edge 선언 시 그룹은 절대 사용하지 않음 (serviceId{{group}} 형태 금지)
           - 주석 절대 쓰지마

           
        2. **아이콘 참고**:
           - <provider>:아이콘명 형식 사용
           - 서비스 / 리소스명은 소문자 _(언더스코어)로 연결 (예: cloud_run, sql_database)
           - GCP: logos:google-cloud, gcp:virtual_private_cloud
           - AWS: logos:aws, aws:amazon_virtual_private_cloud
           - Azure: logos:microsoft-azure, azr:virtual_networks
           - logos: logos:python, logos:react, logos:fastapi-icon
           - mdi: mdi:account, mdi:server, mdi:earth, mdi:heart

        주요 서비스 및 아이콘:
        - GCP: Compute Engine(gcp:compute_engine), Cloud Run(gcp:cloud_run), Cloud Storage(gcp:cloud_storage), Cloud SQL(gcp:cloud_sql), Firestore(gcp:firestore), Vertex AI(gcp:vertexai)
        - AWS: EC2(aws:amazon_ec2_db_instance), VPC(aws:amazon_virtual_private_cloud), Lambda(aws:aws_lambda_lambda_function), S3(aws:amazon_simple_storage_service_s3_standard), RDS(aws:amazon_rds_multi_az), ALB(aws:elastic_load_balancing_application_load_balancer), CloudFront(aws:amazon_cloudfront)
        - Azure: VM(azr:virtual_machine), App Service(azr:app_services), Functions(azr:functions), Blob Storage(azr:blob_block), SQL Database(azr:sql_database)

        ---

        """

        prompt += r"""
        # Architecture Diagrams Documentation (v11.1.0+)

        > In the context of mermaid-js, the architecture diagram is used to show the relationship between services and resources commonly found within the Cloud or CI/CD deployments. In an architecture diagram, services (nodes) are connected by edges. Related services can be placed within groups to better illustrate how they are organized.

        ## Example

        ```mermaid-example
        architecture-beta
            group api(cloud)[API]

            service db(database)[Database] in api
            service disk1(disk)[Storage] in api
            service disk2(disk)[Storage] in api
            service server(server)[Server] in api

            db:L -- R:server
            disk1:T -- B:server
            disk2:T -- B:db
        ```

        ## Syntax

        The building blocks of an architecture are `groups`, `services`, `edges`, and `junctions`.

        For supporting components, icons are declared by surrounding the icon name with `()`, while labels are declared by surrounding the text with `[]`.

        To begin an architecture diagram, use the keyword `architecture-beta`, followed by your groups, services, edges, and junctions. While each of the 3 building blocks can be declared in any order, care must be taken to ensure the identifier was previously declared by another component.

        ### Groups

        The syntax for declaring a group is:

        ```
        group {group id}({icon name})[{title}] (in {parent id})?
        ```

        Put together:

        ```
        group public_api(cloud)[Public API]
        ```

        creates a group identified as `public_api`, uses the icon `cloud`, and has the label `Public API`.

        Additionally, groups can be placed within a group using the optional `in` keyword

        ```
        group private_api(cloud)[Private API] in public_api
        ```

        ### Services

        The syntax for declaring a service is:

        ```
        service {service id}({icon name})[{title}] (in {parent id})?
        ```

        Put together:

        ```
        service database1(database)[My Database]
        ```

        creates the service identified as `database1`, using the icon `database`, with the label `My Database`.

        If the service belongs to a group, it can be placed inside it through the optional `in` keyword

        ```
        service database1(database)[My Database] in private_api
        ```

        ### Edges

        The syntax for declaring an edge is:

        ```
        {serviceId}?:{T|B|L|R} {<}?--{>}? {T|B|L|R}:{serviceId}?
        ```

        #### Edge Direction

        The side of the service the edge comes out of is specified by adding a colon (`:`) to the side of the service connecting to the arrow and adding `L|R|T|B`

        For example:

        ```
        db:R -- L:server
        ```

        creates an edge between the services `db` and `server`, with the edge coming out of the right of `db` and the left of `server`.

        ```
        db:T -- L:server
        ```

        creates a 90 degree edge between the services `db` and `server`, with the edge coming out of the top of `db` and the left of `server`.

        #### Arrows

        Arrows can be added to each side of an edge by adding `<` before the direction on the left, and/or `>` after the direction on the right.

        For example:

        ```
        subnet:R --> L:gateway
        ```

        creates an edge with the arrow going into the `gateway` service

        #### Edges out of Groups

        To have an edge go from a group to another group or service within another group, the `{group}` modifier can be added after the `serviceId`.

        For example:

        ```
        service server[Server] in groupOne
        service subnet[Subnet] in groupTwo

        server{group}:B --> T:subnet{group}
        ```

        creates an edge going out of `groupOne`, adjacent to `server`, and into `groupTwo`, adjacent to `subnet`.

        It's important to note that `groupId`s cannot be used for specifying edges and the `{group}` modifier can only be used for services within a group.

        ### Junctions

        Junctions are a special type of node which acts as a potential 4-way split between edges.

        The syntax for declaring a junction is:

        ```
        junction {junction id} (in {parent id})?
        ```

        ```mermaid-example
        architecture-beta
            service left_disk(disk)[Disk]
            service top_disk(disk)[Disk]
            service bottom_disk(disk)[Disk]
            service top_gateway(internet)[Gateway]
            service bottom_gateway(internet)[Gateway]
            junction junctionCenter
            junction junctionRight

            left_disk:R -- L:junctionCenter
            top_disk:B -- T:junctionCenter
            bottom_disk:T -- B:junctionCenter
            junctionCenter:R -- L:junctionRight
            top_gateway:B -- T:junctionRight
            bottom_gateway:T -- B:junctionRight
        ```

        ---

        이제 위 규칙을 엄격히 따라 architecture-beta Mermaid 코드만 생성해주세요:
"""

        # Bedrock (Claude) 호출 — 비동기로 실행하여 다른 요청 블로킹 방지
        loop = asyncio.get_event_loop()
        mermaid_code = await loop.run_in_executor(
            None, partial(bedrock_client.generate_diagram_code, prompt)
        )

        # 코드 블록 제거 (```로 감싸진 부분)
        if "```" in mermaid_code:
            lines = mermaid_code.split("\n")
            start_idx = -1
            end_idx = -1

            for i, line in enumerate(lines):
                if line.strip().startswith("```"):
                    if start_idx == -1:
                        start_idx = i
                    else:
                        end_idx = i
                        break

            if start_idx != -1 and end_idx != -1:
                mermaid_code = "\n".join(lines[start_idx + 1 : end_idx])
            elif start_idx != -1:
                mermaid_code = "\n".join(lines[start_idx + 1 :])

        mermaid_code = mermaid_code.strip()

        # Mermaid 코드 안전성 검증 및 정리
        mermaid_code = clean_mermaid_code(mermaid_code)

        logger.info(f"생성된 Mermaid 코드: {mermaid_code}")

        # DynamoDB에 저장
        diagram_data = {
            "mermaid_code": mermaid_code,
            "description": request.description,
            "cloud_provider": request.cloud_provider,
            "diagram_type": request.diagram_type,
        }
        diagram_id = dynamodb_client.create_diagram(diagram_data)
        
        # 저장된 다이어그램 조회하여 created_at 가져오기
        saved_diagram = dynamodb_client.get_diagram(diagram_id)

        return DiagramResponse(
            id=diagram_id,
            mermaid_code=mermaid_code,
            description=request.description,
            cloud_provider=request.cloud_provider,
            created_at=saved_diagram["created_at"],
        )

    except Exception as e:
        logger.error(f"다이어그램 생성 실패: {str(e)}")
        raise HTTPException(status_code=503, detail=f"다이어그램 생성 실패: {str(e)}")


@app.get("/diagrams/{diagram_id}", response_model=DiagramResponse)
async def get_diagram(diagram_id: str):
    """저장된 다이어그램 조회"""
    try:
        if dynamodb_client is None:
            raise HTTPException(
                status_code=503, detail="DynamoDB 서비스를 사용할 수 없습니다"
            )
        
        from dynamodb_client import DiagramNotFoundError, DynamoDBClientError
        
        try:
            data = dynamodb_client.get_diagram(diagram_id)
            
            return DiagramResponse(
                id=diagram_id,
                mermaid_code=data["mermaid_code"],
                description=data["description"],
                cloud_provider=data["cloud_provider"],
                created_at=data["created_at"],
            )
        
        except DiagramNotFoundError:
            raise HTTPException(status_code=404, detail="다이어그램을 찾을 수 없습니다")
        except DynamoDBClientError as e:
            logger.error(f"DynamoDB 오류: {str(e)}")
            raise HTTPException(status_code=503, detail="데이터베이스 서비스를 사용할 수 없습니다")

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"다이어그램 조회 실패: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/diagrams")
async def list_diagrams(limit: int = 10):
    """다이어그램 목록 조회"""
    try:
        if dynamodb_client is None:
            raise HTTPException(
                status_code=503, detail="DynamoDB 서비스를 사용할 수 없습니다"
            )
        
        from dynamodb_client import DynamoDBClientError
        
        try:
            diagrams = dynamodb_client.list_diagrams(limit=limit)
            
            diagram_list = []
            for diagram in diagrams:
                diagram_list.append(
                    {
                        "id": diagram["diagram_id"],
                        "description": diagram["description"],
                        "cloud_provider": diagram["cloud_provider"],
                        "mermaid_code": diagram.get("mermaid_code", ""),
                        "created_at": diagram["created_at"],
                    }
                )

            return {"diagrams": diagram_list}
        
        except DynamoDBClientError as e:
            logger.error(f"DynamoDB 오류: {str(e)}")
            raise HTTPException(status_code=503, detail="데이터베이스 서비스를 사용할 수 없습니다")

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"다이어그램 목록 조회 실패: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@app.put("/diagrams/{diagram_id}")
async def update_diagram(diagram_id: str, request: DiagramRequest):
    """다이어그램 수정 (재생성)"""
    try:
        if dynamodb_client is None:
            raise HTTPException(
                status_code=503, detail="DynamoDB 서비스를 사용할 수 없습니다"
            )
        
        if bedrock_client is None:
            raise HTTPException(
                status_code=503, detail="Bedrock 서비스를 사용할 수 없습니다"
            )
        
        from dynamodb_client import DiagramNotFoundError, DynamoDBClientError
        
        try:
            # 기존 다이어그램 확인
            dynamodb_client.get_diagram(diagram_id)
            
            # 새로 생성 (기존 generate_diagram 로직 재사용)
            new_diagram = await generate_diagram(request)

            # 기존 문서 업데이트
            update_data = {
                "mermaid_code": new_diagram.mermaid_code,
                "description": request.description,
                "cloud_provider": request.cloud_provider,
                "diagram_type": request.diagram_type,
            }
            dynamodb_client.update_diagram(diagram_id, update_data)

            return {
                "message": "다이어그램이 업데이트되었습니다",
                "mermaid_code": new_diagram.mermaid_code,
            }
        
        except DiagramNotFoundError:
            raise HTTPException(status_code=404, detail="다이어그램을 찾을 수 없습니다")
        except DynamoDBClientError as e:
            logger.error(f"DynamoDB 오류: {str(e)}")
            raise HTTPException(status_code=503, detail="데이터베이스 서비스를 사용할 수 없습니다")

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"다이어그램 업데이트 실패: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@app.delete("/diagrams/{diagram_id}")
async def delete_diagram(diagram_id: str):
    """다이어그램 삭제"""
    try:
        if dynamodb_client is None:
            raise HTTPException(
                status_code=503, detail="DynamoDB 서비스를 사용할 수 없습니다"
            )
        
        from dynamodb_client import DiagramNotFoundError, DynamoDBClientError
        
        try:
            dynamodb_client.delete_diagram(diagram_id)
            return {"message": "다이어그램이 삭제되었습니다"}
        
        except DiagramNotFoundError:
            raise HTTPException(status_code=404, detail="다이어그램을 찾을 수 없습니다")
        except DynamoDBClientError as e:
            logger.error(f"DynamoDB 오류: {str(e)}")
            raise HTTPException(status_code=503, detail="데이터베이스 서비스를 사용할 수 없습니다")

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"다이어그램 삭제 실패: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/export-iac")
async def export_iac(request: IaCExportRequest):
    """Mermaid 아키텍처 다이어그램을 IaC 코드(Terraform/CloudFormation)로 변환"""
    try:
        if bedrock_client is None:
            raise HTTPException(
                status_code=503, detail="Bedrock 서비스를 사용할 수 없습니다"
            )

        iac_type_label = {
            "terraform": "Terraform (HCL)",
            "cloudformation": "AWS CloudFormation (YAML)",
        }.get(request.iac_type, request.iac_type)

        cloud_label = request.cloud_provider.upper()

        prompt = f"""다음 Mermaid architecture-beta 다이어그램과 설명을 기반으로 {iac_type_label} 코드를 생성해주세요.

## 입력 정보

**클라우드 제공자:** {cloud_label}
**사용자 설명:** {request.description or '(없음)'}

**Mermaid 아키텍처 코드:**
```
{request.mermaid_code}
```

## 요구사항

1. 위 다이어그램에 나타난 모든 서비스/리소스를 {iac_type_label} 코드로 변환하세요.
2. 서비스 간 연결(Edge)을 분석하여 필요한 네트워킹, 보안 그룹, IAM 역할 등을 추가하세요.
3. 실제 배포 가능한 수준의 합리적인 기본값을 사용하세요:
   - 리전: ap-northeast-1 (도쿄) 기본
   - 인스턴스: 비용 효율적인 소형 사이즈
   - 네트워킹: 기본 VPC/서브넷 구성 포함
4. 주석으로 각 리소스가 다이어그램의 어떤 서비스에 해당하는지 표시하세요.
5. 변수(variables)를 활용하여 커스터마이징이 쉽도록 하세요.

## 출력 형식

"""

        if request.iac_type == "terraform":
            prompt += """Terraform HCL 코드만 출력하세요. 설명 텍스트 없이 코드 블록만 반환하세요.
provider 블록, 필요한 variable 블록, resource 블록, output 블록을 포함하세요."""
        else:
            prompt += """AWS CloudFormation YAML 코드만 출력하세요. 설명 텍스트 없이 코드 블록만 반환하세요.
AWSTemplateFormatVersion, Description, Parameters, Resources, Outputs 섹션을 포함하세요."""

        # Bedrock 호출 — 비동기로 실행하여 다른 요청 블로킹 방지
        loop = asyncio.get_event_loop()
        iac_code = await loop.run_in_executor(
            None, partial(bedrock_client.generate_diagram_code, prompt)
        )

        # 코드 블록 마커 제거
        if "```" in iac_code:
            lines = iac_code.split("\n")
            start_idx = -1
            end_idx = -1

            for i, line in enumerate(lines):
                if line.strip().startswith("```"):
                    if start_idx == -1:
                        start_idx = i
                    else:
                        end_idx = i
                        break

            if start_idx != -1 and end_idx != -1:
                iac_code = "\n".join(lines[start_idx + 1 : end_idx])
            elif start_idx != -1:
                iac_code = "\n".join(lines[start_idx + 1 :])

        iac_code = iac_code.strip()

        file_extension = "tf" if request.iac_type == "terraform" else "yaml"
        filename = f"architecture.{file_extension}"

        logger.info(f"IaC 코드 생성 완료: {request.iac_type} ({len(iac_code)} chars)")

        return {
            "iac_code": iac_code,
            "iac_type": request.iac_type,
            "filename": filename,
            "cloud_provider": request.cloud_provider,
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"IaC 코드 생성 실패: {str(e)}")
        raise HTTPException(status_code=503, detail=f"IaC 코드 생성 실패: {str(e)}")


@app.get("/")
async def root():
    return {
        "message": "Cloud Architecture Diagram Generator API",
        "version": "1.0.0",
        "endpoints": {
            "POST /generate-diagram": "다이어그램 생성",
            "GET /diagrams/{id}": "다이어그램 조회",
            "GET /diagrams": "다이어그램 목록",
            "PUT /diagrams/{id}": "다이어그램 수정",
            "DELETE /diagrams/{id}": "다이어그램 삭제",
            "POST /export-iac": "IaC 코드 내보내기",
        },
    }


@app.get("/health")
async def health_check():
    """서비스 상태 확인"""
    status = "healthy"
    issues = []

    # DynamoDB 연결 확인
    dynamodb_status = "healthy"
    if dynamodb_client is None:
        status = "unhealthy"
        dynamodb_status = "unhealthy"
        issues.append("DynamoDB 연결 실패")
    else:
        # DynamoDB 실제 연결 테스트
        try:
            if not dynamodb_client.check_connection():
                status = "unhealthy"
                dynamodb_status = "unhealthy"
                issues.append("DynamoDB 연결 테스트 실패")
        except Exception as e:
            status = "unhealthy"
            dynamodb_status = "unhealthy"
            issues.append(f"DynamoDB 연결 테스트 실패: {str(e)}")

    # Bedrock 모델 확인
    bedrock_status = "healthy"
    if bedrock_client is None:
        status = "unhealthy"
        bedrock_status = "unhealthy"
        issues.append("Bedrock 클라이언트 초기화 실패")

    return {
        "status": status,
        "timestamp": datetime.now().isoformat(),
        "services": {
            "dynamodb": dynamodb_status,
            "bedrock": bedrock_status,
        },
        "issues": issues if issues else None,
    }
