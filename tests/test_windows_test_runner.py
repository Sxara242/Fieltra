"""Focused orchestration checks; mocked workers never launch native processes."""
from contextlib import redirect_stdout
import io
import json
from pathlib import Path
from types import ModuleType
import unittest
from unittest.mock import patch

from tools import run_test_module, run_windows_tests


class WindowsTestRunnerTests(unittest.TestCase):
    def test_failure_summary_keeps_assertion_and_case_before_long_script(self):
        script='PowerShell resource and privacy checks\n'*500
        output=('test failure ... FAIL\nFAIL: test_packaging (tests.fixture.Packaging)\n'
                'Traceback (most recent call last):\n  self.assertIn("one attempt", script)\n'
                'AssertionError: "one attempt" not found in '+script+
                '\nFAIL: test_other (tests.fixture.Packaging)\nAssertionError: other reason\nFAILED (failures=2)\n')
        summary=run_windows_tests.failure_summary(output)
        for text in ('FAIL: test_packaging','self.assertIn("one attempt", script)',
                     'AssertionError: "one attempt" not found','FAIL: test_other','AssertionError: other reason'):
            self.assertIn(text,summary)
        self.assertIn('full output in module log',summary)
        self.assertLess(len(summary),3000)

    @staticmethod
    def outcome(module, status):
        return {'module': module, 'status': status, 'exit_code': 0 if status == 'PASS' else 1,
                'tests': 1, 'failed_cases': [], 'summary': status}

    def test_fail_timeout_and_worker_exception_collect_remaining_results(self):
        modules = ['failure', 'worker_error', 'timeout', 'remaining']

        def worker(module, timeout, output):
            if module == 'worker_error':
                raise OSError('synthetic cleanup failure')
            return self.outcome(module, {'failure': 'FAIL', 'timeout': 'TIMEOUT'}.get(module, 'PASS'))

        # Keep the orchestration regression entirely in memory: no real child
        # process, profile, log or filesystem permission is needed.
        with patch.object(Path, 'mkdir'), patch.object(Path, 'write_text') as write_report:
            with patch.object(run_windows_tests, 'execute', side_effect=worker) as execute:
                with redirect_stdout(io.StringIO()):
                    failed = run_windows_tests.main(['--output', 'synthetic-runner-output', *modules])
            report = json.loads(write_report.call_args.args[0])
        self.assertTrue(failed)
        self.assertEqual(modules, [call.args[0] for call in execute.call_args_list])
        self.assertEqual(['FAIL', 'ERROR', 'TIMEOUT', 'PASS'], [r['status'] for r in report['modules']])
        self.assertEqual(3, report['failed_modules'])
        self.assertEqual(1, report['passed_modules'])
        self.assertIn('synthetic cleanup failure', report['modules'][1]['summary'])

    def test_all_pass_returns_success(self):
        with patch.object(run_windows_tests, 'execute', side_effect=lambda m, *args: self.outcome(m, 'PASS')):
            with redirect_stdout(io.StringIO()):
                self.assertFalse(run_windows_tests.main(['first', 'second']))

    def test_explicit_case_selects_only_requested_test(self):
        name = __name__ + '.WindowsTestRunnerTests.test_all_pass_returns_success'
        suite = run_test_module.suite_for_name(name)
        self.assertEqual(1, suite.countTestCases())
        self.assertEqual(name, list(suite)[0].id())

    def test_whole_module_still_collects_plain_functions(self):
        module = ModuleType('synthetic_runner_fixture')
        def test_plain():
            pass
        test_plain.__module__ = module.__name__
        module.test_plain = test_plain
        with patch.object(run_test_module.importlib, 'import_module', return_value=module):
            self.assertEqual(1, run_test_module.suite_for_name(module.__name__).countTestCases())

    def test_missing_module_dependency_is_not_treated_as_case_selector(self):
        missing = ModuleNotFoundError('missing dependency', name='unavailable_fixture_dependency')
        with patch.object(run_test_module.importlib, 'import_module', side_effect=missing):
            with patch.object(unittest.defaultTestLoader, 'loadTestsFromName') as loader:
                with self.assertRaises(ModuleNotFoundError):
                    run_test_module.suite_for_name('tests.synthetic_fixture')
                loader.assert_not_called()


if __name__ == '__main__':
    unittest.main()
