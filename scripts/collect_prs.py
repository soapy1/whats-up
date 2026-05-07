import json
import re
import sys
import argparse
from datetime import datetime, timedelta
import requests
from pathlib import Path
from transformers import pipeline


PACKAGING_CLASSIFICATIONS = [
    "cve patch",
    "version update",
    "dependency update",
    "re-build",
]

SECURITY_RELATED_CLASSIFICATIONS = [
    "security fix",
    "cve patch",
    "exploit mitigation",
    "security enhancement",
]

OTHER_CLASSIFICATIONS = ["other"]

ALL_CLASSIFICATIONS = set(
    SECURITY_RELATED_CLASSIFICATIONS + PACKAGING_CLASSIFICATIONS + OTHER_CLASSIFICATIONS
)

REPO_CLASSIFICATION_MAPPING = {
    "*": SECURITY_RELATED_CLASSIFICATIONS + OTHER_CLASSIFICATIONS,
    "conda-forge/*": PACKAGING_CLASSIFICATIONS,
    "conda-forge/staged-recipes": None,
}


def load_team_members(filepath: str = "team.txt") -> list[str]:
    """Load GitHub usernames from team.txt file."""
    try:
        with open(filepath, "r") as f:
            members = [line.strip() for line in f if line.strip()]
        return members
    except FileNotFoundError:
        print(f"Error: {filepath} not found")
        sys.exit(1)


def classify_security_fix(title: str, body: str | None, repo: str,classifier) -> str:
    """Classify PR as security fix or not using zero-shot classification."""
    combined_text = f"{title}. {body or ''}"

    # Strip HTML comments
    combined_text = re.sub(r"<!--.*?-->", "", combined_text, flags=re.DOTALL)

    # Truncate to avoid token limit issues
    if len(combined_text) > 512:
        combined_text = combined_text[:512]

    # Determine candidate labels based on repository using REPO_CLASSIFICATION_MAPPING
    # Sort by key length (descending) to check most specific patterns first
    candidate_labels = None
    
    for pattern in REPO_CLASSIFICATION_MAPPING.keys():
        if pattern == "*":
            candidate_labels = REPO_CLASSIFICATION_MAPPING[pattern]
        elif pattern.endswith("/*"):
            # Wildcard pattern (e.g., "conda-forge/*")
            prefix = pattern[:-2]
            if repo.startswith(prefix):
                candidate_labels = REPO_CLASSIFICATION_MAPPING[pattern]
        elif repo == pattern:
                candidate_labels = REPO_CLASSIFICATION_MAPPING[pattern]
                break

    if candidate_labels:
        result = classifier(
            combined_text,
            candidate_labels=candidate_labels
        )
        return result["labels"][0]
    else:
        return "No classification available for this repository"


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

    headers = {
        "Accept": "application/vnd.github.v3+json",
    }
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
                repository = f"{pr["repository_url"].split("/")[-2]}/{pr["repository_url"].split("/")[-1]}"
                classification = classify_security_fix(
                    pr["title"], pr["body"], repository, classifier
                )
                all_prs.append(
                    {
                        "author": member,
                        "title": pr["title"],
                        "body": pr["body"],
                        "url": pr["html_url"],
                        "repository": repository,
                        "created_at": pr["created_at"],
                        "state": pr["state"],
                        "contribution_classification": classification,
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
    classifier = pipeline("zero-shot-classification", model="MoritzLaurer/ModernBERT-large-zeroshot-v2.0")
    print("Model loaded!\n")

    # Example: Last N days
    end_date = datetime.now()
    start_date = end_date - timedelta(days=15)

    print(f"Collecting PRs from {start_date.date()} to {end_date.date()}")
    print()

    members = load_team_members(args.team_file)
    print(f"Found {len(members)} team members\n")

    prs = collect_prs(members, start_date, end_date, classifier)

    security_related_prs = 0
    summary = {
        "members": len(members),
        "total_prs": len(prs),
    }
    security_fixes = {classification: 0 for classification in SECURITY_RELATED_CLASSIFICATIONS}
    
    for pr in prs:
        if pr["contribution_classification"] in SECURITY_RELATED_CLASSIFICATIONS:
            security_related_prs += 1
            security_fixes[pr["contribution_classification"]] += 1
            print(f"{pr['title']} ({pr['url']}) - Classified as: {pr['contribution_classification']}")

    print(f"\nFound {security_related_prs} security-related PRs\n")
    print("\033[1mSummary:\033[0m")
    print(f"Total team members: {summary['members']}")
    print(f"Total PRs collected: {summary['total_prs']}")
    print("Security-related PRs by classification:")
    for classification, count in security_fixes.items():
        print(f"  {classification}: {count}")


    if args.output:
        with open(args.output, "w") as f:
            json.dump(prs, f, indent=2)


if __name__ == "__main__":
    main()
