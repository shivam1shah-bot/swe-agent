"""
LangChain integration for workflow management.
"""

from typing import Dict, Any, List, Optional
try:
    # Try langchain 1.0+ imports with langchain-classic for compatibility
    from langchain_core.prompts import PromptTemplate
    from langchain_classic.chains import LLMChain
    from langchain_classic.memory import ConversationBufferMemory, ConversationBufferWindowMemory
    from langchain_community.llms import Bedrock
except ImportError as e1:
    try:
        # Try langchain 0.x imports (using langchain package directly)
        from langchain.prompts import PromptTemplate
        from langchain.chains import LLMChain
        from langchain.memory import ConversationBufferMemory, ConversationBufferWindowMemory
        from langchain_community.llms import Bedrock
    except ImportError as e2:
        # Final fallback - just use what we can
        from langchain_core.prompts import PromptTemplate
        LLMChain = None
        ConversationBufferMemory = None
        ConversationBufferWindowMemory = None
        from langchain_community.llms import Bedrock
from src.providers.logger import Logger
from src.api.dependencies import get_logger
logger = get_logger("langchain-manager")

class LangChainManager:
    """
    Manager for LangChain integration and workflow management.
    """
    
    def __init__(self, config: Dict[str, Any]):
        """
        Initialize the LangChain manager.
        
        Args:
            config: Configuration dictionary
        """
        self.config = config
        
        # Initialize Bedrock LLM for LangChain
        self.llm = Bedrock(
            model_id=config["aws"]["bedrock_model_id"],
            client=self._get_bedrock_client(),
            model_kwargs={
                "temperature": config["aws"]["temperature"],
                "max_tokens_to_sample": config["aws"]["max_tokens"]
            }
        )
        
        # Set up memory if enabled
        self.memory = None
        if config["langchain"]["use_memory"]:
            self._setup_memory()
        
        logger.info("Initialized LangChain manager")
    
    def _get_bedrock_client(self):
        """
        Get a Bedrock client for LangChain.
        
        Returns:
            Bedrock client
        """
        import boto3
        return boto3.client(
            service_name="bedrock-runtime",
            region_name=self.config["aws"]["region"]
        )
    
    def _setup_memory(self):
        """Set up the memory component based on configuration."""
        memory_type = self.config["langchain"]["memory_type"]
        token_limit = self.config["langchain"]["memory_token_limit"]
        
        if memory_type == "buffer":
            self.memory = ConversationBufferMemory(
                memory_key="chat_history",
                return_messages=True
            )
        elif memory_type == "buffer_window":
            self.memory = ConversationBufferWindowMemory(
                memory_key="chat_history",
                k=5,  # Remember last 5 interactions
                return_messages=True
            )
        else:
            logger.warning(f"Unsupported memory type: {memory_type}, using buffer memory")
            self.memory = ConversationBufferMemory(
                memory_key="chat_history",
                return_messages=True
            )
    
    def create_chain(self, prompt_template: str, output_key: str = "text") -> LLMChain:
        """
        Create a LangChain chain with the specified prompt template.
        
        Args:
            prompt_template: The prompt template string
            output_key: The key for the chain output
            
        Returns:
            LLMChain instance
        """
        prompt = PromptTemplate.from_template(prompt_template)
        
        chain_kwargs = {
            "llm": self.llm,
            "prompt": prompt,
            "output_key": output_key,
            "verbose": True
        }
        
        if self.memory:
            chain_kwargs["memory"] = self.memory
        
        return LLMChain(**chain_kwargs)
    
    def create_chain_from_file(self, template_path: str, output_key: str = "text") -> LLMChain:
        """
        Create a LangChain chain from a template file.
        
        Args:
            template_path: Path to the prompt template file
            output_key: The key for the chain output
            
        Returns:
            LLMChain instance
        """
        try:
            with open(template_path, 'r') as file:
                template_content = file.read()
            
            return self.create_chain(template_content, output_key)
        except Exception as e:
            logger.error(f"Error creating chain from file {template_path}: {str(e)}")
            raise 