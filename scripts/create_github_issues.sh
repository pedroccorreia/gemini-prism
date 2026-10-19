#!/usr/bin/env bash
# ==============================================================================
# Gemini Prism — Automated GitHub Issue Creator for Planned Connectors
# ==============================================================================
set -euo pipefail

REPO="pedroccorreia/gemini-prism"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"
ISSUES_DIR="${ROOT_DIR}/.github/issues"

echo "================================================================="
echo "  Prism Connector Feature Requests — GitHub Issue Publisher"
echo "  Target Repository: ${REPO}"
echo "================================================================="

declare -A ISSUES
ISSUES["01"]="feat(connector): Support Atlassian Confluence Data Connector|enhancement,connector,priority:p1,atlassian|${ISSUES_DIR}/01_confluence_connector.md"
ISSUES["02"]="feat(connector): Support Slack Enterprise Data Connector|enhancement,connector,priority:p2,collaboration|${ISSUES_DIR}/02_slack_connector.md"
ISSUES["03"]="feat(connector): Support HubSpot CRM Data Connector|enhancement,connector,priority:p3,crm|${ISSUES_DIR}/03_hubspot_connector.md"
ISSUES["04"]="feat(connector): Support Google Cloud Identity / Workspace People Directory Connector|enhancement,connector,priority:p4,google-workspace,identity|${ISSUES_DIR}/04_people_directory_connector.md"

create_via_gh() {
  echo ">>> Authenticated GitHub CLI detected. Creating issues..."
  for key in "01" "02" "03" "04"; do
    IFS="|" read -r title labels file <<< "${ISSUES[$key]}"
    echo "Creating Issue [Priority P${key#0}]: ${title}..."
    gh issue create \
      --repo "${REPO}" \
      --title "${title}" \
      --body-file "${file}" \
      --label "${labels}"
  done
  echo ">>> Successfully created all 4 feature request issues on GitHub!"
}

create_via_curl() {
  local token="$1"
  echo ">>> GITHUB_TOKEN detected. Creating issues via GitHub REST API..."
  for key in "01" "02" "03" "04"; do
    IFS="|" read -r title labels file <<< "${ISSUES[$key]}"
    echo "Creating Issue [Priority P${key#0}]: ${title}..."
    body_content=$(cat "${file}")
    
    # Extract labels into JSON array
    IFS="," read -ra label_arr <<< "${labels}"
    labels_json="[]"
    for l in "${label_arr[@]}"; do
      labels_json=$(python3 -c "import json, sys; arr=json.loads(sys.argv[1]); arr.append(sys.argv[2]); print(json.dumps(arr))" "${labels_json}" "${l}")
    done

    payload=$(python3 -c "import json, sys; print(json.dumps({'title': sys.argv[1], 'body': sys.argv[2], 'labels': json.loads(sys.argv[3])}))" "${title}" "${body_content}" "${labels_json}")

    curl -s -f -X POST \
      -H "Authorization: token ${token}" \
      -H "Accept: application/vnd.github.v3+json" \
      "https://api.github.com/repos/${REPO}/issues" \
      -d "${payload}" > /dev/null
  done
  echo ">>> Successfully created all 4 feature request issues via REST API!"
}

# 1. Check if gh CLI is authenticated
if command -v gh >/dev/null 2>&1 && gh auth status >/dev/null 2>&1; then
  create_via_gh
  exit 0
fi

# 2. Check if GITHUB_TOKEN or GH_TOKEN is in environment
if [ -n "${GITHUB_TOKEN:-}" ]; then
  create_via_curl "${GITHUB_TOKEN}"
  exit 0
fi

if [ -n "${GH_TOKEN:-}" ]; then
  create_via_curl "${GH_TOKEN}"
  exit 0
fi

# 3. If neither, print interactive instructions
echo ""
echo "Notice: Neither 'gh' authentication nor GITHUB_TOKEN was detected in this environment."
echo ""
echo "To publish these 4 issues automatically, either:"
echo "  1) Run: gh auth login"
echo "     Then rerun: bash scripts/create_github_issues.sh"
echo "  OR"
echo "  2) Run: export GITHUB_TOKEN=<your_github_token>"
echo "     Then rerun: bash scripts/create_github_issues.sh"
echo ""
echo "Or create them directly using GitHub CLI:"
echo "-----------------------------------------------------------------"
for key in "01" "02" "03" "04"; do
  IFS="|" read -r title labels file <<< "${ISSUES[$key]}"
  echo "gh issue create --repo ${REPO} --title \"${title}\" --body-file \"${file}\" --label \"${labels}\""
done
echo "-----------------------------------------------------------------"
