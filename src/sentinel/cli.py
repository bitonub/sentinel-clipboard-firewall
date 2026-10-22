"""Explicit, local stdin interface for scanning and sanitizing text."""

import argparse
from dataclasses import asdict
import json
import sys

from sentinel.core.sanitize import sanitize
from sentinel.core.scan import scan


MAX_INPUT_BYTES = 1024 * 1024


def main() -> int:
    parser = argparse.ArgumentParser(prog="sentinel")
    parser.add_argument("command", choices=("scan", "sanitize"))
    args = parser.parse_args()

    raw = sys.stdin.buffer.read(MAX_INPUT_BYTES + 1)
    if len(raw) > MAX_INPUT_BYTES:
        print("Error: la entrada supera 1 MiB.", file=sys.stderr)
        return 2
    try:
        content = raw.decode("utf-8")
    except UnicodeDecodeError:
        print("Error: la entrada no es UTF-8 válido.", file=sys.stderr)
        return 2

    if args.command == "scan":
        print(json.dumps([asdict(finding) for finding in scan(content)], ensure_ascii=False))
    else:
        sys.stdout.write(sanitize(content))
    return 0
