# Port Codex Pet

[![CI](https://github.com/i-marshall-hu/port-codex-pet/actions/workflows/ci.yml/badge.svg)](https://github.com/i-marshall-hu/port-codex-pet/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

Move an existing Codex Pet v2 package into a web frontend with a portable,
zero-dependency Web Component.

把 Codex 中已经制作好的 Pet 移植到普通前端项目，保留动画状态、16 向观察、
事件优先级和 reduced-motion 支持。宠物素材会复制进目标项目，生产页面不依赖
`~/.codex` 路径。

## What it includes

- A reusable Codex Skill for discovery, installation, integration, and browser QA.
- Deterministic validation for `pet.json` and the `1536x2288` v2 WebP atlas.
- Safe, idempotent asset copying with hash verification and overwrite protection.
- A framework-neutral `<codex-pet>` Web Component.
- Event mapping, one-shot animations, priority-based interruption, pointer look
  tracking, accessibility defaults, and reduced-motion behavior.

This project ports pets that already pass the Codex Pet v2 contract. It does not
generate or repair pet artwork; use `hatch-pet` for that stage.

## Install the Skill

### Codex Skill Installer

```bash
INSTALLER="${CODEX_HOME:-$HOME/.codex}/skills/.system/skill-installer/scripts/install-skill-from-github.py"
python3 "$INSTALLER" \
  --repo i-marshall-hu/port-codex-pet \
  --path skills/port-codex-pet
```

The Skill becomes available on the next Codex turn.

### Manual clone

```bash
git clone https://github.com/i-marshall-hu/port-codex-pet.git
ln -s "$PWD/port-codex-pet/skills/port-codex-pet" \
  "${CODEX_HOME:-$HOME/.codex}/skills/port-codex-pet"
```

## Use the Skill

Invoke it explicitly:

```text
Use $port-codex-pet to install Pocky into this frontend project.
```

```text
使用 $port-codex-pet，把 ~/.codex/pets/pocky 接入当前 React 项目，
并把 task:running、task:success 和 task:failed 映射成宠物动作。
```

The Skill will inspect the target framework and public asset directory, validate
the source pet, run a dry import when conflicts are possible, install the runtime,
wire product events, and verify the result in a browser.

## Use the CLI directly

After installation:

```bash
SKILL_DIR="${CODEX_HOME:-$HOME/.codex}/skills/port-codex-pet"

python3 "$SKILL_DIR/scripts/validate_pet.py" \
  "${CODEX_HOME:-$HOME/.codex}/pets/pocky"

python3 "$SKILL_DIR/scripts/import_pet.py" \
  --pet "${CODEX_HOME:-$HOME/.codex}/pets/pocky" \
  --target /absolute/path/to/frontend \
  --public-dir public \
  --dry-run
```

Inspect the JSON actions. Remove `--dry-run` to copy the files. If an action is
`replace`, inspect the destination before explicitly adding `--force`.

The default output is:

```text
public/
├── codex-pet/codex-pet-player.js
└── pets/<pet-id>/
    ├── pet.json
    └── spritesheet.webp
```

## Frontend integration

```html
<script type="module" src="/codex-pet/codex-pet-player.js"></script>

<codex-pet
  id="home-pet"
  manifest="/pets/pocky/pet.json"
  size="192"
  pointer-tracking
></codex-pet>
```

Map application events without coupling them to the runtime:

```js
import { bindPetEvents } from "/codex-pet/codex-pet-player.js";

const pet = document.querySelector("#home-pet");
const unbind = bindPetEvents(pet, {
  "app:ready": { state: "waving", once: true, then: "idle", priority: 10 },
  "task:running": { state: "running", priority: 30 },
  "task:success": { state: "jumping", once: true, then: "idle", priority: 40 },
  "approval:needed": { state: "waiting", priority: 50 },
  "task:failed": { state: "failed", priority: 100 },
});
```

Call `unbind()` when the owning view is destroyed. Direct methods include
`play()`, `playDefault()`, `lookAt()`, `pause()`, `resume()`, and `destroy()`.

Supported animation states:

```text
idle, running-right, running-left, waving, jumping,
failed, waiting, running, review, look
```

See the bundled [integration patterns](skills/port-codex-pet/references/integration-patterns.md)
and [v2 contract](skills/port-codex-pet/references/codex-pet-v2-contract.md) for details.

## Development

```bash
python3 -m unittest discover -s skills/port-codex-pet/tests -v
uvx ruff check skills/port-codex-pet/scripts skills/port-codex-pet/tests
uvx ruff format --check skills/port-codex-pet/scripts skills/port-codex-pet/tests
node --check skills/port-codex-pet/assets/runtime/codex-pet-player.js
```

The Python importer is standard-library-only. The browser runtime has no npm
dependencies.

## License

[MIT](LICENSE)
