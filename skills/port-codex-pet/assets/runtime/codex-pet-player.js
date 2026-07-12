const CELL_WIDTH = 192;
const CELL_HEIGHT = 208;
const LOOK_STEP = 22.5;
const DEFAULT_LOOK_RADIUS = 440;
const MIN_SIZE = 48;
const MAX_SIZE = 384;

const state = (row, frames, durations, loop = true) =>
  Object.freeze({
    row,
    frames: Object.freeze(frames),
    durations: Object.freeze(durations),
    loop,
  });

export const CODEX_PET_PLAYER_VERSION = "0.1.0";

export const CODEX_PET_STATES = Object.freeze({
  idle: state(0, [0, 1, 2, 3, 4, 5], [280, 110, 110, 140, 140, 320]),
  "running-right": state(
    1,
    [0, 1, 2, 3, 4, 5, 6, 7],
    [120, 120, 120, 120, 120, 120, 120, 220],
  ),
  "running-left": state(
    2,
    [0, 1, 2, 3, 4, 5, 6, 7],
    [120, 120, 120, 120, 120, 120, 120, 220],
  ),
  waving: state(3, [0, 1, 2, 3], [140, 140, 140, 280], false),
  jumping: state(4, [0, 1, 2, 3, 4], [140, 140, 140, 140, 280], false),
  failed: state(
    5,
    [0, 1, 2, 3, 4, 5, 6, 7],
    [140, 140, 140, 140, 140, 140, 140, 240],
  ),
  waiting: state(6, [0, 1, 2, 3, 4, 5], [150, 150, 150, 150, 150, 260]),
  running: state(7, [0, 1, 2, 3, 4, 5], [120, 120, 120, 120, 120, 220]),
  review: state(8, [0, 1, 2, 3, 4, 5], [150, 150, 150, 150, 150, 280]),
});

const template = `
  <style>
    :host {
      display: inline-block;
      width: var(--codex-pet-width, 192px);
      height: var(--codex-pet-height, 208px);
      contain: content;
      line-height: 0;
    }

    .stage {
      position: relative;
      width: 100%;
      height: 100%;
      overflow: hidden;
    }

    .sprite {
      width: 192px;
      height: 208px;
      visibility: hidden;
      background-position: 0 0;
      background-repeat: no-repeat;
      background-size: 1536px 2288px;
      transform: scale(var(--codex-pet-scale, 1));
      transform-origin: top left;
      will-change: background-position;
    }

    :host([ready]) .sprite {
      visibility: visible;
    }

    @media (prefers-reduced-motion: reduce) {
      .sprite {
        will-change: auto;
      }
    }
  </style>
  <div class="stage" part="stage">
    <div class="sprite" part="sprite"></div>
  </div>
`;

const HTMLElementBase = globalThis.HTMLElement ?? class {};

function frozenRuntime(changes = {}) {
  return Object.freeze({
    frameIndex: 0,
    lookIndex: null,
    paused: false,
    priority: 0,
    state: "idle",
    timerId: null,
    token: 0,
    ...changes,
  });
}

function numberOption(value, fallback) {
  if (value === null || value === "") return fallback;
  const parsed = Number(value);
  return Number.isFinite(parsed) ? parsed : fallback;
}

function validateManifest(manifest) {
  if (!manifest || typeof manifest !== "object" || Array.isArray(manifest)) {
    throw new TypeError("pet.json must contain a JSON object");
  }
  if (manifest.spriteVersionNumber !== 2) {
    throw new TypeError("pet.json spriteVersionNumber must be exactly 2");
  }
  if (typeof manifest.spritesheetPath !== "string" || !manifest.spritesheetPath) {
    throw new TypeError("pet.json spritesheetPath must be a non-empty string");
  }
  if (typeof manifest.displayName !== "string" || !manifest.displayName) {
    throw new TypeError("pet.json displayName must be a non-empty string");
  }
  return Object.freeze({ ...manifest });
}

function preloadImage(url, signal) {
  return new Promise((resolve, reject) => {
    const image = new Image();
    const abort = () => reject(new DOMException("Pet loading aborted", "AbortError"));
    image.addEventListener("load", () => resolve(url), { once: true });
    image.addEventListener(
      "error",
      () => reject(new Error(`Could not load pet spritesheet: ${url}`)),
      { once: true },
    );
    signal.addEventListener("abort", abort, { once: true });
    image.src = url;
  });
}

export class CodexPetPlayer extends HTMLElementBase {
  static get observedAttributes() {
    return ["default-state", "look-radius", "manifest", "pointer-tracking", "size", "state"];
  }

  constructor() {
    super();
    const shadow = this.attachShadow({ mode: "open" });
    shadow.innerHTML = template;
    this._sprite = shadow.querySelector(".sprite");
    this._runtime = frozenRuntime();
    this._ready = false;
    this._connected = false;
    this._loadController = null;
    this._manifest = null;
    this._pendingAction = null;
    this._motionQuery = null;
    this._onMotionChange = () => this.playDefault({ force: true });
    this._onPointerMove = (event) => this.lookAt(event.clientX, event.clientY);
    this._onPlayEvent = (event) => {
      const detail = event.detail ?? {};
      this.play(detail.state, detail);
    };
  }

  connectedCallback() {
    if (this._connected) return;
    this._connected = true;
    if (!this.hasAttribute("role") && !this.hasAttribute("aria-hidden")) {
      this.setAttribute("role", "img");
    }
    this._motionQuery = globalThis.matchMedia("(prefers-reduced-motion: reduce)");
    this._motionQuery.addEventListener("change", this._onMotionChange);
    this.addEventListener("codex-pet:play", this._onPlayEvent);
    this._syncSize();
    this._syncPointerTracking();
    this._loadManifest();
  }

  disconnectedCallback() {
    this._connected = false;
    this._cancelPlayback();
    this._loadController?.abort();
    this._motionQuery?.removeEventListener("change", this._onMotionChange);
    this.removeEventListener("codex-pet:play", this._onPlayEvent);
    globalThis.document?.removeEventListener("pointermove", this._onPointerMove);
  }

  attributeChangedCallback(name, oldValue, newValue) {
    if (!this._connected || oldValue === newValue) return;
    if (name === "manifest") this._loadManifest();
    if (name === "size") this._syncSize();
    if (name === "pointer-tracking") this._syncPointerTracking();
    if (name === "state" && newValue) this.play(newValue, { force: true });
  }

  get ready() {
    return this._ready;
  }

  get currentState() {
    return this._runtime.state;
  }

  get manifestData() {
    return this._manifest;
  }

  async _loadManifest() {
    const manifestAttribute = this.getAttribute("manifest");
    if (!manifestAttribute) {
      this._emitError(new Error("codex-pet requires a manifest attribute"));
      return;
    }

    this._ready = false;
    this.removeAttribute("ready");
    this._loadController?.abort();
    const controller = new AbortController();
    this._loadController = controller;

    try {
      const manifestUrl = new URL(manifestAttribute, globalThis.document.baseURI);
      const response = await fetch(manifestUrl, { signal: controller.signal });
      if (!response.ok) {
        throw new Error(`Could not load pet manifest: HTTP ${response.status}`);
      }
      const manifest = validateManifest(await response.json());
      const spritesheetUrl = new URL(manifest.spritesheetPath, manifestUrl).href;
      await preloadImage(spritesheetUrl, controller.signal);
      if (controller.signal.aborted) return;

      this._manifest = manifest;
      this._sprite.style.backgroundImage = `url("${spritesheetUrl}")`;
      if (!this.hasAttribute("aria-label") && !this.hasAttribute("aria-hidden")) {
        this.setAttribute("aria-label", manifest.displayName);
      }
      this._ready = true;
      this.setAttribute("ready", "");
      const pending = this._pendingAction;
      this._pendingAction = null;
      if (pending) {
        this.play(pending.state, pending.options);
      } else {
        this.play(this.getAttribute("state") || this.defaultState, { force: true });
      }
      this.dispatchEvent(
        new CustomEvent("codex-pet-ready", {
          bubbles: true,
          detail: Object.freeze({ manifest, manifestUrl: manifestUrl.href }),
        }),
      );
    } catch (error) {
      if (error?.name !== "AbortError") this._emitError(error);
    }
  }

  get defaultState() {
    const candidate = this.getAttribute("default-state") || "idle";
    return Object.hasOwn(CODEX_PET_STATES, candidate) ? candidate : "idle";
  }

  _replaceRuntime(changes) {
    this._runtime = frozenRuntime({ ...this._runtime, ...changes });
  }

  _cancelPlayback() {
    if (this._runtime.timerId !== null) {
      globalThis.clearTimeout(this._runtime.timerId);
    }
    const token = this._runtime.token + 1;
    this._replaceRuntime({ timerId: null, token });
    return token;
  }

  _renderFrame(name, row, column, lookIndex = null) {
    const previousState = this._runtime.state;
    const previousLookIndex = this._runtime.lookIndex;
    this._sprite.style.backgroundPosition = `${column * -CELL_WIDTH}px ${row * -CELL_HEIGHT}px`;
    this.dataset.petState = name;
    if (lookIndex === null) delete this.dataset.petLook;
    else this.dataset.petLook = String(lookIndex);
    this._replaceRuntime({ lookIndex, state: name });

    if (previousState !== name || previousLookIndex !== lookIndex) {
      this.dispatchEvent(
        new CustomEvent("codex-pet-state-change", {
          bubbles: true,
          detail: Object.freeze({ lookIndex, state: name }),
        }),
      );
    }
  }

  _emitError(error) {
    const normalized = error instanceof Error ? error : new Error(String(error));
    this.dispatchEvent(
      new CustomEvent("codex-pet-error", {
        bubbles: true,
        detail: Object.freeze({ error: normalized, message: normalized.message }),
      }),
    );
  }

  _prefersReducedMotion() {
    return Boolean(this._motionQuery?.matches);
  }

  play(name, options = {}) {
    const definition = CODEX_PET_STATES[name];
    if (!definition) {
      this._emitError(new RangeError(`Unknown Codex Pet state: ${name}`));
      return false;
    }
    const normalizedOptions = Object.freeze({ ...options });
    if (!this._ready || this._runtime.paused) {
      this._pendingAction = Object.freeze({ state: name, options: normalizedOptions });
      return true;
    }

    const priority = numberOption(normalizedOptions.priority, 0);
    if (!normalizedOptions.force && priority < this._runtime.priority) return false;
    const once = normalizedOptions.once ?? !definition.loop;
    const nextState = normalizedOptions.then ?? (once ? this.defaultState : null);

    if (this._prefersReducedMotion()) {
      this._cancelPlayback();
      const reducedState = this.getAttribute("reduced-motion") === "state" ? name : "idle";
      const reducedDefinition = CODEX_PET_STATES[reducedState];
      this._renderFrame(reducedState, reducedDefinition.row, reducedDefinition.frames[0]);
      this._replaceRuntime({ frameIndex: 0, priority: 0 });
      return true;
    }

    const token = this._cancelPlayback();
    this._replaceRuntime({ priority });
    const advance = (frameIndex) => {
      if (this._runtime.token !== token || this._runtime.paused) return;
      const column = definition.frames[frameIndex];
      this._renderFrame(name, definition.row, column);
      this._replaceRuntime({ frameIndex, priority });
      const isLastFrame = frameIndex === definition.frames.length - 1;
      const timerId = globalThis.setTimeout(() => {
        if (this._runtime.token !== token) return;
        if (!isLastFrame) {
          advance(frameIndex + 1);
          return;
        }
        if (definition.loop && !once) {
          advance(0);
          return;
        }
        if (nextState) {
          this.play(nextState, { force: true, priority: 0 });
          return;
        }
        this._replaceRuntime({ priority: 0, timerId: null });
      }, definition.durations[frameIndex]);
      this._replaceRuntime({ timerId });
    };
    advance(0);
    return true;
  }

  playDefault(options = {}) {
    return this.play(this.defaultState, { ...options, priority: 0 });
  }

  pause() {
    if (this._runtime.paused) return;
    const resumeState = this._runtime.state === "look" ? this.defaultState : this._runtime.state;
    this._cancelPlayback();
    this._pendingAction = Object.freeze({
      state: resumeState,
      options: Object.freeze({ force: true }),
    });
    this._replaceRuntime({ paused: true });
  }

  resume() {
    if (!this._runtime.paused) return;
    const pending = this._pendingAction;
    this._pendingAction = null;
    this._replaceRuntime({ paused: false });
    this.play(pending?.state ?? this.defaultState, pending?.options ?? { force: true });
  }

  lookAt(clientX, clientY) {
    if (
      !this._ready ||
      this._runtime.paused ||
      this._runtime.priority > 0 ||
      this._prefersReducedMotion()
    ) {
      return false;
    }
    const bounds = this.getBoundingClientRect();
    const deltaX = clientX - (bounds.left + bounds.width / 2);
    const deltaY = clientY - (bounds.top + bounds.height / 2);
    const radius = Math.max(
      1,
      numberOption(this.getAttribute("look-radius"), DEFAULT_LOOK_RADIUS),
    );
    if (Math.hypot(deltaX, deltaY) > radius) {
      if (this._runtime.state === "look") this.playDefault({ force: true });
      return false;
    }

    const degrees = (Math.atan2(deltaX, -deltaY) * 180) / Math.PI;
    const normalizedDegrees = (degrees + 360) % 360;
    const lookIndex = Math.round(normalizedDegrees / LOOK_STEP) % 16;
    if (this._runtime.state === "look" && this._runtime.lookIndex === lookIndex) {
      return true;
    }
    this._cancelPlayback();
    const row = lookIndex < 8 ? 9 : 10;
    const column = lookIndex < 8 ? lookIndex : lookIndex - 8;
    this._renderFrame("look", row, column, lookIndex);
    this._replaceRuntime({ frameIndex: 0, priority: 0 });
    return true;
  }

  _syncPointerTracking() {
    globalThis.document?.removeEventListener("pointermove", this._onPointerMove);
    const enabled =
      this.hasAttribute("pointer-tracking") &&
      this.getAttribute("pointer-tracking") !== "false";
    if (enabled) {
      globalThis.document?.addEventListener("pointermove", this._onPointerMove, {
        passive: true,
      });
    }
  }

  _syncSize() {
    const requested = numberOption(this.getAttribute("size"), CELL_WIDTH);
    const size = Math.min(MAX_SIZE, Math.max(MIN_SIZE, requested));
    const scale = size / CELL_WIDTH;
    this.style.setProperty("--codex-pet-width", `${size}px`);
    this.style.setProperty("--codex-pet-height", `${CELL_HEIGHT * scale}px`);
    this.style.setProperty("--codex-pet-scale", String(scale));
  }

  destroy() {
    this.remove();
  }
}

export function bindPetEvents(pet, mappings, target = globalThis.document) {
  if (!pet || typeof pet.play !== "function") {
    throw new TypeError("bindPetEvents requires a CodexPetPlayer-compatible element");
  }
  if (!mappings || typeof mappings !== "object" || Array.isArray(mappings)) {
    throw new TypeError("bindPetEvents mappings must be an object");
  }
  if (!target || typeof target.addEventListener !== "function") {
    throw new TypeError("bindPetEvents target must be an EventTarget");
  }

  const bindings = Object.entries(mappings).map(([eventName, mapping]) => {
    const handler = (event) => {
      const selected = typeof mapping === "function" ? mapping(event) : mapping;
      if (!selected) return;
      const action = typeof selected === "string" ? { state: selected } : selected;
      if (!action.state) return;
      pet.play(action.state, action);
    };
    target.addEventListener(eventName, handler);
    return Object.freeze({ eventName, handler });
  });

  return () => {
    bindings.forEach(({ eventName, handler }) => {
      target.removeEventListener(eventName, handler);
    });
  };
}

if (globalThis.customElements && !globalThis.customElements.get("codex-pet")) {
  globalThis.customElements.define("codex-pet", CodexPetPlayer);
}
