import json
import re
import os
import sys
import argparse
from datetime import datetime, timedelta
import requests
from transformers import pipeline

SECURITY_RELATED_CLASSIFICATIONS = ["security"]

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


def get_github_headers() -> dict:
    """Get GitHub API headers, including authorization if GITHUB_TOKEN is set."""
    headers = GITHUB_HEADERS.copy()
    token = os.getenv("GITHUB_TOKEN")
    if token:
        headers["Authorization"] = f"Bearer {token}"
    return headers


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
    github_headers = get_github_headers()
    try:
        api_url = f"{repo_url}/pulls/{pr_number}/commits"

        response = requests.get(api_url, headers=github_headers)
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
        candidate_labels=["fixes or mitigates an exploitable security vulnerability"],
        hypothesis_template="This pull request {}.",
        multi_label=True,
    )

    score = float(result["scores"][0])

    if score >= 0.95:
        label = "security"
    elif score <= 0.85 and ev:
        label = "security"
    elif score <= 0.70:
        label = "not_secuirity"
    else:
        label = "needs_review"

    return {
        "classification": label,
        "score": score,
        "evidence": ev,
    }


def extract_versions_from_diff(diff: str) -> tuple[str | None, str | None]:
    """
    Extract old and new version numbers from a diff.
    Returns (old_version, new_version) or (None, None) if not found.
    """
    # Pattern to detect version changes in diff
    # Looks for lines like: -  version: 1.2.3
    #                      +  version: 1.2.4
    version_pattern = re.compile(r'version\s*[:=]\s*"([\d\.]+)"', re.MULTILINE)

    matches = version_pattern.findall(diff)
    if len(matches) >= 2:
        return (matches[0], matches[1])

    return (None, None)


def has_version_update_in_diff(diff: str) -> bool:
    """
    Check if the diff contains a package version update.
    Looks for version changes in conda-forge feedstock files (meta.yaml, recipe.yaml, etc).
    """
    old_version, new_version = extract_versions_from_diff(diff)

    if old_version and new_version:
        return True

    # Also check for common conda-forge version reference patterns
    sha_pattern = re.compile(r"^[\+\-]\s+sha256\s*:\s*[a-f0-9]{64}", re.MULTILINE)
    if sha_pattern.search(diff):
        return True

    return False


def query_osv_for_cves(
    package_name: str, old_version: str, new_version: str | None = None
) -> tuple[list[str], list[str]]:
    """
    Query OSV.dev API to find CVEs for a specific package version.
    Returns a tuple of (vulnerable_cves, fixed_cves).

    Args:
        package_name: Name of the package
        old_version: The old/current version to check for vulnerabilities
        new_version: The new version to check if vulnerabilities are fixed (optional)

    Returns:
        list of fixed cves as CVE/GHSA IDs
    """
    vulnerable_cves = []
    fixed_cves = []

    try:
        osv_url = "https://api.osv.dev/v1/query"
        payload = {
            "version": old_version,
            "package": {
                "name": package_name,
                "ecosystem": "PyPI",  # Default to PyPI, could be extended for other ecosystems
            },
        }

        response = requests.post(osv_url, json=payload, timeout=10)
        response.raise_for_status()

        data = response.json()
        vulns = data.get("vulns", [])

        for vuln in vulns:
            vuln_id = vuln.get("id", "")
            if not vuln_id:
                continue

            vulnerable_cves.append(vuln_id)

            # If new_version is provided, check if this vulnerability is fixed
            if new_version:
                affected_versions = vuln.get("affected", [])
                is_fixed = False

                for affected in affected_versions:
                    # Check if new_version is outside the affected range (i.e., fixed)
                    if affected.get("package", {}).get("name") == package_name:
                        ranges = affected.get("ranges", [])
                        for range_info in ranges:
                            events = range_info.get("events", [])
                            for event in events:
                                # Check if new_version is >= fixed version
                                if "fixed" in event:
                                    fixed_version = event.get("fixed", "")
                                    # Simple version comparison (assumes semantic versioning)
                                    if _version_gte(new_version, fixed_version):
                                        is_fixed = True
                                        break
                            if is_fixed:
                                break
                    if is_fixed:
                        break

                if is_fixed:
                    fixed_cves.append(vuln_id)
                    vulnerable_cves.remove(vuln_id)

        return fixed_cves
    except requests.exceptions.RequestException as e:
        print(f"Error querying OSV.dev for {package_name}@{old_version}: {e}")
        return ([], [])


def _version_gte(version1: str, version2: str) -> bool:
    """
    Check if version1 >= version2 using semantic versioning comparison.
    Simple comparison that works for most cases.
    """
    try:
        from packaging import version

        return version.parse(version1) >= version.parse(version2)
    except version.InvalidVersion:
        # Fallback to simple string comparison if packaging not available
        v1_parts = [int(x) for x in version1.split(".")]
        v2_parts = [int(x) for x in version2.split(".")]
        # Pad with zeros
        max_len = max(len(v1_parts), len(v2_parts))
        v1_parts += [0] * (max_len - len(v1_parts))
        v2_parts += [0] * (max_len - len(v2_parts))
        return v1_parts >= v2_parts


def classify_conda_forge_feedstock_fix(pr: dict) -> dict:
    """
    Classify PR as conda-forge feedstock pr as related to a security fix.

    A conda-forge feedstock PR is considered related to a security fix if:
    * it explicitly mentions a CVE or GHSA ID in the title, body, or labels
    * in diff includes a version number bump for a package that has a known security
      vulnerability listed on osv.dev
    """
    ev = evidence(pr)

    github_headers = get_github_headers()
    try:
        diff_url = pr["pull_request"]["diff_url"]
        response = requests.get(diff_url, headers=github_headers)
        response.raise_for_status()
        diff = response.text

        if has_version_update_in_diff(diff):
            # Extract package name from repo name (e.g., "jinja2-feedstock" -> "jinja2")
            repo_name = pr["repository_url"].split("/")[-1]
            package_name = repo_name.replace("-feedstock", "").replace("-", "_")

            # Extract old and new versions
            old_version, new_version = extract_versions_from_diff(diff)

            if old_version:
                # Query OSV.dev for vulnerabilities in the old version and check if fixed in new version
                fixed_cves = query_osv_for_cves(package_name, old_version, new_version)
                if fixed_cves:
                    ev.append(f"cves_fixed:{','.join(fixed_cves)}")
                    return {"classification": "security", "score": 0.99, "evidence": ev}

    except (requests.exceptions.RequestException, KeyError) as e:
        print(f"Error processing PR diff: {e}")

    if "explicit_vuln_id" in ev or "security_keyword" in ev:
        return {"classification": "security", "score": 0.95, "evidence": ev}

    return {"classification": "not_security", "score": 0.01, "evidence": ev}


def collect_prs(
    members: list[str],
    start_date: datetime,
    end_date: datetime,
    classifier,
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
    headers = get_github_headers()

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
                if "openteams-ai/" in pr["repository_url"]:
                    continue  # Skip PRs in openteams-ai org
                if "quansight/" in pr["repository_url"]:
                    continue  # Skip PRs in quansight org

                if (
                    "conda-forge/" in pr["repository_url"]
                    and "-feedstock" in pr["repository_url"]
                ):
                    classification = classify_conda_forge_feedstock_fix(pr)
                else:
                    classification = classify_security_fix(pr, classifier)
                print(
                    f"PR: {pr['title']} - Classified as: {classification['classification']} (score: {classification['score']:.2f}). Evidence: {classification['evidence']}"
                )
                all_prs.append(
                    {
                        "author": member,
                        "title": pr["title"],
                        "body": pr["body"],
                        "url": pr["html_url"],
                        "repository": f"{pr["repository_url"].split("/")[-2]}/{pr["repository_url"].split("/")[-1]}",
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
    classifier = pipeline("zero-shot-classification", model="MoritzLaurer/ModernBERT-large-zeroshot-v2.0")
    print("Model loaded!\n")

    # Example: Last N days
    end_date = datetime.now()
    start_date = end_date - timedelta(days=5)

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
    security_fixes = {
        classification: 0 for classification in SECURITY_RELATED_CLASSIFICATIONS
    }

    for pr in prs:
        if pr["contribution_classification"] in SECURITY_RELATED_CLASSIFICATIONS:
            security_related_prs += 1
            security_fixes[pr["contribution_classification"]] += 1
            print(
                f"{pr['title']} ({pr['url']}) - Classified as: {pr['contribution_classification']}"
            )

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
