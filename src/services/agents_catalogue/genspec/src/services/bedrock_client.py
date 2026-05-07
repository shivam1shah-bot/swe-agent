"""
AWS Bedrock client for interacting with Claude models.
"""

import json
import os
import boto3
import time
import base64
from typing import Dict, Any, Optional, List
from src.providers.logger import Logger
from src.api.dependencies import get_logger


class BedrockClient:
    """
    Client for interacting with AWS Bedrock.
    """
    
    def __init__(self, config: Dict[str, Any]):
        """
        Initialize the Bedrock client.
        
        Args:
            config: Configuration dictionary
        """
        self.logger = get_logger("bedrock-client")
        self.config = config
        self.available_models = []
        
        # Extract AWS configuration
        aws_config = config.get("aws", {})
        region = aws_config.get("region", "us-east-1")
        
        try:
            # Try to get credentials from config (support both naming conventions)
            access_key = (aws_config.get("aws_access_key_id") or 
                         aws_config.get("access_key_id") or 
                         os.environ.get("AWS_ACCESS_KEY_ID"))
            secret_key = (aws_config.get("aws_secret_access_key") or 
                         aws_config.get("secret_access_key") or 
                         os.environ.get("AWS_SECRET_ACCESS_KEY"))
            session_token = (aws_config.get("aws_session_token") or 
                            aws_config.get("session_token") or 
                            os.environ.get("AWS_SESSION_TOKEN"))
            # Create session with credentials if available
            if access_key and secret_key:
                session = boto3.Session(
                    aws_access_key_id=access_key,
                    aws_secret_access_key=secret_key,
                    aws_session_token=session_token,
                    region_name=region
                )
                self.logger.info("Created AWS session with provided credentials")
            else:
                # Try environment variables or default profile
                try:
                    session = boto3.Session(region_name=region)
                    self.logger.info("Created AWS session using environment variables or default profile")
                except Exception as e:
                    # Fall back to profile if no direct credentials
                    profile_name = aws_config.get("profile", "default")
                    session = boto3.Session(
                        profile_name=profile_name,
                        region_name=region
                    )
                    self.logger.info(f"Created AWS session using profile: {profile_name}")
            
            # Get Bedrock configuration
            bedrock_config = aws_config.get("bedrock", {})
            
            # Create Bedrock client and bedrock management client
            self.client = session.client("bedrock-runtime")
            self.mgmt_client = session.client("bedrock")
            
            # Try to get available models
            self.available_models = self.list_available_models()
            
            # Check if we have any models
            if not self.available_models:
                self.logger.error("No models found in AWS Bedrock.")
                raise ValueError("No models found in AWS Bedrock")
            
            # Try to use the model specified in config first
            self.model_id = aws_config.get("model_id") or bedrock_config.get("model_id") or "anthropic.claude-3-5-sonnet-20240620-v1:0"
            
            # Check if the model is in the available models
            if self.model_id not in self.available_models:
                self.logger.warning(f"Specified model {self.model_id} not in available models. Will try alternatives.")
                
                # Try to find a Claude model first
                claude_models = [m for m in self.available_models if "claude" in m.lower()]
                if claude_models:
                    self.model_id = claude_models[0]
                    self.logger.info(f"Using Claude model: {self.model_id}")
                else:
                    # Use the first available model
                    self.model_id = self.available_models[0]
                    self.logger.info(f"Using available model: {self.model_id}")
            
            # Test if we can actually access the model
            self.logger.info(f"Testing access to model: {self.model_id}")
            self._test_model_access(self.model_id)
            self.logger.info(f"Successfully accessed model: {self.model_id}")
            
            # Get other parameters
            self.max_tokens = bedrock_config.get("max_tokens", aws_config.get("max_tokens", 4096))
            self.temperature = bedrock_config.get("temperature", aws_config.get("temperature", 0.7))
            self.top_p = bedrock_config.get("top_p", aws_config.get("top_p", 0.9))
            
            self.logger.info(f"Initialized Bedrock client with model {self.model_id}")
            
        except Exception as e:
            self.logger.error(f"Failed to initialize Bedrock client: {str(e)}")
            raise ValueError(f"Failed to initialize Bedrock client: {str(e)}")
    
    def _test_model_access(self, model_id):
        """
        Test if we can access the model by sending a simple request.
        
        Args:
            model_id: The model ID to test
        """
        try:
            # Different models have different request formats
            if "anthropic.claude" in model_id:
                request_body = {
                    "anthropic_version": "bedrock-2023-05-31",
                    "max_tokens": 10,
                    "temperature": 0.0,
                    "messages": [
                        {
                            "role": "user",
                            "content": "Say hello"
                        }
                    ]
                }
            elif "amazon.titan" in model_id:
                request_body = {
                    "inputText": "Say hello",
                    "textGenerationConfig": {
                        "maxTokenCount": 10,
                        "temperature": 0.0,
                        "topP": 1.0
                    }
                }
            elif "meta.llama" in model_id:
                request_body = {
                    "prompt": "Say hello",
                    "max_gen_len": 10,
                    "temperature": 0.0,
                    "top_p": 1.0
                }
            elif "mistral" in model_id:
                request_body = {
                    "prompt": "Say hello",
                    "max_tokens": 10,
                    "temperature": 0.0,
                    "top_p": 1.0
                }
            elif "cohere" in model_id:
                request_body = {
                    "prompt": "Say hello",
                    "max_tokens": 10,
                    "temperature": 0.0
                }
            else:
                # Generic format for other models
                request_body = {
                    "prompt": "Say hello",
                    "max_tokens": 10
                }
            
            self.logger.debug(f"Testing model {model_id} with request: {json.dumps(request_body)}")
            
            response = self.client.invoke_model(
                modelId=model_id,
                body=json.dumps(request_body)
            )
            
            # If we get here, the model is accessible
            self.logger.debug(f"Successfully tested model {model_id}")
            return True
        except Exception as e:
            self.logger.warning(f"Error testing model {model_id}: {str(e)}")
            raise
    
    def list_available_models(self) -> List[str]:
        """
        List available foundation models in Bedrock.
        
        Returns:
            List of available model IDs
        """
        try:
            response = self.mgmt_client.list_foundation_models()
            models = [model.get('modelId') for model in response.get('modelSummaries', [])]
            self.logger.info(f"Found {len(models)} available models: {models}")
            return models
        except Exception as e:
            self.logger.error(f"Failed to list available models: {str(e)}")
            return []
    
    def generate_text(self, prompt: str, **kwargs) -> str:
        """
        Generate text using the Bedrock model.
        
        Args:
            prompt: The prompt to send to the model
            **kwargs: Additional parameters for the model
                - max_tokens: Maximum number of tokens to generate
                - temperature: Temperature for sampling (higher = more creative)
                - top_p: Top-p sampling parameter
                - timeout: Timeout in seconds for the request (default: 60)
            
        Returns:
            Generated text
        """
        try:
            # Get timeout parameter
            timeout = kwargs.get("timeout", 60)  # Default 60 seconds timeout
            
            # Different models have different request formats
            if "anthropic.claude" in self.model_id:
                request_body = {
                    "anthropic_version": "bedrock-2023-05-31",
                    "max_tokens": kwargs.get("max_tokens", self.max_tokens),
                    "temperature": kwargs.get("temperature", self.temperature),
                    "top_p": kwargs.get("top_p", self.top_p),
                    "messages": [
                        {
                            "role": "user",
                            "content": prompt
                        }
                    ]
                }
            elif "amazon.titan" in self.model_id:
                request_body = {
                    "inputText": prompt,
                    "textGenerationConfig": {
                        "maxTokenCount": kwargs.get("max_tokens", self.max_tokens),
                        "temperature": kwargs.get("temperature", self.temperature),
                        "topP": kwargs.get("top_p", self.top_p)
                    }
                }
            elif "meta.llama" in self.model_id:
                request_body = {
                    "prompt": prompt,
                    "max_gen_len": kwargs.get("max_tokens", self.max_tokens),
                    "temperature": kwargs.get("temperature", self.temperature),
                    "top_p": kwargs.get("top_p", self.top_p)
                }
            elif "mistral" in self.model_id:
                request_body = {
                    "prompt": prompt,
                    "max_tokens": kwargs.get("max_tokens", self.max_tokens),
                    "temperature": kwargs.get("temperature", self.temperature),
                    "top_p": kwargs.get("top_p", self.top_p)
                }
            elif "cohere" in self.model_id:
                request_body = {
                    "prompt": prompt,
                    "max_tokens": kwargs.get("max_tokens", self.max_tokens),
                    "temperature": kwargs.get("temperature", self.temperature)
                }
            else:
                # Generic format for other models
                request_body = {
                    "prompt": prompt,
                    "max_tokens": kwargs.get("max_tokens", self.max_tokens),
                    "temperature": kwargs.get("temperature", self.temperature)
                }
            
            # Add retry logic for transient errors
            max_retries = 3
            retry_delay = 1  # seconds
            
            for attempt in range(max_retries):
                try:
                    # Set socket timeout
                    import socket
                    default_timeout = socket.getdefaulttimeout()
                    socket.setdefaulttimeout(timeout)
                    
                    # Invoke model
                    response = self.client.invoke_model(
                        modelId=self.model_id,
                        body=json.dumps(request_body)
                    )
                    
                    # Reset timeout to default
                    socket.setdefaulttimeout(default_timeout)
                    
                    # Parse response based on model type
                    response_body = json.loads(response.get("body").read())
                    
                    if "anthropic.claude" in self.model_id:
                        content = response_body.get("content", [])
                        text = ""
                        for item in content:
                            if item.get("type") == "text":
                                text += item.get("text", "")
                        return text
                    elif "amazon.titan" in self.model_id:
                        return response_body.get("results", [{}])[0].get("outputText", "")
                    elif "meta.llama" in self.model_id:
                        return response_body.get("generation", "")
                    elif "mistral" in self.model_id:
                        return response_body.get("outputs", [{}])[0].get("text", "")
                    elif "cohere" in self.model_id:
                        return response_body.get("text", "")
                    else:
                        # Generic parsing for other models
                        return str(response_body)
                    
                except socket.timeout:
                    if attempt < max_retries - 1:
                        self.logger.warning(f"Timeout on attempt {attempt + 1}/{max_retries}. Retrying in {retry_delay} seconds...")
                        time.sleep(retry_delay)
                        retry_delay *= 2  # Exponential backoff
                    else:
                        self.logger.error(f"Failed after {max_retries} attempts due to timeout")
                        raise RuntimeError(f"Request timed out after {max_retries} attempts")
                
                except Exception as e:
                    if attempt < max_retries - 1:
                        self.logger.warning(f"Error on attempt {attempt + 1}/{max_retries}: {str(e)}. Retrying in {retry_delay} seconds...")
                        time.sleep(retry_delay)
                        retry_delay *= 2  # Exponential backoff
                    else:
                        self.logger.error(f"Failed after {max_retries} attempts: {str(e)}")
                        raise RuntimeError(f"Failed to generate text after {max_retries} attempts: {str(e)}")
            
        except Exception as e:
            self.logger.error(f"Error generating text: {str(e)}")
            raise RuntimeError(f"Error generating text: {str(e)}")
    
    def analyze_image_architecture(self, image_path: str, image_content: str) -> str:
        """
        Analyze an architecture diagram image using Claude Vision and generate a Mermaid diagram.
           
        Args:
            image_path: Path to the architecture diagram image
            
        Returns:
            Mermaid diagram representation of the architecture
        """        
        if image_content:
            base64_string = image_content
            prefix = "data:image/png;base64,"
            if base64_string.startswith(prefix):
                # Remove the prefix
                base64_image = base64_string[len(prefix):]
        else:
        # Read the image file and encode it as base64
            with open(image_path, "rb") as image_file:
                base64_image = base64.b64encode(image_file.read()).decode('utf-8')
        
        # Create a prompt for Claude Vision
        prompt = f"""
You are an expert system architect analyzing an architecture diagram.

Please examine the provided architecture diagram image carefully and:
1. Identify all components, services, databases, and other elements
2. Determine the relationships and data flow between components
3. Create a detailed Mermaid diagram that accurately represents this architecture
4. Use specific component names from the image
5. Preserve the overall structure and layout of the original diagram
6. Include all connections and data flows shown in the original

7. Create a detailed Mermaid diagram that accurately represents this architecture:
   - Use specific component names from the image
   - Preserve the overall structure and layout of the original diagram
   - Include all connections and data flows shown in the original

Format your response with the detailed description first, followed by the Mermaid diagram code in a code block.
Use the appropriate Mermaid syntax (flowchart TD, classDiagram, etc.) that best represents this type of architecture.
"""
        
        # Add retry logic for transient errors
        max_retries = 3
        retry_delay = 1  # seconds
        timeout = 30  # seconds
        
        for attempt in range(max_retries):
            try:
                # Use Claude Vision to analyze the image with a timeout
                import socket
                default_timeout = socket.getdefaulttimeout()
                socket.setdefaulttimeout(timeout)
                
                self.logger.info(f"Analyzing architecture image (attempt {attempt+1}/{max_retries})")
                
                response = self.client.invoke_model(
                    modelId=self.model_id,
                    contentType="application/json",
                    accept="application/json",
                    body=json.dumps({
                        "anthropic_version": "bedrock-2023-05-31",
                        "max_tokens": 4096,
                        "messages": [
                            {
                                "role": "user",
                                "content": [
                                    {
                                        "type": "text",
                                        "text": prompt
                                    },
                                    {
                                        "type": "image",
                                        "source": {
                                            "type": "base64",
                                            "media_type": "image/jpeg",
                                            "data": base64_image
                                        }
                                    }
                                ]
                            }
                        ]
                    })
                )
                
                # Reset timeout to default
                socket.setdefaulttimeout(default_timeout)
                
                # Parse the response
                response_body = json.loads(response.get('body').read())
                full_response = response_body.get('content', [{}])[0].get('text', '')
                
                # Split the response into description and Mermaid diagram
                description = full_response
                mermaid_diagram = ""
                
                # Extract just the Mermaid code if it's wrapped in markdown code blocks
                if "```mermaid" in full_response:
                    parts = full_response.split("```mermaid", 1)
                    description = parts[0].strip()
                    mermaid_diagram = parts[1]
                    if "```" in mermaid_diagram:
                        mermaid_diagram = mermaid_diagram.split("```")[0].strip()
                
                self.logger.info(f"Successfully generated architecture description and Mermaid diagram from image")
                return {"description": description, "mermaid_diagram": mermaid_diagram}
                
            except socket.timeout:
                self.logger.warning(f"Timeout on attempt {attempt+1}/{max_retries} when analyzing image. Retrying in {retry_delay} seconds...")
                if attempt < max_retries - 1:
                    time.sleep(retry_delay)
                    retry_delay *= 2  # Exponential backoff
                else:
                    self.logger.error(f"Failed after {max_retries} attempts due to timeout")
                    raise TimeoutError(f"Image analysis timed out after {max_retries} attempts")
            
            except Exception as e:
                self.logger.warning(f"Error on attempt {attempt+1}/{max_retries}: {str(e)}. Retrying in {retry_delay} seconds...")
                if attempt < max_retries - 1:
                    time.sleep(retry_delay)
                    retry_delay *= 2  # Exponential backoff
                else:
                    self.logger.error(f"Failed after {max_retries} attempts: {str(e)}")
                    raise RuntimeError(f"Failed to analyze architecture image: {str(e)}")
        
        # This should never be reached due to the raise statements above
        raise RuntimeError("Failed to analyze architecture image after all retries") 