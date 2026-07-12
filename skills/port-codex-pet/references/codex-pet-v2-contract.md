# Codex Pet v2 portable contract

## Package

A portable package contains exactly the identity manifest and its referenced WebP
atlas. QA artifacts from `hatch-pet` remain evidence; they are not browser runtime
dependencies.

```text
<pet-id>/
├── pet.json
└── spritesheet.webp
```

Minimum manifest:

```json
{
  "id": "pocky",
  "displayName": "Pocky",
  "description": "Stable identity description.",
  "spriteVersionNumber": 2,
  "spritesheetPath": "spritesheet.webp"
}
```

Require a lowercase `id` using letters, digits, and hyphens. Require
`spritesheetPath` to be a relative `.webp` path that resolves inside the package.

## Atlas geometry

- Canvas: `1536x2288`
- Grid: 8 columns × 11 rows
- Cell: `192x208`
- Direction order: clockwise in `22.5°` steps

| Row | State | Used columns | Default behavior |
|---:|---|---|---|
| 0 | `idle` | 0–5 | loop |
| 1 | `running-right` | 0–7 | loop |
| 2 | `running-left` | 0–7 | loop |
| 3 | `waving` | 0–3 | one shot |
| 4 | `jumping` | 0–4 | one shot |
| 5 | `failed` | 0–7 | loop |
| 6 | `waiting` | 0–5 | loop |
| 7 | `running` | 0–5 | loop |
| 8 | `review` | 0–5 | loop |
| 9 | look `000`–`157.5` | 0–7 | pointer frame |
| 10 | look `180`–`337.5` | 0–7 | pointer frame |

`000` means up, `090` screen-right, `180` down, and `270` screen-left.
Neutral pointer deadzone falls back to the configured default state.

## Ownership boundary

- `hatch-pet` owns imagery, atlas construction, visual QA, chroma cleanup, and v2
  packaging.
- `port-codex-pet` owns package validation, safe copying, browser playback, product
  event mapping, and frontend verification.
- The target application owns layout, business event names, and state priority.

Do not repair imagery or generate missing cells during import. Return invalid
packages to `hatch-pet` so the original QA contract remains intact.
