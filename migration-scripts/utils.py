"""Shared utilities for migration scripts."""

import shutil
import subprocess
import sys


def check_prerequisites():
    """Verify that gh and git are available on the system.

    Raises SystemExit with a clear error message if either tool is missing.
    """
    for tool in ("gh", "git"):
        if shutil.which(tool) is None:
            sys.exit(f"Error: '{tool}' is not installed or not on PATH. Please install it first.")


def get_repo_root():
    """Detect the repository root via git rev-parse --show-toplevel.

    Returns the absolute path to the repo root as a string.
    Raises RuntimeError if not inside a git repository.
    """
    try:
        result = run_command(["git", "rev-parse", "--show-toplevel"])
        return result.strip()
    except subprocess.CalledProcessError as e:
        raise RuntimeError(
            "Not inside a git repository. Run this script from within a cloned repo."
        ) from e


def run_command(cmd, cwd=None):
    """Run a subprocess command and return its stdout.

    Args:
        cmd: Command and arguments as a list of strings.
        cwd: Optional working directory for the command.

    Returns:
        The command's stdout as a string.

    Raises:
        subprocess.CalledProcessError: If the command exits with non-zero status.
    """
    result = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        check=True,
        cwd=cwd,
    )
    return result.stdout
