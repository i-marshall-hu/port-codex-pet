# Port Codex Pet contributor rules

## Scope

- Keep the distributable Skill under `skills/port-codex-pet/`.
- Preserve the boundary: `hatch-pet` creates and repairs imagery;
  `port-codex-pet` validates, imports, renders, and integrates existing v2 pets.
- Keep the browser runtime framework-neutral and dependency-free.
- Keep Python scripts standard-library-only unless a dependency is unavoidable and
  explicitly documented.

## Contract

- Accept `spriteVersionNumber: 2` only.
- Require a `1536x2288` WebP atlas using `192x208` cells in an 8x11 grid.
- Never allow `spritesheetPath` or target paths to escape their declared roots.
- Never overwrite differing target files unless the caller explicitly uses
  `--force` after inspection.
- Never add credentials, private pet assets, generated spritesheets, or personal
  filesystem paths to this repository.

## Verification

Run before committing:

```bash
python3 -m unittest discover -s skills/port-codex-pet/tests -v
uvx ruff check skills/port-codex-pet/scripts skills/port-codex-pet/tests
uvx ruff format --check skills/port-codex-pet/scripts skills/port-codex-pet/tests
node --check skills/port-codex-pet/assets/runtime/codex-pet-player.js
```

For runtime changes, also import a real validated v2 pet into an isolated fixture
and verify event priority, one-shot return, cardinal look directions, mobile
layout, reduced motion, and console errors in a browser.
