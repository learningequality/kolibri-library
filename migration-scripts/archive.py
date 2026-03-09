"""Archive migrated sushi-chef-* repos."""

import json
import logging
import os
import sys

from discovery import load_manifest
from utils import check_prerequisites, get_repo_root, run_command

logger = logging.getLogger(__name__)


def is_repo_archived(repo_name):
    """Check if a repo is already archived.

    Returns True if archived, False otherwise (including on error).
    """
    try:
        output = run_command(
            ["gh", "repo", "view", f"learningequality/{repo_name}", "--json", "isArchived"]
        )
        data = json.loads(output)
        return data.get("isArchived", False)
    except Exception:
        return False


def archive_repo(repo_name):
    """Archive a single repo via gh CLI.

    Returns True on success, False on failure.
    """
    try:
        run_command(["gh", "repo", "archive", f"learningequality/{repo_name}", "--yes"])
        return True
    except Exception:
        logger.error("Failed to archive %s", repo_name)
        return False


def archive_repos(repo_names):
    """Archive a list of repos, skipping already-archived ones.

    Returns a dict with counts: archived, already_archived, failed.
    """
    archived = 0
    already_archived = 0
    failed = 0

    for name in repo_names:
        if is_repo_archived(name):
            already_archived += 1
            logger.info("Already archived: %s", name)
            continue

        if archive_repo(name):
            archived += 1
            logger.info("Archived: %s", name)
        else:
            failed += 1
            logger.error("Failed to archive: %s", name)

    return {
        "archived": archived,
        "already_archived": already_archived,
        "failed": failed,
    }


def main():
    """Entry point for the archive script."""
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")

    check_prerequisites()
    repo_root = get_repo_root()
    manifest_path = os.path.join(repo_root, "migration-scripts", "manifest.txt")

    repo_names = sorted(load_manifest(manifest_path))
    if not repo_names:
        print("No repos in manifest to archive.")
        return 0

    logger.info("Archiving %d repos from manifest...", len(repo_names))
    result = archive_repos(repo_names)

    print("\nArchive Summary:")
    print(f"  Archived: {result['archived']}")
    print(f"  Already archived: {result['already_archived']}")
    print(f"  Failed: {result['failed']}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
