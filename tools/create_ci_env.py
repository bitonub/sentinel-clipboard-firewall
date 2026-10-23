"""Create a clean job environment and select it for subsequent Actions steps."""

import os
from pathlib import Path
import venv


if __name__ == "__main__":
    target = Path(".venv-ci").resolve()
    if target.exists():
        raise SystemExit("The CI environment must be new.")
    venv.EnvBuilder(with_pip=True).create(target)
    scripts = target / ("Scripts" if os.name == "nt" else "bin")
    with open(os.environ["GITHUB_PATH"], "a", encoding="utf-8") as output:
        output.write(str(scripts) + "\n")
