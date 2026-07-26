from __future__ import annotations

import hashlib
import json
import re
import struct
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Any

ATLAS_WIDTH = 1536
ATLAS_HEIGHT = 2288
CELL_WIDTH = 192
CELL_HEIGHT = 208
SPRITE_VERSION = 2
MAX_SPRITESHEET_BYTES = 100 * 1024 * 1024
PET_ID_PATTERN = re.compile(r"^[a-z0-9][a-z0-9-]{0,63}$")


class PetContractError(ValueError):
    """Raised when a Codex Pet package violates the portable v2 contract."""


@dataclass(frozen=True)
class PetPackage:
    root: Path
    manifest_path: Path
    sprite_path: Path
    pet_id: str
    display_name: str
    description: str
    sprite_version: int
    spritesheet_relative_path: str
    width: int
    height: int
    manifest_sha256: str
    sprite_sha256: str

    def as_dict(self) -> dict[str, Any]:
        return {
            "ok": True,
            "pet_id": self.pet_id,
            "display_name": self.display_name,
            "description": self.description,
            "sprite_version": self.sprite_version,
            "manifest_path": str(self.manifest_path),
            "spritesheet_path": str(self.sprite_path),
            "spritesheet_relative_path": self.spritesheet_relative_path,
            "width": self.width,
            "height": self.height,
            "manifest_sha256": self.manifest_sha256,
            "sprite_sha256": self.sprite_sha256,
        }


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _require_string(manifest: dict[str, Any], key: str) -> str:
    value = manifest.get(key)
    if not isinstance(value, str) or not value.strip():
        raise PetContractError(f"pet.json field {key!r} must be a non-empty string")
    return value.strip()


def _resolve_manifest(pet_path: Path) -> Path:
    candidate = pet_path.expanduser()
    manifest_path = candidate / "pet.json" if candidate.is_dir() else candidate
    if not manifest_path.is_file():
        raise PetContractError(f"pet.json was not found at {manifest_path}")
    if manifest_path.name != "pet.json":
        raise PetContractError(
            "pet package input must be a directory or a pet.json file"
        )
    return manifest_path.resolve()


def _resolve_spritesheet(root: Path, relative_value: str) -> Path:
    if "\\" in relative_value:
        raise PetContractError("spritesheetPath must use a safe relative path")
    relative_path = PurePosixPath(relative_value)
    if relative_path.is_absolute() or ".." in relative_path.parts:
        raise PetContractError("spritesheetPath must use a safe relative path")
    if not relative_path.parts or relative_path.suffix.lower() != ".webp":
        raise PetContractError("spritesheetPath must point to a relative .webp file")

    resolved = (root / Path(*relative_path.parts)).resolve()
    try:
        resolved.relative_to(root)
    except ValueError as error:
        raise PetContractError(
            "spritesheetPath must resolve inside the pet package"
        ) from error
    if not resolved.is_file():
        raise PetContractError(f"spritesheet was not found at {resolved}")
    return resolved


def _read_vp8x_dimensions(payload: bytes) -> tuple[int, int] | None:
    if len(payload) < 10:
        return None
    width = 1 + int.from_bytes(payload[4:7], "little")
    height = 1 + int.from_bytes(payload[7:10], "little")
    return width, height


def _read_vp8_dimensions(payload: bytes) -> tuple[int, int] | None:
    if len(payload) < 10 or payload[3:6] != b"\x9d\x01\x2a":
        return None
    width = int.from_bytes(payload[6:8], "little") & 0x3FFF
    height = int.from_bytes(payload[8:10], "little") & 0x3FFF
    return width, height


def _read_vp8l_dimensions(payload: bytes) -> tuple[int, int] | None:
    if len(payload) < 5 or payload[0] != 0x2F:
        return None
    bits = int.from_bytes(payload[1:5], "little")
    width = (bits & 0x3FFF) + 1
    height = ((bits >> 14) & 0x3FFF) + 1
    return width, height


def read_webp_dimensions(path: Path) -> tuple[int, int]:
    file_size = path.stat().st_size
    if file_size <= 0 or file_size > MAX_SPRITESHEET_BYTES:
        raise PetContractError(
            f"spritesheet size must be between 1 and {MAX_SPRITESHEET_BYTES} bytes"
        )
    data = path.read_bytes()
    if len(data) < 20 or data[:4] != b"RIFF" or data[8:12] != b"WEBP":
        raise PetContractError("spritesheet is not a valid WebP RIFF container")
    declared_size = struct.unpack_from("<I", data, 4)[0] + 8
    if declared_size != len(data):
        raise PetContractError("spritesheet has an invalid WebP container size")

    readers = {
        b"VP8X": _read_vp8x_dimensions,
        b"VP8 ": _read_vp8_dimensions,
        b"VP8L": _read_vp8l_dimensions,
    }
    offset = 12
    while offset + 8 <= len(data):
        chunk_name = data[offset : offset + 4]
        chunk_size = struct.unpack_from("<I", data, offset + 4)[0]
        payload_start = offset + 8
        payload_end = payload_start + chunk_size
        if payload_end > len(data):
            raise PetContractError("spritesheet contains a truncated WebP chunk")
        reader = readers.get(chunk_name)
        if reader is not None:
            dimensions = reader(data[payload_start:payload_end])
            if dimensions is None:
                raise PetContractError(
                    f"spritesheet contains an invalid {chunk_name!r} chunk"
                )
            return dimensions
        offset = payload_end + (chunk_size % 2)
    raise PetContractError("spritesheet WebP dimensions could not be determined")


def load_pet_package(pet_path: str | Path) -> PetPackage:
    manifest_path = _resolve_manifest(Path(pet_path))
    root = manifest_path.parent.resolve()
    try:
        raw_manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as error:
        raise PetContractError(f"pet.json could not be read: {error}") from error
    if not isinstance(raw_manifest, dict):
        raise PetContractError("pet.json must contain a JSON object")

    pet_id = _require_string(raw_manifest, "id")
    if not PET_ID_PATTERN.fullmatch(pet_id):
        raise PetContractError(
            "pet.json id must use lowercase letters, digits, and hyphens"
        )
    display_name = _require_string(raw_manifest, "displayName")
    description = _require_string(raw_manifest, "description")
    sprite_version = raw_manifest.get("spriteVersionNumber")
    if type(sprite_version) is not int or sprite_version != SPRITE_VERSION:
        raise PetContractError("spriteVersionNumber must be exactly 2")
    spritesheet_relative_path = _require_string(raw_manifest, "spritesheetPath")
    sprite_path = _resolve_spritesheet(root, spritesheet_relative_path)
    width, height = read_webp_dimensions(sprite_path)
    if (width, height) != (ATLAS_WIDTH, ATLAS_HEIGHT):
        raise PetContractError(
            "v2 spritesheet must be exactly "
            f"{ATLAS_WIDTH}x{ATLAS_HEIGHT}, got {width}x{height}"
        )

    return PetPackage(
        root=root,
        manifest_path=manifest_path,
        sprite_path=sprite_path,
        pet_id=pet_id,
        display_name=display_name,
        description=description,
        sprite_version=sprite_version,
        spritesheet_relative_path=spritesheet_relative_path,
        width=width,
        height=height,
        manifest_sha256=sha256_file(manifest_path),
        sprite_sha256=sha256_file(sprite_path),
    )
