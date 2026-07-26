from __future__ import annotations

import argparse
import json
import os
import shutil
import sys
import tempfile
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Any

from pet_contract import PetContractError, PetPackage, load_pet_package, sha256_file

RUNTIME_SOURCE = (
    Path(__file__).resolve().parents[1] / "assets" / "runtime" / "codex-pet-player.js"
)


@dataclass(frozen=True)
class CopyAction:
    source: Path
    destination: Path
    status: str
    sha256: str

    def as_dict(self) -> dict[str, str]:
        return {
            "source": str(self.source),
            "destination": str(self.destination),
            "status": self.status,
            "sha256": self.sha256,
        }


def _relative_path(value: str, label: str, *, allow_dot: bool = False) -> Path:
    if "\\" in value:
        raise PetContractError(f"{label} must use a safe relative POSIX path")
    pure_path = PurePosixPath(value)
    if pure_path.is_absolute() or ".." in pure_path.parts:
        raise PetContractError(f"{label} must use a safe relative POSIX path")
    if value == ".":
        if allow_dot:
            return Path()
        raise PetContractError(f"{label} cannot be '.'")
    if not pure_path.parts and not allow_dot:
        raise PetContractError(f"{label} cannot be empty")
    return Path(*pure_path.parts)


def _url(prefix: str, *parts: str) -> str:
    if not prefix.startswith("/") or not prefix.endswith("/"):
        raise PetContractError("--url-prefix must start and end with '/'")
    clean_parts = tuple(part.strip("/") for part in parts if part.strip("/"))
    return prefix + "/".join(clean_parts)


def _plan_action(source: Path, destination: Path) -> CopyAction:
    source_hash = sha256_file(source)
    if not destination.exists():
        return CopyAction(source, destination, "create", source_hash)
    if not destination.is_file():
        raise PetContractError(f"destination is not a file: {destination}")
    status = "unchanged" if sha256_file(destination) == source_hash else "replace"
    return CopyAction(source, destination, status, source_hash)


def _atomic_copy(action: CopyAction) -> None:
    if action.status == "unchanged":
        return
    action.destination.parent.mkdir(parents=True, exist_ok=True)
    temporary_path: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            prefix=f".{action.destination.name}.",
            dir=action.destination.parent,
            delete=False,
        ) as temporary:
            temporary_path = Path(temporary.name)
        shutil.copy2(action.source, temporary_path)
        os.replace(temporary_path, action.destination)
    finally:
        if temporary_path is not None and temporary_path.exists():
            temporary_path.unlink()
    if sha256_file(action.destination) != action.sha256:
        raise PetContractError(f"copy verification failed for {action.destination}")


def _build_report(
    package: PetPackage,
    actions: tuple[CopyAction, ...],
    asset_path: Path,
    runtime_path: Path,
    url_prefix: str,
    dry_run: bool,
) -> dict[str, Any]:
    manifest_url = _url(url_prefix, asset_path.as_posix(), package.pet_id, "pet.json")
    runtime_url = _url(url_prefix, runtime_path.as_posix(), RUNTIME_SOURCE.name)
    return {
        "ok": True,
        "dry_run": dry_run,
        "pet_id": package.pet_id,
        "manifest_url": manifest_url,
        "runtime_url": runtime_url,
        "module_tag": f'<script type="module" src="{runtime_url}"></script>',
        "element_tag": (
            f'<codex-pet manifest="{manifest_url}" size="192" '
            "pointer-tracking></codex-pet>"
        ),
        "actions": [action.as_dict() for action in actions],
    }


def import_pet(
    *,
    pet: Path,
    target: Path,
    public_dir: str,
    asset_path: str,
    runtime_path: str,
    url_prefix: str,
    force: bool,
    dry_run: bool,
) -> dict[str, Any]:
    package = load_pet_package(pet)
    target_root = target.expanduser().resolve()
    if not target_root.is_dir():
        raise PetContractError(
            f"target project directory does not exist: {target_root}"
        )
    if not RUNTIME_SOURCE.is_file():
        raise PetContractError(f"bundled runtime is missing: {RUNTIME_SOURCE}")

    public_relative = _relative_path(public_dir, "--public-dir", allow_dot=True)
    asset_relative = _relative_path(asset_path, "--asset-path")
    runtime_relative = _relative_path(runtime_path, "--runtime-path")
    public_root = target_root / public_relative
    pet_destination = public_root / asset_relative / package.pet_id
    runtime_destination = public_root / runtime_relative / RUNTIME_SOURCE.name
    actions = (
        _plan_action(package.manifest_path, pet_destination / "pet.json"),
        _plan_action(
            package.sprite_path,
            pet_destination / package.spritesheet_relative_path,
        ),
        _plan_action(RUNTIME_SOURCE, runtime_destination),
    )
    conflicts = tuple(
        str(action.destination) for action in actions if action.status == "replace"
    )
    if conflicts and not force:
        joined = "\n  - ".join(conflicts)
        raise PetContractError(
            "destination files differ; inspect them and rerun with --force to replace:\n"
            f"  - {joined}"
        )
    if not dry_run:
        for action in actions:
            _atomic_copy(action)
    return _build_report(
        package,
        actions,
        asset_relative,
        runtime_relative,
        url_prefix,
        dry_run,
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Install a validated Codex Pet v2 package into a web project."
    )
    parser.add_argument("--pet", required=True, type=Path)
    parser.add_argument("--target", required=True, type=Path)
    parser.add_argument("--public-dir", default="public")
    parser.add_argument("--asset-path", default="pets")
    parser.add_argument("--runtime-path", default="codex-pet")
    parser.add_argument("--url-prefix", default="/")
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    arguments = build_parser().parse_args(argv)
    try:
        report = import_pet(
            pet=arguments.pet,
            target=arguments.target,
            public_dir=arguments.public_dir,
            asset_path=arguments.asset_path,
            runtime_path=arguments.runtime_path,
            url_prefix=arguments.url_prefix,
            force=arguments.force,
            dry_run=arguments.dry_run,
        )
    except PetContractError as error:
        print(f"port-codex-pet: {error}", file=sys.stderr)
        return 2
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
