"""Tests for Phase 4: integration, validation, and manifest management."""

import os
import subprocess

from pipeline import clone_repo, linearize_history, rewrite_paths


def _run_git(args, cwd):
    """Helper to run git commands."""
    return subprocess.run(
        ["git"] + args,
        cwd=cwd,
        check=True,
        capture_output=True,
        text=True,
    )


def _create_test_repo(path, num_commits=3):
    """Create a small test repo with some commits."""
    os.makedirs(path, exist_ok=True)
    _run_git(["init", "--initial-branch=main"], cwd=path)
    _run_git(["config", "user.email", "test@test.com"], cwd=path)
    _run_git(["config", "user.name", "Test"], cwd=path)

    for i in range(num_commits):
        filepath = os.path.join(path, f"file{i}.txt")
        with open(filepath, "w") as f:
            f.write(f"content {i}\n")
        _run_git(["add", "."], cwd=path)
        _run_git(["commit", "-m", f"commit {i}"], cwd=path)


def _prepare_processed_repo(tmp_path, subdirectory, num_commits=3):
    """Create a source repo and run it through the pipeline (clone, linearize, rewrite).

    Returns (source_repo_path, processed_repo_path, commits_list).
    """
    source = str(tmp_path / "source")
    _create_test_repo(source, num_commits=num_commits)

    processed = str(tmp_path / "processed")
    clone_repo(source, processed, default_branch="main")
    linearize_history(processed)
    rewrite_paths(processed, subdirectory)

    output = _run_git(["rev-list", "--reverse", "HEAD"], cwd=processed)
    commits = [line.strip() for line in output.stdout.strip().split("\n") if line.strip()]

    return source, processed, commits


def _create_target_repo(path):
    """Create a target repo (simulating kolibri-library) with an initial commit."""
    os.makedirs(path, exist_ok=True)
    _run_git(["init", "--initial-branch=main"], cwd=path)
    _run_git(["config", "user.email", "test@test.com"], cwd=path)
    _run_git(["config", "user.name", "Test"], cwd=path)

    readme = os.path.join(path, "README.md")
    with open(readme, "w") as f:
        f.write("# kolibri-library\n")
    _run_git(["add", "."], cwd=path)
    _run_git(["commit", "-m", "Initial commit"], cwd=path)


class TestIntegrateRepo:
    """Tests for integrate_repo()."""

    def test_cherry_picks_commits_into_target(self, tmp_path):
        """Commits from processed repo should appear in target."""
        from integration import integrate_repo

        _source, processed, commits = _prepare_processed_repo(tmp_path, "test-channel")
        target = str(tmp_path / "target")
        _create_target_repo(target)

        integrate_repo(target, processed, commits)

        # Target should now have files under test-channel/
        assert os.path.isfile(os.path.join(target, "test-channel", "file0.txt"))
        assert os.path.isfile(os.path.join(target, "test-channel", "file1.txt"))
        assert os.path.isfile(os.path.join(target, "test-channel", "file2.txt"))

    def test_no_merge_commits_created(self, tmp_path):
        """Integration should not create merge commits."""
        from integration import integrate_repo

        _source, processed, commits = _prepare_processed_repo(tmp_path, "test-channel")
        target = str(tmp_path / "target")
        _create_target_repo(target)

        integrate_repo(target, processed, commits)

        result = _run_git(["log", "--merges", "--oneline"], cwd=target)
        assert result.stdout.strip() == ""

    def test_correct_number_of_commits_added(self, tmp_path):
        """The right number of commits should be added to the target."""
        from integration import integrate_repo

        _source, processed, commits = _prepare_processed_repo(
            tmp_path, "test-channel", num_commits=3
        )
        target = str(tmp_path / "target")
        _create_target_repo(target)

        count_before = int(_run_git(["rev-list", "--count", "HEAD"], cwd=target).stdout.strip())
        integrate_repo(target, processed, commits)
        count_after = int(_run_git(["rev-list", "--count", "HEAD"], cwd=target).stdout.strip())

        assert count_after == count_before + 3

    def test_returns_pre_integration_sha(self, tmp_path):
        """integrate_repo should return the HEAD SHA from before integration."""
        from integration import integrate_repo

        _source, processed, commits = _prepare_processed_repo(tmp_path, "test-channel")
        target = str(tmp_path / "target")
        _create_target_repo(target)

        expected_sha = _run_git(["rev-parse", "HEAD"], cwd=target).stdout.strip()
        pre_sha = integrate_repo(target, processed, commits)

        assert pre_sha == expected_sha


class TestValidateRepo:
    """Tests for validate_repo()."""

    def test_validation_passes_for_correct_migration(self, tmp_path):
        """Validation should pass when subdirectory contents match source."""
        from integration import integrate_repo, validate_repo

        source, processed, commits = _prepare_processed_repo(tmp_path, "test-channel")
        target = str(tmp_path / "target")
        _create_target_repo(target)

        integrate_repo(target, processed, commits)

        result = validate_repo(target, "test-channel", source, default_branch="main")
        assert result["valid"] is True

    def test_validation_fails_when_files_differ(self, tmp_path):
        """Validation should fail if a file in the subdirectory differs from source."""
        from integration import integrate_repo, validate_repo

        source, processed, commits = _prepare_processed_repo(tmp_path, "test-channel")
        target = str(tmp_path / "target")
        _create_target_repo(target)

        integrate_repo(target, processed, commits)

        # Tamper with a file in the target to cause validation failure
        tampered_file = os.path.join(target, "test-channel", "file0.txt")
        with open(tampered_file, "w") as f:
            f.write("TAMPERED CONTENT\n")
        _run_git(["add", "."], cwd=target)
        _run_git(["commit", "-m", "tamper"], cwd=target)

        result = validate_repo(target, "test-channel", source, default_branch="main")
        assert result["valid"] is False
        assert result["diff"] != ""

    def test_validation_fails_when_files_missing(self, tmp_path):
        """Validation should fail if a source file is missing from the subdirectory."""
        from integration import integrate_repo, validate_repo

        source, processed, commits = _prepare_processed_repo(tmp_path, "test-channel")
        target = str(tmp_path / "target")
        _create_target_repo(target)

        integrate_repo(target, processed, commits)

        # Delete a file from the subdirectory
        deleted_file = os.path.join(target, "test-channel", "file0.txt")
        os.remove(deleted_file)
        _run_git(["add", "."], cwd=target)
        _run_git(["commit", "-m", "delete file"], cwd=target)

        result = validate_repo(target, "test-channel", source, default_branch="main")
        assert result["valid"] is False


class TestSaveManifest:
    """Tests for save_manifest()."""

    def test_writes_repo_names_to_file(self, tmp_path):
        """save_manifest should write one repo name per line."""
        from integration import save_manifest

        manifest_path = str(tmp_path / "manifest.txt")
        save_manifest(manifest_path, ["sushi-chef-alpha", "sushi-chef-beta"])

        with open(manifest_path) as f:
            lines = [line.strip() for line in f if line.strip()]
        assert lines == ["sushi-chef-alpha", "sushi-chef-beta"]

    def test_overwrites_existing_manifest(self, tmp_path):
        """save_manifest should overwrite, not append."""
        from integration import save_manifest

        manifest_path = str(tmp_path / "manifest.txt")
        save_manifest(manifest_path, ["sushi-chef-old"])
        save_manifest(manifest_path, ["sushi-chef-new"])

        with open(manifest_path) as f:
            lines = [line.strip() for line in f if line.strip()]
        assert lines == ["sushi-chef-new"]

    def test_empty_list_creates_empty_file(self, tmp_path):
        """save_manifest with empty list should create an empty file."""
        from integration import save_manifest

        manifest_path = str(tmp_path / "manifest.txt")
        save_manifest(manifest_path, [])

        with open(manifest_path) as f:
            content = f.read()
        assert content.strip() == ""
