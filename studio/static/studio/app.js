/* TilTale authoring interactions.
 *
 * Keep this file dependency-free. Django owns durable state; JavaScript only
 * handles interactions that genuinely benefit from being immediate (dragging,
 * dialogs, preview sizing and flowchart layout).
 */
(() => {
  "use strict";

  /** @returns {string} */
  function csrfToken() {
    const match = document.cookie.match(/(?:^|; )csrftoken=([^;]+)/);
    return match ? decodeURIComponent(match[1]) : "";
  }

  /** @param {string} url @param {Record<string, unknown>} body */
  async function postJson(url, body) {
    const response = await fetch(url, {
      method: "POST",
      headers: {"Content-Type": "application/json", "X-CSRFToken": csrfToken()},
      body: JSON.stringify(body),
    });
    const data = await response.json().catch(() => ({}));
    if (!response.ok) throw new Error(data.error || `Request failed (${response.status}).`);
    return data;
  }

  function setupStatusBar() {
    const bar = document.querySelector("[data-status-bar]");
    if (!bar) return;
    const label = bar.querySelector("[data-status-label]");
    const detail = bar.querySelector("[data-status-detail]");

    /** @param {string} state @param {string} text @param {string} extra */
    const set = (state, text, extra = "") => {
      bar.dataset.state = state;
      label.textContent = text;
      detail.textContent = extra;
    };

    async function refresh() {
      try {
        const response = await fetch(bar.dataset.url, {cache: "no-store"});
        const data = await response.json();
        set(data.state || (response.ok ? "ready" : "error"), data.label || "TilTale", data.detail || "");
      } catch (error) {
        set("error", "Status unavailable", error instanceof Error ? error.message : "Could not reach Django.");
      }
    }

    document.addEventListener("submit", (event) => {
      if (event.target instanceof HTMLFormElement && event.target.method.toLowerCase() === "post") {
        set("busy", "Saving…", "Updating project data");
      }
    });
    window.tiltaleStatus = {set, refresh};
    refresh();
    window.setInterval(refresh, 8000);
  }

  function setupDevelop() {
    const shell = document.querySelector("[data-develop]");
    if (!shell) return;
    const panel = shell.querySelector("[data-frame-panel]");
    const iframe = shell.querySelector("[data-preview-iframe]");
    const deviceShell = shell.querySelector("[data-device-shell]");
    const stage = shell.querySelector("[data-preview-stage]");
    const search = shell.querySelector("[data-frame-search]");
    const device = shell.querySelector("[data-device-select]");
    const resizer = shell.querySelector("[data-panel-resizer]");

    shell.querySelector("[data-collapse-panel]")?.addEventListener("click", () => {
      shell.classList.add("panel-hidden");
      shell.classList.remove("mobile-panel-open");
    });
    shell.querySelector("[data-open-panel]")?.addEventListener("click", () => {
      if (window.matchMedia("(max-width: 620px)").matches) shell.classList.add("mobile-panel-open");
      else shell.classList.remove("panel-hidden");
    });

    if (resizer) {
      let pointerId = null;
      const resize = (clientX) => {
        const bounds = shell.getBoundingClientRect();
        const maximum = Math.min(620, bounds.width * .6);
        const width = Math.max(180, Math.min(maximum, clientX - bounds.left));
        shell.style.setProperty("--panel-width", `${width}px`);
      };
      resizer.addEventListener("pointerdown", (event) => {
        pointerId = event.pointerId;
        resizer.setPointerCapture(pointerId);
        resizer.classList.add("dragging");
      });
      resizer.addEventListener("pointermove", (event) => { if (event.pointerId === pointerId) resize(event.clientX); });
      resizer.addEventListener("pointerup", (event) => {
        if (event.pointerId !== pointerId) return;
        resizer.releasePointerCapture(pointerId); pointerId = null; resizer.classList.remove("dragging");
      });
      resizer.addEventListener("keydown", (event) => {
        if (event.key !== "ArrowLeft" && event.key !== "ArrowRight") return;
        event.preventDefault();
        const current = panel.getBoundingClientRect().width;
        const direction = event.key === "ArrowLeft" ? -20 : 20;
        const bounds = shell.getBoundingClientRect();
        const maximum = Math.min(620, bounds.width * .6);
        shell.style.setProperty("--panel-width", `${Math.max(180, Math.min(maximum, current + direction))}px`);
      });
    }

    search?.addEventListener("input", () => {
      const query = search.value.trim().toLowerCase();
      shell.querySelectorAll("[data-frame-name]").forEach((card) => {
        card.hidden = !card.dataset.frameName.toLowerCase().includes(query);
      });
    });

    function previewUrl(parameters = {}) {
      const url = new URL(shell.dataset.preview, window.location.origin);
      url.searchParams.set("preview", "1");
      Object.entries(parameters).forEach(([key, value]) => url.searchParams.set(key, value));
      return url.toString();
    }

    function markActive(name) {
      shell.querySelectorAll("[data-frame-name]").forEach((card) => card.classList.toggle("active", card.dataset.frameName === name));
    }

    shell.querySelectorAll("[data-view-frame]").forEach((button) => button.addEventListener("click", () => {
      const frame = button.dataset.viewFrame;
      if (iframe) iframe.src = previewUrl({frame});
      markActive(frame);
    }));
    shell.querySelector("[data-restart-preview]")?.addEventListener("click", () => {
      if (iframe) iframe.src = previewUrl({restart: String(Date.now())});
      shell.querySelectorAll("[data-frame-name]").forEach((card) => card.classList.remove("active"));
    });
    shell.querySelector("[data-language-select]")?.addEventListener("change", (event) => {
      const language = event.target.value;
      const url = new URL(window.location.href);
      url.searchParams.set("lang", language);
      window.location.href = url.toString();
    });

    function sizeDevice() {
      if (!deviceShell || !device || !stage) return;
      const [width, height] = device.value.split("x").map(Number);
      deviceShell.style.width = `${width}px`;
      deviceShell.style.height = `${height}px`;
      const availableWidth = Math.max(100, stage.clientWidth - 40);
      const availableHeight = Math.max(100, stage.clientHeight - 40);
      const scale = Math.min(1, availableWidth / width, availableHeight / height);
      deviceShell.style.transform = `scale(${scale})`;
      deviceShell.style.margin = `${(height * (scale - 1)) / 2}px ${(width * (scale - 1)) / 2}px`;
      shell.querySelectorAll("[data-thumb-canvas]").forEach((thumb) => { thumb.style.aspectRatio = `${width} / ${height}`; });
    }
    device?.addEventListener("change", sizeDevice);
    window.addEventListener("resize", sizeDevice);
    sizeDevice();
  }

  function setupEditor() {
    const editor = document.querySelector("[data-frame-editor]");
    if (!editor) return;
    const frame = editor.querySelector("[data-story-frame]");
    if (!frame) return;
    const frameWidth = Number(editor.dataset.frameWidth);
    const frameHeight = Number(editor.dataset.frameHeight);
    const language = editor.dataset.language;
    frame.style.setProperty("--frame-w", String(frameWidth));
    frame.style.setProperty("--frame-h", String(frameHeight));

    editor.querySelector("[data-editor-language]")?.addEventListener("change", (event) => {
      const url = new URL(window.location.href);
      url.searchParams.set("lang", event.target.value);
      window.location.href = url.toString();
    });

    const materialSearch = editor.querySelector("[data-material-search]");
    const materialSelect = editor.querySelector("[data-material-select]");
    const materialSort = editor.querySelector("[data-material-sort]");
    materialSearch?.addEventListener("input", () => {
      const query = materialSearch.value.toLowerCase();
      Array.from(materialSelect?.options || []).forEach((option, index) => {
        if (index > 0) option.hidden = !option.text.toLowerCase().includes(query);
      });
    });
    materialSort?.addEventListener("change", () => {
      if (!materialSelect) return;
      const selected = materialSelect.value;
      const placeholder = materialSelect.options[0];
      const options = Array.from(materialSelect.options).slice(1);
      options.sort((left, right) => materialSort.value === "newest"
        ? Number(right.dataset.modified) - Number(left.dataset.modified)
        : left.dataset.name.localeCompare(right.dataset.name));
      materialSelect.replaceChildren(placeholder, ...options);
      materialSelect.value = selected;
    });

    let activeContentInput = null;
    const contentDialog = editor.querySelector("[data-content-dialog]");
    editor.querySelectorAll("[data-edit-element]").forEach((button) => {
      const open = () => document.getElementById(`element-dialog-${button.dataset.editElement}`)?.showModal();
      button.addEventListener("click", (event) => { event.stopPropagation(); open(); });
      button.closest("[data-element-id]")?.addEventListener("contextmenu", (event) => { event.preventDefault(); open(); });
    });
    editor.querySelectorAll("[data-close-dialog]").forEach((button) => button.addEventListener("click", () => button.closest("dialog")?.close()));
    editor.querySelectorAll("[data-open-content]").forEach((button) => button.addEventListener("click", () => {
      activeContentInput = button.closest("form")?.querySelector("input[name='content_id']") || null;
      contentDialog?.showModal();
    }));
    editor.querySelector("[data-close-content]")?.addEventListener("click", () => contentDialog?.close());
    editor.querySelectorAll("[data-pick-content]").forEach((button) => button.addEventListener("click", () => {
      if (activeContentInput) activeContentInput.value = button.dataset.pickContent;
      contentDialog?.close();
    }));
    editor.querySelector("[data-content-search]")?.addEventListener("input", (event) => {
      const query = event.target.value.trim().toLowerCase();
      editor.querySelectorAll("[data-content-row]").forEach((row) => { row.hidden = !row.dataset.search.toLowerCase().includes(query); });
    });

    editor.querySelectorAll("[data-color-toggle]").forEach((checkbox) => {
      const fields = checkbox.closest("fieldset")?.querySelector(".color-fields");
      const update = () => { if (fields) fields.style.opacity = checkbox.checked ? "1" : ".45"; };
      checkbox.addEventListener("change", update); update();
    });

    function updateElementTextSizes() {
      const scale = frame.clientWidth / frameWidth;
      editor.querySelectorAll("[data-element-id]").forEach((element) => {
        const text = element.querySelector(".component-text");
        const font = Number(getComputedStyle(element).getPropertyValue("--font"));
        if (text && Number.isFinite(font)) text.style.fontSize = `${Math.max(6, font * scale)}px`;
      });
    }
    new ResizeObserver(updateElementTextSizes).observe(frame);
    updateElementTextSizes();

    editor.querySelectorAll("[data-element-id]").forEach((element) => {
      let pointerId = null;
      let moved = false;
      const onMove = (event) => {
        if (event.pointerId !== pointerId) return;
        const bounds = frame.getBoundingClientRect();
        const x = Math.max(0, Math.min(frameWidth, (event.clientX - bounds.left) / bounds.width * frameWidth));
        const y = Math.max(0, Math.min(frameHeight, (event.clientY - bounds.top) / bounds.height * frameHeight));
        element.style.setProperty("--x", String(x));
        element.style.setProperty("--y", String(y));
        element.dataset.x = String(x); element.dataset.y = String(y); moved = true;
      };
      element.addEventListener("pointerdown", (event) => {
        if (event.target.closest("button")) return;
        pointerId = event.pointerId; moved = false; element.setPointerCapture(pointerId); element.classList.add("dragging");
      });
      element.addEventListener("pointermove", onMove);
      element.addEventListener("pointerup", async (event) => {
        if (event.pointerId !== pointerId) return;
        element.classList.remove("dragging"); element.releasePointerCapture(pointerId); pointerId = null;
        if (!moved) return;
        const id = element.dataset.elementId;
        window.tiltaleStatus?.set("busy", "Saving position…", `Element #${id}`);
        try {
          await postJson(`/api/elements/${id}/position/`, {x: Number(element.dataset.x), y: Number(element.dataset.y), language});
          const dialog = document.getElementById(`element-dialog-${id}`);
          if (dialog) { dialog.querySelector("input[name='x']").value = Number(element.dataset.x).toFixed(1); dialog.querySelector("input[name='y']").value = Number(element.dataset.y).toFixed(1); }
          window.tiltaleStatus?.refresh();
        } catch (error) { window.tiltaleStatus?.set("error", "Position not saved", error.message); }
      });
    });
  }

  function setupFlowchart() {
    const root = document.querySelector("[data-flowchart]");
    if (!root) return;
    const viewport = root.querySelector("[data-flow-viewport]");
    const world = root.querySelector("[data-flow-world]");
    const lines = root.querySelector("[data-flow-lines]");
    const inspector = root.querySelector("[data-flow-inspector]");
    const nodes = JSON.parse(document.getElementById("flow-nodes-data")?.textContent || "[]");
    const edges = JSON.parse(document.getElementById("flow-edges-data")?.textContent || "[]");
    const nodeData = new Map(nodes.map((node) => [node.name, node]));
    let zoom = 1;

    function drawLines() {
      lines.replaceChildren();
      const ns = "http://www.w3.org/2000/svg";
      const defs = document.createElementNS(ns, "defs");
      defs.innerHTML = '<marker id="arrow" markerWidth="8" markerHeight="8" refX="7" refY="4" orient="auto"><path d="M0,0 L8,4 L0,8 Z" fill="#6a737d"/></marker>';
      lines.append(defs);
      edges.forEach((edge) => {
        const source = root.querySelector(`[data-flow-node="${CSS.escape(edge.source)}"]`);
        const target = root.querySelector(`[data-flow-node="${CSS.escape(edge.target)}"]`);
        if (!source || !target) return;
        const x1 = Number(source.dataset.x), y1 = Number(source.dataset.y), x2 = Number(target.dataset.x), y2 = Number(target.dataset.y);
        const line = document.createElementNS(ns, "line");
        line.setAttribute("x1", x1); line.setAttribute("y1", y1); line.setAttribute("x2", x2); line.setAttribute("y2", y2);
        line.setAttribute("stroke", "#6a737d"); line.setAttribute("stroke-width", "2"); line.setAttribute("marker-end", "url(#arrow)");
        lines.append(line);
      });
    }

    function select(name) {
      root.querySelectorAll("[data-flow-node]").forEach((node) => node.classList.toggle("selected", node.dataset.flowNode === name));
      inspector.hidden = false; inspector.querySelector("[data-flow-title]").textContent = name;
      const data = nodeData.get(name); inspector.querySelector("[data-flow-edit]").href = data?.edit_url || "#";
      const list = inspector.querySelector("[data-flow-connections]"); list.replaceChildren(); list.className = "connection-list";
      const outgoing = edges.filter((edge) => edge.source === name);
      if (!outgoing.length) list.textContent = "No outgoing connections yet.";
      outgoing.forEach((edge) => {
        const div = document.createElement("div"); div.className = "connection";
        div.textContent = `${edge.label || "Clickable element"} → ${edge.target}`; list.append(div);
      });
      const selected = root.querySelector(`[data-flow-node="${CSS.escape(name)}"]`);
      if (selected && viewport) {
        setZoom(Math.max(zoom, 1.2));
        const x = Number(selected.dataset.x) * zoom;
        const y = Number(selected.dataset.y) * zoom;
        viewport.scrollTo({left: Math.max(0, x - viewport.clientWidth / 2), top: Math.max(0, y - viewport.clientHeight / 2), behavior: "smooth"});
      }
    }
    root.querySelector("[data-flow-close]")?.addEventListener("click", () => { inspector.hidden = true; root.querySelectorAll(".selected").forEach((node) => node.classList.remove("selected")); });
    root.querySelector("[data-flow-language]")?.addEventListener("change", (event) => { const url = new URL(location.href); url.searchParams.set("lang", event.target.value); location.href = url; });

    root.querySelectorAll("[data-flow-node]").forEach((node) => {
      let pointerId = null, dragged = false;
      node.addEventListener("click", () => { if (!dragged) select(node.dataset.flowNode); });
      node.addEventListener("pointerdown", (event) => { pointerId = event.pointerId; dragged = false; node.setPointerCapture(pointerId); });
      node.addEventListener("pointermove", (event) => {
        if (event.pointerId !== pointerId) return;
        const bounds = world.getBoundingClientRect();
        const x = (event.clientX - bounds.left) / zoom, y = (event.clientY - bounds.top) / zoom;
        node.dataset.x = String(Math.max(50, x)); node.dataset.y = String(Math.max(40, y));
        node.style.left = `${node.dataset.x}px`; node.style.top = `${node.dataset.y}px`; dragged = true; drawLines();
      });
      node.addEventListener("pointerup", async (event) => {
        if (event.pointerId !== pointerId) return; node.releasePointerCapture(pointerId); pointerId = null;
        if (!dragged) return;
        try { await postJson(`/api/frames/${encodeURIComponent(node.dataset.flowNode)}/flow-position/`, {x: Number(node.dataset.x), y: Number(node.dataset.y)}); window.tiltaleStatus?.refresh(); }
        catch (error) { window.tiltaleStatus?.set("error", "Flow position not saved", error.message); }
      });
    });

    function setZoom(next) { zoom = Math.max(.5, Math.min(2, next)); world.style.transform = `scale(${zoom})`; root.querySelector("[data-flow-zoom-label]").textContent = `${Math.round(zoom * 100)}%`; }
    root.querySelectorAll("[data-flow-zoom]").forEach((button) => button.addEventListener("click", () => setZoom(zoom + (button.dataset.flowZoom === "in" ? .1 : -.1))));
    drawLines();
  }

  document.addEventListener("DOMContentLoaded", () => {
    setupStatusBar(); setupDevelop(); setupEditor(); setupFlowchart();
  });
})();
