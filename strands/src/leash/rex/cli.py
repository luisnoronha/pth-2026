"""`rex --leash N "prompt"`: run Rex from the terminal."""

import argparse
import logging
import os

from leash.common.config import model_names, model_settings
from leash.hooks.levels import MAX_LEVEL
from leash.rex.agent import build_rex
from leash.rex.offline import gullible_model
from leash.rex.console import BOLD, DIM, RED, RESET, YELLOW, ConsoleHook


class _LeashLogFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        colour = RED if record.levelno >= logging.WARNING else DIM
        return f"   {colour}{YELLOW if record.levelno == logging.WARNING else ''}[leash] {record.getMessage()}{RESET}"


def _setup_logging() -> None:
    handler = logging.StreamHandler()
    handler.setFormatter(_LeashLogFormatter())
    logger = logging.getLogger("leash")
    logger.addHandler(handler)
    logger.setLevel(logging.INFO)
    logger.propagate = False


def main() -> None:
    parser = argparse.ArgumentParser(prog="rex", description="Run Rex at a given leash level.")
    parser.add_argument("--leash", type=int, default=0, choices=range(MAX_LEVEL + 1), help="leash level")
    parser.add_argument("--profile", help="AWS profile to use (e.g. personal)")
    parser.add_argument("--model", choices=model_names(), help="model name from rex.yaml (default: its `active`)")
    parser.add_argument("--offline", action="store_true",
                        help="no model API: a gullible scripted brain that obeys what it reads (no API key needed)")
    parser.add_argument("prompt", help='what to ask Rex, e.g. "Brief me on http://localhost:8000/acme-ir.html"')
    args = parser.parse_args()

    if args.profile:
        os.environ["AWS_PROFILE"] = args.profile
    if args.model:
        os.environ["REX_MODEL"] = args.model
    os.system("")  # enables ANSI colours in the classic Windows console
    _setup_logging()

    offline = " (offline, gullible brain)" if args.offline else f" ({model_settings().name})"
    print(f"{BOLD}Rex, leash level {args.leash}{offline}{RESET}\n")
    model = gullible_model() if args.offline else None
    rex = build_rex(args.leash, model=model, extra_hooks=[ConsoleHook()])
    result = rex(args.prompt)
    briefing = result.structured_output

    if briefing is None:
        print(f"\n{RED}{BOLD}No briefing ({result.stop_reason}): {str(result).strip()}{RESET}")
        return
    print(f"\n{BOLD}Briefing: {briefing.company}{RESET}")
    for line in briefing.lines:
        print(f"  - {line}")
    for source in briefing.sources:
        print(f"  [{source}]")


if __name__ == "__main__":
    main()
