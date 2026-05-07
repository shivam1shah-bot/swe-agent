"""
Google ADK agent adapter for streaming.

Provides a streaming interface for Google ADK agents, converting ADK events
to generic streaming events that can be consumed by any transport layer.
"""

import uuid
import importlib
from datetime import datetime
from typing import AsyncGenerator, Dict, Any, Optional

from .base_agent import BaseStreamingAgent
from src.models.streaming.event import EventTypes

try:
    from src.providers.logger import get_logger
    logger = get_logger(__name__)
except ImportError:
    import logging
    logger = logging.getLogger(__name__)


class ADKAgentAdapter(BaseStreamingAgent):
    """
    Google ADK agent adapter for streaming sessions.
    
    This adapter wraps Google ADK agents and converts their events into
    standardized streaming events that can be consumed by any transport layer.
    """
    
    def __init__(self, agent_module_path: str, agent_config: Optional[Dict[str, Any]] = None):
        """
        Initialize ADK agent adapter.
        
        Args:
            agent_module_path: Python module path to the ADK agent (e.g., 'src.agents.google_adk.trino_agent')
            agent_config: Optional agent-specific configuration
        """
        self.agent_module_path = agent_module_path
        self.agent_config = agent_config or {}
        self.agent = None
        self.agent_info = None
        self._initialized = False
        
        logger.info(f"Created ADK agent adapter for module: {agent_module_path}")
    
    async def initialize(self, config: Dict[str, Any]) -> None:
        """
        Initialize the ADK agent.
        
        Args:
            config: Configuration for the agent
            
        Raises:
            RuntimeError: If agent initialization fails
        """
        try:
            logger.info(f"Initializing ADK agent from module: {self.agent_module_path}")
            
            # Import the agent module
            module = importlib.import_module(self.agent_module_path)
            
            # Get the root_agent from the module
            if hasattr(module, 'root_agent'):
                self.agent = module.root_agent
            elif hasattr(module, 'create_trino_agent'):
                # Fallback for trino agent
                self.agent = module.create_trino_agent()
            else:
                raise RuntimeError(f"No root_agent or create_*_agent function found in {self.agent_module_path}")
            
            if self.agent is None:
                raise RuntimeError(f"Agent initialization returned None for {self.agent_module_path}")
            
            # Store agent info
            self.agent_info = self._extract_agent_info()
            self._initialized = True
            
            logger.info(f"Successfully initialized ADK agent: {self.agent_info.get('name', 'unknown')}")
            
        except Exception as e:
            logger.error(f"Failed to initialize ADK agent from {self.agent_module_path}: {e}")
            raise RuntimeError(f"ADK agent initialization failed: {e}")
    
    async def process_message(self, message: str, context: Dict[str, Any]) -> AsyncGenerator[Dict[str, Any], None]:
        """
        Process message through ADK agent and yield streaming events.
        
        Args:
            message: User message to process
            context: Session context
            
        Yields:
            Dict[str, Any]: Streaming events
            
        Raises:
            RuntimeError: If agent is not initialized or processing fails
        """
        if not self._initialized or self.agent is None:
            raise RuntimeError("ADK agent not initialized. Call initialize() first.")
        
        try:
            logger.info(f"Processing message through ADK agent: {message[:100]}...")
            
            turn_id = str(uuid.uuid4())
            start_time = datetime.utcnow()
            
                        # Import ADK components with path filtering to avoid conflicts
            import sys
            original_path = sys.path.copy()
            try:
                sys.path = [p for p in sys.path if p != '/app']
                from google.adk import Runner
                from google.adk.sessions import InMemorySessionService
                from google.genai import types
            finally:
                # Restore original path
                sys.path = original_path
            
            # Create session service and runner
            session_service = InMemorySessionService()
            app_name = "swe-agent-knowledge-agents"
            
            # Get session information from context
            session_id = context.get("session_id", "default_session")
            user_id = context.get("user_id", "default_user")
            
            # Create session in ADK session service
            adk_session = await session_service.create_session(
                app_name=app_name,
                user_id=user_id,
                session_id=session_id
            )
            logger.info(f"Created ADK session: {adk_session.id}")
            
            runner = Runner(
                app_name=app_name,
                agent=self.agent,
                session_service=session_service
            )
            
            # Create Content object from message string
            part = types.Part(text=message)
            content = types.Content(parts=[part], role="user")
            
            logger.info(f"Running ADK agent with session_id={session_id}, user_id={user_id}")
            
            # Process through ADK agent
            async for event in runner.run_async(
                user_id=user_id,
                session_id=session_id,
                new_message=content
            ):
                # Debug: Log all events from ADK
                logger.info(f"ADK Event received: type={type(event)}, dir={dir(event)}")
                if hasattr(event, '__dict__'):
                    logger.info(f"ADK Event attributes: {event.__dict__}")
                
                # Try to handle different ADK event formats
                event_data = None
                event_type_str = None
                
                # Check for different event formats
                if hasattr(event, 'type') and hasattr(event, 'data'):
                    event_type_str = event.type
                    event_data = event.data
                    logger.info(f"ADK Event format 1: type={event_type_str}, data={event_data}")
                elif hasattr(event, 'event_type'):
                    event_type_str = event.event_type
                    event_data = getattr(event, 'data', event)
                    logger.info(f"ADK Event format 2: event_type={event_type_str}, data={event_data}")
                else:
                    # Check if this is a Content object with function calls/responses
                    if self._is_tool_event(event):
                        # Determine if it's a function call or response
                        if self._has_function_call(event):
                            event_type_str = "function_call"
                        elif self._has_function_response(event):
                            event_type_str = "function_response"
                        else:
                            event_type_str = "tool_call"
                        event_data = event
                        logger.info(f"ADK Tool Event: type={event_type_str}, event={event}")
                    else:
                        # Try to extract from event directly
                        event_type_str = str(type(event).__name__).lower()
                        event_data = event
                        logger.info(f"ADK Event format 3: inferred_type={event_type_str}, event={event}")
                
                # Always try to extract text content regardless of event format
                text_content = self._extract_text_from_adk_event(event)
                logger.info(f"ADK Event text extracted: {text_content}")
                
                # If we have text content, yield a message event
                if text_content and text_content.strip():
                    logger.info(f"Yielding agent message: {text_content[:100]}...")
                    yield {
                        "event_type": EventTypes.AGENT_MESSAGE,
                        "data": {
                            "content": text_content,
                            "content_type": "text",
                            "partial": False,
                            "turn_id": turn_id
                        },
                        "timestamp": self._get_timestamp(),
                        "turn_complete": False
                    }
                
                # Convert ADK events to our streaming format (original logic)
                if event_type_str:
                    converted_event_type = self._convert_adk_event_type(event_type_str)
                    
                    if converted_event_type == EventTypes.TOOL_EXECUTION_START:
                        # Handle tool call events
                        tool_data = self._extract_tool_data_from_adk_event(event)
                        if tool_data:
                            logger.info(f"Yielding tool execution start: {tool_data}")
                            yield {
                                "event_type": converted_event_type,
                                "data": {
                                    "tool_name": tool_data.get("name", "unknown"),
                                    "tool_args": tool_data.get("arguments", {}),
                                    "turn_id": turn_id
                                },
                                "timestamp": self._get_timestamp(),
                                "turn_complete": False
                            }
                    
                    elif converted_event_type == EventTypes.TOOL_EXECUTION_COMPLETE:
                        # Handle tool response events
                        tool_response = self._extract_tool_response_from_adk_event(event)
                        if tool_response:
                            yield {
                                "event_type": converted_event_type,
                                "data": {
                                    "tool_response": tool_response,
                                    "turn_id": turn_id
                                },
                                "timestamp": self._get_timestamp(),
                                "turn_complete": False
                            }
            
            # Signal turn completion
            end_time = datetime.utcnow()
            execution_time = (end_time - start_time).total_seconds()
            
            yield {
                "event_type": EventTypes.TURN_COMPLETE,
                "data": {
                    "turn_id": turn_id,
                    "execution_time": execution_time,
                    "agent_id": self.agent_info.get("id") if self.agent_info else "unknown"
                },
                "timestamp": self._get_timestamp(),
                "turn_complete": True
            }
            
            logger.info(f"ADK agent processing completed in {execution_time:.2f}s")
            
        except Exception as e:
            logger.error(f"Error processing message through ADK agent: {e}", exc_info=True)
            
            # Yield error event
            yield {
                "event_type": EventTypes.ERROR,
                "data": {
                    "error": str(e),
                    "turn_id": turn_id if 'turn_id' in locals() else str(uuid.uuid4())
                },
                "timestamp": self._get_timestamp(),
                "turn_complete": True
            }
            
            raise
    
    def get_agent_info(self) -> Dict[str, Any]:
        """
        Get information about the ADK agent.
        
        Returns:
            Dict[str, Any]: Agent metadata
        """
        if self.agent_info:
            return self.agent_info
        
        # Return minimal info if not initialized
        return {
            "id": self.agent_module_path.split('.')[-1],
            "name": self.agent_module_path.split('.')[-1].replace('_', ' ').title(),
            "framework": "google_adk",
            "module_path": self.agent_module_path,
            "initialized": self._initialized
        }
    
    async def cleanup(self) -> None:
        """Clean up ADK agent resources."""
        if self.agent:
            try:
                # ADK agents typically don't require explicit cleanup
                # but we can add it here if needed in the future
                logger.info("Cleaning up ADK agent resources")
                self.agent = None
                self._initialized = False
            except Exception as e:
                logger.warning(f"Error during ADK agent cleanup: {e}")
    
    def _extract_agent_info(self) -> Dict[str, Any]:
        """
        Extract information from the ADK agent.
        
        Returns:
            Dict[str, Any]: Agent information
        """
        try:
            # Try to get info from the agent object
            agent_name = "Unknown Agent"
            agent_id = self.agent_module_path.split('.')[-1]
            
            # Try to get name from agent attributes
            if hasattr(self.agent, 'name'):
                agent_name = self.agent.name
            elif hasattr(self.agent, '_name'):
                agent_name = self.agent._name
                
            # For trino agent specifically
            if 'trino' in self.agent_module_path.lower():
                agent_name = "Trino Data Assistant"
                capabilities = ["data_query", "data_analysis", "sql_execution"]
            else:
                capabilities = ["general_assistance"]
            
            return {
                "id": agent_id,
                "name": agent_name,
                "description": f"Google ADK agent for {agent_name.lower()}",
                "framework": "google_adk",
                "module_path": self.agent_module_path,
                "capabilities": capabilities,
                "transport_support": ["sse"],
                "initialized": True
            }
            
        except Exception as e:
            logger.warning(f"Failed to extract agent info: {e}")
            return {
                "id": self.agent_module_path.split('.')[-1],
                "name": "ADK Agent",
                "framework": "google_adk",
                "module_path": self.agent_module_path,
                "error": str(e)
            }
    
    def _get_timestamp(self) -> str:
        """
        Get current timestamp in ISO format.
        
        Returns:
            str: ISO formatted timestamp
        """
        return datetime.utcnow().isoformat() + "Z"
    
    def _convert_adk_event_type(self, adk_event_type: str) -> str:
        """
        Convert ADK event type to our streaming event type.
        
        Args:
            adk_event_type: ADK event type string
            
        Returns:
            str: Corresponding streaming event type
        """
        # Map ADK event types to our streaming event types
        event_type_mapping = {
            "agent_message": EventTypes.AGENT_MESSAGE,
            "tool_call": EventTypes.TOOL_EXECUTION_START,
            "tool_response": EventTypes.TOOL_EXECUTION_COMPLETE,
            "function_call": EventTypes.TOOL_EXECUTION_START,
            "function_response": EventTypes.TOOL_EXECUTION_COMPLETE,
            "message": EventTypes.AGENT_MESSAGE,
            "content": EventTypes.AGENT_MESSAGE,
        }
        
        return event_type_mapping.get(adk_event_type.lower(), EventTypes.AGENT_MESSAGE)
    
    def _is_tool_event(self, event) -> bool:
        """
        Check if event contains ONLY tool calls or responses (not mixed with text).
        
        Args:
            event: ADK event object
            
        Returns:
            bool: True if event contains ONLY tool calls/responses
        """
        try:
            has_tool_content = False
            has_text_content = False
            
            # Check for function_call/response in Content parts
            if hasattr(event, 'content') and hasattr(event.content, 'parts'):
                for part in event.content.parts:
                    if hasattr(part, 'function_call') or hasattr(part, 'function_response'):
                        has_tool_content = True
                    if hasattr(part, 'text') and part.text and part.text.strip():
                        has_text_content = True
            
            # Check for function_call/response in data parts  
            if hasattr(event, 'data') and hasattr(event.data, 'parts'):
                for part in event.data.parts:
                    if hasattr(part, 'function_call') or hasattr(part, 'function_response'):
                        has_tool_content = True
                    if hasattr(part, 'text') and part.text and part.text.strip():
                        has_text_content = True
            
            # Check for direct function call attributes
            if hasattr(event, 'function_call') or hasattr(event, 'function_response'):
                has_tool_content = True
                
            if hasattr(event, 'data'):
                if hasattr(event.data, 'function_call') or hasattr(event.data, 'function_response'):
                    has_tool_content = True
            
            # Only consider it a tool event if it has tool content AND no text content
            # If it has both, prioritize text extraction
            return has_tool_content and not has_text_content
            
        except Exception as e:
            logger.warning(f"Error checking if event is tool event: {e}")
            return False
    
    def _has_function_call(self, event) -> bool:
        """Check if event has function_call."""
        try:
            if hasattr(event, 'content') and hasattr(event.content, 'parts'):
                for part in event.content.parts:
                    if hasattr(part, 'function_call'):
                        return True
            if hasattr(event, 'data') and hasattr(event.data, 'parts'):
                for part in event.data.parts:
                    if hasattr(part, 'function_call'):
                        return True
            return False
        except Exception:
            return False
    
    def _has_function_response(self, event) -> bool:
        """Check if event has function_response."""
        try:
            if hasattr(event, 'content') and hasattr(event.content, 'parts'):
                for part in event.content.parts:
                    if hasattr(part, 'function_response'):
                        return True
            if hasattr(event, 'data') and hasattr(event.data, 'parts'):
                for part in event.data.parts:
                    if hasattr(part, 'function_response'):
                        return True
            return False
        except Exception:
            return False
    
    def _extract_text_from_adk_event(self, event) -> Optional[str]:
        """
        Extract text content from ADK event.
        
        Args:
            event: ADK event object
            
        Returns:
            Optional[str]: Extracted text content
        """
        try:
            # First check if this event contains tool calls/responses - if so, skip text extraction
            if self._is_tool_event(event):
                logger.info("Event contains tool call/response, skipping text extraction")
                return None
            
            # Check if event has content with parts (standard ADK format)
            if hasattr(event, 'content') and hasattr(event.content, 'parts'):
                for part in event.content.parts:
                    if hasattr(part, 'text') and part.text:
                        logger.info(f"Found text in event.content.parts: {part.text[:100]}...")
                        return part.text
            
            # Check if event has data with parts (Content format)
            if hasattr(event, 'data') and hasattr(event.data, 'parts'):
                for part in event.data.parts:
                    if hasattr(part, 'text') and part.text:
                        logger.info(f"Found text in event.data.parts: {part.text[:100]}...")
                        return part.text
            
            # Check if event has direct text field
            if hasattr(event, 'text'):
                logger.info(f"Found text in event.text: {event.text[:100]}...")
                return event.text
            
            # Check if event.data has text
            if hasattr(event, 'data') and hasattr(event.data, 'text'):
                logger.info(f"Found text in event.data.text: {event.data.text[:100]}...")
                return event.data.text
            
            # Check if event.content is a string
            if hasattr(event, 'content') and isinstance(event.content, str):
                logger.info(f"Found string content: {event.content[:100]}...")
                return event.content
            
            # Don't fallback to string conversion - this causes tool calls to appear as text
            logger.info("No text content found in event")
            return None
                
        except Exception as e:
            logger.warning(f"Failed to extract text from ADK event: {e}")
        
        return None
    
    def _extract_tool_data_from_adk_event(self, event) -> Optional[Dict[str, Any]]:
        """
        Extract tool call data from ADK event.
        
        Args:
            event: ADK event object
            
        Returns:
            Optional[Dict[str, Any]]: Tool call data
        """
        try:
            # Check for function_call in Content parts
            if hasattr(event, 'content') and hasattr(event.content, 'parts'):
                for part in event.content.parts:
                    if hasattr(part, 'function_call'):
                        func_call = part.function_call
                        return {
                            "name": getattr(func_call, 'name', 'unknown'),
                            "arguments": getattr(func_call, 'args', {})
                        }
            
            # Check for function_call in data parts
            if hasattr(event, 'data') and hasattr(event.data, 'parts'):
                for part in event.data.parts:
                    if hasattr(part, 'function_call'):
                        func_call = part.function_call
                        return {
                            "name": getattr(func_call, 'name', 'unknown'),
                            "arguments": getattr(func_call, 'args', {})
                        }
            
            # Check for function_call in event data
            if hasattr(event, 'data') and hasattr(event.data, 'function_call'):
                func_call = event.data.function_call
                return {
                    "name": getattr(func_call, 'name', 'unknown'),
                    "arguments": getattr(func_call, 'args', {})
                }
            
            # Check for tool_call in event data
            if hasattr(event, 'data') and hasattr(event.data, 'tool_call'):
                tool_call = event.data.tool_call
                return {
                    "name": getattr(tool_call, 'name', 'unknown'),
                    "arguments": getattr(tool_call, 'arguments', {})
                }
            
            # Check if event has direct tool information
            if hasattr(event, 'tool_name'):
                return {
                    "name": event.tool_name,
                    "arguments": getattr(event, 'tool_args', {})
                }
                
        except Exception as e:
            logger.warning(f"Failed to extract tool data from ADK event: {e}")
        
        return None
    
    def _extract_tool_response_from_adk_event(self, event) -> Optional[str]:
        """
        Extract tool response from ADK event.
        
        Args:
            event: ADK event object
            
        Returns:
            Optional[str]: Tool response content
        """
        try:
            # Check for function_response in Content parts
            if hasattr(event, 'content') and hasattr(event.content, 'parts'):
                for part in event.content.parts:
                    if hasattr(part, 'function_response'):
                        func_response = part.function_response
                        if hasattr(func_response, 'response'):
                            return str(func_response.response)
                        return str(func_response)
            
            # Check for function_response in data parts
            if hasattr(event, 'data') and hasattr(event.data, 'parts'):
                for part in event.data.parts:
                    if hasattr(part, 'function_response'):
                        func_response = part.function_response
                        if hasattr(func_response, 'response'):
                            return str(func_response.response)
                        return str(func_response)
            
            # Check for function_response in event data
            if hasattr(event, 'data') and hasattr(event.data, 'function_response'):
                func_response = event.data.function_response
                if hasattr(func_response, 'response'):
                    return str(func_response.response)
                return str(func_response)
            
            # Check for tool_response in event data
            if hasattr(event, 'data') and hasattr(event.data, 'tool_response'):
                return str(event.data.tool_response)
            
            # Check if event has direct response
            if hasattr(event, 'response'):
                return str(event.response)
                
        except Exception as e:
            logger.warning(f"Failed to extract tool response from ADK event: {e}")
        
        return None
