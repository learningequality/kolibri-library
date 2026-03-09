"""Tests for the archive script."""

from unittest.mock import patch


class TestIsRepoArchived:
    """Tests for is_repo_archived()."""

    def test_returns_true_for_archived_repo(self):
        from archive import is_repo_archived

        with patch("archive.run_command", return_value='{"isArchived":true}'):
            assert is_repo_archived("sushi-chef-test") is True

    def test_returns_false_for_non_archived_repo(self):
        from archive import is_repo_archived

        with patch("archive.run_command", return_value='{"isArchived":false}'):
            assert is_repo_archived("sushi-chef-test") is False

    def test_returns_false_on_error(self):
        from archive import is_repo_archived

        with patch("archive.run_command", side_effect=Exception("API error")):
            assert is_repo_archived("sushi-chef-test") is False


class TestArchiveRepo:
    """Tests for archive_repo()."""

    def test_calls_gh_archive(self):
        from archive import archive_repo

        with patch("archive.run_command") as mock_run:
            archive_repo("sushi-chef-test")
            mock_run.assert_called_once_with(
                ["gh", "repo", "archive", "learningequality/sushi-chef-test", "--yes"]
            )

    def test_returns_true_on_success(self):
        from archive import archive_repo

        with patch("archive.run_command"):
            assert archive_repo("sushi-chef-test") is True

    def test_returns_false_on_failure(self):
        from archive import archive_repo

        with patch("archive.run_command", side_effect=Exception("archive failed")):
            assert archive_repo("sushi-chef-test") is False


class TestArchiveRepos:
    """Tests for archive_repos() — the orchestration function."""

    def test_empty_manifest(self):
        from archive import archive_repos

        result = archive_repos([])
        assert result["archived"] == 0
        assert result["already_archived"] == 0
        assert result["failed"] == 0

    def test_skips_already_archived(self):
        from archive import archive_repos

        with patch("archive.is_repo_archived", return_value=True):
            result = archive_repos(["sushi-chef-a", "sushi-chef-b"])
            assert result["archived"] == 0
            assert result["already_archived"] == 2

    def test_archives_non_archived_repos(self):
        from archive import archive_repos

        with (
            patch("archive.is_repo_archived", return_value=False),
            patch("archive.archive_repo", return_value=True),
        ):
            result = archive_repos(["sushi-chef-a"])
            assert result["archived"] == 1
            assert result["already_archived"] == 0

    def test_counts_failures(self):
        from archive import archive_repos

        with (
            patch("archive.is_repo_archived", return_value=False),
            patch("archive.archive_repo", return_value=False),
        ):
            result = archive_repos(["sushi-chef-a"])
            assert result["failed"] == 1
