# Tech Spec - {{ project_name }}

**Author/s:** {{ author }}  
**Team/Pod:** {{ team_pod | default("Not specified") }}  
**Published Date:** {{ (published_date | default(current_date)) | date }}

---

## Reviewers

| Reviewer Name | Reviewed Date | Status |
| ------------- | ------------- | ------ |

{% if reviewers %}
{% for reviewer in reviewers %}
| {{ reviewer.name }} | {{ reviewer.reviewed_date | default("") }} | {{ reviewer.status | default("") }} |
{% endfor %}
{% else %}
| _No reviewers specified_ | | |
{% endif %}

---

## Table of Contents

1. [Problem Statement](#1-problem-statement)
2. [Introduction & Scope](#2-introduction--scope)
   2.1. [Relevant Resources](#21-relevant-resources)
3. [Out of Scope](#3-out-of-scope)
4. [Futuristic Scope](#4-futuristic-scope)
5. [Assumptions, Goals & Non-Goals](#5-assumptions-goals--non-goals)
   5.1. [Assumptions](#51-assumptions)
   5.2. [Goals](#52-goals)
   5.3. [Non-Goals](#53-non-goals)
6. [Current Architecture / Current HLD](#6-current-architecture--current-hld)
7. [Evaluated Approaches & Finalization](#7-evaluated-approaches--finalization)
   7.1. [Approaches Evaluation](#71-approaches-evaluation)
   7.2. [Data model/Schema Changes](#72-data-modelschema-changes)
   7.3. [Business Logic Changes](#73-business-logic-changes)
8. [Non Functional Requirements (NFRs)](#8-non-functional-requirements-nfrs)
   8.1. [Scalability](#81-scalability)
   8.2. [Availability](#82-availability)
   8.3. [Security](#83-security)
   8.4. [Compliance](#84-compliance)
   8.5. [Reliability](#85-reliability)
   8.6. [Infra Cost](#86-infra-cost)
9. [Feature Dependencies & SLAs](#9-feature-dependencies--slas)
   9.1. [Dependencies](#91-dependencies)
10. [Testing Plan](#10-testing-plan)
11. [Go-live plan](#11-go-live-plan)
    11.1. [Production Rollout and Ramp plan](#111-production-rollout-and-ramp-plan)
    11.2. [Backward Compatibility](#112-backward-compatibility)
    11.3. [Rollback plan](#113-rollback-plan)
12. [Monitoring & Logging](#12-monitoring--logging)
13. [Milestones & Timelines](#13-milestones--timelines)

---

## 1. Problem Statement

{{ problem_statement }}

## 2. Introduction & Scope

{% if generated_introduction %}
{{ generated_introduction }}
{% else %}
{{ introduction }}
{% endif %}

{% if generated_scope %}
{{ generated_scope }}
{% else %}
{{ scope }}
{% endif %}

### 2.1. Relevant Resources

{% if relevant_resources %}
{% for resource in relevant_resources %}

- [{{ resource.name }}]({{ resource.url }})
  {% endfor %}
  {% else %}
- No relevant resources specified
  {% endif %}

## 3. Out of Scope

{% if generated_out_of_scope %}
{{ generated_out_of_scope }}
{% elif out_of_scope %}
{% for item in out_of_scope %}

- {{ item }}
  {% endfor %}
  {% else %}
- No out of scope items specified
  {% endif %}

## 4. Futuristic Scope

{% if generated_futuristic_scope %}
{{ generated_futuristic_scope }}
{% elif futuristic_scope %}
{% for item in futuristic_scope %}

- {{ item }}
  {% endfor %}
  {% else %}
- No futuristic scope items specified
  {% endif %}

## 5. Assumptions, Goals & Non-Goals

{% if generated_assumptions_goals %}
{{ generated_assumptions_goals }}
{% else %}

### 5.1. Assumptions

{% if assumptions %}
{% for assumption in assumptions %}

- {{ assumption }}
  {% endfor %}
  {% else %}
- No assumptions specified
  {% endif %}

### 5.2. Goals

{% if goals %}
{% for goal in goals %}

- {{ goal }}
  {% endfor %}
  {% else %}
- No goals specified
  {% endif %}

### 5.3. Non-Goals

{% if non_goals %}
{% for item in non_goals %}

- {{ item }}
  {% endfor %}
  {% else %}
- No non-goals specified
  {% endif %}
  {% endif %}

## 6. Current Architecture / Current HLD

{% if current_architecture_diagram %}

```mermaid
{{ current_architecture_diagram }}
```

{% endif %}

{% if generated_current_architecture %}
{{ generated_current_architecture }}
{% else %}
{{ current_architecture_description }}
{% endif %}

## 7. Evaluated Approaches & Finalization

{% if generated_evaluated_approaches %}
{{ generated_evaluated_approaches }}
{% else %}

### 7.1. Approaches Evaluation

{% if generated_approaches_evaluation %}
{{ generated_approaches_evaluation }}
{% elif approaches_evaluation %}
{{ approaches_evaluation }}
{% elif evaluated_approaches %}
{% for approach in evaluated_approaches %}

#### Approach {{ loop.index }}: {{ approach.name }}

{{ approach.description }}

**Pros:**
{% for pro in approach.pros %}

- {{ pro }}
  {% endfor %}

**Cons:**
{% for con in approach.cons %}

- {{ con }}
  {% endfor %}

{% if approach.diagram %}

```mermaid
{{ approach.diagram }}
```

{% endif %}

{% endfor %}

#### Final Approach

{{ selected_approach.name }}

{{ selected_approach.justification }}
{% else %}
No approaches have been evaluated.
{% endif %}
{% endif %}

<!-- Data model changes, business logic changes, and DB evaluation sections are included in the evaluated approaches section -->
<!-- These sections are generated as part of the evaluated approaches to ensure they appear only once in the document -->

{% endif %}

## 8. Non Functional Requirements (NFRs)

{% if generated_nfr %}
{{ generated_nfr }}
{% else %}

### 8.1. Scalability

{{ scalability }}

### 8.2. Availability

{{ availability }}

### 8.3. Security

{{ security }}

### 8.4. Compliance

{{ compliance }}

### 8.5. Reliability

{{ reliability }}

### 8.6. Infra Cost

{{ infra_cost }}
{% endif %}

## 9. Feature Dependencies & SLAs

{% if generated_dependencies %}
{{ generated_dependencies }}
{% else %}

### 9.1. Dependencies

{% if dependencies %}
| Dependency | Owner | SLA | Notes |
|------------|-------|-----|-------|
{% for dep in dependencies %}
| {{ dep.name }} | {{ dep.owner }} | {{ dep.sla }} | {{ dep.notes }} |
{% endfor %}
{% else %}
No external dependencies identified.
{% endif %}
{% endif %}

## 10. Testing Plan

{% if generated_testing_plan %}
{{ generated_testing_plan }}
{% else %}
{{ testing_plan }}
{% endif %}

## 11. Go-live plan

{% if generated_go_live_plan %}
{{ generated_go_live_plan }}
{% else %}
{{ go_live_plan }}

### 11.1. Production Rollout and Ramp plan

{{ rollout_plan }}

### 11.2. Backward Compatibility

{{ backward_compatibility }}

### 11.3. Rollback plan

{{ rollback_plan }}
{% endif %}

## 12. Monitoring & Logging

{% if generated_monitoring_logging %}
{{ generated_monitoring_logging }}
{% else %}
{{ monitoring_logging }}
{% endif %}

## 13. Milestones & Timelines

{% if generated_milestones_timelines %}
{{ generated_milestones_timelines }}
{% elif milestones %}
| Milestone | Estimated Completion | Owner |
|-----------|----------------------|-------|
{% for milestone in milestones %}
| {{ milestone.name }} | {{ milestone.completion_date }} | {{ milestone.owner }} |
{% endfor %}
{% else %}
No milestones specified.
{% endif %}
