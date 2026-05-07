#!/bin/bash
#
# Install review helper skills from agent-skills repo
#
# This script is for LOCAL DEVELOPMENT ONLY.
# In production, skills are baked into the Docker image during build time.
# See: build/docker/prod/Dockerfile.worker.code_review
#
# Use this script when:
# - Running review workers outside Docker (local development)
# - Testing skill integration locally before building Docker image
#

set -e

echo "📦 Installing review helper skills for local development..."
echo "ℹ️  Note: In production, skills are baked into Docker image at build time"

# Install pre-mortem skill for PreMortemSubAgent
echo "  → Installing pre-mortem skill..."
npx skills add https://github.com/razorpay/agent-skills \
  --skill pre-mortem \
  --env claude \
  --full-depth \
  --yes

# Move symlink to review-helpers directory (expected by subagent)
if [ -L ".claude/skills/pre-mortem" ]; then
  rm .claude/skills/pre-mortem
  mkdir -p .claude/skills/review-helpers
  ln -s ../../.agents/skills/pre-mortem .claude/skills/review-helpers/pre-mortem
  echo "  ✓ pre-mortem skill installed to .claude/skills/review-helpers/pre-mortem"
fi

echo "✅ Review helper skills installed successfully"
echo "💡 Remember: This is for local dev only. Docker images install skills at build time."
