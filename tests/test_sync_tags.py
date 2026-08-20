import io
import unittest
from contextlib import redirect_stdout
from unittest.mock import patch

import sync_tags


class SyncTagsTests(unittest.TestCase):
    @patch("sync_tags.trigger_build")
    @patch("sync_tags.create_fork_tag")
    @patch("sync_tags.get_tag_commit_sha", return_value="abcdef1234567890")
    @patch("sync_tags.fork_tag_names", return_value=set())
    @patch(
        "sync_tags.sorted_release_tags",
        return_value=["v1.100.0", "v1.101.0"],
    )
    @patch("sync_tags.list_tags", return_value=[{"name": "v1.101.0"}])
    @patch("sync_tags.github_session")
    def test_dry_run_does_not_create_or_trigger(
        self,
        _mock_session,
        _mock_list_tags,
        _mock_sorted_release_tags,
        _mock_fork_tags,
        _mock_get_sha,
        mock_create_tag,
        mock_trigger_build,
    ):
        output = io.StringIO()
        with redirect_stdout(output):
            exit_code = sync_tags.sync_tags(dry_run=True)

        self.assertEqual(exit_code, 0)
        self.assertIn("[DRY-RUN] Would create tag v1.101.0", output.getvalue())
        self.assertIn("[DRY-RUN] Would trigger build for v1.101.0", output.getvalue())
        mock_create_tag.assert_not_called()
        mock_trigger_build.assert_not_called()

    @patch("sync_tags.list_tags", return_value=[{"name": "v1.101.0"}])
    @patch("sync_tags.github_session")
    def test_no_new_tags(self, _mock_session, _mock_list_tags):
        with patch("sync_tags.sorted_release_tags", return_value=["v1.101.0"]), patch(
            "sync_tags.fork_tag_names", return_value={"v1.101.0"}
        ):
            output = io.StringIO()
            with redirect_stdout(output):
                exit_code = sync_tags.sync_tags(dry_run=True)

        self.assertEqual(exit_code, 0)
        self.assertIn("No new tags found", output.getvalue())


if __name__ == "__main__":
    unittest.main()
