#!/usr/bin/env python3
"""
Master Test Runner

Runs all tests in the Feature Voting System backend in a logical order with
progress reporting and summary.

Usage:
    python run_tests.py                # Run all tests
    python run_tests.py --coverage     # Include coverage report
    python run_tests.py --fast         # Skip slow integration tests
    python run_tests.py --verbose      # Detailed output
    python run_tests.py --category=unit  # Run specific category only

Categories:
    - unit: Fast unit tests (pytest tests/)
    - integration: Integration tests (test_*.py files)
    - all: All tests (default)
"""

import sys
import subprocess
import time
import argparse
from pathlib import Path
from typing import List, Tuple


class Colors:
    """ANSI color codes for terminal output."""
    GREEN = '\033[0;32m'
    YELLOW = '\033[1;33m'
    RED = '\033[0;31m'
    BLUE = '\033[0;34m'
    NC = '\033[0m'  # No Color
    BOLD = '\033[1m'


class TestRunner:
    """Master test runner for the Feature Voting System."""

    def __init__(self, args):
        self.args = args
        self.backend_dir = Path(__file__).parent
        self.results = []
        self.start_time = time.time()

    def print_header(self, message: str):
        """Print section header."""
        print(f"\n{Colors.BLUE}{'=' * 80}{Colors.NC}")
        print(f"{Colors.BLUE}{message:^80}{Colors.NC}")
        print(f"{Colors.BLUE}{'=' * 80}{Colors.NC}\n")

    def print_step(self, message: str):
        """Print step message."""
        print(f"{Colors.BOLD}==>{Colors.NC} {message}")

    def print_success(self, message: str):
        """Print success message."""
        print(f"{Colors.GREEN}✓{Colors.NC} {message}")

    def print_warning(self, message: str):
        """Print warning message."""
        print(f"{Colors.YELLOW}!{Colors.NC} {message}")

    def print_error(self, message: str):
        """Print error message."""
        print(f"{Colors.RED}✗{Colors.NC} {message}")

    def run_command(self, cmd: List[str], description: str, timeout: int = 300) -> Tuple[bool, float]:
        """
        Run a command and return success status and duration.

        Args:
            cmd: Command to run as list
            description: Test description
            timeout: Timeout in seconds

        Returns:
            Tuple of (success, duration_seconds)
        """
        self.print_step(f"Running: {description}")
        start = time.time()

        try:
            if self.args.verbose:
                result = subprocess.run(
                    cmd,
                    cwd=self.backend_dir,
                    timeout=timeout,
                    check=False
                )
            else:
                result = subprocess.run(
                    cmd,
                    cwd=self.backend_dir,
                    timeout=timeout,
                    check=False,
                    capture_output=True,
                    text=True
                )

            duration = time.time() - start
            success = result.returncode == 0

            if success:
                self.print_success(f"{description} - Passed ({duration:.1f}s)")
            else:
                self.print_error(f"{description} - Failed ({duration:.1f}s)")
                if not self.args.verbose and hasattr(result, 'stdout'):
                    print(f"\n{Colors.YELLOW}Last 20 lines of output:{Colors.NC}")
                    lines = result.stdout.split('\n')
                    print('\n'.join(lines[-20:]))

            self.results.append({
                'description': description,
                'success': success,
                'duration': duration
            })

            return success, duration

        except subprocess.TimeoutExpired:
            duration = time.time() - start
            self.print_error(f"{description} - Timeout after {timeout}s")
            self.results.append({
                'description': description,
                'success': False,
                'duration': duration
            })
            return False, duration

        except Exception as e:
            duration = time.time() - start
            self.print_error(f"{description} - Error: {e}")
            self.results.append({
                'description': description,
                'success': False,
                'duration': duration
            })
            return False, duration

    def run_unit_tests(self):
        """Run pytest unit tests."""
        self.print_header("UNIT TESTS (pytest)")

        # Check if pytest is available
        try:
            subprocess.run(
                ["python", "-m", "pytest", "--version"],
                check=True,
                capture_output=True
            )
        except subprocess.CalledProcessError:
            self.print_warning("pytest not found, installing...")
            subprocess.run(
                ["pip", "install", "pytest", "pytest-asyncio"],
                check=True
            )

        # Build pytest command
        cmd = ["python", "-m", "pytest", "tests/", "-v"]

        if self.args.coverage:
            cmd.extend(["--cov=app", "--cov-report=term-missing"])

        if self.args.verbose:
            cmd.append("-vv")
        else:
            cmd.append("--tb=short")

        success, duration = self.run_command(cmd, "Pytest Unit Tests")

        if self.args.coverage:
            # Generate HTML coverage report
            self.print_step("Generating HTML coverage report...")
            subprocess.run(
                ["python", "-m", "pytest", "tests/", "--cov=app", "--cov-report=html"],
                cwd=self.backend_dir,
                capture_output=True
            )
            self.print_success(f"Coverage report: {self.backend_dir}/htmlcov/index.html")

        return success

    def run_integration_tests(self):
        """Run integration tests."""
        self.print_header("INTEGRATION TESTS")

        # List of integration tests to run
        integration_tests = [
            ("test_schemas.py", "Schema Validation Tests", 10),
            ("test_llm_service.py", "LLM Service Tests", 30),
            ("test_detailed_features.py", "Detailed Features Integration Test", 60),
            ("test_password_management.py", "Password Management Tests", 20),
            ("test_search.py", "Vector Search Tests", 30),
        ]

        # Optionally add slow tests
        if not self.args.fast:
            integration_tests.append(
                ("test_complete_api.py", "Complete API Workflow Test", 180)
            )

        all_passed = True
        for test_file, description, timeout in integration_tests:
            test_path = self.backend_dir / test_file

            if not test_path.exists():
                self.print_warning(f"Skipping {test_file} (not found)")
                continue

            success, _ = self.run_command(
                ["python", str(test_path)],
                description,
                timeout=timeout
            )

            if not success:
                all_passed = False

        return all_passed

    def print_summary(self):
        """Print test summary."""
        total_duration = time.time() - self.start_time

        self.print_header("TEST SUMMARY")

        # Count results
        total = len(self.results)
        passed = sum(1 for r in self.results if r['success'])
        failed = total - passed

        # Print results table
        print(f"{'Test Category':<50} {'Result':<10} {'Duration'}")
        print("-" * 80)

        for result in self.results:
            status = f"{Colors.GREEN}PASSED{Colors.NC}" if result['success'] else f"{Colors.RED}FAILED{Colors.NC}"
            print(f"{result['description']:<50} {status:<20} {result['duration']:.1f}s")

        print("-" * 80)

        # Print totals
        if failed == 0:
            print(f"\n{Colors.GREEN}✓ ALL TESTS PASSED{Colors.NC}")
            print(f"  Total: {total}")
            print(f"  Passed: {passed}")
            print(f"  Duration: {total_duration:.1f}s")
        else:
            print(f"\n{Colors.RED}✗ SOME TESTS FAILED{Colors.NC}")
            print(f"  Total: {total}")
            print(f"  Passed: {Colors.GREEN}{passed}{Colors.NC}")
            print(f"  Failed: {Colors.RED}{failed}{Colors.NC}")
            print(f"  Duration: {total_duration:.1f}s")

        print()

        return failed == 0

    def run_all(self):
        """Run all tests."""
        self.print_header("FEATURE VOTING SYSTEM - TEST SUITE")

        all_passed = True

        # Run unit tests
        if self.args.category in ['all', 'unit']:
            if not self.run_unit_tests():
                all_passed = False

        # Run integration tests
        if self.args.category in ['all', 'integration']:
            if not self.run_integration_tests():
                all_passed = False

        # Print summary
        success = self.print_summary()

        return 0 if success else 1


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Master test runner for Feature Voting System",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python run_tests.py                   # Run all tests
  python run_tests.py --coverage        # With coverage report
  python run_tests.py --fast            # Skip slow integration tests
  python run_tests.py --verbose         # Detailed output
  python run_tests.py --category=unit   # Unit tests only
        """
    )

    parser.add_argument(
        '--coverage',
        action='store_true',
        help='Generate coverage report'
    )

    parser.add_argument(
        '--fast',
        action='store_true',
        help='Skip slow integration tests'
    )

    parser.add_argument(
        '--verbose', '-v',
        action='store_true',
        help='Verbose output'
    )

    parser.add_argument(
        '--category',
        choices=['all', 'unit', 'integration'],
        default='all',
        help='Test category to run (default: all)'
    )

    args = parser.parse_args()

    runner = TestRunner(args)
    sys.exit(runner.run_all())


if __name__ == "__main__":
    main()
