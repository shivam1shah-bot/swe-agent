# Code Review Metrics

## Overview

This document provides a comprehensive catalog of all metrics for the Code Review dashboard. All metrics are measured on a daily basis from 12:00 AM to 11:59 PM IST. The metrics are organized into categories based on their purpose and data source.

## Metrics [Per Repo, Per Day]

### 1. Stats

### 1. 1. Review Comments

- **Comments [Daily 12AM-11:59PM IST]**: 430 - Comments generated during daily measurement period

### 2. PRs Reviewed

- **PRs Reviewed per Repo [Daily 12AM-11:59PM IST]**: Daily view of PR reviews per repository

### 3. Comment Categories

- **Category Distribution [Daily 12AM-11:59PM IST]**: Pie chart showing:
  - General
  - Possible Issue
  - Other categories

### 4. Comment Severity Metrics

- **Comment Severity Trends [Daily 12AM-11:59PM IST]**: Line chart showing trends for:
  - High severity (≥6)
  - Low severity (<6)

### 2. Effectiveness

#### 1 Comment Acceptance Rate

- **Formula**: `(AI Comments with 👍 OR (no reactions AND outdated)) / Total AI Comments) × 100`
- **Measurement**: Percentage of AI comments that are accepted (prioritizing explicit reactions over outdated status)

#### 1.2 Issue Detection Accuracy

- **Precision**: `True Positives / (True Positives + False Positives)`
- **Recall**: `True Positives / (True Positives + False Negatives)`
- **F1-Score**: `2 × (Precision × Recall) / (Precision + Recall)`
- **Measurement**: AI predictions vs ground truth expert annotations
- **Data Source**: Ground truth dataset with pr-author labeled issues
- **Target**: F1-Score > 60%

**Identifying TP/FP/FN Using Reactions with Outdated Status Fallback**:

- **True Positives (TP)**:
  - AI comments with 👍 reaction (explicit approval)
  - OR if no reactions, AI comments that became outdated (developer addressed)
- **False Positives (FP)**:
  - AI comments with 👎 reaction (explicit disagreement)
  - OR if no reactions, AI comments that remain active (not addressed)
- **False Negatives (FN)**: Human reviewer comments (issues AI missed completely)

#### 1.3 Critical Issue Accepted Rate

- **Formula**: `(High-Severity (≥ 6) AI Issues with 👍 OR (no reactions AND outdated) / Total High-Severity AI Issues) × 100`
- **Measurement**: Track accepted critical suggestions (prioritizing reactions over outdated status)

#### 1.4 False Positive Rate (Developer Disagreement)

- **Formula**: `(AI Comments with 👎 OR (no reactions AND not outdated) / Total AI Comments) × 100`
- **Measurement**: AI comments that are explicitly disagreed with or remain unaddressed

#### 1.5 Category Wise Accepted Suggestions

- **Formula**: `(Comments accepted per category / Total comments per category) × 100`
- **Measurement**: Acceptance rates grouped by suggestion type

### 2. Developer Productivity & Time Savings

#### 2.1 Review Turnaround Time

- **Formula**: `AVERAGE(Processing Latency across all PR sizes)`
- **Measurement**: Average AI response time from PR creation to first AI comment
- **Data Source**: Calculated from processing_latency median values weighted by PR count
- **Target**: < 10 minutes average

#### 2.2 Human Review Comment Percentage

- **Formula**: `(Human Comments / Total Comments) × 100`
- **Measurement**: Percentage of review comments that are from human reviewers
- **Data Source**: Count of human vs AI comments during 12AM-11:59PM IST period
- **Target**: Balanced mix (e.g., 30-50% human involvement)

#### 2.3 Human Comments Count

- **Formula**: `Total Human Comments`
- **Measurement**: Absolute count of human reviewer comments per day
- **Data Source**: Line-specific human comments during 12AM-11:59PM IST period
- **Target**: Consistent human engagement (varies by team size)

#### 2.4 Human Review Time Savings

- **Formula**: `Accepted AI Comments × 2 minutes`
- **Calculation**: `Daily Accepted AI Comments × 2 minutes = Daily Minutes Saved`
- **Measurement**: Estimate time human reviewers would spend on issues caught by AI during full daily periods
- **Target**: > 200 minutes saved per daily measurement period

#### 2.5 Feedback Quality Rate

- **Formula**: `(AI Comments with Reactions / Total AI Comments) × 100`
- **Measurement**: Percentage of AI comments that received any reaction (👍 or 👎)
- **Data Source**: Comments with thumbs up or thumbs down reactions
- **Target**: >60% (indicates developers are engaging with AI suggestions)

### 3. Technical Performance & Reliability

#### 3.1 System Uptime

- **Formula**: `(PRs with Successful AI Reviews / Total PRs) × 100`
- **Measurement**: AI review coverage - includes PRs with "No code suggestions found"
- **Data Source**: System events showing successful AI review processing
- **Target**: > 95% PR coverage

#### 3.2 Processing Latency

- **Small PRs (<5 files)**: `MEDIAN(First AI Comment Time - PR Creation Time)`
- **Medium PRs (5-20 files)**: `MEDIAN(First AI Comment Time - PR Creation Time)`
- **Large PRs (>20 files)**: `MEDIAN(First AI Comment Time - PR Creation Time)`
- **Measurement**: Time from PR creation to first AI feedback (throughput)
- **Data Source**: PR creation timestamp vs first AI comment timestamp
- **Target**: < 3 min (small), < 10 min (medium), < 15 min (large)

## File Object Structure Reference

### Directory Structure

```
uploads/metrics/
├── raw/                          # Raw data for processing
│   ├── 2024-01-15/
│   │   ├── owner-repo1-raw.json
│   │   └── owner-repo2-raw.json
│   └── 2024-01-16/
└── extracted/                    # Lean metrics for UI
    ├── 2024-01-15/
    │   ├── owner-repo1-metrics.json
    │   └── owner-repo2-metrics.json
    └── 2024-01-16/
```

### Raw Data File Structure

`uploads/metrics/raw/{date}/{repo}-raw.json`

```json
{
  "metadata": {
    "generated_at": "2024-01-15T12:00:00Z",
    "measurement_period": {
      "start": "2024-01-15T00:00:00+05:30",
      "end": "2024-01-15T23:59:00+05:30",
      "timezone": "IST"
    },
    "repository": "owner/repo-name",
    "version": "1.0"
  },
  "prs": [
    {
      "pr_id": "123",
      "created_at": "2024-01-15T08:30:00Z",
      "merged_at": "2024-01-15T11:45:00Z",
      "files_changed": 8,
      "ai_comments": [
        {
          "comment_id": "c1",
          "created_at": "2024-01-15T08:35:00Z",
          "category": "possible_issue",
          "severity": 8,
          "status": {
            "current": "outdated",
            "outdated": true,
            "outdated_reason": "line_changed",
            "became_outdated_at": "2024-01-15T09:15:00Z"
          },
          "reactions": {
            "thumbs_up": 1,
            "thumbs_down": 0
          },
          "has_detailed_feedback": true,
          "github_metadata": {
            "line": null,
            "original_line": 45,
            "diff_hunk": "@@ -40,7 +40,10 @@",
            "commit_id": "abc123"
          }
        }
      ],
      "human_comments": [
        {
          "comment_id": "h1",
          "created_at": "2024-01-15T09:00:00Z",
          "author_type": "reviewer"
        }
      ]
    }
  ],
  "system_events": [
    {
      "event_type": "ai_review_requested",
      "pr_id": "123",
      "timestamp": "2024-01-15T08:30:05Z",
      "processing_time_ms": 45000,
      "status": "success"
    }
  ]
}
```

### Extracted Metrics File Structure

`uploads/metrics/extracted/{date}/{repo}-metrics.json`

```json
{
  "metadata": {
    "date": "2024-01-15",
    "repository": "owner/repo-name",
    "generated_at": "2024-01-15T12:00:00Z",
    "version": "1.0"
  },
  "stats": {
    "total_comments": 430,
    "prs_reviewed": 25,
    "comment_categories": {
      "general": 200,
      "possible_issue": 180,
      "security": 50
    },
    "severity_distribution": {
      "high": 200,
      "low": 230
    }
  },
  "effectiveness": {
    "comment_acceptance_rate": 72.5,
    "issue_detection_accuracy": {
      "precision": 0.68,
      "recall": 0.75,
      "f1_score": 0.71
    },
    "critical_issue_accepted_rate": 85.2,
    "false_positive_rate": 4.8,
    "category_acceptance_rates": {
      "security": 95.0,
      "performance": 78.5,
      "general": 65.2
    }
  },
  "productivity": {
    "review_turnaround_time_minutes": 8.5,
    "human_review_comment_percent": 35.2,
    "human_comments_count": 8,
    "time_saved_minutes": 12.0,
    "feedback_quality_rate": 45.8
  },
  "technical": {
    "system_uptime_percent": 98.5,
    "processing_latency": {
      "small_prs_median_minutes": 2.1,
      "medium_prs_median_minutes": 7.8,
      "large_prs_median_minutes": 12.3
    }
  }
}
```

### API Endpoints

```typescript
// UI endpoints - serve extracted data
GET / api / metrics / { repo } / daily / { date }; // Loads extracted metrics
GET / api / metrics / available; // Lists available dates/repos

// Processing endpoints - use raw data
GET / api / metrics / { repo } / raw / { date }; // For recalculation
POST / api / metrics / recalculate / { repo } / { date }; // Regenerate from raw data
```

### Processing Workflow

```
1. Collect GitHub data → Raw files
2. Process raw files → Extracted metrics
3. UI loads extracted metrics only
4. Background jobs work with raw data
```
