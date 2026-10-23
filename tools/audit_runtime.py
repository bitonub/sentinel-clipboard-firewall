"""Audit resolved runtime graphs; the auditor and build tools stay outside them."""

import argparse
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import venv

from packaging.requirements import Requirement
from packaging.utils import canonicalize_name

try:
    from tools.check_packages import python_in
except ModuleNotFoundError:
    from check_packages import python_in


INVENTORY = """
import importlib.metadata as m
import json
print(json.dumps([{'name': d.metadata['Name'], 'version': d.version,
                   'requires': d.requires or []} for d in m.distributions()]))
"""


def runtime_graph(records, extras):
    installed = {canonicalize_name(r["name"]): r for r in records}
    pending = [("sentinel-clipboard-firewall", frozenset(extras))]
    visited, selected = set(), {}
    while pending:
        name, selected_extras = pending.pop()
        key = (name, selected_extras)
        if key in visited:
            continue
        visited.add(key)
        record = installed[name]  # Missing dependencies fail, never silently skip.
        if name != "sentinel-clipboard-firewall":
            selected[name] = record["version"]
        for text in record["requires"]:
            dependency = Requirement(text)
            if dependency.marker and not any(dependency.marker.evaluate({"extra": extra})
                                             for extra in {"", *selected_extras}):
                continue
            child = canonicalize_name(dependency.name)
            if installed[child]["version"] not in dependency.specifier:
                raise RuntimeError("Installed runtime does not satisfy its metadata.")
            pending.append((child, frozenset(dependency.extras)))
    return selected


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--wheel", type=Path)
    args = parser.parse_args()
    candidates = [args.wheel] if args.wheel else list(Path("dist").glob("*.whl"))
    if len(candidates) != 1:
        parser.error("Expected exactly one wheel; build it first or pass --wheel.")
    wheel = candidates[0].resolve()
    with tempfile.TemporaryDirectory(prefix="sentinel-ci-audit-") as directory:
        work = Path(directory)
        venv.EnvBuilder(with_pip=True).create(work / "runtime")
        python = python_in(work / "runtime")
        subprocess.run([str(python), "-m", "pip", "install", str(wheel) + "[gui]"], check=True, timeout=600)
        subprocess.run([str(python), "-m", "pip", "check"], check=True, timeout=60)
        records = json.loads(subprocess.check_output(
            [str(python), "-I", "-X", "utf8", "-c", INVENTORY], encoding="utf-8", timeout=30))
        failures = []
        for label, extras in (("cli", set()), ("gui", {"gui"})):
            graph = runtime_graph(records, extras)
            print(f"Runtime {label}: {len(graph)} external dependencies.", flush=True)
            if label == "gui" and "pyside6" not in graph:
                raise RuntimeError("The GUI graph must include PySide6.")
            if not graph:
                continue  # Explicitly empty runtime graph, not a skipped audit error.
            requirements = work / f"{label}.txt"
            requirements.write_text("".join(f"{name}=={version}\n" for name, version in sorted(graph.items())),
                                    encoding="utf-8")
            result = subprocess.run([sys.executable, "-m", "pip_audit", "-r", str(requirements),
                                     "--no-deps", "--disable-pip", "--strict", "--progress-spinner", "off"],
                                    check=False, timeout=300)
            if result.returncode:
                failures.append(label)
        if failures:
            raise SystemExit("Runtime audit failed: " + ", ".join(failures))


if __name__ == "__main__":
    main()
