---
tracking_type: code-dev
doc_kind: status
schema_version: 2.4.0
rules_version: 2.4.0
design_version: 2.4.0
layout: single
project_state: active
updated_at: 2026-07-12T17:02:22+08:00
resume:
  updated_from_head: e886a8d6e82b15d45251b24a6f537aaff2637561
  confidence: fresh
  next_actions: []
  do_not_do:
    - "Commit private pet assets, generated spritesheets, secrets, or personal filesystem paths"
    - "Expand the importer into pet image generation; that remains hatch-pet's responsibility"
  blocked_on: []
sync:
  last_synced_at: 2026-07-12T17:02:22+08:00
  verified_at: 2026-07-12T17:02:22+08:00
  verification_subjects:
    - { kind: git, path: ".", ref: main, head: e886a8d6e82b15d45251b24a6f537aaff2637561, dirty: false }
  verification_evidence:
    - { kind: command, command: "python3 -m unittest discover -s skills/port-codex-pet/tests -v", result: pass, verified_at: 2026-07-12T17:02:22+08:00 }
    - { kind: command, command: "uvx coverage report --fail-under=80 (92%)", result: pass, verified_at: 2026-07-12T17:02:22+08:00 }
    - { kind: command, command: "ruff check + format --check; node --check; skill quick_validate", result: pass, verified_at: 2026-07-12T17:02:22+08:00 }
promotion_thresholds: { status_lines: 250, features: 12, adrs: 8 }
pending_promotions: []
---

# Project Status

<!-- progress:resume:start -->
## Resume Card

- Current focus: Initial open-source release of `port-codex-pet`.
- Next: Accept field feedback and keep the public distribution synchronized with
  the validated Skill source.
- Acceptance: Public repository installs through the Codex Skill Installer and CI
  stays green.
- Do not do: Add private pet assets or merge pet generation into this repository.
<!-- progress:resume:end -->

<!-- progress:scope-guard:start -->
## Scope Guard

### In Scope

- Validate and import packaged Codex Pet v2 assets.
- Provide a framework-neutral browser runtime and integration guidance.
- Maintain tests, CI, and public installation documentation.

### Out Of Scope

- Generate, repair, or visually approve pet artwork.
- Store user pets or generated spritesheets.
- Provide framework-specific wrappers without a demonstrated consumer need.

### Deferred

- npm distribution; revisit after at least two independent consumers need it.

### Traps

- A public GitHub repository is a distribution surface; scan every change for
  credentials, private paths, and copyrighted pet assets before release.
<!-- progress:scope-guard:end -->

<!-- progress:features:start -->
## Features

```yaml
features:
  - id: F001
    title: "Initial public port-codex-pet release"
    phase: P001
    progress_state: done
    done_state: shipped
    evidence_refs:
      - { kind: commit, ref: e886a8d }
      - { kind: command, ref: "15 tests passed; 92% branch coverage; browser QA passed" }
    blocked_on: []
    depends_on: []
    supersedes: []
    superseded_by: []
```
<!-- progress:features:end -->

<!-- progress:phases:start -->
## Phases

```yaml
phases:
  - id: P001
    title: "Open-source MVP"
    phase_state: active
    acceptance: "Public repository exists, installation is documented, and CI passes"
```
<!-- progress:phases:end -->

<!-- progress:adrs:start -->
## ADRs

```yaml
adrs:
  - id: D001
    date: 2026-07-12
    type: scope-change
    status: accepted
    retroactive: false
    affects: [F001]
    decision: "Publish as a Skill repository with the installable Skill under skills/port-codex-pet, using MIT and a zero-dependency Web Component runtime."
```
<!-- progress:adrs:end -->

<!-- progress:scope-inbox:start -->
## Scope Delta Inbox

```yaml
scope_deltas: []
```
<!-- progress:scope-inbox:end -->

<!-- progress:changelog:start -->
## Changelog

### [Unreleased]

#### Added

- Initial public Skill, runtime, deterministic importer, validation scripts,
  documentation, MIT license, and CI workflow.
<!-- progress:changelog:end -->
