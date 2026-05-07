# Agents Catalogue

_Guide for creating AI agents in the SWE Agent system._

## 🎯 Overview

Centralized system for teams to create and execute AI agents for development workflows like gateway integration, pipeline generation, documentation, and test generation.

## 📚 Documentation

**[Agent Development](./agent_development.md)** - Backend service creation  
**[Frontend Components](./frontend_components.md)** _(coming soon)_ - UI components  
**[Examples](./examples.md)** _(coming soon)_ - Reference implementations  
**[Best Practices](./best_practices.md)** _(coming soon)_ - Guidelines and checklist

## 🏗️ Architecture

**Components**: Backend Service + Frontend Component + API Integration + Service Registry

**Flow**: `User Input → Frontend → API → Service Registry → Backend → Queue → Worker → AI Agent → Results`

## 🚀 Quick Start

**Backend**: [Agent Development Guide](./agent_development.md)  
**Frontend**: [Frontend Components Guide](./frontend_components.md) _(coming soon)_  
**Examples**: [Agent Examples](./examples.md) _(coming soon)_

## 📋 Common Use Cases

**Development**: CI/CD pipelines, gateway integration, documentation automation, test generation  
**Code Analysis**: Code review, security analysis, performance optimization, dependency management  
**Project Management**: Issue triage, release planning, monitoring setup

## 🎯 Development Workflow

1. **Plan**: Define use case, input parameters, expected output
2. **Backend**: Create service using [Agent Development Guide](./agent_development.md)
3. **Frontend**: Create React component _(guide coming soon)_
4. **Deploy**: Test and deploy using best practices _(guide coming soon)_

## 🔧 System Integration

**Queue-Based**: Async execution with task tracking  
**AI Integration**: Structured prompts with tool access  
**Service Registry**: Dynamic service discovery and routing

---

## 📞 Need Help?

**Development**: [Agent Development Guide](./agent_development.md) • [Architecture Guide](../architecture.md) • [Agent Navigation](../../AGENT.md)

**Implementation**: Study existing agents in `src/services/agents_catalogue/` and `ui/src/pages/AgentsCatalogue/`

---

_Build custom AI agents for development workflows with consistency and reliability._
