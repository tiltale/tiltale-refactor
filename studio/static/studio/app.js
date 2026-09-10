// TilTale studio behavior. Each setup function returns early when its page is not open.
"use strict";

const PLAYTEST_TIMEOUT_MS = 60000;
const LOG_SETTLE_MS = 1000; // the last log requests of a play-test may still be in flight
const DRAG_THRESHOLD_PX = 4;
const TOAST_MS = 6000;
const STATUS_POLL_MS = 5000;
const STAGE_MARGIN_PX = 32;

function showToast(message, kind = "info") {
  const toast = document.createElement("div");
  toast.className = `toast ${kind}`;
  toast.setAttribute("role", "status");
  toast.textContent = message;
  document.querySelector(".toasts").append(toast);
  setTimeout(() => toast.remove(), TOAST_MS);
}

async function postJson(url, csrfToken, body) {
  const response = await fetch(url, {
    method: "POST",
    headers: { "Content-Type": "application/json", "X-CSRFToken": csrfToken },
    body: JSON.stringify(body),
  });
  if (!response.ok) throw new Error((await response.json()).error || `HTTP ${response.status}`);
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

function setupStatusBar() {
  const bar = document.querySelector("[data-status-bar]");
  const render = (status) => {
    bar.dataset.state = status.state;
    bar.querySelector("[data-status-label]").textContent = status.label;
    bar.querySelector("[data-status-detail]").textContent = status.detail;
  };
  const offline = { state: "error", label: "Studio not reachable", detail: "Is python manage.py runserver still running?" };
  const refresh = () => fetch(bar.dataset.url).then((response) => response.json()).then(render, () => render(offline));
  refresh();
  setInterval(refresh, STATUS_POLL_MS);
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

function setupResults() {
  const toggle = document.querySelector("[data-hide-test-sessions]");
  if (!toggle) return;
  toggle.addEventListener("change", () => {
    for (const row of document.querySelectorAll("tr[data-kind]")) row.hidden = toggle.checked && row.dataset.kind !== "study";
  });
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
    const button = event.target.closest("[data-view-frame]");
    if (button && preview) preview.src = button.dataset.viewFrame;
  });
  page.querySelector("[data-frame-filter]").addEventListener("input", (event) => {
    const query = event.target.value.trim().toLowerCase();
    for (const thumb of page.querySelectorAll("[data-frame-name]")) thumb.hidden = !thumb.dataset.frameName.includes(query);
  });
}

function setupEditor() {
  const page = document.querySelector("[data-editor]");
  if (!page) return;
  const stage = page.querySelector("[data-canvas-stage]");
  const canvas = page.querySelector("[data-canvas]");
  const picker = document.getElementById("content-picker");
  const view = { scale: 1 };
  let contentInput = null;

  const fitCanvas = () => {
    view.scale = Math.min(
      (stage.clientWidth - STAGE_MARGIN_PX) / Number(canvas.dataset.width),
      (stage.clientHeight - STAGE_MARGIN_PX) / Number(canvas.dataset.height),
    );
    canvas.style.transform = `translate(-50%, -50%) scale(${view.scale})`;
  };
  new ResizeObserver(fitCanvas).observe(stage);
  for (const node of canvas.querySelectorAll("[data-element]")) makeElementDraggable(node, page, view);

  const backgroundType = page.querySelector("[name=background_type]");
  const showBackgroundFields = () => {
    for (const group of page.querySelectorAll("[data-show-when]")) group.hidden = group.dataset.showWhen !== backgroundType.value;
  };
  backgroundType.addEventListener("change", showBackgroundFields);
  showBackgroundFields();

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
  picker.querySelector("[data-content-filter]").addEventListener("input", (event) => {
    const query = event.target.value.trim().toLowerCase();
    for (const row of picker.querySelectorAll("[data-content-id]")) row.hidden = !row.textContent.toLowerCase().includes(query);
  });
}

function makeElementDraggable(node, page, view) {
  const dialog = document.getElementById(`element-${node.dataset.element}`);
  node.addEventListener("keydown", (event) => {
    if (event.key === "Enter") dialog.showModal();
  });
  node.addEventListener("pointerdown", (event) => {
    const start = { x: event.clientX, y: event.clientY, left: parseFloat(node.style.left), top: parseFloat(node.style.top) };
    let moved = false;
    node.setPointerCapture(event.pointerId);
    const onMove = (move) => {
      const dx = (move.clientX - start.x) / view.scale;
      const dy = (move.clientY - start.y) / view.scale;
      moved = moved || Math.hypot(dx, dy) * view.scale > DRAG_THRESHOLD_PX;
      node.style.left = `${Math.round(start.left + dx)}px`;
      node.style.top = `${Math.round(start.top + dy)}px`;
    };
    const onUp = () => {
      node.removeEventListener("pointermove", onMove);
      node.removeEventListener("pointerup", onUp);
      if (!moved) {
        dialog.showModal();
        return;
      }
      saveElementPosition(node, page, dialog);
    };
    node.addEventListener("pointermove", onMove);
    node.addEventListener("pointerup", onUp);
  });
}

async function saveElementPosition(node, page, dialog) {
  const x = parseFloat(node.style.left);
  const y = parseFloat(node.style.top);
  // Keep the settings dialog in sync, or saving it later would move the element back.
  dialog.querySelector("[name=x]").value = x;
  dialog.querySelector("[name=y]").value = y;
  try {
    await postJson(node.dataset.positionUrl, page.dataset.csrf, { x, y, language: page.dataset.language });
  } catch (error) {
    showToast(`Position not saved: ${error.message}`, "error");
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
    for (const [name, node] of nodes) node.classList.toggle("is-selected", selected.has(name));
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
  const save = async (names) => {
    const positions = names.map((name) => ({ name, ...position(nodes.get(name)) }));
    try {
      await postJson(page.dataset.saveUrl, page.dataset.csrf, { positions });
    } catch (error) {
      showToast(`Layout not saved: ${error.message}`, "error");
    }
  };

  const dragNodes = (event, node) => {
    const starts = new Map([...selected].map((name) => [name, position(nodes.get(name))]));
    const origin = { x: event.clientX, y: event.clientY };
    let moved = false;
    trackPointer(viewport, event, (move) => {
      const dx = (move.clientX - origin.x) / view.zoom;
      const dy = (move.clientY - origin.y) / view.zoom;
      moved = moved || Math.hypot(dx, dy) * view.zoom > DRAG_THRESHOLD_PX;
      for (const [name, start] of starts) place(nodes.get(name), Math.round(start.x + dx), Math.round(start.y + dy));
      drawEdges();
    }, () => {
      if (moved) return save([...starts.keys()]);
      inspect(node);
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
    const name = node.dataset.node;
    if (event.shiftKey) {
      if (selected.has(name)) selected.delete(name);
      else selected.add(name);
      return markSelection();
    }
    if (!selected.has(name)) selected.clear();
    selected.add(name);
    markSelection();
    dragNodes(event, node);
  });
  viewport.addEventListener("dblclick", (event) => {
    const node = event.target.closest("[data-node]");
    if (node) window.location = node.dataset.editUrl;
  });
  viewport.addEventListener("keydown", (event) => {
    const node = event.target.closest("[data-node]");
    if (node && event.key === "Enter") window.location = node.dataset.editUrl;
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
  const source = nodes.get(edge.source);
  const target = nodes.get(edge.target);
  if (!source || (!target && !edge.end)) return null;
  const start = position(source);
  const x1 = start.x + source.offsetWidth;
  const y1 = start.y + source.offsetHeight / 2;
  const group = svgElement("g", { class: `edge ${edgeKind(edge)}` });
  group.append(svgElement("title", {}));
  group.firstChild.textContent = `${edge.label} → ${edgeDestination(edge)}`;
  if (!target) {
    group.append(svgElement("path", { d: `M${x1} ${y1} h36`, "marker-end": "url(#flow-arrow)" }));
    group.append(svgElement("circle", { cx: x1 + 46, cy: y1, r: 8 }));
    return group;
  }
  const end = position(target);
  const x2 = end.x;
  const y2 = end.y + target.offsetHeight / 2;
  const bend = Math.max(40, Math.abs(x2 - x1) / 2);
  group.append(svgElement("path", { d: `M${x1} ${y1} C${x1 + bend} ${y1} ${x2 - bend} ${y2} ${x2} ${y2}`, "marker-end": "url(#flow-arrow)" }));
  return group;
}

function edgeKind(edge) {
  if (edge.end) return "end";
  if (edge.language) return "language";
  return "frame";
}

function edgeDestination(edge) {
  return { end: "End story", language: `${edge.language} story`, frame: edge.target }[edgeKind(edge)];
}

function showInspector(page, node, edges) {
  const inspector = page.querySelector("[data-inspector]");
  const frame = inspector.querySelector("[data-inspector-frame]");
  const name = node.dataset.node;
  const frameUrl = `${node.dataset.previewUrl}?inspect=1&frame=${encodeURIComponent(name)}`;
  inspector.hidden = false;
  inspector.querySelector("[data-inspector-title]").textContent = name;
  inspector.querySelector("[data-inspector-edit]").href = node.dataset.editUrl;
  if (frame) frame.src = frameUrl;
  const items = edges.filter((edge) => edge.source === name).map((edge) => {
    const item = document.createElement("li");
    item.textContent = `${edge.label} → ${edgeDestination(edge)}`;
    item.addEventListener("mouseenter", () => { if (frame) frame.src = `${frameUrl}&element=${edge.element_id}`; });
    return item;
  });
  if (!items.length) items.push(Object.assign(document.createElement("li"), { className: "muted", textContent: "No buttons lead anywhere yet." }));
  inspector.querySelector("[data-inspector-links]").replaceChildren(...items);
}

function setupPlaytest() {
  const grid = document.querySelector("[data-playtest]");
  const runButton = document.querySelector("[data-run-all]");
  if (!grid || !runButton) return;
  runButton.addEventListener("click", async () => {
    runButton.disabled = true;
    for (const card of grid.querySelectorAll("[data-build-url]")) await runPlaytest(card, grid.dataset);
    runButton.disabled = false;
  });
}

async function runPlaytest(card, settings) {
  const label = card.dataset.buildLabel.toLowerCase().replace(/[^a-z0-9]+/g, "-");
  const participant = `playtest-${label}-${Date.now()}`;
  setPlaytestState(card, "running", "Running…", "The robot is playing this page.");
  card.querySelector("[data-log]").hidden = true;
  const result = await waitForPlaytest(card.querySelector("[data-frame]"), card.dataset.buildUrl, settings.participantParameter, participant);
  const note = result.unvisited && result.unvisited.length ? ` Not visited on this path: ${result.unvisited.join(", ")}.` : "";
  setPlaytestState(card, result.ok ? "pass" : "fail", result.ok ? "Pass" : "Fail", result.message + note);
  if (!result.log_file) return;
  await new Promise((resolve) => setTimeout(resolve, LOG_SETTLE_MS));
  await showPlaytestLog(card, settings, result.log_file);
}

function waitForPlaytest(frame, url, parameter, participant) {
  return new Promise((resolve) => {
    const finish = (result) => {
      clearTimeout(timer);
      window.removeEventListener("message", onMessage);
      resolve(result);
    };
    const onMessage = (event) => {
      if (event.source !== frame.contentWindow || event.data?.tiltale !== "playtest") return;
      finish(event.data);
    };
    const timer = setTimeout(() => finish({ ok: false, message: "No result within 60 seconds. Open the page in the preview to see what happens." }), PLAYTEST_TIMEOUT_MS);
    window.addEventListener("message", onMessage);
    frame.src = `${url}?${new URLSearchParams({ autoplay: "1", preview: "1", restart: "1", [parameter]: participant })}`;
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
  if (error) showToast(`Log not found: ${error}`, "error");
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

setupToasts();
setupForms();
setupDialogs();
setupStatusBar();
setupConfig();
setupResults();
setupDevelop();
setupEditor();
setupFlowchart();
setupPlaytest();
