"""Builds build/lambda.zip: one zip for the three Lambdas (api, rex, webhook).

    python scripts/build_lambda.py

Linux wheels for Python 3.12 (the Lambda runtime), the `leash` package, rex.yaml
and the three handlers at the zip root (api_handler, rex_handler, webhook_handler).
Run it before `terraform plan` / `apply`. Needs `uv`.
"""

import shutil
import subprocess
import sys
import zipfile
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
STRANDS = REPO / "strands"
BUILD = REPO / "build"
PKG = BUILD / "lambda"
ZIP = BUILD / "lambda.zip"
HANDLERS = {"api": "api_handler.py", "rex_lambda": "rex_handler.py", "webhook_board": "webhook_handler.py"}
SKIP = {"__pycache__", "tests", "test"}


def run(*cmd: str) -> None:
    print("$", " ".join(cmd))
    subprocess.run(cmd, check=True, cwd=STRANDS)


def main() -> None:
    shutil.rmtree(BUILD, ignore_errors=True)
    PKG.mkdir(parents=True)
    requirements = BUILD / "requirements.txt"
    run("uv", "export", "--frozen", "--no-dev", "--no-hashes", "--no-emit-project", "-o", str(requirements))
    run("uv", "pip", "install", "-r", str(requirements), "--target", str(PKG),
        "--python-platform", "x86_64-manylinux2014", "--python-version", "3.12", "--only-binary", ":all:")

    shutil.copytree(STRANDS / "src" / "leash", PKG / "leash", ignore=shutil.ignore_patterns("__pycache__"))
    shutil.copy(STRANDS / "rex.yaml", PKG / "rex.yaml")
    for folder, name in HANDLERS.items():
        shutil.copy(REPO / "backend" / folder / "handler.py", PKG / name)

    with zipfile.ZipFile(ZIP, "w", zipfile.ZIP_DEFLATED) as archive:
        for path in sorted(PKG.rglob("*")):
            if path.is_file() and not SKIP & set(path.relative_to(PKG).parts):
                info = zipfile.ZipInfo(str(path.relative_to(PKG)).replace("\\", "/"), date_time=(2026, 1, 1, 0, 0, 0))
                info.external_attr = 0o644 << 16
                info.compress_type = zipfile.ZIP_DEFLATED
                archive.writestr(info, path.read_bytes())

    unzipped = sum(p.stat().st_size for p in PKG.rglob("*") if p.is_file()) / 1e6
    print(f"\n{ZIP}: {ZIP.stat().st_size / 1e6:.1f} MB zipped, {unzipped:.0f} MB unzipped (Lambda limit: 250 MB)")
    if unzipped > 250:
        sys.exit("Too big for Lambda: trim dependencies.")


if __name__ == "__main__":
    main()
