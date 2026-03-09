"""Per-repo migration pipeline: clone, linearize, rewrite paths."""

import os
import shutil
import subprocess
import tempfile

from utils import run_command


def clone_repo(source_url, target_dir, default_branch="main"):
    """Clone a repo into target_dir, single branch only.

    Args:
        source_url: URL or path of the source repository.
        target_dir: Directory to clone into.
        default_branch: The default branch to clone.
    """
    run_command(
        [
            "git",
            "clone",
            "--single-branch",
            "--branch",
            default_branch,
            source_url,
            target_dir,
        ]
    )


def linearize_history(repo_dir):
    """Linearize history by rebasing to flatten merge commits.

    Uses git rebase --root to make the history fully linear.
    Safe for repos that are already linear (no-op).
    """
    # Check if there are any merge commits
    result = run_command(
        ["git", "log", "--merges", "--oneline"],
        cwd=repo_dir,
    )
    if not result.strip():
        # Already linear, nothing to do
        return

    # Configure git user for rebase (needed in clone context)
    run_command(
        ["git", "config", "user.email", "migration@learningequality.org"],
        cwd=repo_dir,
    )
    run_command(
        ["git", "config", "user.name", "Migration Script"],
        cwd=repo_dir,
    )

    # Save the original tree state before linearizing
    original_tree = run_command(
        ["git", "rev-parse", "HEAD^{tree}"],
        cwd=repo_dir,
    ).strip()

    # Use --strategy-option=theirs since merge commits are present and
    # conflicts are likely; the tree-fixup below guarantees correctness
    run_command(
        ["git", "rebase", "--root", "--strategy-option=theirs"],
        cwd=repo_dir,
    )

    # Verify the tree matches the original; fix up if auto-resolution diverged
    new_tree = run_command(
        ["git", "rev-parse", "HEAD^{tree}"],
        cwd=repo_dir,
    ).strip()

    if new_tree != original_tree:
        # Restore the original tree and commit the correction
        run_command(["git", "read-tree", "--reset", "-u", original_tree], cwd=repo_dir)
        run_command(
            ["git", "commit", "-m", "Restore original tree after linearization"],
            cwd=repo_dir,
        )


def rewrite_paths(repo_dir, subdirectory):
    """Rewrite all paths in the repo history to be under a subdirectory.

    Uses git-filter-repo --force --to-subdirectory-filter.
    """
    run_command(
        [
            "git",
            "filter-repo",
            "--force",
            "--to-subdirectory-filter",
            subdirectory,
        ],
        cwd=repo_dir,
    )


def run_pipeline(source_url, subdirectory, default_branch="main"):
    """Run the full migration pipeline for a single repo.

    Steps:
    1. Clone into temp directory
    2. Linearize history
    3. Rewrite paths into subdirectory

    Args:
        source_url: URL or path of the source repository.
        subdirectory: Target subdirectory name.
        default_branch: The default branch to clone.

    Returns:
        Path to the processed repo (temp directory — caller manages cleanup).
    """
    tmp_dir = tempfile.mkdtemp(prefix=f"migration-{subdirectory}-")
    clone_dir = os.path.join(tmp_dir, "repo")

    clone_repo(source_url, clone_dir, default_branch=default_branch)
    linearize_history(clone_dir)
    rewrite_paths(clone_dir, subdirectory)

    return clone_dir


def process_repo(source_url, subdirectory, default_branch="main"):
    """Run the migration pipeline with temp directory cleanup and error handling.

    Returns a dict with keys:
        success: bool
        subdirectory: str
        commits: list of SHA strings (oldest first) on success
        repo_dir: None (always cleaned up)
        error: str or None
    """
    tmp_dir = tempfile.mkdtemp(prefix=f"migration-{subdirectory}-")
    try:
        clone_dir = os.path.join(tmp_dir, "repo")
        clone_repo(source_url, clone_dir, default_branch=default_branch)
        linearize_history(clone_dir)
        rewrite_paths(clone_dir, subdirectory)

        # Collect commit SHAs in chronological order (oldest first)
        output = run_command(
            ["git", "rev-list", "--reverse", "HEAD"],
            cwd=clone_dir,
        )
        commits = [line.strip() for line in output.strip().split("\n") if line.strip()]

        return {
            "success": True,
            "subdirectory": subdirectory,
            "commits": commits,
            "repo_dir": None,
            "error": None,
        }
    except subprocess.CalledProcessError as e:
        detail = e.stderr if e.stderr else e.stdout if e.stdout else str(e)
        return {
            "success": False,
            "subdirectory": subdirectory,
            "commits": [],
            "repo_dir": None,
            "error": f"Command failed: {e.cmd}: {detail}",
        }
    except Exception as e:
        return {
            "success": False,
            "subdirectory": subdirectory,
            "commits": [],
            "repo_dir": None,
            "error": str(e),
        }
    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)
