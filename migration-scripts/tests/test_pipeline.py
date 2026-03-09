"""Tests for the per-repo migration pipeline."""

import os
import subprocess

from pipeline import clone_repo, linearize_history, process_repo, rewrite_paths, run_pipeline


def _create_test_repo(path, num_commits=3, with_merge=False):
    """Helper to create a small git repo with some commits."""
    os.makedirs(path, exist_ok=True)
    run_opts = {"cwd": path, "check": True, "capture_output": True}
    subprocess.run(["git", "init", "--initial-branch=main"], **run_opts)
    subprocess.run(["git", "config", "user.email", "test@test.com"], **run_opts)
    subprocess.run(["git", "config", "user.name", "Test"], **run_opts)

    for i in range(num_commits):
        filepath = os.path.join(path, f"file{i}.txt")
        with open(filepath, "w") as f:
            f.write(f"content {i}\n")
        subprocess.run(["git", "add", "."], cwd=path, check=True, capture_output=True)
        subprocess.run(
            ["git", "commit", "-m", f"commit {i}"],
            cwd=path,
            check=True,
            capture_output=True,
        )

    if with_merge:
        # Create a branch with a commit and merge it
        subprocess.run(
            ["git", "checkout", "-b", "feature"],
            cwd=path,
            check=True,
            capture_output=True,
        )
        filepath = os.path.join(path, "feature.txt")
        with open(filepath, "w") as f:
            f.write("feature content\n")
        subprocess.run(["git", "add", "."], cwd=path, check=True, capture_output=True)
        subprocess.run(
            ["git", "commit", "-m", "feature commit"],
            cwd=path,
            check=True,
            capture_output=True,
        )
        subprocess.run(
            ["git", "checkout", "main"],
            cwd=path,
            check=True,
            capture_output=True,
        )
        subprocess.run(
            ["git", "merge", "feature", "--no-ff", "-m", "Merge feature"],
            cwd=path,
            check=True,
            capture_output=True,
        )


class TestCloneRepo:
    """Tests for clone_repo()."""

    def test_clones_into_target_dir(self, tmp_path):
        source = str(tmp_path / "source")
        _create_test_repo(source)

        clone_dir = str(tmp_path / "clone")
        clone_repo(source, clone_dir, default_branch="main")

        assert os.path.isdir(os.path.join(clone_dir, ".git"))
        assert os.path.isfile(os.path.join(clone_dir, "file0.txt"))

    def test_single_branch_only(self, tmp_path):
        source = str(tmp_path / "source")
        _create_test_repo(source, with_merge=True)

        clone_dir = str(tmp_path / "clone")
        clone_repo(source, clone_dir, default_branch="main")

        # Should only have one local branch
        result = subprocess.run(
            ["git", "branch"],
            cwd=clone_dir,
            capture_output=True,
            text=True,
            check=True,
        )
        local_branches = [b.strip() for b in result.stdout.strip().split("\n") if b.strip()]
        assert len(local_branches) == 1


class TestLinearizeHistory:
    """Tests for linearize_history()."""

    def test_already_linear_is_noop(self, tmp_path):
        source = str(tmp_path / "source")
        _create_test_repo(source, num_commits=3)

        clone_dir = str(tmp_path / "clone")
        clone_repo(source, clone_dir, default_branch="main")

        # Count commits before
        result = subprocess.run(
            ["git", "rev-list", "--count", "HEAD"],
            cwd=clone_dir,
            capture_output=True,
            text=True,
            check=True,
        )
        count_before = int(result.stdout.strip())

        linearize_history(clone_dir)

        result = subprocess.run(
            ["git", "rev-list", "--count", "HEAD"],
            cwd=clone_dir,
            capture_output=True,
            text=True,
            check=True,
        )
        count_after = int(result.stdout.strip())
        assert count_after == count_before

    def test_flattens_merge_commits(self, tmp_path):
        source = str(tmp_path / "source")
        _create_test_repo(source, with_merge=True)

        clone_dir = str(tmp_path / "clone")
        # Clone with full history (not single-branch to get merge)
        subprocess.run(
            ["git", "clone", source, clone_dir],
            check=True,
            capture_output=True,
        )

        linearize_history(clone_dir)

        # Verify no merge commits remain
        result = subprocess.run(
            ["git", "log", "--merges", "--oneline"],
            cwd=clone_dir,
            capture_output=True,
            text=True,
            check=True,
        )
        assert result.stdout.strip() == ""

    def test_single_commit_repo(self, tmp_path):
        source = str(tmp_path / "source")
        _create_test_repo(source, num_commits=1)

        clone_dir = str(tmp_path / "clone")
        clone_repo(source, clone_dir, default_branch="main")

        linearize_history(clone_dir)  # Should not raise


class TestRewritePaths:
    """Tests for rewrite_paths()."""

    def test_files_moved_to_subdirectory(self, tmp_path):
        source = str(tmp_path / "source")
        _create_test_repo(source, num_commits=2)

        clone_dir = str(tmp_path / "clone")
        clone_repo(source, clone_dir, default_branch="main")

        rewrite_paths(clone_dir, "my-channel")

        # Files should now be under my-channel/
        assert os.path.isfile(os.path.join(clone_dir, "my-channel", "file0.txt"))
        assert os.path.isfile(os.path.join(clone_dir, "my-channel", "file1.txt"))
        # Files should NOT exist at root
        assert not os.path.isfile(os.path.join(clone_dir, "file0.txt"))

    def test_history_preserved_in_subdirectory(self, tmp_path):
        source = str(tmp_path / "source")
        _create_test_repo(source, num_commits=3)

        clone_dir = str(tmp_path / "clone")
        clone_repo(source, clone_dir, default_branch="main")

        rewrite_paths(clone_dir, "my-channel")

        # All commits should reference paths under my-channel/
        result = subprocess.run(
            ["git", "log", "--oneline"],
            cwd=clone_dir,
            capture_output=True,
            text=True,
            check=True,
        )
        commits = result.stdout.strip().split("\n")
        assert len(commits) == 3


class TestRunPipeline:
    """Tests for the full run_pipeline()."""

    def test_full_pipeline(self, tmp_path):
        source = str(tmp_path / "source")
        _create_test_repo(source, num_commits=2)

        result_dir = run_pipeline(source, "test-channel", default_branch="main")
        try:
            assert os.path.isdir(result_dir)
            assert os.path.isfile(os.path.join(result_dir, "test-channel", "file0.txt"))
            assert os.path.isfile(os.path.join(result_dir, "test-channel", "file1.txt"))

            # Verify linear history
            result = subprocess.run(
                ["git", "log", "--merges", "--oneline"],
                cwd=result_dir,
                capture_output=True,
                text=True,
                check=True,
            )
            assert result.stdout.strip() == ""
        finally:
            import shutil

            shutil.rmtree(os.path.dirname(result_dir), ignore_errors=True)

    def test_pipeline_with_merge_commits(self, tmp_path):
        source = str(tmp_path / "source")
        _create_test_repo(source, with_merge=True)

        result_dir = run_pipeline(source, "merged-channel", default_branch="main")
        try:
            assert os.path.isfile(os.path.join(result_dir, "merged-channel", "file0.txt"))
            assert os.path.isfile(os.path.join(result_dir, "merged-channel", "feature.txt"))

            # No merge commits
            result = subprocess.run(
                ["git", "log", "--merges", "--oneline"],
                cwd=result_dir,
                capture_output=True,
                text=True,
                check=True,
            )
            assert result.stdout.strip() == ""
        finally:
            import shutil

            shutil.rmtree(os.path.dirname(result_dir), ignore_errors=True)


def _create_conflicting_merge_repo(path):
    """Helper to create a repo with a merge commit that resolved conflicts."""
    os.makedirs(path, exist_ok=True)
    run_opts = {"cwd": path, "check": True, "capture_output": True}
    subprocess.run(["git", "init", "--initial-branch=main"], **run_opts)
    subprocess.run(["git", "config", "user.email", "test@test.com"], **run_opts)
    subprocess.run(["git", "config", "user.name", "Test"], **run_opts)

    filepath = os.path.join(path, "shared.txt")
    with open(filepath, "w") as f:
        f.write("line1\nline2\nline3\n")
    subprocess.run(["git", "add", "."], **run_opts)
    subprocess.run(["git", "commit", "-m", "initial"], **run_opts)

    # Branch modifies same file
    subprocess.run(["git", "checkout", "-b", "feature"], **run_opts)
    with open(filepath, "w") as f:
        f.write("line1\nfeature-change\nline3\n")
    subprocess.run(["git", "add", "."], **run_opts)
    subprocess.run(["git", "commit", "-m", "feature change"], **run_opts)

    # Main makes conflicting change
    subprocess.run(["git", "checkout", "main"], **run_opts)
    with open(filepath, "w") as f:
        f.write("line1\nmain-change\nline3\n")
    subprocess.run(["git", "add", "."], **run_opts)
    subprocess.run(["git", "commit", "-m", "main change"], **run_opts)

    # Merge fails with conflict
    subprocess.run(
        ["git", "merge", "feature", "--no-ff", "-m", "Merge feature"],
        cwd=path,
        capture_output=True,
    )

    # Resolve by combining both changes
    with open(filepath, "w") as f:
        f.write("line1\nmain-change\nfeature-change\nline3\n")
    subprocess.run(["git", "add", "."], **run_opts)
    subprocess.run(["git", "commit", "-m", "Merge feature (resolved)"], **run_opts)


class TestLinearizeHistoryWithConflicts:
    """Tests for linearize_history() with conflicting merge commits."""

    def test_linearizes_repo_with_conflicting_merge(self, tmp_path):
        """A merge commit that resolved conflicts should still linearize."""
        repo = str(tmp_path / "repo")
        _create_conflicting_merge_repo(repo)

        clone_dir = str(tmp_path / "clone")
        subprocess.run(
            ["git", "clone", repo, clone_dir],
            check=True,
            capture_output=True,
        )

        linearize_history(clone_dir)

        # Verify no merge commits remain
        result = subprocess.run(
            ["git", "log", "--merges", "--oneline"],
            cwd=clone_dir,
            capture_output=True,
            text=True,
            check=True,
        )
        assert result.stdout.strip() == ""

    def test_preserves_final_tree_after_conflict_resolution(self, tmp_path):
        """After linearizing, the working tree should match the original."""
        repo = str(tmp_path / "repo")
        _create_conflicting_merge_repo(repo)

        clone_dir = str(tmp_path / "clone")
        subprocess.run(
            ["git", "clone", repo, clone_dir],
            check=True,
            capture_output=True,
        )

        linearize_history(clone_dir)

        # The final file should have BOTH changes (the custom merge resolution)
        with open(os.path.join(clone_dir, "shared.txt")) as f:
            content = f.read()
        assert "main-change" in content
        assert "feature-change" in content


class TestProcessRepo:
    """Tests for process_repo() — context-managed pipeline with error handling."""

    def test_success_cleans_up_temp_dir(self, tmp_path):
        """After successful processing, temp dir should be cleaned up."""
        source = str(tmp_path / "source")
        _create_test_repo(source, num_commits=2)

        result = process_repo(source, "cleanup-test", default_branch="main")

        assert result["success"] is True
        assert result["repo_dir"] is None  # cleaned up
        assert "cleanup-test" in result.get("subdirectory", "")

    def test_success_returns_commits(self, tmp_path):
        """Successful processing should return the list of commit SHAs."""
        source = str(tmp_path / "source")
        _create_test_repo(source, num_commits=3)

        result = process_repo(source, "commits-test", default_branch="main")

        assert result["success"] is True
        assert len(result["commits"]) == 3

    def test_failure_cleans_up_temp_dir(self, tmp_path):
        """On failure, temp dir should still be cleaned up."""
        # Use a nonexistent source to cause clone failure
        result = process_repo("/nonexistent/repo", "fail-test", default_branch="main")

        assert result["success"] is False
        assert result["error"] is not None

    def test_failure_returns_error_message(self, tmp_path):
        """On failure, error message should describe what went wrong."""
        result = process_repo("/nonexistent/repo", "fail-test", default_branch="main")

        assert result["success"] is False
        assert isinstance(result["error"], str)
        assert len(result["error"]) > 0

    def test_commits_are_in_order(self, tmp_path):
        """Commits should be returned in chronological order (oldest first)."""
        source = str(tmp_path / "source")
        _create_test_repo(source, num_commits=3)

        result = process_repo(source, "order-test", default_branch="main")

        assert result["success"] is True
        commits = result["commits"]
        # Verify these are valid SHA strings
        for sha in commits:
            assert len(sha) == 40  # full SHA
