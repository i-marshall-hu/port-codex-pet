from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Sequence
from pathlib import Path

from pet_contract import PetContractError, load_pet_package


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Validate a portable Codex Pet v2 package."
    )
    parser.add_argument(
        "pet",
        type=Path,
        help="Pet directory or absolute path to pet.json.",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    arguments = build_parser().parse_args(argv)
    try:
        package = load_pet_package(arguments.pet)
    except PetContractError as error:
        print(f"port-codex-pet: {error}", file=sys.stderr)
        return 2
    print(json.dumps(package.as_dict(), ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
