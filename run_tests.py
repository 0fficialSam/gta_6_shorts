"""
=============================================================================
  GTA 6 AUTOMATION ENGINE — STUDIO PRO TEST RUNNER
  Standalone automated test execution with colored reporting & benchmarking
=============================================================================
"""

import os
import sys
import time
import unittest

# Ensure project root and studio are on sys.path
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
STUDIO_DIR = os.path.join(BASE_DIR, "studio")
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)
if STUDIO_DIR not in sys.path:
    sys.path.insert(0, STUDIO_DIR)

# Configure Django settings
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "studio_project.settings")
import django
django.setup()

# ANSI Color codes for Windows & Terminal
GREEN = "\033[92m"
RED = "\033[91m"
YELLOW = "\033[93m"
CYAN = "\033[96m"
BOLD = "\033[1m"
RESET = "\033[0m"


class CustomTestResult(unittest.TextTestResult):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.test_timings = {}
        self._current_start = 0

    def startTest(self, test):
        self._current_start = time.time()
        super().startTest(test)

    def addSuccess(self, test):
        elapsed = time.time() - self._current_start
        self.test_timings[test.id()] = (elapsed, "PASS")
        name = test.id().split(".")[-1]
        doc = (test.shortDescription() or "").strip()
        desc = f" — {doc}" if doc else ""
        print(f"  {GREEN}[PASS]{RESET} {name:40}{desc} ({elapsed:.3f}s)")
        super().addSuccess(test)

    def addFailure(self, test, err):
        elapsed = time.time() - self._current_start
        self.test_timings[test.id()] = (elapsed, "FAIL")
        name = test.id().split(".")[-1]
        print(f"  {RED}[FAIL]{RESET} {name:40} ({elapsed:.3f}s)")
        super().addFailure(test, err)

    def addError(self, test, err):
        elapsed = time.time() - self._current_start
        self.test_timings[test.id()] = (elapsed, "ERROR")
        name = test.id().split(".")[-1]
        print(f"  {RED}[ERR ]{RESET} {name:40} ({elapsed:.3f}s)")
        super().addError(test, err)


class CustomTestRunner(unittest.TextTestRunner):
    resultclass = CustomTestResult


def run_all_tests():
    print(f"\n{BOLD}{CYAN}{'=' * 75}{RESET}")
    print(f"{BOLD}{CYAN}  GTA 6 AUTOMATION ENGINE & STUDIO PRO — COMPREHENSIVE TEST SUITE{RESET}")
    print(f"{BOLD}{CYAN}{'=' * 75}{RESET}\n")

    from dashboard.tests import (
        ApiEndpointUnitTests,
        FeatureUnitTests,
        UiButtonsAndDomTests,
        AdversarialAndEdgeCaseUnitTests
    )

    suites = [
        ("API & BACKEND ROUTE ENDPOINTS", ApiEndpointUnitTests),
        ("GENERATION, AUDIO & PIPELINE FEATURES", FeatureUnitTests),
        ("UI BUTTONS, ONCLICK HANDLERS & DOM INTEGRITY", UiButtonsAndDomTests),
        ("ADVERSARIAL, EDGE CASE & BOUNDARY STRESS TESTS", AdversarialAndEdgeCaseUnitTests),
    ]

    total_start = time.time()
    all_passed = True
    total_ran = 0
    total_failures = 0
    total_errors = 0

    for suite_name, test_class in suites:
        print(f"{BOLD}{YELLOW}▶ SUITE: {suite_name}{RESET}")
        print(f"{'-' * 75}")
        loader = unittest.TestLoader()
        suite = loader.loadTestsFromTestCase(test_class)
        runner = CustomTestRunner(verbosity=0, stream=open(os.devnull, "w"))
        result = runner.run(suite)

        total_ran += result.testsRun
        total_failures += len(result.failures)
        total_errors += len(result.errors)

        if not result.wasSuccessful():
            all_passed = False
            for test, err in result.failures + result.errors:
                print(f"\n{RED}Error in {test.id()}:{RESET}")
                print(err)

        print(f"  Ran {result.testsRun} tests in this suite\n")

    total_duration = time.time() - total_start

    print(f"{BOLD}{CYAN}{'=' * 75}{RESET}")
    print(f"{BOLD}SUMMARY: {total_ran} tests executed in {total_duration:.2f} seconds{RESET}")
    print(f"  Passed : {GREEN}{total_ran - total_failures - total_errors}{RESET}")
    print(f"  Failed : {RED if total_failures else GREEN}{total_failures}{RESET}")
    print(f"  Errors : {RED if total_errors else GREEN}{total_errors}{RESET}")

    if all_passed:
        print(f"\n{BOLD}{GREEN}✔ 100% SUCCESS — ALL APIS, FEATURES & BUTTON TESTS PASSED PERFECTLY!{RESET}")
        print(f"{BOLD}{CYAN}{'=' * 75}{RESET}\n")
        return 0
    else:
        print(f"\n{BOLD}{RED}✘ SOME TESTS FAILED — PLEASE REVIEW ERROR TRACES ABOVE{RESET}")
        print(f"{BOLD}{CYAN}{'=' * 75}{RESET}\n")
        return 1


if __name__ == "__main__":
    sys.exit(run_all_tests())
