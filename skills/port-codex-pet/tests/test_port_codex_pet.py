from __future__ import annotations

import io
import json
import struct
import subprocess
import sys
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from unittest.mock import patch

SKILL_ROOT = Path(__file__).resolve().parents[1]
SCRIPTS_DIR = SKILL_ROOT / "scripts"
sys.path.insert(0, str(SCRIPTS_DIR))

import import_pet as import_pet_module
from import_pet import import_pet
from import_pet import main as import_main
from pet_contract import (
    PetContractError,
    load_pet_package,
    read_webp_dimensions,
)
from validate_pet import main as validate_main


def write_vp8x_webp(path: Path, width: int = 1536, height: int = 2288) -> None:
    payload = (
        b"\x00\x00\x00\x00"
        + (width - 1).to_bytes(3, "little")
        + (height - 1).to_bytes(3, "little")
    )
    chunk = b"VP8X" + struct.pack("<I", len(payload)) + payload
    path.write_bytes(b"RIFF" + struct.pack("<I", 4 + len(chunk)) + b"WEBP" + chunk)


def write_chunk_webp(path: Path, chunk_name: bytes, payload: bytes) -> None:
    padding = b"\x00" if len(payload) % 2 else b""
    chunk = chunk_name + struct.pack("<I", len(payload)) + payload + padding
    path.write_bytes(b"RIFF" + struct.pack("<I", 4 + len(chunk)) + b"WEBP" + chunk)


def write_pet(
    root: Path,
    *,
    pet_id: str = "pocky",
    version: int = 2,
    spritesheet_path: str = "spritesheet.webp",
    width: int = 1536,
    height: int = 2288,
) -> Path:
    root.mkdir(parents=True, exist_ok=True)
    manifest = {
        "id": pet_id,
        "displayName": "Pocky",
        "description": "A test pet.",
        "spriteVersionNumber": version,
        "spritesheetPath": spritesheet_path,
    }
    (root / "pet.json").write_text(
        json.dumps(manifest, ensure_ascii=False), encoding="utf-8"
    )
    sprite = root / spritesheet_path
    sprite.parent.mkdir(parents=True, exist_ok=True)
    write_vp8x_webp(sprite, width=width, height=height)
    return root


class PetContractTests(unittest.TestCase):
    def test_loads_valid_v2_package(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            pet_dir = write_pet(Path(temp_dir) / "pet")

            package = load_pet_package(pet_dir)

            self.assertEqual(package.pet_id, "pocky")
            self.assertEqual(package.sprite_version, 2)
            self.assertEqual((package.width, package.height), (1536, 2288))
            self.assertEqual(len(package.sprite_sha256), 64)

    def test_rejects_v1_package(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            pet_dir = write_pet(Path(temp_dir) / "pet", version=1)

            with self.assertRaisesRegex(PetContractError, "spriteVersionNumber"):
                load_pet_package(pet_dir)

    def test_rejects_wrong_dimensions(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            pet_dir = write_pet(Path(temp_dir) / "pet", height=1872)

            with self.assertRaisesRegex(PetContractError, "1536x2288"):
                load_pet_package(pet_dir)

    def test_rejects_spritesheet_path_escape(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            pet_dir = write_pet(root / "pet")
            manifest_path = pet_dir / "pet.json"
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            manifest["spritesheetPath"] = "../spritesheet.webp"
            manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
            write_vp8x_webp(root / "spritesheet.webp")

            with self.assertRaisesRegex(PetContractError, "relative path"):
                load_pet_package(pet_dir)

    def test_reads_vp8_and_vp8l_dimensions(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            vp8_path = root / "vp8.webp"
            vp8_payload = (
                b"\x00\x00\x00"
                + b"\x9d\x01\x2a"
                + (1536).to_bytes(2, "little")
                + (2288).to_bytes(2, "little")
            )
            write_chunk_webp(vp8_path, b"VP8 ", vp8_payload)
            vp8l_path = root / "vp8l.webp"
            vp8l_bits = (1536 - 1) | ((2288 - 1) << 14)
            write_chunk_webp(
                vp8l_path,
                b"VP8L",
                b"\x2f" + vp8l_bits.to_bytes(4, "little"),
            )

            self.assertEqual(read_webp_dimensions(vp8_path), (1536, 2288))
            self.assertEqual(read_webp_dimensions(vp8l_path), (1536, 2288))

    def test_rejects_malformed_manifest_and_webp_variants(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            wrong_name = root / "manifest.json"
            wrong_name.write_text("{}", encoding="utf-8")
            with self.assertRaisesRegex(PetContractError, "directory or a pet.json"):
                load_pet_package(wrong_name)

            pet_dir = write_pet(root / "pet")
            manifest_path = pet_dir / "pet.json"
            manifest_path.write_text("[]", encoding="utf-8")
            with self.assertRaisesRegex(PetContractError, "JSON object"):
                load_pet_package(pet_dir)

            manifest_path.write_text("{", encoding="utf-8")
            with self.assertRaisesRegex(PetContractError, "could not be read"):
                load_pet_package(pet_dir)

            invalid_webp = root / "invalid.webp"
            invalid_webp.write_bytes(b"not-webp")
            with self.assertRaisesRegex(PetContractError, "RIFF container"):
                read_webp_dimensions(invalid_webp)

    def test_rejects_invalid_pet_fields_and_sprite_locations(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            pet_dir = write_pet(root / "pet")
            manifest_path = pet_dir / "pet.json"
            original = json.loads(manifest_path.read_text(encoding="utf-8"))

            for key, value, message in (
                ("displayName", "", "non-empty string"),
                ("id", "Not Valid", "lowercase letters"),
                ("spritesheetPath", "sprite.png", "relative .webp"),
                ("spritesheetPath", "nested/missing.webp", "was not found"),
                ("spritesheetPath", "nested\\sprite.webp", "relative path"),
            ):
                manifest_path.write_text(
                    json.dumps({**original, key: value}), encoding="utf-8"
                )
                with self.assertRaisesRegex(PetContractError, message):
                    load_pet_package(pet_dir)


class ImportPetTests(unittest.TestCase):
    def run_import(self, *arguments: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [sys.executable, str(SCRIPTS_DIR / "import_pet.py"), *arguments],
            check=False,
            capture_output=True,
            text=True,
        )

    def test_imports_runtime_and_pet_idempotently(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            pet_dir = write_pet(root / "pet")
            target = root / "target"
            target.mkdir()

            first = self.run_import("--pet", str(pet_dir), "--target", str(target))
            second = self.run_import("--pet", str(pet_dir), "--target", str(target))

            self.assertEqual(first.returncode, 0, first.stderr)
            self.assertEqual(second.returncode, 0, second.stderr)
            report = json.loads(second.stdout)
            self.assertEqual(report["pet_id"], "pocky")
            self.assertEqual(report["manifest_url"], "/pets/pocky/pet.json")
            self.assertTrue((target / "public/pets/pocky/spritesheet.webp").is_file())
            self.assertTrue((target / "public/codex-pet/codex-pet-player.js").is_file())
            self.assertEqual(
                {action["status"] for action in report["actions"]}, {"unchanged"}
            )

    def test_refuses_conflict_without_force_and_force_replaces_it(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            pet_dir = write_pet(root / "pet")
            target = root / "target"
            conflict = target / "public/pets/pocky/pet.json"
            conflict.parent.mkdir(parents=True)
            conflict.write_text("conflict", encoding="utf-8")

            refused = self.run_import("--pet", str(pet_dir), "--target", str(target))
            forced = self.run_import(
                "--pet", str(pet_dir), "--target", str(target), "--force"
            )

            self.assertEqual(refused.returncode, 2)
            self.assertIn("--force", refused.stderr)
            self.assertEqual(forced.returncode, 0, forced.stderr)
            self.assertEqual(
                json.loads(conflict.read_text(encoding="utf-8"))["id"], "pocky"
            )

    def test_dry_run_does_not_write(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            pet_dir = write_pet(root / "pet")
            target = root / "target"
            target.mkdir()

            result = self.run_import(
                "--pet", str(pet_dir), "--target", str(target), "--dry-run"
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertFalse((target / "public").exists())
            self.assertEqual(
                {action["status"] for action in json.loads(result.stdout)["actions"]},
                {"create"},
            )

    def test_import_api_copies_and_reuses_identical_files(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            pet_dir = write_pet(root / "pet")
            target = root / "target"
            target.mkdir()

            first = import_pet(
                pet=pet_dir,
                target=target,
                public_dir="public",
                asset_path="pets",
                runtime_path="codex-pet",
                url_prefix="/",
                force=False,
                dry_run=False,
            )
            second = import_pet(
                pet=pet_dir,
                target=target,
                public_dir="public",
                asset_path="pets",
                runtime_path="codex-pet",
                url_prefix="/",
                force=False,
                dry_run=False,
            )

            self.assertEqual(first["actions"][0]["status"], "create")
            self.assertEqual(
                {action["status"] for action in second["actions"]}, {"unchanged"}
            )

    def test_import_api_protects_conflicts_and_validates_paths(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            pet_dir = write_pet(root / "pet")
            target = root / "target"
            conflict = target / "public/pets/pocky/pet.json"
            conflict.parent.mkdir(parents=True)
            conflict.write_text("conflict", encoding="utf-8")
            arguments = {
                "pet": pet_dir,
                "target": target,
                "public_dir": "public",
                "asset_path": "pets",
                "runtime_path": "codex-pet",
                "url_prefix": "/",
                "force": False,
                "dry_run": False,
            }

            with self.assertRaisesRegex(PetContractError, "--force"):
                import_pet(**arguments)
            forced = import_pet(**{**arguments, "force": True})
            self.assertEqual(forced["actions"][0]["status"], "replace")
            with self.assertRaisesRegex(PetContractError, "safe relative"):
                import_pet(**{**arguments, "public_dir": "../outside"})
            with self.assertRaisesRegex(PetContractError, "url-prefix"):
                import_pet(**{**arguments, "url_prefix": "portal"})

    def test_import_api_validates_target_runtime_and_destinations(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            pet_dir = write_pet(root / "pet")
            target = root / "target"
            target.mkdir()
            arguments = {
                "pet": pet_dir,
                "target": target,
                "public_dir": ".",
                "asset_path": "pets",
                "runtime_path": "codex-pet",
                "url_prefix": "/portal/",
                "force": False,
                "dry_run": True,
            }

            report = import_pet(**arguments)
            self.assertEqual(report["manifest_url"], "/portal/pets/pocky/pet.json")
            with self.assertRaisesRegex(PetContractError, "target project"):
                import_pet(**{**arguments, "target": root / "missing"})
            with self.assertRaisesRegex(PetContractError, "safe relative"):
                import_pet(**{**arguments, "asset_path": "bad\\path"})
            with self.assertRaisesRegex(PetContractError, "cannot be empty"):
                import_pet(**{**arguments, "asset_path": ""})
            with self.assertRaisesRegex(PetContractError, "cannot be '.'"):
                import_pet(**{**arguments, "asset_path": "."})
            with (
                patch.object(
                    import_pet_module, "RUNTIME_SOURCE", root / "missing-runtime.js"
                ),
                self.assertRaisesRegex(PetContractError, "runtime is missing"),
            ):
                import_pet(**arguments)

            destination = target / "pets/pocky/pet.json"
            destination.mkdir(parents=True)
            with self.assertRaisesRegex(PetContractError, "not a file"):
                import_pet(**arguments)

    def test_import_main_reports_success_and_failure(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            pet_dir = write_pet(root / "pet")
            target = root / "target"
            target.mkdir()
            stdout = io.StringIO()
            stderr = io.StringIO()

            with redirect_stdout(stdout), redirect_stderr(stderr):
                success = import_main(
                    [
                        "--pet",
                        str(pet_dir),
                        "--target",
                        str(target),
                        "--dry-run",
                    ]
                )
                failure = import_main(
                    [
                        "--pet",
                        str(pet_dir),
                        "--target",
                        str(root / "missing"),
                    ]
                )

            self.assertEqual(success, 0)
            self.assertTrue(json.loads(stdout.getvalue())["dry_run"])
            self.assertEqual(failure, 2)
            self.assertIn("target project directory", stderr.getvalue())


class ValidatePetCliTests(unittest.TestCase):
    def test_validate_main_reports_success_and_failure(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            pet_dir = write_pet(root / "pet")
            stdout = io.StringIO()
            stderr = io.StringIO()

            with redirect_stdout(stdout), redirect_stderr(stderr):
                success = validate_main([str(pet_dir)])
                failure = validate_main([str(root / "missing")])

            self.assertEqual(success, 0)
            self.assertEqual(json.loads(stdout.getvalue())["pet_id"], "pocky")
            self.assertEqual(failure, 2)
            self.assertIn("pet.json was not found", stderr.getvalue())


if __name__ == "__main__":
    unittest.main()
