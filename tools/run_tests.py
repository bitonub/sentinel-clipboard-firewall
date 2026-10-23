"""Run unittest with explicit contracts for missing Qt and unexpected skips."""

import argparse
import importlib.util
from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]


def flatten(suite):
    for test in suite:
        if isinstance(test, unittest.TestSuite):
            yield from flatten(test)
        else:
            yield test


def gate_errors(mode, gui_ids, discovered, result):
    errors = []
    if not gui_ids or discovered == 0 or result.testsRun != discovered:
        errors.append("Incomplete test discovery or execution.")
    skipped_ids = {test.id() for test, _ in result.skipped}
    expected = gui_ids if mode == "cli" else set()
    if skipped_ids != expected:
        errors.append("Unexpected skips or missing expected Qt skips.")
    if not result.wasSuccessful():
        errors.append("Tests failed.")
    return errors


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", choices=("cli", "gui"), required=True)
    args = parser.parse_args()
    has_qt = importlib.util.find_spec("PySide6") is not None
    if has_qt != (args.mode == "gui"):
        parser.error("CLI requires no Qt; GUI requires Qt installed.")
    suite = unittest.defaultTestLoader.discover(str(ROOT / "tests"), top_level_dir=str(ROOT))
    tests = list(flatten(suite))
    gui_ids = {test.id() for test in tests
               if type(test).__module__ == "tests.test_gui" and type(test).__name__ == "GuiTests"}
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    errors = gate_errors(args.mode, gui_ids, len(tests), result)
    for error in errors:
        print("GATE:", error)
    print(f"Mode: {args.mode}; discovered: {len(tests)}; GUI tests: {len(gui_ids)}; "
          f"skipped: {len(result.skipped)}; expected Qt skips: {len(gui_ids) if args.mode == 'cli' else 0}.")
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
