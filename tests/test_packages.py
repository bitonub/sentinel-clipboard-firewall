"""Package-boundary regressions: licenses, payload integrity and exclusions."""
import base64
import contextlib
import csv
from email.parser import BytesParser
import hashlib
import io
from pathlib import Path
import tarfile
import tempfile
import tomllib
import unittest
from unittest import mock
import warnings
import zipfile

from tools import check_packages


class PackageArchiveTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory(prefix="sentinel-package-regression-")
        self.addCleanup(self.directory.cleanup)
        self.root = check_packages.ROOT
        self.project = tomllib.loads((self.root / "pyproject.toml").read_text(encoding="utf-8"))["project"]
        name = self.project["name"].replace("-", "_")
        self.prefix = f"{name}-{self.project['version']}"
        self.info = self.prefix + ".dist-info"
        self.egg = f"src/{name}.egg-info"
        self.wheel = Path(self.directory.name) / "fixture.whl"
        self.sdist = Path(self.directory.name) / "fixture.tar.gz"
        headers = ("Metadata-Version: 2.4\n"
                   f"Name: {self.project['name']}\nVersion: {self.project['version']}\n"
                   f"Requires-Python: {self.project['requires-python']}\n"
                   "License-Expression: MIT\nLicense-File: LICENSE\n"
                   "License-File: THIRD_PARTY_NOTICES.md\nProvides-Extra: gui\n"
                   f"Requires-Dist: {self.project['optional-dependencies']['gui'][0]}; extra == 'gui'\n\n")
        metadata = headers.encode() + (self.root / "README.md").read_bytes()
        self.wheel_files = {p.relative_to(self.root / "src").as_posix(): p.read_bytes()
                            for p in (self.root / "src/sentinel").rglob("*.py")}
        self.wheel_files.update({
            f"{self.info}/METADATA": metadata,
            f"{self.info}/WHEEL": b"Wheel-Version: 1.0\nRoot-Is-Purelib: true\nTag: py3-none-any\n",
            f"{self.info}/entry_points.txt": (b"[console_scripts]\nsentinel = sentinel.cli:main\n"
                                              b"[gui_scripts]\nsentinel-gui = sentinel.gui.app:main\n"),
            f"{self.info}/top_level.txt": b"sentinel\n",
        })
        for filename in self.project["license-files"]:
            self.wheel_files[f"{self.info}/licenses/{filename}"] = (self.root / filename).read_bytes()
        self.source_files = {name: (self.root / name).read_bytes() for name in
                             ("README.md", "MANIFEST.in", "pyproject.toml", "requirements-dev.txt",
                              *self.project["license-files"])}
        for directory in ("src/sentinel", "tests", "tools"):
            pattern = "*.py"
            self.source_files.update({p.relative_to(self.root).as_posix(): p.read_bytes()
                                      for p in (self.root / directory).rglob(pattern)})
        self.source_files.update({name: (self.root / name).read_bytes()
                                  for name in check_packages.PUBLIC_DOCUMENTS})
        self.source_files.update({"PKG-INFO": metadata, "setup.cfg": b"[egg_info]\n"})
        for filename in ("PKG-INFO", "SOURCES.txt", "dependency_links.txt", "entry_points.txt",
                         "requires.txt", "top_level.txt"):
            self.source_files[f"{self.egg}/{filename}"] = metadata if filename == "PKG-INFO" else b""

    def write_archives(self, *, bad_record=False):
        rows = []
        for name, data in sorted(self.wheel_files.items()):
            digest = base64.urlsafe_b64encode(hashlib.sha256(data).digest()).rstrip(b"=").decode()
            rows.append((name, "sha256=" + digest, str(len(data))))
        if bad_record:
            rows[0] = (rows[0][0], "sha256=synthetic-corruption", rows[0][2])
        rows.append((f"{self.info}/RECORD", "", ""))
        record = io.StringIO()
        csv.writer(record).writerows(rows)
        with zipfile.ZipFile(self.wheel, "w") as archive:
            for name, data in self.wheel_files.items():
                archive.writestr(name, data)
            archive.writestr(f"{self.info}/RECORD", record.getvalue())
        with tarfile.open(self.sdist, "w:gz") as archive:
            for name, data in self.source_files.items():
                entry = tarfile.TarInfo(f"{self.prefix}/{name}")
                entry.size = len(data)
                archive.addfile(entry, io.BytesIO(data))

    def audit(self):
        with contextlib.redirect_stdout(io.StringIO()):
            check_packages.audit_archives(self.wheel, self.sdist)

    def test_accepts_mit_and_exact_payload(self):
        self.write_archives()
        self.audit()

    def test_readme_crlf_checkout_matches_only_complete_text(self):
        readme = (self.root / "README.md").read_bytes().replace(b"\r\n", b"\n")
        windows_checkout = readme.replace(b"\n", b"\r\n")
        self.assertNotEqual(windows_checkout, readme)
        self.source_files["README.md"] = windows_checkout
        metadata_path = f"{self.info}/METADATA"
        self.wheel_files[metadata_path] = (
            self.wheel_files[metadata_path].replace(b"\r\n", b"\n").replace(b"\n", b"\r\n"))
        self.write_archives()
        with zipfile.ZipFile(self.wheel) as archive:
            description = BytesParser().parsebytes(archive.read(metadata_path)).get_payload(decode=True)
        readme_text = windows_checkout.decode("utf-8").replace("\r\n", "\n")
        self.assertEqual(description.count(b"\r\n"), windows_checkout.count(b"\r\n"))
        self.assertNotEqual(description.decode("utf-8").rstrip("\n"), readme_text.rstrip("\n"))
        original_read_bytes = Path.read_bytes

        def read_windows_checkout(path):
            if path == self.root / "README.md":
                return windows_checkout
            return original_read_bytes(path)

        original_metadata = self.wheel_files[metadata_path]
        with mock.patch.object(Path, "read_bytes", read_windows_checkout):
            self.audit()
            for changed_description in (
                original_metadata + b"\n",
                original_metadata.replace(b"SENTINEL", b"SENTINEX", 1),
            ):
                with self.subTest(changed_description=changed_description[-12:]):
                    self.wheel_files[metadata_path] = changed_description
                    self.write_archives()
                    with self.assertRaisesRegex(RuntimeError, "Wheel README mismatch"):
                        self.audit()

    def test_rejects_missing_license_even_with_consistent_record(self):
        del self.wheel_files[f"{self.info}/licenses/LICENSE"]
        self.write_archives()
        with self.assertRaisesRegex(RuntimeError, "missing wheel files"):
            self.audit()

    def test_rejects_altered_notice_even_with_consistent_record(self):
        self.wheel_files[f"{self.info}/licenses/THIRD_PARTY_NOTICES.md"] = b"Synthetic altered notice\n"
        self.write_archives()
        with self.assertRaisesRegex(RuntimeError, "license/notice mismatch"):
            self.audit()

    def test_rejects_changed_sdist_document_of_same_size(self):
        path = "docs/guia-tecnica.md"
        data = self.source_files[path]
        self.source_files[path] = b"!" + data[1:]
        self.write_archives()
        with self.assertRaisesRegex(RuntimeError, "source content mismatch"):
            self.audit()

    def test_rejects_wrong_sdist_license_expression(self):
        self.source_files["PKG-INFO"] = self.source_files["PKG-INFO"].replace(
            b"License-Expression: MIT", b"License-Expression: BSD-3-Clause")
        self.write_archives()
        with self.assertRaisesRegex(RuntimeError, "license expression"):
            self.audit()

    def test_rejects_secret_file_outside_allowlist(self):
        self.source_files[".env"] = b"SYNTHETIC_FIXTURE_ONLY=1\n"
        self.write_archives()
        with self.assertRaisesRegex(RuntimeError, "Unexpected or missing sdist files"):
            self.audit()

    def test_rejects_duplicate_wheel_entries(self):
        self.write_archives()
        name = "sentinel/__init__.py"
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", UserWarning)
            with zipfile.ZipFile(self.wheel, "a") as archive:
                archive.writestr(name, self.wheel_files[name])
        with self.assertRaisesRegex(RuntimeError, "Duplicate wheel files"):
            self.audit()

    def test_rejects_invalid_record_hash(self):
        self.write_archives(bad_record=True)
        with self.assertRaisesRegex(RuntimeError, "RECORD hash/size"):
            self.audit()

    def test_rejects_private_documents_even_when_they_exist_locally(self):
        for name in sorted(check_packages.PRIVATE_DOCUMENTS):
            with self.subTest(path=name):
                # Never copy private originals into regression archives.
                self.source_files[name] = b"Synthetic private-document fixture only.\n"
                self.write_archives()
                with self.assertRaisesRegex(RuntimeError, "Private document in sdist"):
                    self.audit()
                del self.source_files[name]

    def test_rejects_unlisted_markdown_document(self):
        self.source_files["docs/conversacion-exportada.md"] = b"Synthetic export fixture only.\n"
        self.write_archives()
        with self.assertRaisesRegex(RuntimeError, "Unexpected or missing sdist files"):
            self.audit()
