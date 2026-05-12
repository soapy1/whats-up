import json
import re
import sys
import argparse
from datetime import datetime, timedelta
import requests
from pathlib import Path
from transformers import pipeline


GITHUB_HEADERS = {
    "Accept": "application/vnd.github.v3+json",
}

VULN_ID_RE = re.compile(
    r"\b(CVE-\d{4}-\d{4,7}|GHSA-[a-z0-9]{4}-[a-z0-9]{4}-[a-z0-9]{4}|CWE-\d+)\b",
    re.I,
)

SECURITY_HINT_RE = re.compile(
    r"\b("
    r"security|vulnerability|exploit|xss|csrf|ssrf|rce|injection|"
    r"path traversal|directory traversal|auth bypass|privilege escalation|"
    r"deserialization|sandbox escape|secret leak|token leak|sanitize|"
    r"permission check|access control|cve|ghsa|cwe"
    r")\b",
    re.I,
)

SECURITY_FILE_RE = re.compile(
    r"(auth|oauth|jwt|session|permission|rbac|acl|crypto|secret|token|"
    r"password|sanitize|csrf|xss|ssrf|parser|sandbox|policy)",
    re.I,
)


def load_team_members(filepath: str = "team.txt") -> list[str]:
    """Load GitHub usernames from team.txt file."""
    try:
        with open(filepath, "r") as f:
            members = [line.strip() for line in f if line.strip()]
        return members
    except FileNotFoundError:
        print(f"Error: {filepath} not found")
        sys.exit(1)


def get_commit_messages(repo_url: str, pr_number: str) -> list[str]:
    """Fetch all commit messages from a PR."""
    try:
        api_url = f"{repo_url}/pulls/{pr_number}/commits"
        
        response = requests.get(api_url, headers=GITHUB_HEADERS)
        response.raise_for_status()
        
        commits = response.json()
        messages = [commit.get("commit", {}).get("message", "") for commit in commits]
        return messages
    except requests.exceptions.RequestException as e:
        print(f"Error fetching commits for {repo_url}/pulls/{pr_number}: {e}")
        return []


def build_text(pr: dict) -> str:
    return f"""
PR_TITLE: {pr.get("title", "")}

PR_BODY:
{pr.get("body", "")}

PR_LABELS:
{" ".join([label.get("name", "") for label in pr.get("labels", [])])}

COMMIT_MESSAGES:
{" ".join(get_commit_messages(pr["repository_url"], pr["number"]))}
""".strip()


def evidence(pr: dict) -> list[str]:
    text = build_text(pr)
    files = pr.get("changed_files", [])

    ev = []

    if VULN_ID_RE.search(text):
        ev.append("explicit_vuln_id")

    if SECURITY_HINT_RE.search(text):
        ev.append("security_keyword")

    if any(SECURITY_FILE_RE.search(f) for f in files):
        ev.append("security_file")

    if pr.get("dependabot_security_alert"):
        ev.append("dependabot_security_alert")

    return ev


def classify_security_fix(pr: dict, classifier) -> str:
    """Classify PR as security fix or not using zero-shot classification."""
    ev = evidence(pr)

    if "explicit_vuln_id" in ev:
        return {"classification": "security", "score": 0.99, "evidence": ev}

    if "dependabot_security_alert" in ev:
        return {"classification": "security", "score": 0.95, "evidence": ev}

    text = build_text(pr)

    result = classifier(
        text,
        candidate_labels=[
            "fixes or mitigates an exploitable security vulnerability"
        ],
        hypothesis_template="This pull request {}.",
        multi_label=True,
    )

    score = float(result["scores"][0])

    if score >= 0.85:
        label = "security"
    elif score <= 0.85 and ev:
        label = "security"
    elif score >= 0.75 or ev:
        label = "needs_review"
    else:
        label = "not_security"

    return {
        "classification": label,
        "score": score,
        "evidence": ev,
    }


def collect_prs(
    members: list[str],
    start_date: datetime,
    end_date: datetime,
    classifier,
    token: str | None = None,
) -> list[dict]:
    """
    Collect public PRs from team members within a given time period.

    Args:
        members: List of GitHub usernames
        start_date: Start date for PR search
        end_date: End date for PR search
        token: GitHub API token (optional, uses GITHUB_TOKEN env var if not provided)

    Returns:
        List of PR dictionaries
    """
    # if token is None:
    #     token = os.getenv("GITHUB_TOKEN")

    headers = GITHUB_HEADERS
    if token:
        headers["Authorization"] = f"token {token}"

    all_prs = []
    start_str = start_date.isoformat()
    end_str = end_date.isoformat()

    for member in members:
        print(f"Fetching PRs for {member}...")

        # Search for PRs authored by this user
        query = f"author:{member} is:pr created:{start_str}..{end_str}"
        url = "https://api.github.com/search/issues"
        params = {"q": query, "sort": "created", "order": "desc", "per_page": 100}

        try:
            response = requests.get(url, headers=headers, params=params)
            response.raise_for_status()

            data = response.json()
            for pr in data.get("items", []):
                classification = classify_security_fix(
                    pr, classifier
                )
                print(f"PR: {pr['title']} - Classified as: {classification['classification']} (score: {classification['score']:.2f}). Evidence: {classification['evidence']}")
                all_prs.append(
                    {
                        "author": member,
                        "title": pr["title"],
                        "body": pr["body"],
                        "url": pr["html_url"],
                        "repository": pr["repository_url"].split("/")[-1],
                        "created_at": pr["created_at"],
                        "state": pr["state"],
                        "contribution_classification": classification["classification"],
                    }
                )
        except requests.exceptions.RequestException as e:
            print(f"Error fetching PRs for {member}: {e}")

    return all_prs


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Collect public GitHub PRs from team members"
    )
    parser.add_argument(
        "--team-file",
        default="team.txt",
        help="Path to the team file containing GitHub usernames (default: team.txt)",
    )
    parser.add_argument(
        "--output",
        help="Path to output file for JSON results",
    )

    args = parser.parse_args()

    # Initialize zero-shot classifier
    print("Loading zero-shot classification model...")
    classifier = pipeline("zero-shot-classification", model="facebook/bart-large-mnli")
    print("Model loaded!\n")

    # Example: Last N days
    end_date = datetime.now()
    start_date = end_date - timedelta(days=30)

    print(f"Collecting PRs from {start_date.date()} to {end_date.date()}")
    print()

    members = load_team_members(args.team_file)
    print(f"Found {len(members)} team members\n")

    prs = collect_prs(members, start_date, end_date, classifier)

    # security_related_prs = 0
    # summary = {
    #     "members": len(members),
    #     "total_prs": len(prs),
    # }
    # security_fixes = {classification: 0 for classification in SECURITY_RELATED_CLASSIFICATIONS}
    
    # for pr in prs:
    #     if pr["contribution_classification"] in SECURITY_RELATED_CLASSIFICATIONS:
    #         security_related_prs += 1
    #         security_fixes[pr["contribution_classification"]] += 1
    #         print(f"{pr['title']} ({pr['url']}) - Classified as: {pr['contribution_classification']}")

    # print(f"\nFound {security_related_prs} security-related PRs\n")
    # print("\033[1mSummary:\033[0m")
    # print(f"Total team members: {summary['members']}")
    # print(f"Total PRs collected: {summary['total_prs']}")
    # print("Security-related PRs by classification:")
    # for classification, count in security_fixes.items():
    #     print(f"  {classification}: {count}")


    if args.output:
        with open(args.output, "w") as f:
            json.dump(prs, f, indent=2)


if __name__ == "__main__":
    main()
