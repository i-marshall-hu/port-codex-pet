---
name: port-codex-pet
description: Install a validated Codex Pet v2 package into a web frontend with a portable zero-dependency player, event-driven animations, pointer look tracking, reduced-motion behavior, deterministic asset copying, and browser verification. Use when a user asks to reuse, migrate, embed, transfer, or integrate an existing Codex pet, pet.json, or 8x11 spritesheet in an HTML, React, Next.js, Vue, Svelte, Vite, or other browser project. Hand pet creation or repair to hatch-pet instead.
---

# Port Codex Pet

Move an existing Codex Pet into a frontend without retaining runtime references to
`~/.codex`. Keep pet identity assets, the portable player, and product-specific
event mapping separate.

## Workflow

1. Inspect the target repository instructions, dirty state, framework, static asset
   directory, base URL, and existing pet code. Preserve unrelated changes.
2. Locate the source package at `${CODEX_HOME:-$HOME/.codex}/pets/<pet-id>` or
   the user-provided path. If no packaged pet exists, or validation shows a visual
   or atlas defect, stop this workflow and use `hatch-pet` to create or repair it.
3. Validate before copying:

   ```bash
   SKILL_DIR="${CODEX_HOME:-$HOME/.codex}/skills/port-codex-pet"
   python3 "$SKILL_DIR/scripts/validate_pet.py" /absolute/path/to/pet
   ```

4. Choose the target's public directory. Use `public` for conventional
   Next.js/Vite/React projects, `.` for a static site root, or the framework's
   configured equivalent. Run a dry import first when files may already exist:

   ```bash
   python3 "$SKILL_DIR/scripts/import_pet.py" \
     --pet /absolute/path/to/pet \
     --target /absolute/path/to/project \
     --public-dir public \
     --dry-run
   ```

5. Run the same command without `--dry-run`. Inspect every reported `replace`
   action before using `--force`; never overwrite a target file blindly. The
   importer copies and hash-verifies the manifest, spritesheet, and runtime.
6. Add the reported module and element tags, or import the module from application
   code. Read [integration-patterns.md](references/integration-patterns.md) for
   event mapping, priority, framework, accessibility, and base-path patterns.
7. Map product events to states in product code. Do not bake HoomeGate or another
   product's event names into the runtime.
8. Verify with the target project's normal checks and a real browser. Exercise
   initial load, every mapped state, one-shot return to idle, competing priorities,
   pointer look directions, offline/error handling when mapped, responsive sizing,
   reduced motion, and console/network errors.

## Contract

Read [codex-pet-v2-contract.md](references/codex-pet-v2-contract.md) when
validation fails, when integrating a nonstandard renderer, or when changing the
runtime. Accept v2 packages only; do not silently upgrade v1 assets or infer missing
rows.

The installed runtime exposes:

- `<codex-pet manifest="..." size="192" pointer-tracking>`
- `play(state, { once, then, priority, force })`
- `playDefault()`, `lookAt(x, y)`, `pause()`, `resume()`, and `destroy()`
- `bindPetEvents(pet, mappings, target)`
- `codex-pet-ready`, `codex-pet-state-change`, and `codex-pet-error` events

## Hard Rules

- Never point production markup at `~/.codex`, a hatch run directory, or another
  machine-local path. Vendor the validated package into the target project.
- Never modify the source pet package during an import.
- Keep `pet.json` beside the relative spritesheet path it declares.
- Reject unsafe paths, malformed WebP files, non-v2 manifests, and atlases other
  than `1536x2288`.
- Keep the Web Component runtime framework-neutral. Add a framework adapter only
  after a real consumer requires behavior the browser component cannot provide.
- Preserve reduced-motion behavior and accessible naming. Use `aria-hidden="true"`
  only when the pet is purely decorative.
- Do not publish an npm package until at least two independent projects need
  versioned package-manager distribution.
