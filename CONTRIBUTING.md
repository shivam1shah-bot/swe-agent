# Contributing to SWE Agent

_Guidelines for contributing to the SWE Agent AI-powered automation platform._

## 🎯 Overview

SWE Agent is an enterprise AI automation platform. We welcome contributions that enhance developer workflows, add new AI agent capabilities, or improve system reliability.

## 🚀 Quick Start

**Setup**: Follow [Setup Guide](./docs/setup.md) to get the development environment running

**Essential Reading**:

- **[Architecture Guide](./docs/architecture.md)** - System design and patterns
- **[Agent Navigation Guide](./AGENT.md)** - Codebase navigation
- **[Agents Catalogue](./docs/agents_catalogue/)** - Agent development

---

## 🏗️ Development Workflow

### Branch Strategy

```
feature/your-feature-name       # New features
bugfix/issue-description        # Bug fixes
docs/documentation-update       # Documentation
refactor/component-name         # Refactoring
```

### Development Process

1. **Create branch**: `git checkout -b feature/my-feature`
2. **Follow patterns**: Use [Architecture Guide](./docs/architecture.md) and [Agent Navigation](./AGENT.md)
3. **Test changes**: `make test` (see [Testing Guide](./docs/testing.md))
4. **Commit**: Use conventional commits (`feat:`, `fix:`, `docs:`)
5. **Create PR**: Follow PR template and checklist

### Pull Request Checklist

- ✅ Tests pass and coverage adequate
- ✅ Follows architecture patterns
- ✅ Documentation updated if needed
- ✅ No breaking changes (or documented)

---

## 🎨 Code Standards

### Python Standards

- **Layered Architecture**: API → Service → Repository → Model (see [Architecture Guide](./docs/architecture.md))
- **Type hints** for all function signatures
- **Dependency injection** for testability
- **Structured logging** with context
- **Docstrings** for public methods

### Frontend Standards

- **React/TypeScript** with component patterns
- **UI components** from `/components/ui/`
- **Type interfaces** for all props

### Testing Standards

- **Unit tests** for all business logic
- **Integration tests** for complex workflows
- **Mocking** for external dependencies
- See [Testing Guide](./docs/testing.md) for detailed patterns

---

## 🤖 Adding New AI Agents

### Agent Development

**Detailed Guide**: [Agents Catalogue Development](./docs/agents_catalogue/agent_development.md)

**Quick Steps**:

1. **Backend**: Create service in `src/services/agents_catalogue/`
2. **Frontend**: Create component in `ui/src/pages/AgentsCatalogue/`
3. **Register**: Add to service registry and component registry
4. **Test**: Unit and integration tests

**Available Agents**: Claude Code, Gemini CLI, Autonomous Agent (see `src/agents/`)

**Patterns**: Study existing agents for implementation patterns and best practices

---

## 🧪 Testing Guidelines

**Detailed Guide**: [Testing Guide](./docs/testing.md)

**Test Types**:

- **Unit**: Fast, isolated tests (required)
- **Integration**: Multi-component tests (required for complex features)
- **E2E**: Full workflows (recommended)

**Running Tests**:

```bash
make test               # All tests
make test-unit         # Unit tests only
make test-integration  # Integration tests only
```

---

## 📚 Documentation Requirements

**Code Documentation** (required):

- Docstrings for public methods
- Type hints for function signatures
- Inline comments for complex logic

**User Documentation** (update when adding features):

- [README.md](./README.md) for core changes
- [Agents Catalogue](./docs/agents_catalogue/) for new agents
- [Architecture Guide](./docs/architecture.md) for system changes

**All Documentation**: See [Documentation Index](./docs/README.md)

---

## 🔍 Code Review Guidelines

**What Reviewers Check**:

- ✅ Architecture compliance (see [Architecture Guide](./docs/architecture.md))
- ✅ Code quality and error handling
- ✅ Test coverage and patterns
- ✅ Documentation completeness

**Review Process**: Automated checks → Architecture → Code → Testing → Documentation

---

## 🎯 Contribution Areas

**High Priority**: New AI agents, tool integrations, performance optimizations, monitoring

**Medium Priority**: UI/UX improvements, test coverage, documentation, API enhancements

**Low Priority**: Code refactoring, dev tooling, experimental features

---

## 📞 Getting Help

**Before starting**: Create an issue to discuss your proposal

**Documentation**: [Documentation Index](./docs/README.md) has all guides

**Stuck?**: Study existing implementations and follow established patterns

---

## 📄 License

By contributing, you agree your contributions will be licensed under the same license as the project.

**Copyright © Razorpay**

---

_🚀 Thank you for contributing to SWE Agent!_
