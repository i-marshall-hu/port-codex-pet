# Frontend integration patterns

## Static markup

Use the URLs printed by `import_pet.py`:

```html
<script type="module" src="/codex-pet/codex-pet-player.js"></script>
<codex-pet
  id="home-pet"
  manifest="/pets/pocky/pet.json"
  size="192"
  pointer-tracking
></codex-pet>
```

For an application mounted below `/portal/`, import with
`--url-prefix /portal/` and use the reported URLs. Do not hand-concatenate base
paths after installation.

## Event mapping

Keep business events outside the player:

```js
import { bindPetEvents } from "/codex-pet/codex-pet-player.js";

const pet = document.querySelector("#home-pet");
const unbind = bindPetEvents(pet, {
  "app:ready": { state: "waving", once: true, then: "idle", priority: 10 },
  "task:running": { state: "running", priority: 30 },
  "task:success": { state: "jumping", once: true, then: "idle", priority: 40 },
  "task:failed": { state: "failed", priority: 100 },
  "approval:needed": { state: "waiting", priority: 50 },
});
```

Call `unbind()` when the owning view is destroyed. A mapping may also be a
function receiving the event and returning an action or `null`.

Use priorities consistently:

- `0`: idle and pointer look
- `10`: ambient greetings and hover reactions
- `30–50`: active work and user attention
- `100`: blocking error or offline state

Lower-priority actions cannot interrupt higher-priority playback. Release a
persistent state explicitly:

```js
pet.play("idle", { force: true, priority: 0 });
```

For a one-off command without a mapping:

```js
pet.dispatchEvent(
  new CustomEvent("codex-pet:play", {
    detail: { state: "waving", once: true, then: "idle", priority: 10 },
  }),
);
```

## React and other component frameworks

Load the module on the client, render the custom element, and keep a ref when
calling methods. React may require a local JSX intrinsic-element type declaration;
that is a type-system adapter, not a new runtime. Vue and Svelte can use the same
element directly.

Do not server-render code that calls `play()` or accesses browser events. The
module itself is safe to parse during SSR, while element registration occurs only
when `customElements` exists.

## Accessibility and motion

The player sets `role="img"` and uses `displayName` as its label unless the caller
provides `aria-label` or `aria-hidden`. Under `prefers-reduced-motion: reduce`, it
shows the first idle frame. Set `reduced-motion="state"` only when a static frame
from the requested state conveys essential status.

## Verification

In a browser, check:

1. `codex-pet-ready` fires and the sprite request returns 200.
2. Every mapped state uses the expected row and returns correctly after one shots.
3. A lower-priority event cannot override an error/waiting state.
4. Pointer motion reaches all four cardinal directions and yields to active work.
5. The component stays inside its layout at mobile size.
6. Reduced motion produces a stable frame with no timer-driven animation.
7. Console and network panels contain no pet errors.
