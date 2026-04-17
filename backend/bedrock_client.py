"""
Amazon Bedrock client module for AI-powered diagram generation.
Replaces Vertex AI (Gemini) with Amazon Bedrock (Claude).
"""

import os
import json
import logging
import time
from typing import Optional
import boto3
from botocore.exceptions import ClientError
from botocore.config import Config

logger = logging.getLogger(__name__)


class BedrockClient:
    """Client for interacting with Amazon Bedrock Runtime API."""

    def __init__(self, model_id: Optional[str] = None, region: Optional[str] = None):
        """
        Initialize Bedrock Runtime client with boto3.

        Args:
            model_id: Bedrock model ID or inference profile ID
            region: AWS region for Bedrock Runtime endpoint (e.g., 'us-east-1')
        """
        self.model_id = model_id or os.getenv(
            "BEDROCK_MODEL_ID", "jp.anthropic.claude-sonnet-4-6"
        )
        # Bedrock 호출 리전은 BEDROCK_REGION 환경변수로 별도 지정 가능
        self.region = region or os.getenv("BEDROCK_REGION", os.getenv("AWS_REGION", "us-east-1"))

        try:
            bedrock_config = Config(
                read_timeout=120,
                connect_timeout=10,
                retries={"max_attempts": 0}  # 자체 재시도 로직 사용
            )
            self.client = boto3.client(
                service_name="bedrock-runtime",
                region_name=self.region,
                config=bedrock_config,
            )
            logger.info(
                f"Bedrock Runtime client initialized: region={self.region}, model={self.model_id}"
            )
        except Exception as e:
            logger.error(f"Failed to initialize Bedrock Runtime client: {e}")
            raise

    def generate_diagram_code(self, prompt: str) -> str:
        """
        Call Claude model via Bedrock to generate Mermaid diagram code.

        Args:
            prompt: The prompt text for diagram generation

        Returns:
            Generated Mermaid code as string

        Raises:
            Exception: If model invocation fails after retries
        """
        # Prepare request body for Claude model
        request_body = {
            "anthropic_version": "bedrock-2023-05-31",
            "max_tokens": 4096,
            "messages": [{"role": "user", "content": prompt}],
            "temperature": 0.7,
        }

        # Exponential backoff retry logic
        max_retries = 3
        base_delay = 1  # seconds

        for attempt in range(max_retries):
            try:
                logger.info(
                    f"Invoking Bedrock model (attempt {attempt + 1}/{max_retries})"
                )

                response = self.client.invoke_model(
                    modelId=self.model_id,
                    body=json.dumps(request_body),
                    contentType="application/json",
                    accept="application/json",
                )

                # Parse response
                response_body = json.loads(response["body"].read())

                # Extract text from Claude response
                if "content" in response_body and len(response_body["content"]) > 0:
                    generated_text = response_body["content"][0]["text"]
                    logger.info("Successfully generated diagram code from Bedrock")
                    return generated_text
                else:
                    raise Exception("No content in Bedrock response")

            except ClientError as e:
                error_code = e.response.get("Error", {}).get("Code", "")

                # Handle throttling with exponential backoff
                if error_code == "ThrottlingException":
                    if attempt < max_retries - 1:
                        delay = base_delay * (2**attempt)
                        logger.warning(
                            f"Throttling detected, retrying in {delay} seconds..."
                        )
                        time.sleep(delay)
                        continue
                    else:
                        logger.error(
                            f"Max retries reached for ThrottlingException: {e}"
                        )
                        raise Exception(
                            f"Bedrock API throttling: Max retries exceeded"
                        ) from e

                # Handle service unavailable
                elif error_code in ["ServiceUnavailableException", "InternalServerError"]:
                    if attempt < max_retries - 1:
                        delay = base_delay * (2**attempt)
                        logger.warning(
                            f"Service unavailable, retrying in {delay} seconds..."
                        )
                        time.sleep(delay)
                        continue
                    else:
                        logger.error(f"Max retries reached for {error_code}: {e}")
                        raise Exception(
                            f"Bedrock service unavailable: {error_code}"
                        ) from e

                # Other client errors - don't retry
                else:
                    logger.error(f"Bedrock client error: {error_code} - {e}")
                    raise Exception(f"Bedrock invocation failed: {error_code}") from e

            except Exception as e:
                logger.error(f"Unexpected error invoking Bedrock model: {e}")
                if attempt < max_retries - 1:
                    delay = base_delay * (2**attempt)
                    logger.warning(f"Retrying in {delay} seconds...")
                    time.sleep(delay)
                    continue
                else:
                    raise Exception(f"Failed to generate diagram code: {str(e)}") from e

        # Should not reach here, but just in case
        raise Exception("Failed to generate diagram code after all retries")
