/* Framework-free TilTale runtime. STORY is prepended by the generator.
 *
 * This file intentionally avoids newer browser syntax such as optional chaining,
 * Promise.allSettled(), replaceChildren(), and crypto.randomUUID(). Generated
 * stories should remain usable on older phones even though the authoring app
 * itself targets a current desktop browser.
 */
(function () {
  "use strict";

  var viewport = document.getElementById("viewport");
  var storyNode = document.getElementById("story");
  var loading = document.getElementById("loading");
  var loadingDetail = document.getElementById("loading-detail");
  var params = new URLSearchParams(window.location.search);
  var inspect = params.has("inspect") || params.has("frame");
  var storageKey = "tiltale:" + STORY.project + ":" + STORY.language + ":session";
  var frameMap = new Map(STORY.frames.map(function (frame) { return [frame.name, frame]; }));
  var session = readSession();

  viewport.style.setProperty("--letterbox", STORY.letterbox_color);
  storyNode.style.width = STORY.frame_width + "px";
  storyNode.style.height = STORY.frame_height + "px";

  /** @returns {string} */
  function uuid() {
    if (window.crypto && typeof window.crypto.randomUUID === "function") {
      return window.crypto.randomUUID();
    }
    var bytes = new Uint8Array(16);
    if (window.crypto && typeof window.crypto.getRandomValues === "function") {
      window.crypto.getRandomValues(bytes);
    } else {
      for (var i = 0; i < bytes.length; i += 1) bytes[i] = Math.floor(Math.random() * 256);
    }
    bytes[6] = (bytes[6] & 15) | 64;
    bytes[8] = (bytes[8] & 63) | 128;
    var hex = Array.prototype.map.call(bytes, function (value) { return value.toString(16).padStart(2, "0"); }).join("");
    return hex.slice(0, 8) + "-" + hex.slice(8, 12) + "-" + hex.slice(12, 16) + "-" + hex.slice(16, 20) + "-" + hex.slice(20);
  }

  /** @returns {{session_id:string,current_frame:(string|null),seq:number}} */
  function readSession() {
    if (inspect) return {session_id: "inspect-" + uuid(), current_frame: null, seq: 0};
    if (params.has("restart")) localStorage.removeItem(storageKey);
    try {
      var stored = JSON.parse(localStorage.getItem(storageKey) || "null");
      if (stored && stored.session_id) return stored;
    } catch (error) {
      // Invalid local state is safer to replace than preserve.
    }
    var created = {session_id: uuid(), current_frame: null, seq: 0};
    localStorage.setItem(storageKey, JSON.stringify(created));
    return created;
  }

  function saveSession() {
    if (!inspect) localStorage.setItem(storageKey, JSON.stringify(session));
  }

  /** @param {string} name @returns {string} */
  function cookie(name) {
    var match = document.cookie.match(new RegExp("(?:^|; )" + name + "=([^;]*)"));
    return match ? decodeURIComponent(match[1]) : "";
  }

  /** @param {string} event @param {Object<string, *>} details */
  function logEvent(event, details) {
    if (inspect) return;
    details = details || {};
    session.seq += 1;
    saveSession();
    var payload = {
      event_id: uuid(),
      session_id: session.session_id,
      seq: session.seq,
      timestamp: new Date().toISOString(),
      project: STORY.project,
      language: STORY.language,
      event: event
    };
    Object.keys(details).forEach(function (key) { payload[key] = details[key]; });

    var endpoint = STORY.log_endpoint || "";
    var localPreview = window.location.pathname.indexOf("/preview/") === 0;
    if (!endpoint && localPreview) endpoint = "/api/study-log/";
    if (!endpoint) {
      storeFallback(payload);
      return;
    }

    var headers = {"Content-Type": "application/json"};
    if (localPreview) headers["X-CSRFToken"] = cookie("csrftoken");
    fetch(endpoint, {
      method: "POST",
      headers: headers,
      body: JSON.stringify(payload),
      keepalive: true,
      credentials: localPreview ? "same-origin" : "omit"
    }).catch(function () { storeFallback(payload); });
  }

  /** @param {Object<string, *>} payload */
  function storeFallback(payload) {
    var key = storageKey + ":fallback-logs";
    try {
      var events = JSON.parse(localStorage.getItem(key) || "[]");
      events.push(payload);
      localStorage.setItem(key, JSON.stringify(events.slice(-5000)));
    } catch (error) {
      // Logging must never stop the story.
    }
  }

  /** @param {Array<Object<string, *>>} sources @returns {Object<string, *>|null} */
  function chooseSource(sources) {
    if (!sources || !sources.length) return null;
    var connection = navigator.connection || navigator.mozConnection || navigator.webkitConnection;
    var saveData = connection ? connection.saveData : false;
    var effectiveType = connection ? connection.effectiveType : "";
    var slow = effectiveType === "slow-2g" || effectiveType === "2g";
    var desired = saveData || slow
      ? 480
      : Math.min(1920, Math.ceil(Math.max(window.innerWidth, window.innerHeight) * (window.devicePixelRatio || 1)));
    for (var i = 0; i < sources.length; i += 1) {
      if (sources[i].width >= desired) return sources[i];
    }
    return sources[sources.length - 1];
  }

  /** @returns {Promise<number>} */
  function preloadBackgrounds() {
    var selected = new Map();
    STORY.frames.forEach(function (frame) {
      if (frame.background.type !== "image") return;
      var source = chooseSource(frame.background.sources);
      if (source) selected.set(source.path, source);
    });
    var sources = Array.from(selected.values());
    var loads = sources.map(function (source) {
      return new Promise(function (resolve) {
        var image = new Image();
        image.onload = resolve;
        image.onerror = resolve;
        image.src = source.path;
      });
    });
    return Promise.all(loads).then(function () {
      return sources.reduce(function (total, source) {
        return total + Number(source.bytes || 0);
      }, Number(STORY.base_bytes || 0));
    });
  }

  function sizeStory() {
    var scale = Math.min(window.innerWidth / STORY.frame_width, window.innerHeight / STORY.frame_height);
    storyNode.style.transform = "scale(" + scale + ")";
  }

  /** @param {Object<string, *>} frame @param {Object<string, *>} element @returns {HTMLElement} */
  function makeElement(frame, element) {
    var node = document.createElement(element.clickable ? "button" : "div");
    node.className = "story-element component-" + element.component;
    node.id = frame.name + "--element-" + element.id;
    node.style.left = element.x + "px";
    node.style.top = element.y + "px";
    node.style.width = element.width + "px";
    node.style.height = element.height + "px";
    node.style.fontSize = element.font_size + "px";
    if (element.fill) node.style.setProperty("--element-fill", element.fill);
    if (element.border) node.style.setProperty("--element-border", element.border);
    if (element.text_color) node.style.setProperty("--element-text", element.text_color);
    if (element.break_long_words) node.classList.add("break-words");

    var shape = document.createElement("div");
    shape.className = "component-shape";
    shape.innerHTML = element.svg;
    if (element.accepts_content) {
      var text = document.createElement("span");
      text.className = "component-text";
      text.textContent = element.text;
      shape.appendChild(text);
    }
    node.appendChild(shape);

    var delay = Number(STORY.default_delay_seconds || 0);
    if ((element.delay_mode === "fade" || element.delay_mode === "both") && delay > 0) {
      node.classList.add("delay-fade");
      node.style.setProperty("--delay", delay + "s");
    }
    if ((element.delay_mode === "disable" || element.delay_mode === "both") && delay > 0 && element.clickable) {
      node.classList.add("delay-disabled");
      window.setTimeout(function () { node.classList.add("delay-ready"); }, delay * 1000);
    }
    if (element.clickable) {
      node.addEventListener("click", function () {
        if (!element.target) return;
        logEvent("choice", {
          frame: frame.name,
          element_id: element.id,
          component: element.component,
          content_id: element.content_id,
          target: element.target
        });
        showFrame(element.target);
      });
    }
    return node;
  }

  /** @param {string} name @param {boolean=} synchronize */
  function showFrame(name, synchronize) {
    if (synchronize === undefined) synchronize = true;
    var frame = frameMap.get(name);
    if (!frame) return;
    storyNode.innerHTML = "";
    var panel = document.createElement("section");
    panel.className = "story-frame" + (frame.fade_in ? " frame-fade" : "");
    panel.id = frame.name;
    if (frame.background.type === "solid") panel.style.backgroundColor = frame.background.color;
    if (frame.background.type === "image") {
      var source = chooseSource(frame.background.sources);
      if (source) panel.style.backgroundImage = "url(\"" + source.path + "\")";
    }
    frame.elements.forEach(function (element) { panel.appendChild(makeElement(frame, element)); });
    storyNode.appendChild(panel);
    if (!inspect && synchronize) {
      session.current_frame = name;
      saveSession();
    }
    logEvent("frame", {frame: name});
  }

  window.addEventListener("resize", sizeStory, {passive: true});
  window.addEventListener("orientationchange", function () { window.setTimeout(sizeStory, 80); }, {passive: true});
  window.addEventListener("storage", function (event) {
    if (inspect || event.key !== storageKey || !event.newValue) return;
    try {
      var incoming = JSON.parse(event.newValue);
      if (incoming.current_frame && incoming.current_frame !== session.current_frame) {
        session = incoming;
        showFrame(incoming.current_frame, false);
      }
    } catch (error) {
      // Ignore corrupt state written by another tab and keep the current frame.
    }
  });
  document.addEventListener("gesturestart", function (event) { event.preventDefault(); }, {passive: false});

  function start() {
    sizeStory();
    logEvent("Loading IDN – started", {event_type: "loading_started"});
    preloadBackgrounds().then(function (totalBytes) {
      var megabytes = Number((totalBytes / 1024 / 1024).toFixed(2));
      logEvent("Loading IDN – completed (" + megabytes.toFixed(2) + " MB)", {
        event_type: "loading_completed",
        megabytes: megabytes,
        bytes: totalBytes
      });
      loadingDetail.textContent = megabytes.toFixed(2) + " MB ready";
      loading.hidden = true;
      storyNode.hidden = false;
      var forced = params.get("frame");
      var startFrame = forced && frameMap.has(forced)
        ? forced
        : (session.current_frame && frameMap.has(session.current_frame) ? session.current_frame : STORY.start_frame);
      if (startFrame) showFrame(startFrame, !forced);
      else storyNode.textContent = "This story has no frames yet.";
    });
  }

  start();
}());
