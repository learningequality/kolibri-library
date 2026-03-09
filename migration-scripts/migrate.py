"""Migrate sushi-chef-* repos into kolibri-library."""

import logging
import os
import shutil
import subprocess
import sys
import tempfile

from discovery import derive_subdirectory_name, discover_repos, load_manifest
from integration import integrate_repo, save_manifest, validate_repo
from pipeline import clone_repo, linearize_history, rewrite_paths
from utils import check_prerequisites, get_repo_root, run_command

logger = logging.getLogger(__name__)


def process_and_integrate_repo(source_url, subdirectory, default_branch, target_dir):
    """Run the full pipeline for a single repo: clone, rewrite, integrate, validate.

    Returns a dict with keys:
        success: bool
        subdirectory: str
        error: str or None
        validation_diff: str or None
    """
    tmp_dir = tempfile.mkdtemp(prefix=f"migration-{subdirectory}-")
    try:
        clone_dir = os.path.join(tmp_dir, "repo")
        clone_repo(source_url, clone_dir, default_branch=default_branch)
        linearize_history(clone_dir)
        rewrite_paths(clone_dir, subdirectory)

        # Collect commit SHAs
        output = run_command(
            ["git", "rev-list", "--reverse", "HEAD"],
            cwd=clone_dir,
        )
        commits = [line.strip() for line in output.strip().split("\n") if line.strip()]

        # Integrate into target
        pre_head = integrate_repo(target_dir, clone_dir, commits)

        # Validate
        result = validate_repo(target_dir, subdirectory, source_url, default_branch=default_branch)

        if not result["valid"]:
            # Revert on validation failure
            logger.warning("Validation failed for %s, reverting", subdirectory)
            run_command(["git", "reset", "--hard", pre_head], cwd=target_dir)
            return {
                "success": False,
                "subdirectory": subdirectory,
                "error": "Validation failed",
                "validation_diff": result["diff"],
            }

        return {
            "success": True,
            "subdirectory": subdirectory,
            "error": None,
            "validation_diff": None,
        }

    except subprocess.CalledProcessError as e:
        detail = e.stderr if e.stderr else e.stdout if e.stdout else str(e)
        return {
            "success": False,
            "subdirectory": subdirectory,
            "error": f"Command failed: {e.cmd}: {detail}",
            "validation_diff": None,
        }
    except Exception as e:
        return {
            "success": False,
            "subdirectory": subdirectory,
            "error": str(e),
            "validation_diff": None,
        }
    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)


def generate_report(discovered, migrated, previously_migrated, skipped, failed, validation_failed):
    """Generate a human-readable migration report.

    Args:
        discovered: Total number of repos discovered.
        migrated: List of repo names successfully migrated in this run.
        previously_migrated: Number of repos already in manifest.
        skipped: List of dicts with 'name' and 'reason' keys.
        failed: List of dicts with 'name' and 'error' keys.
        validation_failed: List of dicts with 'name' and 'diff' keys.

    Returns:
        Formatted report string.
    """
    lines = []
    lines.append("=" * 60)
    lines.append("Migration Report")
    lines.append("=" * 60)
    lines.append("")
    lines.append(f"Discovered: {discovered}")
    lines.append(f"Migrated: {len(migrated)}")
    lines.append(f"Previously migrated: {previously_migrated}")
    lines.append(f"Skipped: {len(skipped)}")
    lines.append(f"Failed: {len(failed)}")
    lines.append(f"Validation failures: {len(validation_failed)}")

    if migrated:
        lines.append("")
        lines.append("--- Migrated ---")
        for name in migrated:
            lines.append(f"  {name}")

    if skipped:
        lines.append("")
        lines.append("--- Skipped ---")
        for entry in skipped:
            lines.append(f"  {entry['name']}: {entry['reason']}")

    if failed:
        lines.append("")
        lines.append("--- Failed ---")
        for entry in failed:
            lines.append(f"  {entry['name']}: {entry['error']}")

    if validation_failed:
        lines.append("")
        lines.append("--- Validation Failures ---")
        for entry in validation_failed:
            lines.append(f"  {entry['name']}")

    lines.append("")
    return "\n".join(lines)


def main():
    """Entry point for the migration script."""
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")

    check_prerequisites()
    repo_root = get_repo_root()
    manifest_path = os.path.join(repo_root, "migration-scripts", "manifest.txt")

    logger.info("Discovering repos...")
    eligible, skipped = discover_repos(manifest_path=manifest_path)
    previously_migrated = len(load_manifest(manifest_path))
    discovered = len(eligible) + len(skipped) + previously_migrated

    logger.info("Found %d eligible repos, %d skipped", len(eligible), len(skipped))

    migrated = []
    failed = []
    validation_failed = []

    for repo in eligible:
        name = repo["name"]
        subdirectory = derive_subdirectory_name(name)
        default_branch = repo.get("defaultBranchRef", {}).get("name", "main")
        source_url = f"https://github.com/learningequality/{name}.git"

        logger.info("Processing %s -> %s/", name, subdirectory)

        result = process_and_integrate_repo(
            source_url=source_url,
            subdirectory=subdirectory,
            default_branch=default_branch,
            target_dir=repo_root,
        )

        if result["success"]:
            migrated.append(name)
            logger.info("Successfully migrated %s", name)
        elif result.get("validation_diff"):
            validation_failed.append({"name": name, "diff": result["validation_diff"]})
            logger.warning("Validation failed for %s", name)
        else:
            failed.append({"name": name, "error": result["error"]})
            logger.error("Failed to migrate %s: %s", name, result["error"])

    # Update manifest with all migrated repos (previous + new)
    all_migrated = sorted(load_manifest(manifest_path) | set(migrated))
    save_manifest(manifest_path, all_migrated)

    if migrated:
        # Commit manifest update
        run_command(["git", "add", manifest_path], cwd=repo_root)
        run_command(
            ["git", "commit", "-m", "Update migration manifest"],
            cwd=repo_root,
        )

    report = generate_report(
        discovered=discovered,
        migrated=migrated,
        previously_migrated=previously_migrated,
        skipped=skipped,
        failed=failed,
        validation_failed=validation_failed,
    )
    print(report)

    return 0


if __name__ == "__main__":
    sys.exit(main())
