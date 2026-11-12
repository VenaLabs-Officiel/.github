import importlib.util
from pathlib import Path
import tempfile
import unittest

spec = importlib.util.spec_from_file_location('policy', Path(__file__).with_name('check_runner_policy.py'))
policy = importlib.util.module_from_spec(spec)
spec.loader.exec_module(policy)


class PolicyTests(unittest.TestCase):
    def scan(self, text, exceptions=()):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'ci.yml'
            path.write_text(text, encoding='utf-8')
            return policy.scan_workflow(path, exceptions)

    def job(self, body, root=''):
        return root + 'jobs:\n  test:\n    timeout-minutes: 5\n' + body

    def test_multiline_shared_labels(self):
        self.assertEqual([], self.scan(self.job('    runs-on:\n      - self-hosted\n      - venalabs-ci\n')))

    def test_root_write_permissions_are_effective(self):
        self.assertIn('permission issues: write', self.scan(self.job('    runs-on: [self-hosted, venalabs-ci]\n', 'permissions:\n  issues: write\n'))[0])

    def test_job_permissions_replace_root(self):
        self.assertEqual([], self.scan(self.job('    runs-on: [self-hosted, venalabs-ci]\n    permissions: {contents: read}\n', 'permissions: {issues: write}\n')))

    def test_write_all_refused(self):
        self.assertIn('write-all', self.scan(self.job('    runs-on: [self-hosted, venalabs-ci]\n    permissions: write-all\n'))[0])

    def test_dynamic_runner_refused(self):
        self.assertTrue(self.scan(self.job('    runs-on: ${{ matrix.runner }}\n')))

    def test_exact_hosted_exception(self):
        exception = [{'workflow':'ci.yml','job':'test','allowed_hosted_labels':['ubuntu-slim']}]
        self.assertEqual([], self.scan(self.job('    runs-on: ubuntu-slim\n'), exception))
        self.assertTrue(self.scan(self.job('    runs-on: ubuntu-24.04\n'), exception))

    def test_self_hosted_needs_pool_label(self):
        self.assertTrue(self.scan(self.job('    runs-on: [self-hosted]\n')))

    def test_mac_exception_is_exact(self):
        exception = [{'workflow':'ci.yml','job':'test','allowed_self_hosted_labels':['self-hosted','macOS','venalabs-ios']}]
        self.assertEqual([], self.scan(self.job('    runs-on: [self-hosted, macOS, venalabs-ios]\n'), exception))

    def test_comments_and_script_literals_are_not_actions(self):
        self.assertEqual([], self.scan(self.job('    runs-on: [self-hosted, venalabs-ci]\n    steps:\n      - run: |\n          echo "uses: actions/checkout@v1"\n')))

    def test_quoted_uses_must_be_pinned(self):
        self.assertTrue(self.scan(self.job('    runs-on: [self-hosted, venalabs-ci]\n    steps:\n      - uses: "actions/checkout@v4"\n')))

    def test_pinned_reusable_workflow(self):
        self.assertEqual([], self.scan('jobs:\n  test:\n    uses: org/repo/.github/workflows/ci.yml@'+'a'*40+'\n'))

    def test_duplicate_keys_refused(self):
        self.assertIn('dupliquée', self.scan(self.job('    runs-on: ubuntu-slim\n    runs-on: [self-hosted, venalabs-ci]\n'))[0])

    def test_timeout_required(self):
        self.assertTrue(self.scan('jobs:\n  test:\n    runs-on: [self-hosted, venalabs-ci]\n'))

    def test_docker_action_digest_required(self):
        self.assertIsNotNone(policy.action_error('docker://alpine:latest'))
        self.assertIsNone(policy.action_error('docker://alpine@sha256:'+'a'*64))


if __name__ == '__main__':
    unittest.main()
