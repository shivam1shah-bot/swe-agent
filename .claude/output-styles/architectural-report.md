# Architectural Report Output Style

## Format
Provide architectural analysis in the following structured format:

---

# Architecture Analysis Report

## Executive Summary
High-level overview of the architecture state and key findings.

## Current Architecture

### Layer Overview
```
┌─────────────────────────────────────┐
│         API Layer (FastAPI)         │
│  Routes, Dependencies, Middleware   │
└─────────────────────────────────────┘
                 ↓
┌─────────────────────────────────────┐
│       Service Layer (Business)      │
│  Orchestration, Workflows, Logic    │
└─────────────────────────────────────┘
                 ↓
┌─────────────────────────────────────┐
│    Repository Layer (Data Access)   │
│   SQLAlchemy, CRUD, Abstractions    │
└─────────────────────────────────────┘
                 ↓
┌─────────────────────────────────────┐
│      Model Layer (Domain/Data)      │
│   Entities, Schemas, Validations    │
└─────────────────────────────────────┘
```

### Key Components
- **Component Name**: Brief description and purpose
- **Dependencies**: What it depends on
- **Responsibilities**: What it does

## Design Patterns Used

### Pattern Name
- **Where**: Location in codebase
- **Purpose**: Why it's used
- **Implementation**: How it's implemented
- **Effectiveness**: How well it works

## Data Flow Analysis

### Request Flow
1. Entry point → Processing → Response
2. Key transformations
3. Integration points

### Task Processing Flow
1. Queue → Worker → Execution → Result
2. State transitions
3. Error handling

## Integration Points

### External Systems
- **System Name**: Integration method, purpose, dependencies

### Internal Communications
- Service-to-service interactions
- Data sharing patterns
- Event flows

## Strengths 💪

- Well-implemented patterns
- Strong architectural decisions
- Good separation of concerns
- Effective abstractions

## Areas for Improvement 🔧

### Priority 1 (High Impact)
- Issue description
- Why it matters
- Suggested approach

### Priority 2 (Medium Impact)
- Issue description
- Potential benefits of addressing

### Priority 3 (Low Impact)
- Nice-to-have improvements
- Long-term considerations

## Technical Debt

- **Debt Item**: Description, impact, effort to fix
- Recommended timeline for addressing

## Scalability Assessment

- **Current Limitations**: What might not scale
- **Bottlenecks**: Potential performance issues
- **Recommendations**: How to improve

## Security Posture

- Authentication mechanisms
- Authorization patterns
- Data protection measures
- Identified risks

## Recommendations

### Short-term (1-3 months)
1. Specific actionable items
2. Expected benefits

### Medium-term (3-6 months)
1. Strategic improvements
2. Refactoring opportunities

### Long-term (6-12 months)
1. Architectural evolution
2. Technology upgrades

## Conclusion
Summary of overall architecture health and key next steps.

---
