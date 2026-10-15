/* A non-modal guide: pinning preserves it while the examiner explores views. */
(() => {
  "use strict";
  const panel = document.querySelector("#purpose-window");
  const titlebar = document.querySelector("#purpose-titlebar");
  const pinButton = document.querySelector("#purpose-pin");
  const maximiseButton = document.querySelector("#purpose-maximise");
  const opacity = document.querySelector("#purpose-opacity");
  let pinned = false,
    maximised = false,
    geometry,
    restoredGeometry,
    gesture;
  const clamp = (value, min, max) => Math.min(max, Math.max(min, value));
  const bounds = () => ({
    left: 12,
    top: 12,
    width: Math.max(1, innerWidth - 24),
    height: Math.max(1, innerHeight - 24 - (innerWidth <= 600 ? 70 : 0)),
  });

  function fit(rect) {
    const b = bounds();
    const width = clamp(rect.width, Math.min(360, b.width), b.width);
    const height = clamp(rect.height, Math.min(300, b.height), b.height);
    return {
      width,
      height,
      left: clamp(rect.left, b.left, b.left + b.width - width),
      top: clamp(rect.top, b.top, b.top + b.height - height),
    };
  }

  function place(rect) {
    geometry = fit(rect);
    for (const [key, value] of Object.entries(geometry))
      panel.style[key] = `${value}px`;
  }

  function syncOpener() {
    document
      .querySelector("#purpose-open")
      ?.setAttribute("aria-expanded", String(!panel.hidden));
  }

  function show() {
    const b = bounds();
    if (!geometry) {
      const width = Math.min(680, b.width),
        height = Math.min(700, b.height);
      geometry = {
        width,
        height,
        left: (innerWidth - width) / 2,
        top: b.top + Math.min(65, (b.height - height) / 2),
      };
    }
    panel.hidden = false;
    place(maximised ? b : geometry);
    syncOpener();
    document.querySelector("#purpose-close").focus({ preventScroll: true });
  }

  function hide(restoreFocus = true) {
    panel.hidden = true;
    gesture = null;
    syncOpener();
    if (restoreFocus)
      (
        document.querySelector("#purpose-open") ||
        document.querySelector("#main")
      )?.focus({ preventScroll: true });
  }

  function maximise() {
    if (!maximised) restoredGeometry = { ...geometry };
    maximised = !maximised;
    place(maximised ? bounds() : restoredGeometry);
    panel.classList.toggle("maximised", maximised);
    const label = maximised ? "Restore window" : "Maximise window";
    maximiseButton.setAttribute("aria-label", label);
    maximiseButton.title = label;
    maximiseButton.setAttribute("aria-pressed", String(maximised));
    maximiseButton.innerHTML = `<i data-lucide="${maximised ? "minimize-2" : "maximize-2"}"></i>`;
    window.lucide?.createIcons();
  }

  document.addEventListener("click", (event) => {
    if (event.target.closest("#purpose-open")) show();
    const route = event.target.closest(".purpose-route a");
    if (route && !pinned) hide(false);
  });
  document.addEventListener("pointerdown", (event) => {
    if (
      !panel.hidden &&
      !pinned &&
      !panel.contains(event.target) &&
      !event.target.closest("#purpose-open")
    )
      hide(false);
  });
  document.addEventListener("keydown", (event) => {
    if (
      event.key === "Escape" &&
      !panel.hidden &&
      !document.querySelector("#issue-dialog").open
    ) {
      event.preventDefault();
      hide();
    }
  });
  window.addEventListener("hashchange", () => {
    if (!pinned && !panel.hidden) hide(false);
    syncOpener();
  });
  // Filters rerender the heading without replacing the floating guide.
  new MutationObserver(syncOpener).observe(document.querySelector("#main"), {
    childList: true,
  });
  window.addEventListener("resize", () => {
    if (!panel.hidden) place(maximised ? bounds() : geometry);
  });
  document.querySelector("#purpose-close").onclick = () => hide();
  pinButton.onclick = () => {
    pinned = !pinned;
    pinButton.setAttribute("aria-pressed", String(pinned));
    pinButton.title = pinned
      ? "Unpin: close when navigating away"
      : "Pin: keep open while navigating";
    document.querySelector("#purpose-pin-state").textContent = pinned
      ? "Pinned"
      : "Unpinned";
  };
  maximiseButton.onclick = maximise;
  opacity.oninput = () => {
    panel.style.opacity = Number(opacity.value) / 100;
    document.querySelector("#purpose-opacity-value").textContent =
      `${opacity.value}%`;
  };
  titlebar.addEventListener("dblclick", (event) => {
    if (!event.target.closest("button")) maximise();
  });
  titlebar.addEventListener("keydown", (event) => {
    if (event.target !== titlebar) return;
    if (event.key === "Enter") {
      event.preventDefault();
      maximise();
      return;
    }
    if (
      maximised ||
      !["ArrowLeft", "ArrowRight", "ArrowUp", "ArrowDown"].includes(event.key)
    )
      return;
    event.preventDefault();
    const dx =
      event.key === "ArrowLeft" ? -16 : event.key === "ArrowRight" ? 16 : 0;
    const dy =
      event.key === "ArrowUp" ? -16 : event.key === "ArrowDown" ? 16 : 0;
    place(
      event.shiftKey
        ? {
            ...geometry,
            width: geometry.width + dx,
            height: geometry.height + dy,
          }
        : { ...geometry, left: geometry.left + dx, top: geometry.top + dy },
    );
  });

  panel.addEventListener("pointerdown", (event) => {
    const handle = event.target.closest("[data-resize]");
    const drag =
      event.target.closest("#purpose-titlebar") &&
      !event.target.closest("button");
    if (
      maximised ||
      (!handle && !drag) ||
      event.button !== 0 ||
      !event.isPrimary
    )
      return;
    event.preventDefault();
    gesture = {
      pointer: event.pointerId,
      x: event.clientX,
      y: event.clientY,
      start: { ...geometry },
      edge: handle?.dataset.resize || "move",
      capture: handle || titlebar,
    };
    gesture.capture.setPointerCapture(event.pointerId);
  });
  panel.addEventListener("pointermove", (event) => {
    if (!gesture || gesture.pointer !== event.pointerId) return;
    const { start, edge } = gesture;
    const dx = event.clientX - gesture.x,
      dy = event.clientY - gesture.y;
    if (edge === "move") {
      place({ ...start, left: start.left + dx, top: start.top + dy });
      return;
    }
    const b = bounds(),
      minWidth = Math.min(360, b.width),
      minHeight = Math.min(300, b.height);
    let left = start.left,
      top = start.top,
      right = left + start.width,
      bottom = top + start.height;
    if (edge.includes("e"))
      right = clamp(right + dx, left + minWidth, b.left + b.width);
    if (edge.includes("w")) left = clamp(left + dx, b.left, right - minWidth);
    if (edge.includes("s"))
      bottom = clamp(bottom + dy, top + minHeight, b.top + b.height);
    if (edge.includes("n")) top = clamp(top + dy, b.top, bottom - minHeight);
    place({ left, top, width: right - left, height: bottom - top });
  });
  const release = (event) => {
    if (gesture?.pointer !== event.pointerId) return;
    const capture = gesture.capture;
    gesture = null;
    if (capture.hasPointerCapture(event.pointerId))
      capture.releasePointerCapture(event.pointerId);
  };
  panel.addEventListener("pointerup", release);
  panel.addEventListener("pointercancel", release);
  panel.addEventListener("lostpointercapture", () => {
    gesture = null;
  });
})();
