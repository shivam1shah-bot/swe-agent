# Sub-Agent Configuration Files

This directory contains JSON configuration files for comment analyzer sub-agents.

## Structure

Each sub-agent has its own JSON configuration file: `{sub_agent_name}.json`

### Configuration Schema

```json
{
  "name": "sub-agent-name",
  "identifier": "review-identifier",
  "description": "Description of what this sub-agent does",
  "severity_threshold": 9,
  "thresholds": {
    "fail_on_critical_count": 1
  },
  "filter": {
    "include_extensions": [],
    "exclude_extensions": [".md", ".txt"],
    "exclude_patterns": ["**/test/**", "**/vendor/**"]
  },
  "authorization": {
    "enabled": true,
    "authorized_team": "org/team-slug",
    "allow_tp_feedback": true,
    "allow_fp_feedback": true
  }
}
```

## Configuration Fields

### Top-Level Fields

- **name** (string): Sub-agent name (must match the registry name)
- **identifier** (string): Identifier used in review headers and status names
- **description** (string): Human-readable description of the sub-agent
- **severity_threshold** (number): Minimum severity score (1-10) to consider an issue critical

### Thresholds

- **fail_on_critical_count** (number): Number of critical issues that will cause the PR to fail

### Filter

File filtering configuration:

- **include_extensions** (array): Only analyze files with these extensions (empty = all files)
- **exclude_extensions** (array): Never analyze files with these extensions
- **exclude_patterns** (array): Glob patterns for files to exclude

### Authorization

Controls whether authorized team members can mark comments as TP/FP:

- **enabled** (boolean): Enable/disable authorization feedback
- **authorized_team** (string): GitHub team in format "org/team-slug"
- **allow_tp_feedback** (boolean): Allow marking True Positive
- **allow_fp_feedback** (boolean): Allow marking False Positive

## Examples

### I18N Sub-Agent

See [i18n.json](./i18n.json) for the internationalization sub-agent configuration.

### Adding a New Sub-Agent

1. Create a new JSON file: `{sub_agent_name}.json`
2. Define the configuration following the schema above
3. Implement the sub-agent class in `../` directory
4. Register the sub-agent in `../sub_agent_registry.py`

## Loading Configuration

Sub-agents load their configuration using the `SubAgentConfigLoader`:

```python
from src.services.comment_analyzer.agents.config_loader import SubAgentConfigLoader

# Load default config
config = SubAgentConfigLoader.load_config("i18n")

# Load and merge with runtime overrides
config = SubAgentConfigLoader.load_and_merge("i18n", override_config={
    "severity_threshold": 8
})
```

## Runtime Overrides

Configuration can be overridden at runtime through environment variables or passed config:

- Environment variables take precedence (e.g., `I18N_AUTHORIZED_TEAM`)
- Config passed to `GenericOrchestrator` overrides defaults
- Default JSON config is used if no overrides provided
