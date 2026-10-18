"""Run unittest classes and plain test functions without silently omitting either."""
import importlib
import faulthandler
import inspect
import os
import sys
import unittest

def suite_for(module):
    suite = unittest.defaultTestLoader.loadTestsFromModule(module)
    for name, function in inspect.getmembers(module, inspect.isfunction):
        if name.startswith('test_') and function.__module__ == module.__name__:
            suite.addTest(unittest.FunctionTestCase(function))
    return suite

def suite_for_name(name):
    """Keep whole-module discovery, also allowing one explicit unittest case."""
    try:
        module = importlib.import_module(name)
    except ModuleNotFoundError as error:
        # A dotted class/method isn't a module. Do not conceal a missing
        # dependency raised while importing an actual test module.
        if not error.name or (error.name != name and not name.startswith(error.name + '.')):
            raise
        return unittest.defaultTestLoader.loadTestsFromName(name)
    return suite_for(module)

if __name__ == '__main__':
    if len(sys.argv) != 2:
        raise SystemExit('Provide exactly one test module or dotted unittest case')
    # Capture a stack just before the parent's bound, including native Qt waits.
    # The parent still owns timeout/process-tree cleanup; this never waives it.
    timeout = int(os.environ.get('MASTIXA_TEST_TIMEOUT', '0'))
    if timeout >= 10:
        faulthandler.dump_traceback_later(timeout - 5)
    suite = suite_for_name(sys.argv[1])
    if not suite.countTestCases():
        raise SystemExit('No test cases found; refusing a silent pass')
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    faulthandler.cancel_dump_traceback_later()
    raise SystemExit(not result.wasSuccessful())
