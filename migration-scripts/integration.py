"""Phase 4: Integration, validation, and manifest management.

Integrates rewritten commits into the target repo, validates correctness,
and maintains the migration manifest.
"""

import os
import shutil
import subprocess
import tempfile

from utils import run_command


def integrate_repo(target_dir, processed_repo_dir, commits):
    """Cherry-pick commits from a processed repo into the target repo.

    Adds the processed repo as a temporary remote, fetches its objects,
    and cherry-picks each commit in order. No merge commits are created.

    Args:
        target_dir: Path to the target repository (e.g. kolibri-library).
        processed_repo_dir: Path to the processed repo with rewritten paths.
        commits: List of commit SHAs to cherry-pick (oldest first).

    Returns:
        The HEAD SHA of target_dir before integration (for rollback).
    """
    pre_head = run_command(["git", "rev-parse", "HEAD"], cwd=target_dir).strip()

    remote_name = "migration-temp"

    # Remove stale remote if it exists
    try:
        run_command(["git", "remote", "remove", remote_name], cwd=target_dir)
    except subprocess.CalledProcessError:
        pass

    run_command(["git", "remote", "add", remote_name, processed_repo_dir], cwd=target_dir)
    try:
        run_command(["git", "fetch", remote_name], cwd=target_dir)

        for sha in commits:
            run_command(["git", "cherry-pick", sha], cwd=target_dir)
    finally:
        # Always clean up the remote
        try:
            run_command(["git", "remote", "remove", remote_name], cwd=target_dir)
        except subprocess.CalledProcessError:
            pass

    return pre_head


def validate_repo(target_dir, subdirectory, source_url, default_branch="main"):
    """Validate that the integrated subdirectory matches the original source repo.

    Clones the source repo fresh and compares file contents against the
    subdirectory in the target repo using git diff --no-index.

    Args:
        target_dir: Path to the target repository.
        subdirectory: Name of the subdirectory that was integrated.
        source_url: URL or path of the original source repository.
        default_branch: The default branch of the source repo.

    Returns:
        Dict with keys:
            valid: bool - True if contents match
            diff: str - diff output if validation failed, empty string otherwise
    """
    tmp_dir = tempfile.mkdtemp(prefix=f"validate-{subdirectory}-")
    try:
        clone_dir = os.path.join(tmp_dir, "repo")
        run_command(
            ["git", "clone", "--single-branch", "--branch", default_branch, source_url, clone_dir]
        )

        subdirectory_path = os.path.join(target_dir, subdirectory)

        # Remove .git from the fresh clone so we only compare working tree files
        shutil.rmtree(os.path.join(clone_dir, ".git"))

        # Use git diff --no-index to compare the two directories
        # This returns exit code 1 if there are differences, so we can't use check=True
        result = subprocess.run(
            ["git", "diff", "--no-index", clone_dir, subdirectory_path],
            capture_output=True,
            text=True,
            cwd=target_dir,
        )

        # Exit code 0 = no differences, 1 = differences found
        if result.returncode == 0:
            return {"valid": True, "diff": ""}
        else:
            return {"valid": False, "diff": result.stdout}
    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)


def save_manifest(manifest_path, repo_names):
    """Write the list of migrated repo names to the manifest file.

    Overwrites the file completely (not append).

    Args:
        manifest_path: Path to the manifest file.
        repo_names: List of repo name strings to write.
    """
    with open(manifest_path, "w") as f:
        for name in repo_names:
            f.write(f"{name}\n")
