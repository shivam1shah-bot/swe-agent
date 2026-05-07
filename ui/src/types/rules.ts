/**
 * Types and interfaces for Rules Configuration
 */

export enum RuleSeverity {
  BLOCKER = "Blocker",
  CRITICAL = "Critical", 
  MAJOR = "Major",
  MINOR = "Minor"
}

export enum RuleType {
  CODE_SMELL = "CODE_SMELL",
  BUG = "BUG",
  VULNERABILITY = "VULNERABILITY"
}

export interface Rule {
  id: string;
  name: string;
  description: string;
  severity: RuleSeverity;
  type: RuleType;
  enabled: boolean;
  isOrgLevel: boolean;
  repositoryId?: string;
  createdAt: string;
  updatedAt: string;
}

export interface RuleConfig {
  organizationId: string;
  repositoryId?: string;
  rules: Rule[];
}

export interface RuleDetails {
  id: string;
  name: string;
  description: string;
  severity: RuleSeverity;
  type: RuleType;
  rationale: string;
  examples: {
    good: string[];
    bad: string[];
  };
  references: string[];
  tags: string[];
}

export interface Repository {
  id: string;
  name: string;
  fullName: string;
  isPrivate: boolean;
}

export interface Organization {
  id: string;
  name: string;
  displayName: string;
}

// Rule Suggestions Types
export interface RuleSuggestion {
  id: string;
  suggestedRuleName: string;
  description: string;
  rationale: string;
  severity: RuleSeverity;
  type: RuleType;
  scope: 'global' | 'repository';
  repositoryId?: string;
  repositoryName?: string;
  confidence: number; // 0-100
  basedOnComments: CommentAnalysis[];
  suggestedAt: string;
  status: 'pending' | 'approved' | 'rejected';
  reviewedBy?: string;
  reviewedAt?: string;
}

export interface CommentAnalysis {
  id: string;
  prNumber: number;
  prTitle: string;
  commentText: string;
  author: string;
  repository: string;
  createdAt: string;
  frequency: number; // How often this pattern occurs
}

export interface SuggestionApproval {
  suggestionId: string;
  action: 'approve' | 'reject';
  customizations?: {
    ruleName?: string;
    description?: string;
    severity?: RuleSeverity;
    scope?: 'global' | 'repository';
  };
  feedback?: string;
}
