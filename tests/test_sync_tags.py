import io
import unittest
from contextlib import redirect_stdout
from unittest.mock import MagicMock, patch

import sync_tags


class SyncTagsTests(unittest.TestCase):
    @patch("sync_tags.trigger_build")
    @patch("sync_tags.create_fork_tag")
    @patch("sync_tags.fork_default_branch_sha", return_value=("localsha1234567890", "main"))
    @patch("sync_tags.get_tag_commit_sha", return_value="abcdef1234567890")
    @patch("sync_tags.fork_tag_names", return_value=set())
    @patch("sync_tags.get_latest_release_tag", return_value="v1.101.0")
    @patch("sync_tags.github_session")
    def test_dry_run_does_not_create_or_trigger(
        self,
        _mock_session,
        _mock_get_latest_release_tag,
        _mock_fork_tags,
        _mock_get_sha,
        _mock_fork_sha,
        mock_create_tag,
        mock_trigger_build,
    ):
        output = io.StringIO()
        with redirect_stdout(output):
            exit_code = sync_tags.sync_tags(dry_run=True)

        self.assertEqual(exit_code, 0)
        self.assertIn("[DRY-RUN] Would create tag v1.101.0 at main (localsh)", output.getvalue())
        self.assertIn("upstream commit is abcdef1", output.getvalue())
        self.assertIn("[DRY-RUN] Would trigger build for v1.101.0", output.getvalue())
        mock_create_tag.assert_not_called()
        mock_trigger_build.assert_not_called()

    @patch("sync_tags.github_session")
    @patch("sync_tags.get_latest_release_tag", return_value="v1.101.0")
    def test_latest_tag_already_exists(self, _mock_get_latest_release_tag, _mock_session):
        with patch("sync_tags.fork_tag_names", return_value={"v1.101.0"}):
            output = io.StringIO()
            with redirect_stdout(output):
                exit_code = sync_tags.sync_tags(dry_run=True)

            self.assertEqual(exit_code, 0)
            self.assertIn(
                "Latest upstream tag v1.101.0 already exists in fork",
                output.getvalue(),
            )

    def test_create_fork_tag_points_at_local_commit(self):
        session = MagicMock()
        response = MagicMock()
        response.status_code = 201
        session.post.return_value = response

        created = sync_tags.create_fork_tag("v1.102.4", "localsha1234567890", session)

        self.assertTrue(created)
        session.post.assert_called_once_with(
            "https://api.github.com/repos/betdev-cloud/tailscale/git/refs",
            json={"ref": "refs/tags/v1.102.4", "sha": "localsha1234567890"},
        )


if __name__ == "__main__":
    unittest.main()
