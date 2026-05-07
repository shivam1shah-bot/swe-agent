# PR-Prompt-Kit: Suggestion Code Quality Enhancement Plan

## Overview

This plan enhances the quality of `suggestion_code` output from sub-agent prompts and adds validation in the filter layer. The goal is to ensure all code suggestions are:

1. Syntactically valid and compilable
2. Semantically correct (actually fix the issue)
3. Directly committable via GitHub's suggestion feature
4. Free of instruction-style comments like "// delete this"

---

## Problem Statement

### Current Issues

1. **No explicit quality criteria**: Prompts say "must contain actual, applicable code fix" but lack specific requirements
2. **No handling for deletions**: When the fix is to DELETE code, LLM doesn't know to set `suggestion_code` to null
3. **Instruction-style code slips through**: LLM sometimes outputs `// delete this line` instead of actual replacement code
4. **No verification requirement**: No instruction to verify the suggested code is correct before outputting
5. **Filter layer has no code quality validation**: Only scores based on impact, not suggestion_code quality

### Impact

- GitHub shows nonsensical suggestions like "// delete this" that would ADD a comment if committed
- Users lose trust in AI suggestions when they're non-functional
- Review quality suffers from low-quality code suggestions

---

## Files to Modify

All files are located in: `pr_agent/settings/`

| File                                          | Type      | Changes                                         |
| --------------------------------------------- | --------- | ----------------------------------------------- |
| `sub_agents/bug_detection_prompt.toml`        | Sub-agent | Add `<suggestion_code_quality>` section         |
| `sub_agents/security_analysis_prompt.toml`    | Sub-agent | Add `<suggestion_code_quality>` section         |
| `sub_agents/performance_analysis_prompt.toml` | Sub-agent | Add `<suggestion_code_quality>` section         |
| `sub_agents/code_quality_prompt.toml`         | Sub-agent | Add `<suggestion_code_quality>` section         |
| `sub_agents/testing_coverage_prompt.toml`     | Sub-agent | Add `<suggestion_code_quality>` section         |
| `filter_layer/suggestion_filter_prompt.toml`  | Filter    | Add quality validation to scoring and checklist |

---

## Implementation Details

### Change 1: Sub-Agent Prompts (All 5 files)

**Location**: Insert after the `</output_format>` closing tag (before `<examples>`)

**Content to add**:

````toml
<suggestion_code_quality>
SUGGESTION_CODE QUALITY REQUIREMENTS

Your suggestion_code MUST meet ALL of these criteria:

1. **SYNTACTICALLY VALID**
   - Compiles/runs without syntax errors
   - Correct for the target language (Go, Python, TypeScript, etc.)
   - Proper indentation and formatting

2. **SEMANTICALLY CORRECT**
   - Actually fixes the described issue
   - Doesn't introduce new bugs or regressions
   - Handles edge cases mentioned in description

3. **COMPLETE REPLACEMENT**
   - Full replacement for the lines being changed
   - Not partial snippets or pseudocode
   - Includes necessary context (imports, error handling)

4. **DIRECTLY COMMITTABLE**
   - Can be applied via GitHub's "Commit suggestion" button
   - No placeholder text like "// add logic here"
   - No TODO/FIXME comments that aren't part of the fix

FORBIDDEN PATTERNS (NEVER output these in suggestion_code):
❌ Instructions disguised as code: "// delete this", "# remove this line"
❌ Placeholder code: "// implement validation here", "// TODO: fix this"
❌ Incomplete snippets: "..." or "// rest of code"
❌ Plain English instructions in code block
❌ Comments explaining what to do instead of actual code

WHEN CODE FIX IS NOT POSSIBLE:
If you cannot provide a complete, correct code fix:
- Set suggestion_code to null (do not include the field)
- Provide clear guidance in the description field
- Example description: "Remove the duplicate import statement on line 42"

VERIFICATION BEFORE OUTPUT:
Before outputting any suggestion, mentally verify:
1. ✓ Code is syntactically valid for the language
2. ✓ Code actually fixes the described issue
3. ✓ Code doesn't break existing functionality
4. ✓ Code follows patterns found in the codebase
5. ✓ All required imports/dependencies are available

If ANY verification fails, either:
- Fix the suggestion_code to pass verification, OR
- Set suggestion_code to null and explain in description

EXAMPLES OF GOOD vs BAD suggestion_code:

✅ GOOD - Actual replacement code:
```yaml
description: "Add nil check before dereferencing user pointer"
suggestion_code: |
  if user == nil {
      return fmt.Errorf("user cannot be nil")
  }
  balance := user.Balance
````

❌ BAD - Instruction instead of code:

```yaml
description: "Remove duplicate import"
suggestion_code: "// delete this line"
```

✅ CORRECT way to handle deletion:

```yaml
description: "Remove duplicate import 'fmt' on line 5"
suggestion_code: null
```

</suggestion_code_quality>

````

### Change 2: Filter Layer Prompt

**File**: `filter_layer/suggestion_filter_prompt.toml`

#### 2a. Add to `<scoring_guidelines>` section

**Location**: Under "Score 0: REJECT (Forbidden)" bullet list, add:

```toml
- Poor suggestion_code quality:
  * Instructions instead of code ("// delete this", "# remove", "// TODO")
  * Incomplete or placeholder code ("...", "// implement here")
  * Syntactically invalid code for the target language
  * Code that demonstrably doesn't fix the described issue
  * Plain English text in what should be a code block
  → Score 0 with reason: "suggestion_code contains [specific issue]"
````

#### 2b. Add to `<verification_checklist>` section

**Location**: Add as item 6 after the existing checklist items:

```toml
6. **SUGGESTION_CODE QUALITY**
   - Read the target file to verify suggested code context
   - Check: Is suggestion_code actual replacement code (not instructions)?
   - Check: Is it syntactically valid for the language?
   - Check: Does it logically address the described issue?
   - Check: Are required imports/types available in the file?
   - Red flags to reject:
     * "// delete", "# remove", "// TODO", "// FIXME" as the fix
     * Placeholder text or incomplete snippets
     * Plain English instead of code
   → Score 0 if suggestion_code quality is poor
```

#### 2c. Add example to `<examples>` section

**Location**: Add after Example 12 (False Assumption):

```toml
---

**Example 14: Non-Committable Code (Score 0)**
Suggestion:
  file: api/handlers.go, line: 45
  category: BUG
  description: Remove duplicate import
  suggestion_code: "// delete this line"

Evaluation:
  index: 0
  score: 0
  reason: "suggestion_code is instruction, not committable replacement code"

---

**Example 15: Placeholder Code (Score 0)**
Suggestion:
  file: service/payment.go, line: 89
  category: BUG
  description: Add error handling for payment failure
  suggestion_code: "// TODO: add error handling here"

Evaluation:
  index: 0
  score: 0
  reason: "suggestion_code is placeholder, not actual implementation"
```

---

## Verification Checklist

After implementing changes, verify:

- [ ] All 5 sub-agent prompts have the `<suggestion_code_quality>` section
- [ ] Section is placed after `</output_format>` and before `<examples>`
- [ ] Filter layer has updated `<scoring_guidelines>` with quality rules
- [ ] Filter layer has updated `<verification_checklist>` with item 6
- [ ] Filter layer has new examples 14 and 15
- [ ] All TOML files parse correctly (no syntax errors)
- [ ] Package version is bumped in `pyproject.toml` or equivalent

---

## Testing

After implementation, test with these scenarios:

### Test Case 1: Good Suggestion

```yaml
suggestions:
  - file: api/user.go
    line: 42
    category: BUG
    importance: 9
    confidence: 0.95
    description: "Add nil check before dereferencing"
    suggestion_code: |
      if user == nil {
          return nil, fmt.Errorf("user is nil")
      }
```

**Expected**: Passes quality check, scored based on impact

### Test Case 2: Instruction-Style Code

```yaml
suggestions:
  - file: api/user.go
    line: 42
    category: BUG
    importance: 8
    confidence: 0.90
    description: "Remove duplicate line"
    suggestion_code: "// delete this line"
```

**Expected**: Filter layer scores 0, reason mentions non-committable code

### Test Case 3: Deletion with Null Code

```yaml
suggestions:
  - file: api/user.go
    line: 42
    category: BUG
    importance: 7
    confidence: 0.85
    description: "Remove duplicate import 'fmt' on line 42"
    suggestion_code: null
```

**Expected**: Passes quality check (null is valid for deletions)

---

## Rollout Plan

1. **Implement changes** in pr-prompt-kit repository
2. **Bump version** (e.g., 1.1.0 → 1.2.0)
3. **Update swe-agent** to use new pr-prompt-kit version
4. **Monitor** first few reviews for quality improvement
5. **Iterate** on prompts based on observed output

---

## Files Reference

### Sub-Agent Prompt Structure (for context)

Each sub-agent prompt follows this structure:

```
[{category}_prompt]
system="""
<role>...</role>
<category_focus>...</category_focus>
<quality_threshold>...</quality_threshold>
<context_gathering>...</context_gathering>
<repository_access>...</repository_access>
<skill_usage>...</skill_usage>
<output_format>...</output_format>
<suggestion_code_quality>NEW SECTION GOES HERE</suggestion_code_quality>
<examples>...</examples>
<critical_reminder>...</critical_reminder>
"""

user="""..."""
```

### Filter Layer Prompt Structure (for context)

```
[suggestion_filter_prompt]
system="""
<role>...</role>
<repository_access>...</repository_access>
<scoring_guidelines>UPDATE HERE</scoring_guidelines>
<verification_checklist>UPDATE HERE</verification_checklist>
<duplicate_detection>...</duplicate_detection>
<output_format>...</output_format>
<examples>ADD NEW EXAMPLES HERE</examples>
<category_validation>...</category_validation>
"""

user="""..."""
```

---

## Success Criteria

1. **Zero instruction-style suggestions**: No more "// delete this" in production
2. **Higher commit rate**: More suggestions get committed via GitHub's feature
3. **Better user trust**: Fewer complaints about non-functional suggestions
4. **Filter layer catches escapes**: Any bad suggestions from sub-agents get scored 0

---

## Notes for Implementing Agent

- Use exact TOML syntax - escape quotes properly
- Maintain consistent indentation within the prompt strings
- The `<suggestion_code_quality>` content uses markdown-style formatting that renders well in logs
- Test TOML parsing after changes to catch syntax errors early
- The section should be self-contained and not reference other sections
