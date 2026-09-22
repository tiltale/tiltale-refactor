// TilTale studio behavior. Each setup function returns early when its page is not open.
"use strict";

const PLAYTEST_STALL_MS = 60000; // without a next frame for this long, the robot is considered stuck
const LOG_SETTLE_MS = 1000; // the last log requests of a play-test may still be in flight
const DRAG_THRESHOLD_PX = 4;
const TOAST_MS = 6000;
const FOCUS_ZOOM = 1; // clicking a frame zooms in to at least this, so its neighbours stay visible
const FOCUS_MS = 350; // same duration as .flow-world.is-animating in app.css
const STAGE_MARGIN_PX = 32;
const SNAP_PX = 6; // an edge this close (on screen) to another element's edge sticks to it
const MIN_BOX_PX = 20; // same minimum width and height as BOX_FIELDS in views.py
const SIDES = { n: "top", s: "bottom", w: "left", e: "right" }; // the corner handles: "nw" sits at the top-left

// Background saves (dragging elements or frames) report failures in the status bar, which stays visible.
function reportError(message) {
  const bar = document.querySelector("[data-status-bar]");
  bar.dataset.state = "error";
  bar.querySelector("[data-status-label]").textContent = message;
  bar.querySelector("[data-status-detail]").textContent = "Reload the page to see what was saved.";
}

async function postJson(url, csrfToken, body) {
  const response = await fetch(url, {
    method: "POST",
    headers: { "Content-Type": "application/json", "X-CSRFToken": csrfToken },
    body: JSON.stringify(body),
  });
  if (!response.ok) throw new Error((await response.json()).error || `HTTP ${response.status}`);
}

/* A message at the top right, like the ones the server sends after a page load. Errors stay until closed. */
function showToast(message, kind = "error") {
  const toast = document.createElement("div");
  toast.className = `toast ${kind}`;
  toast.setAttribute("role", "status");
  toast.textContent = message;
  const close = Object.assign(document.createElement("button"), { type: "button", className: "toast-close", textContent: "×" });
  close.setAttribute("aria-label", "Dismiss");
  close.addEventListener("click", () => toast.remove());
  toast.append(close);
  document.querySelector(".toasts").append(toast);
  if (kind !== "error") setTimeout(() => toast.remove(), TOAST_MS);
}

function setupToasts() {
  for (const toast of document.querySelectorAll("[data-toast]")) {
    toast.querySelector("[data-dismiss]").addEventListener("click", () => toast.remove());
    if (!toast.classList.contains("error")) setTimeout(() => toast.remove(), TOAST_MS);
  }
}

function setupForms() {
  let unsaved = false;
  document.addEventListener("change", (event) => {
    if (event.target.matches("[data-autosubmit]")) event.target.form.submit();
  });
  document.addEventListener("input", (event) => {
    if (event.target.closest("[data-unsaved-guard]")) unsaved = true;
  });
  document.addEventListener("submit", (event) => {
    const question = event.target.dataset.confirm;
    if (question && !confirm(question)) {
      event.preventDefault();
      return;
    }
    unsaved = false;
    const button = event.submitter;
    if (button?.dataset.busy) { // e.g. Regenerate: show that something is happening (the terminal shows details)
      button.textContent = button.dataset.busy;
      button.disabled = true;
    }
  });
  window.addEventListener("beforeunload", (event) => {
    if (unsaved) event.preventDefault();
  });
}

function setupDialogs() {
  document.addEventListener("click", (event) => {
    const opener = event.target.closest("[data-open-dialog]");
    if (opener) document.getElementById(opener.dataset.openDialog).showModal();
    if (event.target.closest("[data-close]")) event.target.closest("dialog").close();
  });
}

// Settings: a Basic and an Advanced tab. The URL's ?tab= opens the right one after a save.
function setupTabs() {
  const page = document.querySelector("[data-tabs]");
  if (!page) return;
  const show = (name) => {
    for (const panel of page.querySelectorAll("[data-panel]")) panel.hidden = panel.dataset.panel !== name;
    for (const button of page.querySelectorAll("[data-tab-button]")) button.setAttribute("aria-selected", button.dataset.tabButton === name);
  };
  for (const button of page.querySelectorAll("[data-tab-button]")) button.addEventListener("click", () => show(button.dataset.tabButton));
  show(page.dataset.tab || "basic");
}

// "+ Add" and other <details data-menu>: close when clicking elsewhere or pressing Escape.
function setupMenus() {
  const menus = document.querySelectorAll("details[data-menu]");
  if (!menus.length) return;
  const closeAll = (except) => { for (const menu of menus) if (menu !== except) menu.open = false; };
  document.addEventListener("click", (event) => closeAll(event.target.closest("details[data-menu]")));
  document.addEventListener("keydown", (event) => { if (event.key === "Escape") closeAll(); });
}

/* Grid thumbnails (Materials page, image picker): shimmer while loading, then un-blur to sharp. */
function setupBlurIn() {
  const ready = (image) => image.classList.add("is-loaded");
  for (const image of document.querySelectorAll("img.blur-in")) if (image.complete && image.naturalWidth) ready(image);
  // "load" does not bubble; the capture phase sees it for images that arrive later (lazy ones too).
  document.addEventListener("load", (event) => {
    if (event.target instanceof HTMLImageElement && event.target.classList.contains("blur-in")) ready(event.target);
  }, true);
}

/* The Materials page: the first tile uploads — by click (file dialog) or by dropping files anywhere. */
function setupMaterials() {
  const page = document.querySelector("[data-materials-page]");
  if (!page) return;
  const form = page.querySelector("[data-upload-form]");
  const input = form.querySelector("[data-upload-input]");
  input.addEventListener("change", () => { if (input.files.length) form.submit(); });
  const zone = page.querySelector("[data-dropzone]");
  for (const name of ["dragover", "dragenter"]) {
    document.addEventListener(name, (event) => {
      event.preventDefault();
      zone.classList.add("is-dropping");
    });
  }
  document.addEventListener("dragleave", (event) => { if (!event.relatedTarget) zone.classList.remove("is-dropping"); });
  document.addEventListener("drop", (event) => {
    event.preventDefault();
    zone.classList.remove("is-dropping");
    if (!event.dataTransfer?.files.length) return;
    input.files = event.dataTransfer.files; // hand the dropped files to the same form
    form.submit();
  });
}

/* The Content page: texts save row by row without a reload, fonts preview and save on choice. */
function setupContent() {
  const page = document.querySelector("[data-content-page]");
  if (!page) return;
  // Rows with changes that are not in content.xlsx yet: leaving the page asks first.
  const unsaved = new Set();
  window.addEventListener("beforeunload", (event) => { if (unsaved.size) event.preventDefault(); });
  for (const row of page.querySelectorAll("[data-content-row]")) {
    const button = row.querySelector("[data-save-row]");
    const label = button.textContent;
    row.addEventListener("input", () => {
      unsaved.add(row);
      row.classList.add("is-unsaved");
      row.classList.remove("is-failed");
      button.disabled = false;
      button.textContent = label;
    });
    button.addEventListener("click", async () => {
      const values = {};
      for (const area of row.querySelectorAll("[data-value]")) values[area.dataset.value] = area.value;
      const body = { id: row.dataset.contentRow ? Number(row.dataset.contentRow) : null, note: row.querySelector("[data-note]").value, values };
      button.disabled = true;
      button.textContent = "Saving…";
      try {
        await postJson(page.dataset.rowsApi, page.dataset.csrf, body);
      } catch (error) { // e.g. content.xlsx is open in Excel: say so where the user is looking, keep the edit
        button.disabled = false;
        button.textContent = "Retry";
        row.classList.add("is-failed");
        showToast(`Text not saved. ${error.message}`);
        return;
      }
      unsaved.delete(row);
      row.classList.remove("is-unsaved", "is-failed"); // a successful Retry clears the red too
      button.textContent = "Saved";
      if (!row.dataset.contentRow) location.reload(); // the new row's id comes from the workbook
    });
  }
  for (const fontRow of page.querySelectorAll("[data-font-row]")) {
    const select = fontRow.querySelector("[data-font-select]");
    select.addEventListener("change", async () => {
      const option = select.selectedOptions[0];
      if (!option.value) return; // "Custom": hand-edited CSS is left alone
      fontRow.querySelector("[data-font-sample]").style.fontFamily = option.dataset.stack;
      const state = fontRow.querySelector("[data-font-state]");
      state.textContent = "Saving…";
      try {
        await postJson(page.dataset.fontsApi, page.dataset.csrf, { component: fontRow.dataset.component, preset: option.value });
        state.textContent = "Saved. Regenerate to apply it to the story.";
      } catch (error) {
        state.textContent = "";
        reportError(`Font not saved: ${error.message}`);
      }
    });
  }
}

function setupConfig() {
  const input = document.querySelector("[name=finish_redirect_url]");
  const example = document.querySelector("[data-redirect-example]");
  if (!input || !example) return;
  const update = () => {
    example.hidden = !input.value.includes("{ID}");
    example.querySelector("[data-redirect-result]").textContent = input.value.replaceAll("{ID}", "R_example123");
  };
  input.addEventListener("input", update);
  update();
}

// Results: the visits on the left drive the statistics drawn on the flowchart (set up by setupFlowchart first).
function setupResults() {
  const page = document.querySelector("[data-results]");
  if (!page) return;
  const sessions = JSON.parse(document.getElementById("results-sessions").textContent);
  const items = [...page.querySelectorAll("[data-session]")];
  const filters = page.querySelector("[data-filters]").elements;
  const showAll = page.querySelector("[data-show-all]");
  const nodes = [...page.querySelectorAll("[data-node]")];
  const edges = [...page.querySelectorAll("[data-flow-paths] [data-element]")];
  let selected = null;

  const isShown = (session) =>
    !(filters.exclude_tests.checked && session.kind !== "study")
    && !(filters.finished_only.checked && !session.finished)
    && (!filters.from.value || session.started.slice(0, 10) >= filters.from.value)
    && (!filters.to.value || session.started.slice(0, 10) <= filters.to.value);
  const seconds = (value) => `${Math.round(value)} s`;

  const render = () => {
    const shown = sessions.filter(isShown);
    items.forEach((item, index) => { item.hidden = !isShown(sessions[index]); });
    if (selected !== null && !isShown(sessions[selected])) selected = null;
    const person = selected === null ? null : sessions[selected];
    const stats = aggregate(shown);
    showAll.classList.toggle("is-active", person === null);
    showAll.querySelector("[data-shown-count]").textContent = `(${shown.length})`;
    page.classList.toggle("has-selection", person !== null);
    for (const node of nodes) {
      const frame = stats.frames[node.dataset.key];
      const times = frame?.times ?? [];
      const spread = times.length ? ` · avg ${seconds(times.reduce((a, b) => a + b) / times.length)} (min ${seconds(Math.min(...times))}, max ${seconds(Math.max(...times))})` : "";
      // A document frame is optional: count how many visits opened it 0×, 1×, 2×… rather than visits.
      const opened = node.classList.contains("is-document") ? shown.map((session) => session.frames.filter(([key]) => key === node.dataset.key).length) : null;
      const usage = opened ? [...new Set(opened)].sort((a, b) => a - b).map((count) => `${count}×: ${opened.filter((value) => value === count).length}`).join(", ") : "";
      node.querySelector("[data-stats]").textContent = opened ? `opened ${usage}${spread}` : frame ? `n = ${frame.n}${spread}` : "";
      const visits = person ? person.frames.filter(([key]) => key === node.dataset.key) : [];
      node.classList.toggle("is-path", visits.length > 0);
      const known = visits.map(([, secs]) => secs).filter((secs) => secs !== null);
      node.querySelector("[data-person]").textContent = visits.length ? `${known.length ? seconds(known.reduce((a, b) => a + b)) : "last frame"}${visits.length > 1 ? ` in ${visits.length} visits` : ""}` : "";
    }
    for (const edge of edges) {
      const total = edge.classList.contains("document") ? 0 : stats.frames[edge.dataset.source]?.n; // documents: see the node
      edge.querySelector("text").textContent = total ? `${Math.round((stats.choices[edge.dataset.element] ?? 0) / total * 100)}%` : "";
      edge.classList.toggle("is-path", Boolean(person?.choices.map(String).includes(edge.dataset.element)));
    }
  };

  for (const [index, item] of items.entries()) {
    item.addEventListener("toggle", () => {
      if (item.open) {
        for (const other of items) if (other !== item) other.open = false;
        selected = index;
      } else if (selected === index) {
        selected = null;
      }
      render();
    });
  }
  showAll.addEventListener("click", () => { for (const item of items) item.open = false; selected = null; render(); });
  page.querySelector("[data-filters]").addEventListener("input", render);
  render();
}

// Visits per frame (with the seconds spent there) and clicks per element, over the given sessions.
function aggregate(sessions) {
  const frames = {};
  const choices = {};
  for (const session of sessions) {
    for (const [key, secs] of session.frames) {
      const frame = (frames[key] ??= { n: 0, times: [] });
      frame.n += 1;
      if (secs !== null) frame.times.push(secs);
    }
    for (const id of session.choices) choices[id] = (choices[id] ?? 0) + 1;
  }
  return { frames, choices };
}

function setupDevelop() {
  const page = document.querySelector("[data-develop]");
  if (!page) return;
  const stage = page.querySelector("[data-stage]");
  const shell = page.querySelector("[data-device-shell]");
  const preview = page.querySelector("[data-preview]");
  const deviceSelect = page.querySelector("[data-device]");
  const zoomLabel = page.querySelector("[data-zoom]");
  let rotated = localStorage.getItem("tiltale.rotated") === "1";
  const savedDevice = localStorage.getItem("tiltale.device");
  if ([...deviceSelect.options].some((option) => option.value === savedDevice)) deviceSelect.value = savedDevice;

  // The shell gets the device's real CSS size and is only scaled afterwards,
  // so the story inside sees exactly the aspect ratio of the chosen phone.
  const fitDevice = () => {
    if (!shell) return;
    const [width, height] = deviceSelect.value.split("x").map(Number);
    const [shellWidth, shellHeight] = rotated ? [height, width] : [width, height];
    const scale = Math.min(1, (stage.clientWidth - STAGE_MARGIN_PX) / shellWidth, (stage.clientHeight - STAGE_MARGIN_PX) / shellHeight);
    shell.style.width = `${shellWidth}px`;
    shell.style.height = `${shellHeight}px`;
    shell.style.transform = `translate(-50%, -50%) scale(${scale})`;
    zoomLabel.textContent = `${Math.round(scale * 100)}%`;
  };
  new ResizeObserver(fitDevice).observe(stage);

  deviceSelect.addEventListener("change", () => {
    localStorage.setItem("tiltale.device", deviceSelect.value);
    fitDevice();
  });
  page.querySelector("[data-rotate]").addEventListener("click", () => {
    rotated = !rotated;
    localStorage.setItem("tiltale.rotated", rotated ? "1" : "0");
    fitDevice();
  });
  page.querySelector("[data-toggle-panel]").addEventListener("click", () => page.classList.toggle("panel-hidden"));
  page.querySelector("[data-restart]").addEventListener("click", () => {
    if (!preview) return;
    const url = new URL(preview.src);
    url.searchParams.delete("frame");
    url.searchParams.set("restart", "1");
    preview.src = url;
  });
  page.addEventListener("click", (event) => {
    const thumb = event.target.closest("[data-view-frame]");
    if (thumb && preview && !event.target.closest("a")) preview.src = thumb.dataset.viewFrame;
  });
  // "Show essentials only": hide the minor preflight warnings; the choice is remembered per browser.
  const essentials = page.querySelector("[data-essentials-only]");
  if (essentials) {
    const apply = () => {
      for (const item of page.querySelectorAll("[data-issues] [data-minor]")) item.hidden = essentials.checked;
      localStorage.setItem("tiltale.essentialsOnly", essentials.checked ? "1" : "0");
    };
    essentials.checked = localStorage.getItem("tiltale.essentialsOnly") === "1";
    essentials.addEventListener("change", apply);
    apply();
  }
  page.querySelector("[data-frame-filter]").addEventListener("input", (event) => {
    const query = event.target.value.trim().toLowerCase();
    for (const thumb of page.querySelectorAll("[data-frame-name]")) thumb.hidden = !thumb.dataset.frameName.includes(query);
  });

  // "Save and exit" in the frame editor returns with ?selected=<id>: scroll that frame's thumbnail
  // into view, highlight it and show it in the preview, instead of springing back to frame 1.
  const selected = page.querySelector(`[data-frame-id="${CSS.escape(page.dataset.selected)}"]`);
  if (!selected) return;
  selected.classList.add("is-selected");
  selected.scrollIntoView({ block: "center" });
  if (preview) preview.src = selected.dataset.viewFrame;
}

function setupEditor() {
  const page = document.querySelector("[data-editor]");
  if (!page) return;
  setupRules(page);
  setupElementOrder(page);
  setupPicker(page, document.getElementById("component-picker"));
  setupPicker(page, document.getElementById("material-picker"));
  const stage = page.querySelector("[data-canvas-stage]");
  const canvas = page.querySelector("[data-canvas]");
  const picker = document.getElementById("content-picker");
  const view = { scale: 1 };
  let contentInput = null;
  if (!canvas) return; // documents and validation points have no canvas

  const fitCanvas = () => {
    view.scale = Math.min(
      (stage.clientWidth - STAGE_MARGIN_PX) / Number(canvas.dataset.width),
      (stage.clientHeight - STAGE_MARGIN_PX) / Number(canvas.dataset.height),
    );
    canvas.style.transform = `translate(-50%, -50%) scale(${view.scale})`;
    canvas.style.setProperty("--canvas-scale", view.scale); // keeps handles and guides the same size on screen
  };
  new ResizeObserver(fitCanvas).observe(stage);
  const boxes = [...canvas.querySelectorAll("[data-box-url]")];
  const history = { undo: [], redo: [] }; // moves and resizes on this page; a reload starts a new history
  const onDrop = (node, before) => {
    history.undo.push({ node, before, after: readBox(node) });
    history.redo = [];
    saveBox(node, page);
  };
  for (const node of boxes) makeBoxEditable(node, boxes, canvas, view, onDrop);
  document.addEventListener("click", (event) => { // after setupDialogs opened it, so the preview has a size
    const opener = event.target.closest("[data-open-dialog]");
    if (!opener) return;
    const dialog = document.getElementById(opener.dataset.openDialog);
    TilTaleBubbles.draw(dialog);
    scalePreviews(dialog);
  });
  document.addEventListener("keydown", (event) => {
    if (!(event.ctrlKey || event.metaKey) || event.key.toLowerCase() !== "z") return;
    if (event.target.closest("input, textarea, select, dialog")) return; // text fields keep their own undo
    event.preventDefault();
    const [from, to] = event.shiftKey ? [history.redo, history.undo] : [history.undo, history.redo];
    const step = from.pop();
    if (!step) return;
    to.push(step);
    placeBox(step.node, event.shiftKey ? step.after : step.before);
    saveBox(step.node, page);
  });

  const backgroundType = page.querySelector("[name=background_type]");
  const showBackgroundFields = () => {
    for (const group of page.querySelectorAll("[data-show-when]")) group.hidden = group.dataset.showWhen !== backgroundType.value;
  };
  backgroundType.addEventListener("change", showBackgroundFields);
  showBackgroundFields();
  page.addEventListener("click", (event) => {
    const button = event.target.closest("[data-use-background]");
    if (!button) return;
    backgroundType.value = "image";
    backgroundType.form.elements.background_image.value = button.dataset.useBackground;
    backgroundType.form.requestSubmit(); // also saves unsaved edits in the frame form, like its own button
  });

  for (const toggle of page.querySelectorAll("[data-color-toggle]")) {
    const inputs = toggle.closest("fieldset").querySelectorAll("[data-colors] input");
    const apply = () => inputs.forEach((input) => { input.disabled = !toggle.checked; });
    toggle.addEventListener("change", apply);
    apply();
  }

  page.addEventListener("click", (event) => {
    const button = event.target.closest("[data-pick-content]");
    if (!button) return;
    contentInput = button.closest("dialog").querySelector("[data-content-input]");
    picker.showModal();
  });
  picker.addEventListener("click", (event) => {
    const row = event.target.closest("[data-content-id]");
    if (!row) return;
    contentInput.value = row.dataset.contentId;
    picker.close();
  });
  const copyButton = page.querySelector("[data-copy-prompt]");
  copyButton?.addEventListener("click", async () => {
    await navigator.clipboard.writeText(page.querySelector("[data-prompt]").value);
    copyButton.textContent = "Copied";
  });
  picker.querySelector("[data-content-filter]").addEventListener("input", (event) => {
    const query = event.target.value.trim().toLowerCase();
    for (const row of picker.querySelectorAll("[data-content-id]")) row.hidden = !row.textContent.toLowerCase().includes(query);
  });
}

/* The "(Re)order elements" pills: drag to restack (top of the list is the front layer), or the
   hover buttons ⤒ / ⤓. The order is saved in the background and the canvas restacks to match.
   "Every frame" scoreboards and the background pill stay where they are (their layer is fixed). */
function setupElementOrder(page) {
  const list = page.querySelector("[data-element-order]");
  if (!list) return;
  const canvas = page.querySelector("[data-canvas]");
  const owned = () => [...list.querySelectorAll("[data-owned]")];
  let dragged = null;

  list.addEventListener("dragstart", (event) => {
    dragged = event.target.closest("[data-owned]");
    if (!dragged) return;
    dragged.classList.add("is-dragging");
    event.dataTransfer.effectAllowed = "move";
  });
  list.addEventListener("dragover", (event) => {
    if (!dragged) return;
    event.preventDefault();
    const over = event.target.closest("[data-owned]");
    if (!over || over === dragged) return;
    const children = [...list.children];
    list.insertBefore(dragged, children.indexOf(over) > children.indexOf(dragged) ? over.nextSibling : over);
  });
  list.addEventListener("drop", (event) => event.preventDefault());
  list.addEventListener("dragend", () => {
    dragged?.classList.remove("is-dragging");
    dragged = null;
    saveOrder();
  });
  list.addEventListener("click", (event) => {
    const button = event.target.closest("[data-order-move]");
    if (!button) return;
    const pill = button.closest("[data-owned]");
    if (button.dataset.orderMove === "front") list.prepend(pill);
    else list.insertBefore(pill, list.querySelector(".pill-locked")); // just above the locked background
    saveOrder();
  });

  async function saveOrder() {
    const ids = owned().map((pill) => Number(pill.dataset.elementId)); // top of the list = front
    try {
      await postJson(list.dataset.orderUrl, page.dataset.csrf, { order: ids });
    } catch (error) {
      reportError(`Order not saved: ${error.message}`);
      return;
    }
    if (!canvas) return; // restack the canvas to match: its children run back to front
    for (const id of [...ids].reverse()) {
      const node = canvas.querySelector(`[data-dialog="element-${id}"]`);
      if (node) canvas.appendChild(node);
    }
    for (const guide of canvas.querySelectorAll("[data-snap-guide]")) canvas.appendChild(guide); // guides stay on top
  }
}

/* Component previews are real elements at their default size, text layout and font — exactly what
   would land on the canvas — shrunk to fit their card, the way the canvas itself is scaled. */
function scalePreviews(dialog) {
  for (const element of dialog.querySelectorAll(".picker-preview > .story-element")) {
    const box = element.parentElement;
    const tailRoom = "tail" in element.dataset ? 100 : 0; // bubbles.js tails reach 90px below the body
    const scale = Math.min(1,
      (box.clientWidth - 16) / element.offsetWidth,
      (box.clientHeight - 16) / (element.offsetHeight + tailRoom));
    element.style.setProperty("--preview-scale", scale);
    element.style.top = `calc(50% - ${tailRoom * scale / 2}px)`; // keep body plus tail centered together
  }
}

/* The component and image pickers: clicking a card selects it and wakes the footer buttons up. */
function setupPicker(page, dialog) {
  if (!dialog) return;
  const input = dialog.querySelector("[data-picked]");
  const nameLabel = dialog.querySelector("[data-picked-name]");
  dialog.addEventListener("click", (event) => {
    const card = event.target.closest(".picker-card");
    if (!card) return;
    for (const other of dialog.querySelectorAll(".picker-card")) other.classList.toggle("is-selected", other === card);
    input.value = card.dataset.pickComponent ?? card.dataset.pickMaterial;
    nameLabel.textContent = card.dataset.pickName;
    for (const button of dialog.querySelectorAll("[data-picker-confirm], [data-use-background]")) {
      button.disabled = false;
      if ("useBackground" in button.dataset) button.dataset.useBackground = input.value; // the shared handler reads it
    }
  });
  const filter = dialog.querySelector("[data-material-filter]");
  filter?.addEventListener("input", () => {
    const query = filter.value.trim().toLowerCase();
    for (const card of dialog.querySelectorAll("[data-file-name]")) card.hidden = !card.dataset.fileName.includes(query);
  });
}

// Validation points: add and remove rule rows; the rows are numbered rule.0, rule.1, … for the view.
function setupRules(page) {
  const form = page.querySelector("[data-rules]");
  if (!form) return;
  const list = form.querySelector("[data-rule-list]");
  const template = form.querySelector("[data-rule-template]");
  const renumber = () => {
    for (const [index, row] of [...list.querySelectorAll("[data-rule]")].entries()) {
      for (const field of row.querySelectorAll("[name]")) field.name = field.name.replace(/rule\.[^.]+\./, `rule.${index}.`);
    }
  };
  form.querySelector("[data-add-rule]").addEventListener("click", () => {
    list.append(template.content.cloneNode(true));
    renumber();
  });
  form.addEventListener("click", (event) => {
    const button = event.target.closest("[data-remove-rule]");
    if (!button) return;
    button.closest("[data-rule]").remove();
    renumber();
  });
}

// Elements, images and the background: drag to move (snapping to other edges), drag the corner to resize.
function makeBoxEditable(node, boxes, canvas, view, onDrop) {
  const dialog = document.getElementById(node.dataset.dialog); // the background has none
  const guides = [...canvas.querySelectorAll("[data-snap-guide]")];
  placeBox(node, readBox(node));
  node.addEventListener("keydown", (event) => {
    if (event.key === "Enter") dialog?.showModal();
  });
  node.addEventListener("pointerdown", (event) => {
    const start = { x: event.clientX, y: event.clientY, box: readBox(node) };
    const handle = event.target.closest("[data-resize]");
    const tailing = Boolean(event.target.closest("[data-tail-handle]"));
    // An element that grew with its text is resized from the height it shows, not from its minimum.
    if (handle && "autoHeight" in node.dataset) start.box.height = node.offsetHeight;
    const others = boxes.filter((other) => other !== node).map(readBox);
    let moved = false;
    trackPointer(node, event, (move) => {
      const delta = { x: (move.clientX - start.x) / view.scale, y: (move.clientY - start.y) / view.scale };
      moved = moved || Math.hypot(delta.x, delta.y) * view.scale > DRAG_THRESHOLD_PX;
      if (tailing) return placeBox(node, { ...start.box, tail_x: start.box.tail_x + delta.x, tail_y: start.box.tail_y + delta.y });
      // Images keep their proportions and components do not; Shift does the opposite.
      if (handle) return placeBox(node, resizedBox(start.box, delta.x, delta.y, ("keepRatio" in node.dataset) !== move.shiftKey, handle.dataset.resize));
      // Shift keeps the drag horizontal or vertical, whichever way it has gone furthest (as in Illustrator).
      const axes = move.shiftKey ? [Math.abs(delta.x) > Math.abs(delta.y) ? "x" : "y"] : ["x", "y"];
      const box = { ...start.box };
      for (const axis of axes) box[axis] += delta[axis];
      const snap = snapBox(box, others, SNAP_PX / view.scale, axes);
      showGuides(guides, snap.lines);
      placeBox(node, snap.box);
    }, () => {
      showGuides(guides, {});
      if (moved) return onDrop(node, start.box);
      placeBox(node, start.box); // a click that wobbled a little is not a move
      dialog?.showModal();
    });
  });
}

// Elements that grow with their text store a minimum height instead of a height.
const heightProperty = (node) => ("autoHeight" in node.dataset ? "minHeight" : "height");

function readBox(node) {
  const box = { x: parseFloat(node.style.left), y: parseFloat(node.style.top), width: parseFloat(node.style.width), height: parseFloat(node.style[heightProperty(node)]) };
  if (!("tail" in node.dataset)) return box;
  const stored = { x: parseFloat(node.style.getPropertyValue("--tail-x")), y: parseFloat(node.style.getPropertyValue("--tail-y")) };
  const tail = Number.isNaN(stored.x) ? TilTaleBubbles.defaultTail(box.width, box.height) : stored;
  return { ...box, tail_x: tail.x, tail_y: tail.y };
}

function placeBox(node, box) {
  const frame = node.parentElement.dataset; // the canvas
  node.style.left = `${Math.round(box.x)}px`;
  node.style.top = `${Math.round(box.y)}px`;
  node.style.width = `${Math.round(box.width)}px`;
  node.style[heightProperty(node)] = `${Math.round(box.height)}px`;
  if ("tail" in node.dataset) {
    node.style.setProperty("--tail-x", `${Math.round(box.tail_x)}px`);
    node.style.setProperty("--tail-y", `${Math.round(box.tail_y)}px`);
    TilTaleBubbles.draw(node);
  }
  // The corners stay inside the frame, or a background larger than the frame could never be resized.
  const overflow = {
    left: Math.max(0, box.width / 2 - box.x), top: Math.max(0, box.height / 2 - box.y),
    right: Math.max(0, box.x + box.width / 2 - Number(frame.width)), bottom: Math.max(0, box.y + box.height / 2 - Number(frame.height)),
  };
  for (const handle of node.querySelectorAll("[data-resize]")) {
    for (const letter of handle.dataset.resize) handle.style[SIDES[letter]] = `${overflow[SIDES[letter]]}px`;
  }
}

// Dragging `corner` ("nw", "ne", "se" or "sw") keeps the opposite corner in place.
function resizedBox(start, dx, dy, keepRatio, corner) {
  const signX = corner.includes("w") ? -1 : 1; // a left corner grows the box when dragged left
  const signY = corner.includes("n") ? -1 : 1;
  const ratio = start.height / start.width;
  const width = Math.max(MIN_BOX_PX, start.width + signX * dx, keepRatio ? MIN_BOX_PX / ratio : 0);
  const height = keepRatio ? width * ratio : Math.max(MIN_BOX_PX, start.height + signY * dy);
  return { ...start, x: start.x + signX * (width - start.width) / 2, y: start.y + signY * (height - start.height) / 2, width, height };
}

// Moves `box` along `axes` so its closest edge meets an edge of another box, if one is within `reach`.
function snapBox(box, others, reach, axes) {
  const snapped = { ...box };
  const lines = {};
  for (const axis of axes) {
    const edge = closestEdge(box, others, reach, axis);
    if (!edge) continue;
    snapped[axis] += edge.shift;
    lines[axis] = edge.line;
  }
  return { box: snapped, lines };
}

function closestEdge(box, others, reach, axis) {
  const size = axis === "x" ? "width" : "height";
  const edges = (item) => [item[axis] - item[size] / 2, item[axis] + item[size] / 2];
  const targets = others.flatMap(edges);
  const shifts = edges(box).flatMap((edge) => targets.map((line) => ({ shift: line - edge, line })));
  return shifts.filter(({ shift }) => Math.abs(shift) <= reach).sort((a, b) => Math.abs(a.shift) - Math.abs(b.shift))[0];
}

function showGuides(guides, lines) {
  for (const guide of guides) {
    const axis = guide.dataset.snapGuide;
    guide.hidden = lines[axis] === undefined;
    guide.style[axis === "x" ? "left" : "top"] = `${lines[axis]}px`;
  }
}

async function saveBox(node, page) {
  const box = readBox(node);
  const dialog = document.getElementById(node.dataset.dialog);
  // Keep the settings dialog in sync, or saving it later would undo the drag. (The tail has no field there.)
  if (dialog) for (const [name, value] of Object.entries(box)) {
    const input = dialog.querySelector(`[name=${name}]`);
    if (input) input.value = value;
  }
  try {
    await postJson(node.dataset.boxUrl, page.dataset.csrf, { ...box, language: page.dataset.language });
  } catch (error) {
    reportError(`Position not saved: ${error.message}`);
  }
}

function svgElement(tag, attributes) {
  const node = document.createElementNS("http://www.w3.org/2000/svg", tag);
  for (const [name, value] of Object.entries(attributes)) node.setAttribute(name, value);
  return node;
}

function setupFlowchart() {
  const page = document.querySelector("[data-flowchart]");
  if (!page) return;
  const readonly = "readonly" in page.dataset; // Results: look, do not move or edit
  const viewport = page.querySelector("[data-flow-viewport]");
  const world = page.querySelector("[data-flow-world]");
  const paths = page.querySelector("[data-flow-paths]");
  const zoomLabel = page.querySelector("[data-zoom]");
  const edges = JSON.parse(document.getElementById("flow-edges").textContent);
  const nodes = new Map([...world.querySelectorAll("[data-node]")].map((node) => [node.dataset.node, node]));
  const selected = new Set();
  const view = { x: 0, y: 0, zoom: 1 };
  const position = (node) => ({ x: Number(node.dataset.x), y: Number(node.dataset.y) });

  const place = (node, x, y) => {
    node.dataset.x = x;
    node.dataset.y = y;
    node.style.transform = `translate(${x}px, ${y}px)`;
  };
  const applyView = () => {
    world.style.transform = `translate(${view.x}px, ${view.y}px) scale(${view.zoom})`;
    zoomLabel.textContent = `${Math.round(view.zoom * 100)}%`;
  };
  const drawEdges = () => paths.replaceChildren(...edges.map((edge) => edgeGroup(edge, nodes, position)).filter(Boolean));
  const markSelection = () => {
    for (const [id, node] of nodes) node.classList.toggle("is-selected", selected.has(id));
  };
  const zoomAt = (zoom, clientX, clientY) => {
    const rect = viewport.getBoundingClientRect();
    const next = Math.min(2, Math.max(0.2, zoom));
    view.x = clientX - rect.left - (clientX - rect.left - view.x) * next / view.zoom;
    view.y = clientY - rect.top - (clientY - rect.top - view.y) * next / view.zoom;
    view.zoom = next;
    applyView();
  };
  const fit = () => {
    if (!nodes.size) return;
    const boxes = [...nodes.values()].map((node) => ({ ...position(node), width: node.offsetWidth, height: node.offsetHeight }));
    const left = Math.min(...boxes.map((box) => box.x));
    const top = Math.min(...boxes.map((box) => box.y));
    const width = Math.max(...boxes.map((box) => box.x + box.width)) - left;
    const height = Math.max(...boxes.map((box) => box.y + box.height)) - top;
    view.zoom = Math.min(1, (viewport.clientWidth - 80) / width, (viewport.clientHeight - 80) / height);
    view.x = (viewport.clientWidth - width * view.zoom) / 2 - left * view.zoom;
    view.y = (viewport.clientHeight - height * view.zoom) / 2 - top * view.zoom;
    applyView();
  };
  const inspect = (node) => showInspector(page, node, edges);
  const focus = (node) => {
    const { x, y } = position(node);
    view.zoom = Math.max(view.zoom, FOCUS_ZOOM);
    view.x = viewport.clientWidth / 2 - (x + node.offsetWidth / 2) * view.zoom;
    view.y = viewport.clientHeight / 2 - (y + node.offsetHeight / 2) * view.zoom;
    world.classList.add("is-animating");
    applyView();
    setTimeout(() => world.classList.remove("is-animating"), FOCUS_MS);
  };
  const save = async (ids) => {
    const positions = ids.map((id) => ({ id: Number(id), ...position(nodes.get(id)) }));
    try {
      await postJson(page.dataset.saveUrl, page.dataset.csrf, { positions });
    } catch (error) {
      reportError(`Layout not saved: ${error.message}`);
    }
  };

  const dragNodes = (event, node) => {
    const starts = new Map([...selected].map((id) => [id, position(nodes.get(id))]));
    const origin = { x: event.clientX, y: event.clientY };
    let moved = false;
    trackPointer(viewport, event, (move) => {
      const dx = (move.clientX - origin.x) / view.zoom;
      const dy = (move.clientY - origin.y) / view.zoom;
      moved = moved || Math.hypot(dx, dy) * view.zoom > DRAG_THRESHOLD_PX;
      for (const [id, start] of starts) place(nodes.get(id), Math.round(start.x + dx), Math.round(start.y + dy));
      drawEdges();
    }, () => {
      if (moved) return save([...starts.keys()]);
      inspect(node); // first, so the viewport has its final width when centring
      focus(node);
    });
  };
  const pan = (event) => {
    const origin = { x: event.clientX - view.x, y: event.clientY - view.y };
    let moved = false;
    trackPointer(viewport, event, (move) => {
      moved = true;
      view.x = move.clientX - origin.x;
      view.y = move.clientY - origin.y;
      applyView();
    }, () => {
      if (moved) return;
      selected.clear();
      markSelection();
    });
  };

  viewport.addEventListener("pointerdown", (event) => {
    const node = event.target.closest("[data-node]");
    if (!node) return pan(event);
    const id = node.dataset.node;
    if (event.shiftKey) {
      if (selected.has(id)) selected.delete(id);
      else selected.add(id);
      return markSelection();
    }
    if (!selected.has(id)) selected.clear();
    selected.add(id);
    markSelection();
    if (readonly) return inspect(node);
    dragNodes(event, node);
  });
  viewport.addEventListener("dblclick", (event) => {
    const node = event.target.closest("[data-node]");
    if (node && !readonly) window.location = node.dataset.editUrl;
  });
  viewport.addEventListener("keydown", (event) => {
    const node = event.target.closest("[data-node]");
    if (node && event.key === "Enter" && !readonly) window.location = node.dataset.editUrl;
  });
  viewport.addEventListener("wheel", (event) => {
    event.preventDefault();
    zoomAt(view.zoom * (event.deltaY < 0 ? 1.1 : 1 / 1.1), event.clientX, event.clientY);
  }, { passive: false });
  for (const button of page.querySelectorAll("[data-zoom-step]")) {
    button.addEventListener("click", () => {
      const rect = viewport.getBoundingClientRect();
      zoomAt(view.zoom * 1.2 ** Number(button.dataset.zoomStep), rect.left + rect.width / 2, rect.top + rect.height / 2);
    });
  }
  page.querySelector("[data-fit]").addEventListener("click", fit);

  for (const node of nodes.values()) place(node, Number(node.dataset.x), Number(node.dataset.y));
  drawEdges();
  fit();
  const preselected = nodes.get(page.dataset.selected);
  if (!preselected) return;
  selected.add(preselected.dataset.node);
  markSelection();
  inspect(preselected);
  focus(preselected);
}

function trackPointer(surface, event, onMove, onUp) {
  surface.setPointerCapture(event.pointerId);
  const stop = () => {
    surface.removeEventListener("pointermove", onMove);
    surface.removeEventListener("pointerup", stop);
    onUp();
  };
  surface.addEventListener("pointermove", onMove);
  surface.addEventListener("pointerup", stop);
}

function edgeGroup(edge, nodes, position) {
  const source = nodes.get(String(edge.source));
  const target = nodes.get(String(edge.target));
  if (!source || (!target && !edge.end && !edge.restart)) return null;
  const start = position(source);
  const x1 = start.x + source.offsetWidth;
  const y1 = start.y + source.offsetHeight / 2;
  const group = svgElement("g", { class: `edge ${edgeKind(edge)}`, "data-element": edge.element_id, "data-source": source.dataset.key });
  group.append(svgElement("title", {}));
  group.firstChild.textContent = `${edgeLabel(edge)} → ${edgeDestination(edge)}`;
  if (!target) { // "End story" and "Restart": a short stub with a dot instead of a target frame
    group.append(svgElement("path", { d: `M${x1} ${y1} h36`, "marker-end": "url(#flow-arrow)" }));
    group.append(svgElement("circle", { cx: x1 + 46, cy: y1, r: 8 }));
    group.append(svgElement("text", { class: "edge-label", x: x1 + 18, y: y1 - 10 })); // filled in by the Results page
    return group;
  }
  const end = position(target);
  if (edge.document) { // a document sits above (or below) the frame that opens it: a straight two-way arrow between their middles
    const x = start.x + source.offsetWidth / 2;
    const above = end.y < start.y;
    const [ya, yb] = above ? [start.y, end.y + target.offsetHeight] : [start.y + source.offsetHeight, end.y];
    group.append(svgElement("path", { d: `M${x} ${ya} L${x} ${yb}`, "marker-start": "url(#flow-arrow-document)", "marker-end": "url(#flow-arrow-document)" }));
    group.append(svgElement("text", { class: "edge-label", x: x + 8, y: (ya + yb) / 2 }));
    return group;
  }
  const x2 = end.x;
  const y2 = end.y + target.offsetHeight / 2;
  const bend = Math.max(40, Math.abs(x2 - x1) / 2);
  group.append(svgElement("path", { d: `M${x1} ${y1} C${x1 + bend} ${y1} ${x2 - bend} ${y2} ${x2} ${y2}`, "marker-end": "url(#flow-arrow)" }));
  group.append(svgElement("text", { class: "edge-label", x: (x1 + x2) / 2, y: (y1 + y2) / 2 - 6 })); // the curve's midpoint
  return group;
}

function edgeLabel(edge) {
  return edge.text || edge.component;
}

function edgeKind(edge) {
  if (edge.end) return "end";
  if (edge.restart) return "restart";
  if (edge.language) return "language";
  const kind = edge.rule ? "frame rule" : "frame";
  return edge.document ? `${kind} document` : kind;
}

function edgeDestination(edge) {
  if (edge.end) return "End story";
  if (edge.restart) return "Restart the story";
  return edge.language ? `${edge.language} story` : edge.target_name;
}

function showInspector(page, node, edges) {
  const inspector = page.querySelector("[data-inspector]");
  const frame = inspector.querySelector("[data-inspector-frame]");
  const frameUrl = `${node.dataset.previewUrl}?inspect=1&frame=${encodeURIComponent(node.dataset.key)}`;
  inspector.hidden = false;
  inspector.querySelector("[data-inspector-title]").textContent = node.dataset.name;
  const edit = inspector.querySelector("[data-inspector-edit]"); // absent on the Results page
  if (edit) edit.href = node.dataset.editUrl;
  if (frame) frame.src = frameUrl;
  const items = edges.filter((edge) => String(edge.source) === node.dataset.node).map((edge) => {
    const item = document.createElement("li");
    item.textContent = `${edgeLabel(edge)} → ${edgeDestination(edge)}`;
    item.addEventListener("mouseenter", () => { if (frame) frame.src = `${frameUrl}&element=${edge.element_id}`; });
    return item;
  });
  if (!items.length) items.push(Object.assign(document.createElement("li"), { className: "muted", textContent: "No buttons or rules lead anywhere yet." }));
  inspector.querySelector("[data-inspector-links]").replaceChildren(...items);
}

/* The Test page: one place for both robots. The settings decide what runs: the quick Play-test
   (one run per page) or the thorough Stress-test (every page under every pretended condition),
   over the ticked pages, optionally with "Element delay" temporarily 0.01 s so the robot never
   waits for fades (?delay=, see runtime/tiltale.js; the story itself is unchanged). */
function setupTest() {
  const page = document.querySelector("[data-test]");
  const runButton = document.querySelector("[data-run-test]");
  if (!page || !runButton) return;
  const form = page.querySelector("[data-test-settings]");
  const cards = [...page.querySelectorAll("[data-build-url]")];
  const progress = page.querySelector("[data-test-progress]");

  const showMode = () => {
    for (const panel of page.querySelectorAll("[data-stress-panel]")) panel.hidden = form.elements.mode.value !== "stress";
  };
  form.addEventListener("change", showMode);
  showMode();

  // Leaving the page ends the robot's run: ask first (links in the studio get our own words,
  // closing or reloading the tab gets the browser's generic dialog).
  const question = "Leave this page? That ends the test.";
  let running = false;
  window.addEventListener("beforeunload", (event) => { if (running) event.preventDefault(); });
  document.addEventListener("click", (event) => {
    const link = event.target.closest("a[href]");
    if (running && link && !link.target && !confirm(question)) event.preventDefault();
  });

  const chosenCards = () => {
    const boxes = [...form.querySelectorAll("[name=build]")]; // absent on a single-page story
    if (!boxes.length) return cards;
    const wanted = new Set(boxes.filter((box) => box.checked).map((box) => box.value));
    return cards.filter((card) => wanted.has(card.dataset.buildLabel));
  };

  runButton.addEventListener("click", async () => {
    const chosen = chosenCards();
    if (!chosen.length) {
      progress.textContent = "Tick at least one page to test.";
      return;
    }
    runButton.disabled = true;
    running = true;
    const delay = form.elements.speed.checked ? "0.01" : "";
    if (form.elements.mode.value === "play") await runAllPlaytests(chosen, page.dataset, progress, delay);
    else await runStresstest(page, chosen, progress, delay);
    running = false;
    runButton.disabled = false;
  });
}

async function runAllPlaytests(cards, settings, progress, delay) {
  for (const [index, card] of cards.entries()) {
    progress.textContent = `Play-testing ${card.dataset.buildLabel} (${index + 1} of ${cards.length})…`;
    card.scrollIntoView({ block: "nearest" }); // on a small screen the active page stays visible
    await runPlaytest(card, settings, delay);
  }
  progress.textContent = "Done.";
}

async function runPlaytest(card, settings, delay) {
  const label = card.dataset.buildLabel.toLowerCase().replace(/[^a-z0-9]+/g, "-");
  const participant = `playtest-${label}-${Date.now()}`;
  setPlaytestState(card, "running", "Running…", "The robot is playing this page.");
  card.querySelector("[data-log]").hidden = true;
  const result = await waitForPlaytest(card.querySelector("[data-frame]"), card.dataset.buildUrl, settings.participantParameter, participant, "", delay);
  const note = result.unvisited && result.unvisited.length ? ` Not visited on this path: ${result.unvisited.join(", ")}.` : "";
  setPlaytestState(card, result.ok ? "pass" : "fail", result.ok ? "Pass" : "Fail", result.message + note);
  if (!result.log_file) return;
  await new Promise((resolve) => setTimeout(resolve, LOG_SETTLE_MS));
  await showPlaytestLog(card, settings, result.log_file);
}

/* Resolves with the robot's report. stress: ?stress= conditions the story pretends (see runtime/tiltale.js).
   A report with unsent log events counts as a failure: a study would have lost them. */
function waitForPlaytest(frame, url, parameter, participant, stress = "", delay = "") {
  return new Promise((resolve) => {
    // A long story takes minutes, so the clock measures time since the robot's last frame, not the whole run.
    let timer;
    const wait = () => {
      clearTimeout(timer);
      timer = setTimeout(() => finish({
        ok: false,
        message: `No next frame for ${PLAYTEST_STALL_MS / 1000} seconds. Open the page in the preview to see what happens.`,
      }), PLAYTEST_STALL_MS);
    };
    const finish = (result) => {
      clearTimeout(timer);
      window.removeEventListener("message", onMessage);
      if (result.unsent) Object.assign(result, { ok: false, message: `${result.message} But ${result.unsent} log event(s) never reached the server.` });
      resolve(result);
    };
    const onMessage = (event) => {
      if (event.source !== frame.contentWindow || event.data?.tiltale !== "playtest") return;
      if (event.data.progress) return wait(); // still going: the robot reached another frame
      finish(event.data);
    };
    wait();
    window.addEventListener("message", onMessage);
    const query = new URLSearchParams({ autoplay: "1", preview: "1", restart: "1", stress, [parameter]: participant });
    if (delay) query.set("delay", delay);
    frame.src = `${url}?${query}`;
  });
}

function setPlaytestState(card, state, badge, message) {
  card.dataset.state = state;
  card.querySelector("[data-state]").textContent = badge;
  card.querySelector("[data-message]").textContent = message;
}

async function showPlaytestLog(card, settings, fileName) {
  const response = await fetch(settings.logApi.replace("FILE", encodeURIComponent(fileName)));
  const { events = [], error } = await response.json();
  if (error) reportError(`Play-test log not found: ${error}`);
  const rows = events.map((event) => {
    const row = document.createElement("tr");
    for (const value of [event.seq, event.timestamp, event.event, event.frame]) row.insertCell().textContent = value ?? "";
    return row;
  });
  const box = card.querySelector("[data-log]");
  box.querySelector("[data-rows]").replaceChildren(...rows);
  box.querySelector("[data-count]").textContent = rows.length;
  box.querySelector("[data-session-link]").href = settings.sessionUrl.replace("FILE", encodeURIComponent(fileName));
  box.hidden = false;
  box.open = card.dataset.state === "fail";
}

/* Stress-test: every [data-stress] row is one robot run per selected page; a [data-result] row was
   checked by the server when the page opened. Afterwards the rows are sorted red, orange, green. */
const STATUS_ORDER = { red: 0, orange: 1, green: 2, "": 3 };
const MOBILE_BYTES_PER_SECOND = 100000; // an ordinary 3G connection; 4G is about ten times faster

async function runStresstest(page, cards, progress, delay) {
  const list = page.querySelector("[data-stresstest]");
  const rows = [...list.querySelectorAll("[data-stress]")];
  // The rows the server checked when the page opened appear now, so nothing is coloured before the run.
  for (const row of list.querySelectorAll("[data-result]")) setStressRow(row, row.dataset.result, row.dataset.result, row.dataset.resultMessage);
  let bytes = 0;
  for (const [index, row] of rows.entries()) {
    setStressRow(row, "running", "Running…", "");
    const verdicts = [];
    for (const card of cards) {
      progress.textContent = `Stress-test check ${index + 1} of ${rows.length}: ${card.dataset.buildLabel}…`;
      setPlaytestState(card, "running", "Running…", `Playing: ${row.querySelector("strong").textContent}`);
      card.scrollIntoView({ block: "nearest" }); // on a small screen the active page stays visible
      const participant = `playtest-stress-${Date.now()}`;
      const result = await waitForPlaytest(card.querySelector("[data-frame]"), card.dataset.buildUrl, page.dataset.participantParameter, participant, row.dataset.stress, delay);
      bytes = Math.max(bytes, result.bytes || 0);
      const crashed = !result.ok && result.message.startsWith("JavaScript error");
      const good = row.dataset.expect === "fail" ? crashed : result.ok;
      verdicts.push({ good, text: `${card.dataset.buildLabel}: ${result.message}` });
    }
    const failed = verdicts.filter((verdict) => !verdict.good);
    setStressRow(row, failed.length ? "red" : "green", failed.length ? "red" : "green", (failed.length ? failed : verdicts).map((verdict) => verdict.text).join(" · "));
  }
  const seconds = bytes / MOBILE_BYTES_PER_SECOND;
  const loadRow = list.querySelector("[data-load-time]");
  const status = seconds <= 20 ? "green" : seconds <= 60 ? "orange" : "red";
  setStressRow(loadRow, status, status, `${(bytes / 1048576).toFixed(1)} MB to download before the first frame: about ${Math.round(seconds)} s on 3G, ${Math.max(1, Math.round(seconds / 10))} s on 4G.`);
  progress.textContent = "Done. Red rows first.";
  for (const card of cards) setPlaytestState(card, card.dataset.state || "pass", "Done", "");
  list.replaceChildren(...[...list.children].sort((a, b) => STATUS_ORDER[a.dataset.status] - STATUS_ORDER[b.dataset.status]));
}

function setStressRow(row, state, badge, message) {
  row.dataset.status = state === "running" ? "" : state;
  const label = row.querySelector("[data-badge]");
  label.className = `badge ${state}`;
  label.textContent = badge;
  row.querySelector("[data-message]").textContent = message;
  const advice = row.querySelector(".advice");
  advice.hidden = state === "running" || state === "green";
  advice.textContent = row.dataset.advice;
}

setupToasts();
setupForms();
setupDialogs();
setupTabs();
setupMenus();
setupBlurIn();
setupMaterials();
setupContent();
setupConfig();
setupDevelop();
setupEditor();
setupFlowchart();
setupResults();
setupTest();
