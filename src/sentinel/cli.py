"""Explicit, local stdin interface for scanning and sanitizing text."""

import argparse
from dataclasses import asdict
import json
import sys

from sentinel.core.sanitize import sanitize
from sentinel.core.scan import scan
from sentinel.core.command_guard import CommandSyntaxError, check_command
from sentinel.adapters.wayland import ClipboardError, sanitize_clipboard


MAX_INPUT_BYTES = 1024 * 1024


def main() -> int:
    parser = argparse.ArgumentParser(prog="sentinel")
    parser.add_argument("command", choices=("scan", "sanitize", "check-command", "clipboard"))
    parser.add_argument("action", nargs="?", choices=("sanitize",))
    parser.add_argument("--shell", choices=("bash", "powershell"), default=None)
    args = parser.parse_args()
    if args.shell is not None and args.command != "check-command":
        parser.error("--shell solo se admite con check-command.")
    if args.command == "clipboard":
        if args.action != "sanitize":
            parser.error("clipboard requiere la acción sanitize.")
        try:
            result = sanitize_clipboard()
        except ClipboardError as error:
            print(f"Error: {error}", file=sys.stderr)
            return 2
        status = "Portapapeles actualizado" if result.changed else "Sin cambios"
        print(f"{status}; hallazgos: {result.findings}.")
        return 0
    if args.action is not None:
        parser.error("La acción sanitize solo se admite con clipboard.")

    raw = sys.stdin.buffer.read(MAX_INPUT_BYTES + 1)
    if len(raw) > MAX_INPUT_BYTES:
        print("Error: la entrada supera 1 MiB.", file=sys.stderr)
        return 2
    try:
        content = raw.decode("utf-8")
    except UnicodeDecodeError:
        print("Error: la entrada no es UTF-8 válido.", file=sys.stderr)
        return 2

    if args.command == "check-command":
        try:
            findings = check_command(content, shell=args.shell or "bash")
        except CommandSyntaxError:
            print("Error: no se pudo analizar la sintaxis del comando.", file=sys.stderr)
            return 2
        print(json.dumps([asdict(finding) for finding in findings], ensure_ascii=False))
    elif args.command == "scan":
        print(json.dumps([asdict(finding) for finding in scan(content)], ensure_ascii=False))
    else:
        sys.stdout.write(sanitize(content))
    return 0
