#!/bin/bash

# Collect GitHub usernames from openteams and quansight and write to team.txt
# Usage: ./scripts/collect_team.sh

set -e

OUTPUT_FILE="${1:-team.txt}"

echo "Fetching team members from GitHub organizations..."

# Collect members from both organizations and sort/uniq to remove duplicates
{
    echo "# Fetching from /orgs/openteams-ai/members"
    gh api --paginate /orgs/openteams-ai/members --jq '.[].login' 2>/dev/null || echo "# Failed to fetch openteams-ai members" >&2
    
    echo "# Fetching from /orgs/quansight/members"
    gh api --paginate /orgs/quansight/members --jq '.[].login' 2>/dev/null || echo "# Failed to fetch quansight members" >&2
} | grep -v "^#" | sort -u > "$OUTPUT_FILE"

echo "✓ Wrote $(wc -l < "$OUTPUT_FILE") unique team members to $OUTPUT_FILE"
