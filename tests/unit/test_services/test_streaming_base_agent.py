"""
Unit tests for BaseStreamingAgent.

Tests for the base streaming agent abstract interface and concrete methods.
"""

import pytest
from abc import ABC
from typing import AsyncGenerator, Dict, Any
from unittest.mock import Mock, AsyncMock

from src.services.streaming.agents.base_agent import BaseStreamingAgent


class TestStreamingAgent(BaseStreamingAgent):
    """Test implementation of BaseStreamingAgent for testing."""
    
    def __init__(self, agent_info: Dict[str, Any] = None):
        """Initialize test agent with optional agent info."""
        self._agent_info = agent_info or {
            "id": "test_agent",
            "name": "Test Agent",
            "description": "A test agent implementation",
            "framework": "test_framework",
            "capabilities": ["test_capability_1", "test_capability_2"],
            "version": "1.0.0"
        }
        self._initialized = False
        self._cleanup_called = False
    
    async def process_message(self, message: str, context: Dict[str, Any]) -> AsyncGenerator[Dict[str, Any], None]:
        """Test implementation of process_message."""
        if not self._initialized:
            raise RuntimeError("Agent not initialized")
        
        # Simulate processing events
        yield {
            "event_type": "tool_execution_start",
            "data": {"tool_name": "test_tool", "message": message},
            "timestamp": "2023-01-01T12:00:00Z",
            "turn_complete": False
        }
        
        yield {
            "event_type": "agent_message", 
            "data": {"content": f"Processed: {message}"},
            "timestamp": "2023-01-01T12:00:01Z",
            "turn_complete": False
        }
        
        yield {
            "event_type": "turn_complete",
            "data": {},
            "timestamp": "2023-01-01T12:00:02Z",
            "turn_complete": True
        }
    
    def get_agent_info(self) -> Dict[str, Any]:
        """Test implementation of get_agent_info."""
        return self._agent_info
    
    async def initialize(self, config: Dict[str, Any]) -> None:
        """Test implementation of initialize."""
        if config.get("fail_init"):
            raise RuntimeError("Initialization failed")
        self._initialized = True
    
    async def cleanup(self) -> None:
        """Test implementation of cleanup."""
        if self._agent_info.get("fail_cleanup"):
            raise RuntimeError("Cleanup failed")
        self._cleanup_called = True
        self._initialized = False


class FailingTestAgent(BaseStreamingAgent):
    """Test agent that raises errors for testing error handling."""
    
    async def process_message(self, message: str, context: Dict[str, Any]) -> AsyncGenerator[Dict[str, Any], None]:
        """Always raises an error."""
        raise ValueError("Processing failed")
        yield  # This makes it an async generator (unreachable but required for type)
    
    def get_agent_info(self) -> Dict[str, Any]:
        """Always raises an error."""
        raise RuntimeError("Info retrieval failed")
    
    async def initialize(self, config: Dict[str, Any]) -> None:
        """Always raises an error."""
        raise ValueError("Initialization failed")


@pytest.mark.unit
class TestBaseStreamingAgentInterface:
    """Test cases for BaseStreamingAgent abstract interface."""
    
    def test_base_agent_is_abstract(self):
        """Test that BaseStreamingAgent is an abstract base class."""
        assert issubclass(BaseStreamingAgent, ABC)
        
        # Should not be able to instantiate directly
        with pytest.raises(TypeError):
            BaseStreamingAgent()
    
    def test_abstract_methods_defined(self):
        """Test that required abstract methods are defined."""
        abstract_methods = BaseStreamingAgent.__abstractmethods__
        
        expected_methods = {
            'process_message',
            'get_agent_info', 
            'initialize'
        }
        
        assert abstract_methods == expected_methods
    
    def test_concrete_implementation_works(self):
        """Test that concrete implementation can be instantiated."""
        agent = TestStreamingAgent()
        assert isinstance(agent, BaseStreamingAgent)
    
    def test_incomplete_implementation_fails(self):
        """Test that incomplete implementations fail to instantiate."""
        # Create a class that doesn't implement all abstract methods
        class IncompleteAgent(BaseStreamingAgent):
            def get_agent_info(self) -> Dict[str, Any]:
                return {}
            
            # Missing process_message and initialize
        
        with pytest.raises(TypeError):
            IncompleteAgent()


@pytest.mark.unit
@pytest.mark.asyncio
class TestBaseStreamingAgentConcreteMethods:
    """Test cases for concrete methods in BaseStreamingAgent."""
    
    async def test_cleanup_default_implementation(self):
        """Test that default cleanup implementation does nothing."""
        agent = TestStreamingAgent()
        
        # Default cleanup should not raise an error
        await agent.cleanup()
    
    def test_get_supported_capabilities(self):
        """Test getting supported capabilities from agent info."""
        agent_info = {
            "id": "capability_test_agent",
            "name": "Capability Test Agent", 
            "capabilities": ["capability_1", "capability_2", "capability_3"]
        }
        agent = TestStreamingAgent(agent_info)
        
        capabilities = agent.get_supported_capabilities()
        
        assert capabilities == ["capability_1", "capability_2", "capability_3"]
    
    def test_get_supported_capabilities_empty(self):
        """Test getting capabilities when none are defined."""
        agent_info = {
            "id": "no_caps_agent",
            "name": "No Capabilities Agent"
            # No capabilities field
        }
        agent = TestStreamingAgent(agent_info)
        
        capabilities = agent.get_supported_capabilities()
        
        assert capabilities == []
    
    def test_supports_capability_true(self):
        """Test checking for supported capability that exists."""
        agent_info = {
            "id": "test_agent",
            "name": "Test Agent",
            "capabilities": ["data_query", "sql_execution", "analysis"]
        }
        agent = TestStreamingAgent(agent_info)
        
        assert agent.supports_capability("data_query") is True
        assert agent.supports_capability("sql_execution") is True
        assert agent.supports_capability("analysis") is True
    
    def test_supports_capability_false(self):
        """Test checking for capability that is not supported."""
        agent_info = {
            "id": "test_agent", 
            "name": "Test Agent",
            "capabilities": ["data_query", "sql_execution"]
        }
        agent = TestStreamingAgent(agent_info)
        
        assert agent.supports_capability("file_upload") is False
        assert agent.supports_capability("image_generation") is False
        assert agent.supports_capability("unknown_capability") is False
    
    def test_supports_capability_no_capabilities(self):
        """Test capability check when agent has no capabilities."""
        agent_info = {
            "id": "no_caps_agent",
            "name": "No Capabilities Agent"
        }
        agent = TestStreamingAgent(agent_info)
        
        assert agent.supports_capability("any_capability") is False
    
    def test_get_framework(self):
        """Test getting framework name from agent info."""
        agent_info = {
            "id": "framework_test_agent",
            "name": "Framework Test Agent",
            "framework": "google_adk"
        }
        agent = TestStreamingAgent(agent_info)
        
        framework = agent.get_framework()
        
        assert framework == "google_adk"
    
    def test_get_framework_default(self):
        """Test getting framework when not defined."""
        agent_info = {
            "id": "no_framework_agent", 
            "name": "No Framework Agent"
            # No framework field
        }
        agent = TestStreamingAgent(agent_info)
        
        framework = agent.get_framework()
        
        assert framework == "unknown"


@pytest.mark.unit
@pytest.mark.asyncio
class TestTestStreamingAgentImplementation:
    """Test cases for the test agent implementation."""
    
    async def test_initialize_success(self):
        """Test successful agent initialization."""
        agent = TestStreamingAgent()
        
        await agent.initialize({})
        
        assert agent._initialized is True
    
    async def test_initialize_failure(self):
        """Test agent initialization failure."""
        agent = TestStreamingAgent()
        
        with pytest.raises(RuntimeError, match="Initialization failed"):
            await agent.initialize({"fail_init": True})
    
    def test_get_agent_info_success(self):
        """Test successful agent info retrieval."""
        agent = TestStreamingAgent()
        
        info = agent.get_agent_info()
        
        assert info["id"] == "test_agent"
        assert info["name"] == "Test Agent"
        assert info["framework"] == "test_framework"
        assert "capabilities" in info
    
    def test_get_agent_info_custom(self):
        """Test agent info with custom data."""
        custom_info = {
            "id": "custom_agent",
            "name": "Custom Agent",
            "framework": "custom_framework",
            "version": "2.0.0"
        }
        agent = TestStreamingAgent(custom_info)
        
        info = agent.get_agent_info()
        
        assert info == custom_info
    
    async def test_process_message_success(self):
        """Test successful message processing."""
        agent = TestStreamingAgent()
        await agent.initialize({})
        
        events = []
        async for event in agent.process_message("Hello", {}):
            events.append(event)
        
        assert len(events) == 3
        
        # Check event sequence
        assert events[0]["event_type"] == "tool_execution_start"
        assert events[0]["data"]["message"] == "Hello"
        assert events[0]["turn_complete"] is False
        
        assert events[1]["event_type"] == "agent_message"
        assert "Processed: Hello" in events[1]["data"]["content"]
        assert events[1]["turn_complete"] is False
        
        assert events[2]["event_type"] == "turn_complete"
        assert events[2]["turn_complete"] is True
    
    async def test_process_message_not_initialized(self):
        """Test message processing when agent is not initialized."""
        agent = TestStreamingAgent()
        # Don't initialize
        
        with pytest.raises(RuntimeError, match="Agent not initialized"):
            async for event in agent.process_message("Hello", {}):
                pass
    
    async def test_cleanup_success(self):
        """Test successful agent cleanup."""
        agent = TestStreamingAgent()
        await agent.initialize({})
        
        await agent.cleanup()
        
        assert agent._cleanup_called is True
        assert agent._initialized is False
    
    async def test_cleanup_failure(self):
        """Test agent cleanup failure."""
        agent_info = {"fail_cleanup": True}
        agent = TestStreamingAgent(agent_info)
        
        with pytest.raises(RuntimeError, match="Cleanup failed"):
            await agent.cleanup()


@pytest.mark.unit
@pytest.mark.asyncio 
class TestFailingTestAgent:
    """Test cases for the failing test agent implementation."""
    
    async def test_process_message_failure(self):
        """Test message processing failure."""
        agent = FailingTestAgent()
        
        with pytest.raises(ValueError, match="Processing failed"):
            async for event in agent.process_message("Hello", {}):
                pass
    
    def test_get_agent_info_failure(self):
        """Test agent info retrieval failure."""
        agent = FailingTestAgent()
        
        with pytest.raises(RuntimeError, match="Info retrieval failed"):
            agent.get_agent_info()
    
    async def test_initialize_failure(self):
        """Test agent initialization failure."""
        agent = FailingTestAgent()
        
        with pytest.raises(ValueError, match="Initialization failed"):
            await agent.initialize({})


@pytest.mark.unit
class TestBaseStreamingAgentIntegration:
    """Integration tests for BaseStreamingAgent interface."""
    
    def test_agent_info_capabilities_integration(self):
        """Test integration between get_agent_info and capability methods."""
        capabilities = ["capability_a", "capability_b", "capability_c"]
        agent_info = {
            "id": "integration_agent",
            "name": "Integration Test Agent",
            "capabilities": capabilities,
            "framework": "test_framework"
        }
        agent = TestStreamingAgent(agent_info)
        
        # Test that all methods return consistent data
        info = agent.get_agent_info()
        supported_capabilities = agent.get_supported_capabilities()
        framework = agent.get_framework()
        
        assert info["capabilities"] == capabilities
        assert supported_capabilities == capabilities
        assert framework == "test_framework"
        
        # Test capability checking
        for capability in capabilities:
            assert agent.supports_capability(capability) is True
        
        assert agent.supports_capability("non_existent_capability") is False
    
    @pytest.mark.asyncio
    async def test_full_agent_lifecycle(self):
        """Test complete agent lifecycle from init to cleanup."""
        agent = TestStreamingAgent()
        
        # 1. Initialize
        await agent.initialize({"test_config": "value"})
        assert agent._initialized is True
        
        # 2. Get info
        info = agent.get_agent_info()
        assert info["id"] == "test_agent"
        
        # 3. Check capabilities
        assert agent.supports_capability("test_capability_1") is True
        assert agent.get_framework() == "test_framework"
        
        # 4. Process message
        events = []
        async for event in agent.process_message("Lifecycle test", {}):
            events.append(event)
        
        assert len(events) == 3
        assert events[-1]["turn_complete"] is True
        
        # 5. Cleanup
        await agent.cleanup()
        assert agent._cleanup_called is True
        assert agent._initialized is False
    
    def test_different_agent_configurations(self):
        """Test agents with different configurations."""
        # Agent with minimal info
        minimal_agent = TestStreamingAgent({
            "id": "minimal",
            "name": "Minimal Agent"
        })
        
        assert minimal_agent.get_supported_capabilities() == []
        assert minimal_agent.get_framework() == "unknown"
        assert minimal_agent.supports_capability("anything") is False
        
        # Agent with full info
        full_agent = TestStreamingAgent({
            "id": "full",
            "name": "Full Agent", 
            "description": "A fully configured agent",
            "framework": "advanced_framework",
            "capabilities": ["cap1", "cap2", "cap3", "cap4"],
            "version": "2.1.0",
            "additional_field": "value"
        })
        
        assert len(full_agent.get_supported_capabilities()) == 4
        assert full_agent.get_framework() == "advanced_framework"
        assert full_agent.supports_capability("cap2") is True
        assert full_agent.supports_capability("cap5") is False
    
    @pytest.mark.asyncio
    async def test_error_handling_in_lifecycle(self):
        """Test error handling throughout agent lifecycle."""
        # Test initialization error
        agent = TestStreamingAgent()
        with pytest.raises(RuntimeError):
            await agent.initialize({"fail_init": True})
        
        # Test processing without initialization
        with pytest.raises(RuntimeError, match="Agent not initialized"):
            async for event in agent.process_message("test", {}):
                pass
        
        # Test cleanup error 
        error_agent = TestStreamingAgent({"fail_cleanup": True})
        await error_agent.initialize({})
        with pytest.raises(RuntimeError, match="Cleanup failed"):
            await error_agent.cleanup()


@pytest.mark.unit
class TestAbstractMethodSignatures:
    """Test cases to verify abstract method signatures."""
    
    def test_process_message_signature(self):
        """Test that process_message has correct signature."""
        import inspect
        
        sig = inspect.signature(BaseStreamingAgent.process_message)
        params = list(sig.parameters.keys())
        
        # Should have self, message, context parameters
        expected_params = ['self', 'message', 'context']
        assert params == expected_params
        
        # Check parameter types
        assert sig.parameters['message'].annotation == str
        assert sig.parameters['context'].annotation == Dict[str, Any]
        
        # Check return type
        expected_return_type = AsyncGenerator[Dict[str, Any], None]
        assert sig.return_annotation == expected_return_type
    
    def test_get_agent_info_signature(self):
        """Test that get_agent_info has correct signature."""
        import inspect
        
        sig = inspect.signature(BaseStreamingAgent.get_agent_info)
        params = list(sig.parameters.keys())
        
        # Should have only self parameter
        assert params == ['self']
        
        # Check return type
        assert sig.return_annotation == Dict[str, Any]
    
    def test_initialize_signature(self):
        """Test that initialize has correct signature."""
        import inspect
        
        sig = inspect.signature(BaseStreamingAgent.initialize)
        params = list(sig.parameters.keys())
        
        # Should have self, config parameters
        expected_params = ['self', 'config']
        assert params == expected_params
        
        # Check parameter types
        assert sig.parameters['config'].annotation == Dict[str, Any]
        
        # Check return type (should be None)
        assert sig.return_annotation == None or sig.return_annotation == type(None)
