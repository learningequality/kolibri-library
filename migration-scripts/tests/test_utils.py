"""Tests for migration-scripts utility functions."""

import subprocess
from unittest.mock import patch

import pytest

from utils import check_prerequisites, get_repo_root, run_command


class TestCheckPrerequisites:
    """Tests for check_prerequisites()."""

    def test_succeeds_when_gh_and_git_available(self):
        """Should return without error when both gh and git are found."""
        check_prerequisites()  # Should not raise

    def test_fails_when_gh_missing(self):
        """Should raise SystemExit when gh is not available."""
        original_which = __import__("shutil").which

        def mock_which(cmd):
            if cmd == "gh":
                return None
            return original_which(cmd)

        with patch("shutil.which", side_effect=mock_which):
            with pytest.raises(SystemExit, match="gh"):
                check_prerequisites()

    def test_fails_when_git_missing(self):
        """Should raise SystemExit when git is not available."""
        original_which = __import__("shutil").which

        def mock_which(cmd):
            if cmd == "git":
                return None
            return original_which(cmd)

        with patch("shutil.which", side_effect=mock_which):
            with pytest.raises(SystemExit, match="git"):
                check_prerequisites()


class TestGetRepoRoot:
    """Tests for get_repo_root()."""

    def test_returns_path_string(self):
        """Should return a non-empty string path."""
        root = get_repo_root()
        assert isinstance(root, str)
        assert len(root) > 0

    def test_returns_directory_that_exists(self):
        """Should return a path that actually exists."""
        import os

        root = get_repo_root()
        assert os.path.isdir(root)

    def test_fails_outside_git_repo(self, tmp_path):
        """Should raise RuntimeError when not in a git repo."""
        with patch(
            "subprocess.run",
            side_effect=subprocess.CalledProcessError(128, "git"),
        ):
            with pytest.raises(RuntimeError, match="git"):
                get_repo_root()


class TestRunCommand:
    """Tests for run_command()."""

    def test_returns_stdout(self):
        """Should return the stdout of a successful command."""
        result = run_command(["echo", "hello"])
        assert result.strip() == "hello"

    def test_raises_on_failure(self):
        """Should raise subprocess.CalledProcessError on non-zero exit."""
        with pytest.raises(subprocess.CalledProcessError):
            run_command(["false"])

    def test_accepts_cwd(self, tmp_path):
        """Should run command in the specified working directory."""
        result = run_command(["pwd"], cwd=str(tmp_path))
        assert result.strip() == str(tmp_path)
