import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import run_custom_series as series


class FreshSeriesTests(unittest.TestCase):
    def test_dry_run_never_reads_preparation_or_creates_files(self):
        with tempfile.TemporaryDirectory() as temporary:
            folder = Path(temporary) / "new"
            with patch.object(series, "prepare") as prepare:
                self.assertEqual(series.main(["--output-dir", str(folder)]), 0)
            prepare.assert_not_called()
            self.assertFalse(folder.exists())

    def run_workflow(self, preparation_code=0, selected=1, comparison_code=0):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        folder = Path(temporary.name) / "new"
        states = [dict(status="finished", selected_target=selected),
                  dict(status="finished", completed=list(range(6)))]
        with patch.object(series, "prepare", return_value=preparation_code), \
             patch.object(series, "compare", return_value=comparison_code) as compare, \
             patch.object(series, "read", side_effect=states):
            code = series.main(["--output-dir", str(folder), "--execute"])
        return code, json.loads((folder / "workflow.json").read_text()), compare

    def test_failed_preparation_never_starts_comparison(self):
        code, state, compare = self.run_workflow(preparation_code=1)
        self.assertEqual((code, state["status"]), (1, "stopped"))
        compare.assert_not_called()

    def test_changed_selection_never_starts_comparison(self):
        code, state, compare = self.run_workflow(selected=2)
        self.assertEqual((code, state["status"]), (1, "stopped"))
        compare.assert_not_called()

    def test_complete_workflow_and_failed_comparison_are_distinct(self):
        code, state, compare = self.run_workflow()
        self.assertEqual((code, state["status"]), (0, "finished"))
        self.assertNotIn("--resume", compare.call_args.args[0])
        code, state, _ = self.run_workflow(comparison_code=1)
        self.assertEqual((code, state["status"]), (1, "stopped"))
