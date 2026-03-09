"""Repository discovery and filtering for sushi-chef migration."""

import json
import sys

from utils import run_command

SUSHI_CHEF_PREFIX = "sushi-chef-"


def derive_subdirectory_name(repo_name):
    """Derive subdirectory name by stripping sushi-chef- prefix and lowercasing.

    Example: sushi-chef-Khan-Academy -> khan-academy
    """
    return repo_name[len(SUSHI_CHEF_PREFIX) :].lower()


def check_collisions(repos):
    """Check for subdirectory name collisions among repos.

    Raises SystemExit if two repos map to the same subdirectory name.
    """
    seen = {}
    for repo in repos:
        subdir = derive_subdirectory_name(repo["name"])
        if subdir in seen:
            sys.exit(
                f"Error: subdirectory name collision detected: "
                f"'{seen[subdir]}' and '{repo['name']}' both map to '{subdir}'"
            )
        seen[subdir] = repo["name"]


def load_manifest(manifest_path):
    """Load the set of already-migrated repo names from the manifest file.

    Returns an empty set if the file doesn't exist or is empty.
    """
    try:
        with open(manifest_path) as f:
            return {line.strip() for line in f if line.strip()}
    except FileNotFoundError:
        return set()


def filter_repos(repos, manifest):
    """Filter repos into eligible and skipped lists.

    Silent skips (not reported): non-sushi-chef, forks, already in manifest.
    Reported skips: empty repos (no default branch), multi-branch, open PRs.
    Multi-branch and open PR checks are deferred to a secondary pass.

    Returns (eligible, skipped) where skipped contains dicts with 'name' and 'reason'.
    """
    eligible = []
    skipped = []

    for repo in repos:
        name = repo["name"]

        # Silent skip: not a sushi-chef repo
        if not name.startswith(SUSHI_CHEF_PREFIX):
            continue

        # Silent skip: fork
        if repo.get("isFork", False):
            continue

        # Silent skip: already migrated
        if name in manifest:
            continue

        # Reported skip: empty repo (no default branch / no commits)
        if repo.get("defaultBranchRef") is None:
            skipped.append({"name": name, "reason": "Empty repo (no commits)"})
            continue

        eligible.append(repo)

    return eligible, skipped


def sort_repos_chronologically(repos):
    """Sort repos by pushedAt date, oldest first."""
    return sorted(repos, key=lambda r: r.get("pushedAt", ""))


def check_multi_branch_and_prs(repos):
    """Check each repo for multiple branches and open PRs via gh CLI.

    Excludes stale branches (0 commits ahead of default), dependabot branches,
    and dependabot PRs from the counts.

    Returns (eligible, skipped) lists.
    """
    eligible = []
    skipped = []

    for repo in repos:
        name = repo["name"]
        org_repo = f"learningequality/{name}"
        default_branch = repo.get("defaultBranchRef", {}).get("name", "main")

        # Check branch count (excluding stale and dependabot branches)
        try:
            branches_json = run_command(
                [
                    "gh",
                    "api",
                    f"repos/{org_repo}/branches",
                    "--paginate",
                    "--jq",
                    ".[].name",
                ]
            )
            branch_names = [line for line in branches_json.strip().split("\n") if line.strip()]

            # Filter out default branch, dependabot branches, and stale branches
            extra_branches = []
            for branch in branch_names:
                if branch == default_branch:
                    continue
                if branch.startswith("dependabot/"):
                    continue
                # Check if branch is stale (0 commits ahead of default)
                try:
                    compare_json = run_command(
                        [
                            "gh",
                            "api",
                            f"repos/{org_repo}/compare/{default_branch}...{branch}",
                            "--jq",
                            "{ahead_by: .ahead_by}",
                        ]
                    )
                    compare_data = json.loads(compare_json)
                    if compare_data.get("ahead_by", 1) == 0:
                        continue
                except Exception:
                    pass
                extra_branches.append(branch)

            if extra_branches:
                skipped.append(
                    {
                        "name": name,
                        "reason": f"Multiple branches ({len(extra_branches) + 1})",
                    }
                )
                continue
        except Exception:
            # If we can't check, let it through (will fail later if there's an issue)
            pass

        # Check open PRs (excluding dependabot PRs)
        try:
            prs_json = run_command(
                [
                    "gh",
                    "pr",
                    "list",
                    "--repo",
                    org_repo,
                    "--state",
                    "open",
                    "--json",
                    "number,headRefName,author",
                ]
            )
            prs = json.loads(prs_json)
            # Filter out dependabot PRs
            real_prs = [
                pr
                for pr in prs
                if not pr.get("headRefName", "").startswith("dependabot/")
                and pr.get("author", {}).get("login") != "dependabot[bot]"
            ]
            if real_prs:
                skipped.append(
                    {
                        "name": name,
                        "reason": f"Open pull requests ({len(real_prs)})",
                    }
                )
                continue
        except Exception:
            pass

        eligible.append(repo)

    return eligible, skipped


def discover_repos(manifest_path="migration-scripts/manifest.txt"):
    """Discover and filter sushi-chef repos from the learningequality org.

    Returns (eligible, skipped) where eligible repos are sorted oldest-first.
    """
    # Fetch all public, non-fork, non-archived repos
    output = run_command(
        [
            "gh",
            "repo",
            "list",
            "learningequality",
            "--visibility",
            "public",
            "--no-archived",
            "--source",
            "--limit",
            "1000",
            "--json",
            "name,isFork,defaultBranchRef,pushedAt",
        ]
    )
    repos = json.loads(output)

    manifest = load_manifest(manifest_path)
    eligible, skipped = filter_repos(repos, manifest)

    # Check for collisions before doing expensive API calls
    check_collisions(eligible)

    # Check multi-branch and open PRs
    eligible, extra_skipped = check_multi_branch_and_prs(eligible)
    skipped.extend(extra_skipped)

    # Sort oldest first
    eligible = sort_repos_chronologically(eligible)

    return eligible, skipped
