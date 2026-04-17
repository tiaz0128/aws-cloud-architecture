"""
DynamoDB 클라이언트 모듈
Firestore를 대체하여 다이어그램 데이터를 DynamoDB에 저장하고 조회합니다.
"""

import os
import uuid
import logging
from datetime import datetime
from typing import Optional, List, Dict, Any
import boto3
from botocore.exceptions import ClientError

logger = logging.getLogger(__name__)


class DynamoDBClientError(Exception):
    """DynamoDB 클라이언트 에러"""
    pass


class DiagramNotFoundError(DynamoDBClientError):
    """다이어그램을 찾을 수 없음"""
    pass


class DynamoDBClient:
    """DynamoDB 클라이언트 클래스"""
    
    def __init__(self, table_name: Optional[str] = None, region: Optional[str] = None):
        """
        DynamoDB 클라이언트 초기화
        
        Args:
            table_name: DynamoDB 테이블 이름 (환경변수 DYNAMODB_TABLE_NAME에서 읽음)
            region: AWS 리전 (환경변수 AWS_REGION에서 읽음)
        """
        self.table_name = table_name or os.getenv('DYNAMODB_TABLE_NAME')
        self.region = region or os.getenv('AWS_REGION', 'us-east-1')
        
        if not self.table_name:
            raise DynamoDBClientError("DYNAMODB_TABLE_NAME 환경변수가 설정되지 않았습니다")
        
        try:
            # boto3 DynamoDB 리소스 초기화
            self.dynamodb = boto3.resource('dynamodb', region_name=self.region)
            self.table = self.dynamodb.Table(self.table_name)
            
            # 테이블 존재 확인
            self.table.load()
            logger.info(f"DynamoDB 클라이언트 초기화 성공: {self.table_name} (리전: {self.region})")
            
        except ClientError as e:
            error_code = e.response['Error']['Code']
            if error_code == 'ResourceNotFoundException':
                raise DynamoDBClientError(f"DynamoDB 테이블을 찾을 수 없습니다: {self.table_name}")
            else:
                raise DynamoDBClientError(f"DynamoDB 연결 실패: {str(e)}")
        except Exception as e:
            raise DynamoDBClientError(f"DynamoDB 클라이언트 초기화 실패: {str(e)}")
    
    def create_diagram(self, diagram_data: Dict[str, Any]) -> str:
        """
        새 다이어그램 생성
        
        Args:
            diagram_data: 다이어그램 데이터 딕셔너리
                - mermaid_code: Mermaid 코드
                - description: 설명
                - cloud_provider: 클라우드 제공자
                - diagram_type: 다이어그램 타입
        
        Returns:
            생성된 다이어그램 ID (UUID)
        """
        try:
            diagram_id = str(uuid.uuid4())
            created_at = datetime.now().isoformat()
            
            item = {
                'diagram_id': diagram_id,
                'mermaid_code': diagram_data.get('mermaid_code', ''),
                'description': diagram_data.get('description', ''),
                'cloud_provider': diagram_data.get('cloud_provider', 'gcp'),
                'diagram_type': diagram_data.get('diagram_type', 'architecture-beta'),
                'created_at': created_at,
                'updated_at': created_at
            }
            
            self.table.put_item(Item=item)
            logger.info(f"다이어그램 생성 성공: {diagram_id}")
            
            return diagram_id
            
        except ClientError as e:
            logger.error(f"다이어그램 생성 실패: {str(e)}")
            raise DynamoDBClientError(f"다이어그램 생성 실패: {str(e)}")
    
    def get_diagram(self, diagram_id: str) -> Dict[str, Any]:
        """
        다이어그램 조회
        
        Args:
            diagram_id: 다이어그램 ID
        
        Returns:
            다이어그램 데이터 딕셔너리
        
        Raises:
            DiagramNotFoundError: 다이어그램을 찾을 수 없음
        """
        try:
            response = self.table.get_item(Key={'diagram_id': diagram_id})
            
            if 'Item' not in response:
                raise DiagramNotFoundError(f"다이어그램을 찾을 수 없습니다: {diagram_id}")
            
            return response['Item']
            
        except DiagramNotFoundError:
            raise
        except ClientError as e:
            logger.error(f"다이어그램 조회 실패: {str(e)}")
            raise DynamoDBClientError(f"다이어그램 조회 실패: {str(e)}")
    
    def list_diagrams(self, limit: int = 10) -> List[Dict[str, Any]]:
        """
        다이어그램 목록 조회 (최신순 정렬)
        
        Args:
            limit: 조회할 최대 개수
        
        Returns:
            다이어그램 목록 (created_at 내림차순)
        """
        try:
            # Scan을 사용하여 모든 항목 조회 후 정렬
            # 프로덕션에서는 GSI를 사용하는 것이 권장됨
            response = self.table.scan(Limit=limit * 2)  # 정렬을 위해 더 많이 가져옴
            
            items = response.get('Items', [])
            
            # created_at 기준 내림차순 정렬
            items.sort(key=lambda x: x.get('created_at', ''), reverse=True)
            
            # limit 적용
            return items[:limit]
            
        except ClientError as e:
            logger.error(f"다이어그램 목록 조회 실패: {str(e)}")
            raise DynamoDBClientError(f"다이어그램 목록 조회 실패: {str(e)}")
    
    def update_diagram(self, diagram_id: str, diagram_data: Dict[str, Any]) -> None:
        """
        다이어그램 업데이트
        
        Args:
            diagram_id: 다이어그램 ID
            diagram_data: 업데이트할 데이터
        
        Raises:
            DiagramNotFoundError: 다이어그램을 찾을 수 없음
        """
        try:
            # 먼저 항목이 존재하는지 확인
            self.get_diagram(diagram_id)
            
            # 업데이트할 속성 준비
            update_expression = "SET "
            expression_attribute_values = {}
            expression_attribute_names = {}
            
            updates = []
            
            if 'mermaid_code' in diagram_data:
                updates.append("#mc = :mc")
                expression_attribute_names['#mc'] = 'mermaid_code'
                expression_attribute_values[':mc'] = diagram_data['mermaid_code']
            
            if 'description' in diagram_data:
                updates.append("description = :desc")
                expression_attribute_values[':desc'] = diagram_data['description']
            
            if 'cloud_provider' in diagram_data:
                updates.append("cloud_provider = :cp")
                expression_attribute_values[':cp'] = diagram_data['cloud_provider']
            
            if 'diagram_type' in diagram_data:
                updates.append("diagram_type = :dt")
                expression_attribute_values[':dt'] = diagram_data['diagram_type']
            
            # updated_at 항상 업데이트
            updates.append("updated_at = :ua")
            expression_attribute_values[':ua'] = datetime.now().isoformat()
            
            update_expression += ", ".join(updates)
            
            # 업데이트 실행
            update_kwargs = {
                'Key': {'diagram_id': diagram_id},
                'UpdateExpression': update_expression,
                'ExpressionAttributeValues': expression_attribute_values
            }
            
            if expression_attribute_names:
                update_kwargs['ExpressionAttributeNames'] = expression_attribute_names
            
            self.table.update_item(**update_kwargs)
            
            logger.info(f"다이어그램 업데이트 성공: {diagram_id}")
            
        except DiagramNotFoundError:
            raise
        except ClientError as e:
            logger.error(f"다이어그램 업데이트 실패: {str(e)}")
            raise DynamoDBClientError(f"다이어그램 업데이트 실패: {str(e)}")
    
    def delete_diagram(self, diagram_id: str) -> None:
        """
        다이어그램 삭제
        
        Args:
            diagram_id: 다이어그램 ID
        
        Raises:
            DiagramNotFoundError: 다이어그램을 찾을 수 없음
        """
        try:
            # 먼저 항목이 존재하는지 확인
            self.get_diagram(diagram_id)
            
            # 삭제 실행
            self.table.delete_item(Key={'diagram_id': diagram_id})
            
            logger.info(f"다이어그램 삭제 성공: {diagram_id}")
            
        except DiagramNotFoundError:
            raise
        except ClientError as e:
            logger.error(f"다이어그램 삭제 실패: {str(e)}")
            raise DynamoDBClientError(f"다이어그램 삭제 실패: {str(e)}")
    
    def check_connection(self) -> bool:
        """
        DynamoDB 연결 상태 확인
        
        Returns:
            연결 성공 여부
        """
        try:
            self.table.load()
            return True
        except Exception as e:
            logger.error(f"DynamoDB 연결 확인 실패: {str(e)}")
            return False
