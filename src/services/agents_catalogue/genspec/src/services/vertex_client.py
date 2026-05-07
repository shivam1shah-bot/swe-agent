"""
Google Cloud Vertex AI client for Claude 4.5 Sonnet.
"""

import json
import os
import time
import base64
from typing import Dict, Any, Optional, List
from google.cloud import aiplatform
from anthropic import AnthropicVertex
from src.utils.google_cloud_auth import initialize_google_cloud_auth_from_config


class VertexClient:
    """
    Client for interacting with Claude 4.5 Sonnet on Google Cloud Vertex AI.
    """

    def __init__(self, config: Dict[str, Any]):
        """
        Initialize the Vertex AI client.
        
        Args:
            config: Configuration dictionary
        """
        # Simple logger replacement
        self.config = config
        self.available_models = []

        # Extract GCP configuration
        gcp_config = config.get("gcp", {}) or config.get("vertex_ai", {})
        
        # Get project_id and region
        self.project_id = (
            gcp_config.get("project_id") or 
            os.environ.get("GOOGLE_CLOUD_PROJECT") or
            os.environ.get("GCP_PROJECT")
        )
        
        self.region = gcp_config.get("region", "us-east5")

        if not self.project_id:
            raise ValueError("project_id is required. Set it in config or GOOGLE_CLOUD_PROJECT environment variable")

        # Set up Google Cloud credentials before initializing Vertex AI
        initialize_google_cloud_auth_from_config(config)

        try:
            # Initialize Vertex AI
            aiplatform.init(project=self.project_id, location=self.region)
            print(f"Initialized Vertex AI with project: {self.project_id}, region: {self.region}")

            # Initialize Anthropic Vertex client
            self.client = AnthropicVertex(
                project_id=self.project_id,
                region=self.region
            )
            print("Created Anthropic Vertex AI client")

            # Set available Claude models on Vertex AI (these are the model IDs)
            # Note: This model must be enabled in your GCP project through Model Garden
            self.available_models = [
                "claude-sonnet-4-5@20250929",    # Claude 4.5 Sonnet
            ]

            # Use the model specified in config or default to Claude 4.5 Sonnet
            self.model_id = (
                gcp_config.get("model_id") or 
                config.get("model_id") or 
                "claude-sonnet-4-5@20250929"
            )

            # Check if the model is in the available models
            if self.model_id not in self.available_models:
                print(f"Warning: Specified model {self.model_id} not in available models list.")
                print(f"Available models: {', '.join(self.available_models)}")

            # Optionally test access (can be skipped with test_access=False in config)
            test_access = gcp_config.get("test_access", config.get("test_access", False))
            
            if test_access:
                print(f"Testing access to model: {self.model_id}")
                try:
                    self._test_model_access(self.model_id)
                    print(f"✓ Successfully accessed model: {self.model_id}")
                except Exception as test_error:
                    print(f"\n⚠️  Warning: Could not access model {self.model_id}")
                    print(f"Error: {str(test_error)[:200]}")
                    print("\nTo enable Claude models in your GCP project:")
                    print(f"1. Visit: https://console.cloud.google.com/vertex-ai/publishers/anthropic/model-garden")
                    print(f"2. Select the model you want to use")
                    print(f"3. Click 'ENABLE' to add it to your project")
                    print(f"4. Wait a few minutes for the model to be provisioned")
                    print("\nContinuing without model test...")
            else:
                print(f"Using model: {self.model_id} (skipping access test)")

            # Get other parameters
            self.max_tokens = gcp_config.get("max_tokens", config.get("max_tokens", 4096))
            self.temperature = gcp_config.get("temperature", config.get("temperature", 0.7))
            self.top_p = gcp_config.get("top_p", config.get("top_p", 0.9))

            print(f"✓ Initialized Vertex AI client")

        except Exception as e:
            print(f"Failed to initialize Vertex AI client: {str(e)}")
            if "404" in str(e) or "NOT_FOUND" in str(e):
                print("\n⚠️  Claude models may not be enabled in your GCP project.")
                print("To enable them:")
                print("1. Visit: https://console.cloud.google.com/vertex-ai/publishers/anthropic/model-garden")
                print("2. Enable the Claude models you want to use")
                print("3. Wait for provisioning to complete")
            raise ValueError(f"Failed to initialize Vertex AI client: {str(e)}")

    def _test_model_access(self, model_id):
        """
        Test if we can access the model by sending a simple request.
        
        Args:
            model_id: The model ID to test
        """
        try:
            print(f"Testing model {model_id} with a simple request")

            response = self.client.messages.create(
                model=model_id,
                max_tokens=10,
                messages=[
                    {
                        "role": "user",
                        "content": "Say hello"
                    }
                ]
            )

            # If we get here, the model is accessible
            print(f"Successfully tested model {model_id}")
            return True
        except Exception as e:
            print(f"Error testing model {model_id}: {str(e)}")
            raise

    def list_available_models(self) -> List[str]:
        """
        List available Claude models in Vertex AI.
        
        Returns:
            List of available model IDs
        """
        # Return the hardcoded list of available models
        return self.available_models

    def generate_text(self, prompt: str, **kwargs) -> str:
        """
        Generate text using the Vertex AI Claude model.
        
        Args:
            prompt: The prompt to send to the model
            **kwargs: Additional parameters for the model
                - max_tokens: Maximum number of tokens to generate
                - temperature: Temperature for sampling (higher = more creative)
                - top_p: Top-p sampling parameter (note: cannot be used with temperature)
            
        Returns:
            Generated text
        """
        try:
            # Add retry logic for transient errors
            max_retries = 3
            retry_delay = 1  # seconds

            for attempt in range(max_retries):
                try:
                    # Build request parameters
                    # Note: Claude 4.5 doesn't allow both temperature and top_p
                    request_params = {
                        "model": self.model_id,
                        "max_tokens": kwargs.get("max_tokens", self.max_tokens),
                        "messages": [
                            {
                                "role": "user",
                                "content": prompt
                            }
                        ]
                    }
                    
                    # Use either temperature or top_p, not both
                    if "top_p" in kwargs:
                        request_params["top_p"] = kwargs["top_p"]
                    elif "temperature" in kwargs:
                        request_params["temperature"] = kwargs["temperature"]
                    else:
                        # Default to temperature only
                        request_params["temperature"] = self.temperature
                    
                    # Create message request
                    response = self.client.messages.create(**request_params)

                    # Extract text from response
                    text = ""
                    for content_block in response.content:
                        if hasattr(content_block, 'text'):
                            text += content_block.text
                    
                    return text

                except Exception as e:
                    if attempt < max_retries - 1:
                        print(f"Error on attempt {attempt + 1}/{max_retries}: {str(e)}. Retrying in {retry_delay} seconds...")
                        time.sleep(retry_delay)
                        retry_delay *= 2  # Exponential backoff
                    else:
                        print(f"Failed after {max_retries} attempts: {str(e)}")
                        raise RuntimeError(f"Failed to generate text after {max_retries} attempts: {str(e)}")

        except Exception as e:
            print(f"Error generating text: {str(e)}")
            raise RuntimeError(f"Error generating text: {str(e)}")

    def analyze_image_architecture(self, image_path: str, image_content: str = None) -> Dict[str, str]:
        """
        Analyze an architecture diagram image using Claude Vision and generate a Mermaid diagram.
           
        Args:
            image_path: Path to the architecture diagram image
            image_content: Optional base64 encoded image content
            
        Returns:
            Dictionary with description and mermaid_diagram keys
        """        
        if image_content:
            base64_string = image_content
            prefix = "data:image/png;base64,"
            if base64_string.startswith(prefix):
                # Remove the prefix
                base64_image = base64_string[len(prefix):]
            else:
                base64_image = base64_string
        else:
            # Read the image file and encode it as base64
            with open(image_path, "rb") as image_file:
                base64_image = base64.b64encode(image_file.read()).decode('utf-8')

        # Determine media type from file extension or default to jpeg
        if image_path:
            if image_path.lower().endswith('.png'):
                media_type = "image/png"
            elif image_path.lower().endswith(('.jpg', '.jpeg')):
                media_type = "image/jpeg"
            elif image_path.lower().endswith('.webp'):
                media_type = "image/webp"
            elif image_path.lower().endswith('.gif'):
                media_type = "image/gif"
            else:
                media_type = "image/jpeg"
        else:
            media_type = "image/jpeg"

        # Create a prompt for Claude Vision
        prompt_text = """
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

        for attempt in range(max_retries):
            try:
                print(f"Analyzing architecture image (attempt {attempt+1}/{max_retries})")

                # Use Claude Vision to analyze the image
                response = self.client.messages.create(
                    model=self.model_id,
                    max_tokens=4096,
                    messages=[
                        {
                            "role": "user",
                            "content": [
                                {
                                    "type": "text",
                                    "text": prompt_text
                                },
                                {
                                    "type": "image",
                                    "source": {
                                        "type": "base64",
                                        "media_type": media_type,
                                        "data": base64_image
                                    }
                                }
                            ]
                        }
                    ]
                )

                # Extract text from response
                full_response = ""
                for content_block in response.content:
                    if hasattr(content_block, 'text'):
                        full_response += content_block.text

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

                print(f"Successfully generated architecture description and Mermaid diagram from image")
                return {"description": description, "mermaid_diagram": mermaid_diagram}

            except Exception as e:
                print(f"Error on attempt {attempt+1}/{max_retries}: {str(e)}. Retrying in {retry_delay} seconds...")
                if attempt < max_retries - 1:
                    time.sleep(retry_delay)
                    retry_delay *= 2  # Exponential backoff
                else:
                    print(f"Failed after {max_retries} attempts: {str(e)}")
                    raise RuntimeError(f"Failed to analyze architecture image: {str(e)}")

        # This should never be reached due to the raise statements above
        raise RuntimeError("Failed to analyze architecture image after all retries") 