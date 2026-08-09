from __future__ import annotations

import importlib.util
import tempfile
import unittest
from pathlib import Path

MODULE_PATH = Path(__file__).with_name("check_runner_policy.py")
SPEC = importlib.util.spec_from_file_location("check_runner_policy", MODULE_PATH)
assert SPEC and SPEC.loader
POLICY = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(POLICY)


class RunnerPolicyTest(unittest.TestCase):
    def scan(self, content: str, exceptions: list[dict[str, object]] | None = None) -> list[str]:
        with tempfile.TemporaryDirectory() as directory:
            workflow = Path(directory) / "ci.yml"
            workflow.write_text(content, encoding="utf-8")
            return POLICY.scan_workflow(workflow, exceptions or [])

    def test_accepts_self_hosted_and_sha(self) -> None:
        errors = self.scan(
            "jobs:\n  test:\n    runs-on: [self-hosted, venalabs-ci]\n"
            "    steps:\n      - uses: actions/checkout@" + "a" * 40 + "\n"
        )
        self.assertEqual([], errors)

    def test_rejects_github_hosted_and_floating_action(self) -> None:
        errors = self.scan(
            "jobs:\n  test:\n    runs-on: ubuntu-latest\n"
            "    steps:\n      - uses: actions/checkout@v4\n"
        )
        self.assertEqual(2, len(errors))

    def test_scoped_exception_allows_external_watcher(self) -> None:
        errors = self.scan(
            "jobs:\n  veille:\n    runs-on: ubuntu-latest\n    steps:\n      - run: true\n",
            [{"workflow": "ci.yml", "job": "veille", "allow_github_hosted": True}],
        )
        self.assertEqual([], errors)


if __name__ == "__main__":
    unittest.main()
