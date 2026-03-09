"""Tests for repository discovery and filtering."""

import json
from unittest.mock import patch

import pytest

from discovery import (
    check_collisions,
    derive_subdirectory_name,
    discover_repos,
    filter_repos,
    load_manifest,
    sort_repos_chronologically,
)

# Sample repo data mimicking gh CLI JSON output
SAMPLE_REPOS = [
    {
        "name": "sushi-chef-Khan-Academy",
        "isFork": False,
        "defaultBranchRef": {"name": "main"},
        "pushedAt": "2023-06-15T10:00:00Z",
    },
    {
        "name": "sushi-chef-wikipedia",
        "isFork": False,
        "defaultBranchRef": {"name": "master"},
        "pushedAt": "2022-01-10T08:00:00Z",
    },
    {
        "name": "sushi-chef-empty-repo",
        "isFork": False,
        "defaultBranchRef": None,
        "pushedAt": "2021-05-01T00:00:00Z",
    },
    {
        "name": "kolibri",
        "isFork": False,
        "defaultBranchRef": {"name": "develop"},
        "pushedAt": "2024-01-01T00:00:00Z",
    },
    {
        "name": "sushi-chef-forked",
        "isFork": True,
        "defaultBranchRef": {"name": "main"},
        "pushedAt": "2023-03-01T00:00:00Z",
    },
]


class TestDeriveSubdirectoryName:
    """Tests for subdirectory name derivation."""

    def test_strips_prefix_and_lowercases(self):
        assert derive_subdirectory_name("sushi-chef-Khan-Academy") == "khan-academy"

    def test_already_lowercase(self):
        assert derive_subdirectory_name("sushi-chef-wikipedia") == "wikipedia"

    def test_preserves_hyphens(self):
        assert derive_subdirectory_name("sushi-chef-my-channel") == "my-channel"


class TestCheckCollisions:
    """Tests for subdirectory name collision detection."""

    def test_no_collision(self):
        repos = [
            {"name": "sushi-chef-alpha"},
            {"name": "sushi-chef-beta"},
        ]
        check_collisions(repos)  # Should not raise

    def test_collision_raises(self):
        repos = [
            {"name": "sushi-chef-Alpha"},
            {"name": "sushi-chef-alpha"},
        ]
        with pytest.raises(SystemExit, match="collision"):
            check_collisions(repos)


class TestFilterRepos:
    """Tests for filter_repos()."""

    def test_filters_non_sushi_chef_repos(self):
        eligible, skipped = filter_repos(SAMPLE_REPOS, set())
        names = [r["name"] for r in eligible]
        assert "kolibri" not in names

    def test_filters_forks(self):
        eligible, skipped = filter_repos(SAMPLE_REPOS, set())
        names = [r["name"] for r in eligible]
        assert "sushi-chef-forked" not in names

    def test_skips_empty_repos_with_reason(self):
        eligible, skipped = filter_repos(SAMPLE_REPOS, set())
        names = [r["name"] for r in eligible]
        assert "sushi-chef-empty-repo" not in names
        assert any(
            s["name"] == "sushi-chef-empty-repo" and "empty" in s["reason"].lower() for s in skipped
        )

    def test_skips_already_migrated(self):
        manifest = {"sushi-chef-Khan-Academy"}
        eligible, skipped = filter_repos(SAMPLE_REPOS, manifest)
        names = [r["name"] for r in eligible]
        assert "sushi-chef-Khan-Academy" not in names

    def test_eligible_repos_returned(self):
        eligible, skipped = filter_repos(SAMPLE_REPOS, set())
        names = [r["name"] for r in eligible]
        assert "sushi-chef-Khan-Academy" in names
        assert "sushi-chef-wikipedia" in names


class TestSortReposChronologically:
    """Tests for chronological ordering (oldest first)."""

    def test_oldest_first(self):
        repos = [
            {"name": "newer", "pushedAt": "2024-01-01T00:00:00Z"},
            {"name": "older", "pushedAt": "2020-01-01T00:00:00Z"},
        ]
        sorted_repos = sort_repos_chronologically(repos)
        assert sorted_repos[0]["name"] == "older"
        assert sorted_repos[1]["name"] == "newer"


class TestLoadManifest:
    """Tests for loading the manifest file."""

    def test_loads_existing_manifest(self, tmp_path):
        manifest_path = tmp_path / "manifest.txt"
        manifest_path.write_text("sushi-chef-alpha\nsushi-chef-beta\n")
        result = load_manifest(str(manifest_path))
        assert result == {"sushi-chef-alpha", "sushi-chef-beta"}

    def test_empty_manifest(self, tmp_path):
        manifest_path = tmp_path / "manifest.txt"
        manifest_path.write_text("")
        result = load_manifest(str(manifest_path))
        assert result == set()

    def test_missing_manifest(self, tmp_path):
        manifest_path = tmp_path / "nonexistent.txt"
        result = load_manifest(str(manifest_path))
        assert result == set()


class TestCheckMultiBranchAndPrs:
    """Tests for check_multi_branch_and_prs() with stale/dependabot filtering."""

    def _make_repo(self, name="sushi-chef-test"):
        return {
            "name": name,
            "isFork": False,
            "defaultBranchRef": {"name": "main"},
            "pushedAt": "2023-01-01T00:00:00Z",
        }

    def test_single_branch_repo_is_eligible(self):
        """Repo with only one branch should be eligible."""
        from discovery import check_multi_branch_and_prs

        repo = self._make_repo()

        def mock_run_command(cmd, **kwargs):
            cmd_str = " ".join(cmd)
            if "branches" in cmd_str:
                return "main\n"
            if "gh pr list" in cmd_str:
                return "[]"
            return ""

        with patch("discovery.run_command", side_effect=mock_run_command):
            eligible, skipped = check_multi_branch_and_prs([repo])

        assert len(eligible) == 1
        assert len(skipped) == 0

    def test_stale_branch_excluded_from_count(self):
        """Branches with 0 commits ahead of default should not count as extra branches."""
        from discovery import check_multi_branch_and_prs

        repo = self._make_repo()

        def mock_run_command(cmd, **kwargs):
            cmd_str = " ".join(cmd)
            if "branches" in cmd_str:
                return "main\nstale-branch\n"
            if "compare" in cmd_str:
                return '{"ahead_by": 0}'
            if "gh pr list" in cmd_str:
                return "[]"
            return ""

        with patch("discovery.run_command", side_effect=mock_run_command):
            eligible, skipped = check_multi_branch_and_prs([repo])

        assert len(eligible) == 1
        assert len(skipped) == 0

    def test_dependabot_branch_excluded_from_count(self):
        """Branches starting with dependabot/ should not count as extra branches."""
        from discovery import check_multi_branch_and_prs

        repo = self._make_repo()

        def mock_run_command(cmd, **kwargs):
            cmd_str = " ".join(cmd)
            if "branches" in cmd_str:
                return "main\ndependabot/pip/pillow-10.0.1\n"
            if "gh pr list" in cmd_str:
                return "[]"
            return ""

        with patch("discovery.run_command", side_effect=mock_run_command):
            eligible, skipped = check_multi_branch_and_prs([repo])

        assert len(eligible) == 1
        assert len(skipped) == 0

    def test_real_extra_branch_still_skips(self):
        """Repos with real (non-stale, non-dependabot) extra branches should still be skipped."""
        from discovery import check_multi_branch_and_prs

        repo = self._make_repo()

        def mock_run_command(cmd, **kwargs):
            cmd_str = " ".join(cmd)
            if "branches" in cmd_str:
                return "main\nfeature-branch\n"
            if "compare" in cmd_str:
                return '{"ahead_by": 5}'
            if "gh pr list" in cmd_str:
                return "[]"
            return ""

        with patch("discovery.run_command", side_effect=mock_run_command):
            eligible, skipped = check_multi_branch_and_prs([repo])

        assert len(eligible) == 0
        assert len(skipped) == 1
        assert "branch" in skipped[0]["reason"].lower()

    def test_dependabot_pr_excluded_from_count(self):
        """PRs from dependabot or with dependabot/ branch should not count as open PRs."""
        from discovery import check_multi_branch_and_prs

        repo = self._make_repo()

        def mock_run_command(cmd, **kwargs):
            cmd_str = " ".join(cmd)
            if "branches" in cmd_str:
                return "main\n"
            if "gh pr list" in cmd_str:
                return json.dumps(
                    [
                        {
                            "number": 1,
                            "headRefName": "dependabot/pip/pillow-10.0.1",
                            "author": {"login": "dependabot[bot]"},
                        }
                    ]
                )
            return ""

        with patch("discovery.run_command", side_effect=mock_run_command):
            eligible, skipped = check_multi_branch_and_prs([repo])

        assert len(eligible) == 1
        assert len(skipped) == 0

    def test_real_pr_still_skips(self):
        """Repos with real (non-dependabot) open PRs should still be skipped."""
        from discovery import check_multi_branch_and_prs

        repo = self._make_repo()

        def mock_run_command(cmd, **kwargs):
            cmd_str = " ".join(cmd)
            if "branches" in cmd_str:
                return "main\n"
            if "gh pr list" in cmd_str:
                return json.dumps(
                    [
                        {
                            "number": 1,
                            "headRefName": "feature-branch",
                            "author": {"login": "someuser"},
                        }
                    ]
                )
            return ""

        with patch("discovery.run_command", side_effect=mock_run_command):
            eligible, skipped = check_multi_branch_and_prs([repo])

        assert len(eligible) == 0
        assert len(skipped) == 1
        assert "pull request" in skipped[0]["reason"].lower()

    def test_combined_stale_and_dependabot_filtering(self):
        """Repo with stale branch + dependabot branch + dependabot PR should be eligible."""
        from discovery import check_multi_branch_and_prs

        repo = self._make_repo()

        def mock_run_command(cmd, **kwargs):
            cmd_str = " ".join(cmd)
            if "branches" in cmd_str:
                return "main\nstale-branch\ndependabot/pip/markdown2-2.4.0\n"
            if "compare" in cmd_str:
                return '{"ahead_by": 0}'
            if "gh pr list" in cmd_str:
                return json.dumps(
                    [
                        {
                            "number": 1,
                            "headRefName": "dependabot/pip/markdown2-2.4.0",
                            "author": {"login": "dependabot[bot]"},
                        }
                    ]
                )
            return ""

        with patch("discovery.run_command", side_effect=mock_run_command):
            eligible, skipped = check_multi_branch_and_prs([repo])

        assert len(eligible) == 1
        assert len(skipped) == 0


class TestDiscoverRepos:
    """Tests for the top-level discover_repos() function."""

    def test_calls_gh_and_returns_filtered_repos(self):
        gh_output = json.dumps(SAMPLE_REPOS)
        with (
            patch("discovery.run_command", return_value=gh_output),
            patch(
                "discovery.check_multi_branch_and_prs",
                side_effect=lambda repos: (repos, []),
            ),
        ):
            eligible, skipped = discover_repos(manifest_path="/dev/null")
        names = [r["name"] for r in eligible]
        assert "sushi-chef-Khan-Academy" in names
        assert "kolibri" not in names
