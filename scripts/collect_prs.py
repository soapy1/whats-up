import json
import os
import sys
import argparse
from datetime import datetime, timedelta
import requests
from pathlib import Path
from transformers import pipeline


def load_team_members(filepath: str = "team.txt") -> list[str]:
    """Load GitHub usernames from team.txt file."""
    try:
        with open(filepath, "r") as f:
            members = [line.strip() for line in f if line.strip()]
        return members
    except FileNotFoundError:
        print(f"Error: {filepath} not found")
        sys.exit(1)


def classify_security_fix(title: str, body: str | None, classifier) -> str:
    """Classify PR as security fix or not using zero-shot classification."""
    combined_text = f"{title}. {body or ''}"

    # Strip HTML comments
    import re

    combined_text = re.sub(r"<!--.*?-->", "", combined_text, flags=re.DOTALL)

    # Truncate to avoid token limit issues
    if len(combined_text) > 512:
        combined_text = combined_text[:512]

    result = classifier(
        combined_text,
        candidate_labels=["security fix", "cve patch", "other"],
        # multi_class=False
    )

    return result["labels"][0]


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
                classification = classify_security_fix(
                    pr["title"], pr["body"], classifier
                )
                all_prs.append(
                    {
                        "author": member,
                        "title": pr["title"],
                        "body": pr["body"],
                        "url": pr["html_url"],
                        "repository": pr["repository_url"].split("/")[-1],
                        "created_at": pr["created_at"],
                        "state": pr["state"],
                        "security_classification": classification,
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

    print(f"\nFound {len(prs)} PRs\n")

    if args.output:
        with open(args.output, "w") as f:
            json.dump(prs, f, indent=2)
        print(f"Results saved to {args.output}")


if __name__ == "__main__":
    main()
