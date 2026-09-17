/* TilTale story runtime. Every generated page loads its own story.js (var STORY)
 * and then this shared file.
 *
 * Browser target: iOS Safari 12+ and Chrome 61+ (phones from about 2013 on).
 * Hence ES5 syntax plus Promise, fetch and URLSearchParams only.
 *
 * URL parameters
 *   ?<STORY.participant_parameter>=ID  use an external participant ID (e.g. Qualtrics ?ppn=...)
 *   ?restart     forget this browser's progress and start over (also <root>/restart/); the
 *                parameter is removed from the address again, so a refresh continues normally
 *   ?preview     opened inside the TilTale studio (no real redirect at the end)
 *   ?frame=NAME  start at a frame (studio "View" button)
 *   ?inspect     static thumbnail: no splash, no logging, no clicks
 *   ?element=ID  highlight one element (studio flowchart)
 *   ?autoplay    play-test robot: clicks through and reports to the studio
 *
 * Frame kinds (STORY.frames[].kind): "frame", "picker" and "minigame" show their elements;
 * "document" shows one zoomable image; "validation" is never shown: its rules on the global
 * variables (STORY.variables, kept in state.variables) decide the next frame.
 *
 * Offline: every image of the story is downloaded before the first frame (progress bar), kept in
 * memory while playing and, where the browser allows (HTTPS), in its Cache Storage so a restart
 * does not download it again. Log events are queued on the device and sent one by one; a lost
 * connection only delays them (see the logging section).
 */
(function () {
  "use strict";

  var params = new URLSearchParams(window.location.search);
  var preview = params.has("preview");
  var inspect = params.has("inspect");
  var autoplay = params.has("autoplay");
  var restart = params.has("restart");
  var forcedFrame = params.get("frame");
  var storyNode = document.getElementById("story");
  var prefix = "tiltale:" + STORY.project + ":";
  var frames = {};
  STORY.frames.forEach(function (frame) { frames[frame.name] = frame; });

  // ------------------------------------------------------------- storage
  // Private browsing on older Safari throws on every write, so storage is
  // best-effort: the story must keep working without it.
  function storageArea(name) {
    try { return window[name]; } catch (error) { return null; }
  }
  var local = storageArea("localStorage");
  var session = storageArea("sessionStorage");

  function read(area, key) {
    try { return JSON.parse(area.getItem(key)); } catch (error) { return null; }
  }
  function write(area, key, value) {
    try { area.setItem(key, JSON.stringify(value)); } catch (error) { /* best-effort */ }
  }
  function forget(area, key) {
    try { area.removeItem(key); } catch (error) { /* best-effort */ }
  }

  function randomId() {
    var bytes = new Uint8Array(8);
    if (window.crypto && window.crypto.getRandomValues) window.crypto.getRandomValues(bytes);
    else for (var i = 0; i < bytes.length; i += 1) bytes[i] = Math.floor(Math.random() * 256);
    return Array.prototype.map.call(bytes, function (b) { return (b < 16 ? "0" : "") + b.toString(16); }).join("");
  }

  /* Same rule as log.php and the studio: unsafe characters become "-". */
  function safeName(value) {
    return String(value).replace(/[^A-Za-z0-9_-]+/g, "-").replace(/^-+|-+$/g, "").slice(0, 80);
  }

  // ------------------------------------------------------------- who and which visit
  var participantKey = prefix + "participant";
  if (restart) forget(local, participantKey);
  var participantId = (params.get(STORY.participant_parameter) || "").trim();
  if (!participantId) {
    participantId = read(local, participantKey) || (preview ? "preview-" : "anon-") + randomId();
    write(local, participantKey, participantId);
  }

  var stateKey = prefix + "state:" + participantId;  // {language, frame, previous, variables}: resume after a crash
  if (restart) forget(local, stateKey);
  var state = read(local, stateKey) || {};
  state.variables = state.variables || {};
  for (var name in STORY.variables) {  // a variable added after this reader started gets its initial value
    if (Object.prototype.hasOwnProperty.call(STORY.variables, name) && !(name in state.variables)) state.variables[name] = STORY.variables[name];
  }
  if (restart && window.history.replaceState) {
    params["delete"]("restart");
    window.history.replaceState(null, "", window.location.pathname + (params.toString() ? "?" + params : ""));
  }

  // A visit is one page load and gets its own log file. The language picker
  // hands its visit to the language page so that choice and story share a file.
  var handoffKey = prefix + "handoff";
  var handoff = read(session, handoffKey);
  forget(session, handoffKey);
  var visit = handoff && handoff.participant_id === participantId
    ? handoff
    : {participant_id: participantId, visit_id: new Date().toISOString().replace(/[-:]|\.\d+/g, "") + "-" + randomId().slice(0, 4), seq: 0};

  function saveState() {
    if (!inspect) write(local, stateKey, state);
  }

  /* What the header of a log file records about the device (see ETHICS.md): the local time, the screen
     and window size, and what the browser says about itself. No IP address is ever recorded. */
  function visitHeader() {
    var now = new Date();
    var offset = -now.getTimezoneOffset();
    var pad = function (n) { return (n < 10 ? "0" : "") + n; };
    var data = navigator.userAgentData || {};
    return {
      local_time: now.getFullYear() + "-" + pad(now.getMonth() + 1) + "-" + pad(now.getDate()) + "T" + pad(now.getHours()) + ":" + pad(now.getMinutes()) + ":" + pad(now.getSeconds())
        + (offset < 0 ? "-" : "+") + pad(Math.floor(Math.abs(offset) / 60)) + ":" + pad(Math.abs(offset) % 60),
      screen: {width: window.screen.width, height: window.screen.height, pixel_ratio: window.devicePixelRatio || 1},
      window: {width: window.innerWidth, height: window.innerHeight},
      touch: "ontouchstart" in window || navigator.maxTouchPoints > 0,
      user_agent: navigator.userAgent,
      tiltale_version: STORY.version,
      platform: data.platform || navigator.platform || null,
      mobile: typeof data.mobile === "boolean" ? data.mobile : null,
      brands: data.brands ? data.brands.map(function (b) { return b.brand + " " + b.version; }) : null
    };
  }

  // ------------------------------------------------------------- logging
  /* Every event first goes into a queue on the device (mirrored to localStorage, so it survives a
     closed browser), then the queue is sent to log.php one event at a time, oldest first. A failed
     send (offline, slow, server error) is retried a few seconds later, at every next event and when
     the device reports it is online again; whatever is left is sent the next time the story is opened
     in this browser. Sending is a background request, so the story never waits for it. */
  var queueKey = prefix + "unsent";
  var unsent = read(local, queueKey) || [];
  var sending = false;
  var offline = window.location.protocol === "file:";

  function flushUnsent() {
    if (sending || offline || !unsent.length) return;
    sending = true;
    fetch(STORY.root + "log.php", {
      method: "POST",
      headers: {"Content-Type": "application/json"},
      body: JSON.stringify(unsent[0]),
      keepalive: true
    }).then(function (response) { return response.ok; }, function () { return false; }).then(function (sent) {
      sending = false;
      if (!sent) return window.setTimeout(flushUnsent, 5000);
      unsent.shift();
      write(local, queueKey, unsent);
      flushUnsent();
    });
  }
  window.addEventListener("online", flushUnsent);

  function log(event, details) {
    if (inspect) return;
    visit.seq += 1;
    var payload = {
      participant_id: participantId,
      visit_id: visit.visit_id,
      seq: visit.seq,
      timestamp: new Date().toISOString(),
      project: STORY.project,
      language: STORY.language || null,
      event: event
    };
    for (var key in details) if (Object.prototype.hasOwnProperty.call(details, key)) payload[key] = details[key];
    unsent.push(payload);
    write(local, queueKey, unsent.slice(-2000));
    flushUnsent();
  }

  /* Calls back once every event is on the server. Used before the finish redirect: the survey behind
     it needs a connection anyway, so waiting for one costs the reader nothing. */
  function whenLogged(then, waited) {
    if (!unsent.length || offline) return then();
    if (waited >= 2000) notice("Saving\u2026 please keep this page open.");
    window.setTimeout(function () { whenLogged(then, (waited || 0) + 500); }, 500);
  }

  // ------------------------------------------------------------- rendering
  var storyScale = 1;

  function scaleStory() {
    storyScale = Math.min(window.innerWidth / STORY.frame_width, window.innerHeight / STORY.frame_height);
    storyNode.style.transform = "translate(-50%, -50%) scale(" + storyScale + ")";
  }

  function chooseSource(sources) {
    if (!sources || !sources.length) return null;
    var connection = navigator.connection || {};
    var slow = connection.saveData || connection.effectiveType === "slow-2g" || connection.effectiveType === "2g";
    var wanted = slow ? 480 : Math.min(1920, Math.max(window.innerWidth, window.innerHeight) * (window.devicePixelRatio || 1));
    for (var i = 0; i < sources.length; i += 1) if (sources[i].width >= wanted) return sources[i];
    return sources[sources.length - 1];
  }

  function makeElement(frame, element) {
    var node = document.createElement(element.clickable ? "button" : "div");
    node.className = "story-element " + (element.image ? "story-image" : "component-" + element.component) + (element.break_long_words ? " break-words" : "");
    node.id = frame.name + "--" + element.id;
    node.style.left = element.x + "px";
    node.style.top = element.y + "px";
    var component = STORY.components[element.component] || {};
    if (component.auto_height) node.className += " auto-height";
    if (component.tail) node.setAttribute("data-tail", component.tail);
    node.style.width = element.width + "px";
    node.style[component.auto_height ? "minHeight" : "height"] = element.height + "px";
    node.style.fontSize = element.font_size + "px";
    if (element.tail_x !== null && element.tail_x !== undefined) {
      node.style.setProperty("--tail-x", element.tail_x + "px");
      node.style.setProperty("--tail-y", element.tail_y + "px");
    }
    if (element.fill) node.style.setProperty("--element-fill", element.fill);
    if (element.border) node.style.setProperty("--element-border", element.border);
    if (element.text_color) node.style.setProperty("--element-text", element.text_color);
    if (params.get("element") === String(element.id)) node.className += " inspect-highlight";

    node.appendChild(element.image ? makeImage(element.image) : makeShape(element));
    if (element.text) node.appendChild(makeText(element.text));

    var delay = STORY.default_delay_seconds;
    if ((element.delay_mode === "fade" || element.delay_mode === "both") && delay > 0) {
      node.className += " delay-fade";
      node.style.animationDelay = delay + "s";
    }
    if ((element.delay_mode === "disable" || element.delay_mode === "both") && delay > 0 && element.clickable) {
      node.disabled = true;
      window.setTimeout(function () { node.disabled = false; }, delay * 1000);
    }
    if (element.clickable) node.addEventListener("click", function () { activate(frame, element); });
    return node;
  }

  function makeShape(element) {
    var shape = document.createElement("div");
    shape.className = "component-shape";
    shape.innerHTML = (STORY.components[element.component] || {}).svg || "";
    return shape;
  }

  /* {score} in a text becomes the variable's current value; unknown names stay as written. */
  function fillText(value) {
    return value.replace(/\{([A-Za-z][A-Za-z0-9_]*)\}/g, function (match, name) {
      return name in state.variables ? String(state.variables[name]) : match;
    });
  }

  /* One <span> per line, so a line break typed in content.xlsx becomes a line break with some space. */
  function makeText(value) {
    var text = document.createElement("span");
    text.className = "component-text";
    text.setAttribute("data-template", value);
    fillText(value).split("\n").forEach(function (line) {
      var span = document.createElement("span");
      span.textContent = line;
      text.appendChild(span);
    });
    return text;
  }

  /* Re-render every text with a placeholder after a variable changed (scoreboards update at once). */
  function refreshTexts() {
    var texts = storyNode.querySelectorAll(".component-text[data-template]");
    Array.prototype.forEach.call(texts, function (text) {
      if (text.getAttribute("data-template").indexOf("{") === -1) return;
      text.parentNode.replaceChild(makeText(text.getAttribute("data-template")), text);
    });
    if (window.TilTaleBubbles && storyNode.lastChild) TilTaleBubbles.draw(storyNode.lastChild);
  }

  /* The downloaded copy in memory (see preloadImages), else the file on the server. */
  function imageUrl(source) {
    return loaded[source.path] || STORY.root + source.path;
  }

  function makeImage(sources) {
    var image = document.createElement("img");
    var source = chooseSource(sources);
    image.alt = "";
    if (source) image.src = imageUrl(source);
    return image;
  }

  function makePanel(frame) {
    var panel = document.createElement("section");
    panel.className = "story-frame";
    panel.id = frame.name;
    if (frame.background.type === "solid") panel.style.backgroundColor = frame.background.color;
    var source = frame.background.type === "image" ? chooseSource(frame.background.sources) : null;
    if (source) panel.style.backgroundImage = "url(\"" + imageUrl(source) + "\")";
    var box = frame.background.box;  // without one, style.css makes the image cover the frame
    if (box) {
      panel.style.backgroundSize = box.width + "px " + box.height + "px";
      panel.style.backgroundPosition = (box.x - box.width / 2) + "px " + (box.y - box.height / 2) + "px";
    }
    frame.elements.forEach(function (element) { panel.appendChild(makeElement(frame, element)); });
    return panel;
  }

  /* A document is its image, as sharp as available, fitted into the frame; makeViewer then zooms it to the screen. */
  function makeDocumentPanel(frame) {
    var panel = document.createElement("section");
    panel.className = "story-frame document-image";
    panel.id = frame.name;
    var sources = frame.background.sources || [];
    var source = sources[sources.length - 1];
    var image = document.createElement("img");
    image.alt = "";
    if (source) {
      image.src = imageUrl(source);
      var scale = Math.min(STORY.frame_width / source.width, STORY.frame_height / source.height);
      image.style.width = (source.width * scale) + "px";
      image.style.height = (source.height * scale) + "px";
    }
    panel.appendChild(image);
    return panel;
  }

  function makeValidationPanel(frame) {  // only the studio's thumbnails ever see this
    var panel = document.createElement("section");
    panel.className = "story-frame validation-point";
    panel.id = frame.name;
    panel.textContent = "Validation point: " + frame.rules.map(function (rule) { return rule.label; }).join(" · ");
    return panel;
  }

  function showFrame(name, details) {
    var frame = frames[name];
    if (!frame) return;
    if (frame.kind === "validation" && !inspect) return decide(frame);
    var panel = frame.kind === "validation" ? makeValidationPanel(frame) : frame.kind === "document" ? makeDocumentPanel(frame) : makePanel(frame);
    var shown = storyNode.lastChild;
    if (frame.fade_in && !inspect) {
      panel.className += " frame-fade";
      panel.style.animationDuration = STORY.default_delay_seconds + "s";
    }
    storyNode.appendChild(panel);
    // A crossfade keeps the previous frame behind the new one until it is fully in; from black, it goes at once.
    var crossfade = shown && frame.fade_in && !frame.fade_from_black && !inspect;
    if (crossfade) window.setTimeout(function () { storyNode.removeChild(shown); }, STORY.default_delay_seconds * 1000);
    else if (shown) storyNode.removeChild(shown);
    if (window.TilTaleBubbles) TilTaleBubbles.draw(panel);  // needs the elements' final size, so after they are in the page
    viewerBar.hidden = true;
    viewer = frame.kind === "document" && !inspect ? makeViewer(panel, frame) : null;
    // A zoomed document may be dragged past the frame's letterbox, so the page behind it takes the
    // frame's own background color instead of showing the black around and under the frame.
    storyNode.className = viewer ? "document" : "";
    storyNode.style.background = document.body.style.background = viewer ? frame.background.color || "" : "";
    if (inspect) return;
    if (state.frame !== name) state.previous = state.frame;  // where "× Close" goes
    state.frame = name;
    saveState();
    var event = {frame: name};
    for (var key in details) if (Object.prototype.hasOwnProperty.call(details, key)) event[key] = details[key];
    log("frame", event);
    if (autoplay) robotStep(frame);
  }

  // ------------------------------------------------------------- what a click does
  function activate(frame, element) {
    var leads = element.target || element.language || element.ends_story || element.restarts_story;
    if (!leads && !element.update) return;
    log("choice", {
      frame: frame.name,
      element_id: element.id,
      component: element.component,
      content_id: element.content_id,
      text: element.text || null,
      target: element.ends_story ? "end" : element.restarts_story ? "restart" : (element.target || element.language || null)
    });
    if (element.update) applyUpdate(frame, element);
    if (element.ends_story) finish(frame);
    else if (element.restarts_story) restartStory();
    else if (element.language) openLanguage(element.language);
    else if (element.target) showFrame(element.target);
  }

  /* "set" replaces the value, "add" adds to it (numbers only; the studio refuses anything else). */
  function applyUpdate(frame, element) {
    var update = element.update;
    var before = state.variables[update.variable];
    var after = update.operation === "add" ? before + update.value : update.value;
    state.variables[update.variable] = after;
    saveState();
    log("variable", {frame: frame.name, element_id: element.id, variable: update.variable, from: before, to: after});
    refreshTexts();
  }

  var COMPARE = {
    "==": function (a, b) { return a === b; }, "!=": function (a, b) { return a !== b; },
    "<": function (a, b) { return a < b; }, "<=": function (a, b) { return a <= b; },
    ">": function (a, b) { return a > b; }, ">=": function (a, b) { return a >= b; }
  };

  /* A validation point: the first rule that matches decides; a rule without a variable ("otherwise") always matches. */
  function decide(frame) {
    var chosen = null;
    for (var i = 0; i < frame.rules.length && !chosen; i += 1) {
      var rule = frame.rules[i];
      if (!rule.variable || COMPARE[rule.comparator](state.variables[rule.variable], rule.value)) chosen = rule;
    }
    var snapshot = {};
    for (var name in state.variables) if (Object.prototype.hasOwnProperty.call(state.variables, name)) snapshot[name] = state.variables[name];
    log("decision", {
      frame: frame.name, element_id: chosen ? chosen.id : null, rule: chosen ? chosen.label : null,
      target: chosen ? chosen.target : null, variables: snapshot
    });
    if (!chosen || !chosen.target || !frames[chosen.target]) {
      var problem = frame.name + " has no rule for these values" + (chosen ? " that leads to a frame in this build." : ".");
      return autoplay ? report(false, problem) : notice(problem);
    }
    showFrame(chosen.target);
  }

  /* Forget this browser's progress (also the variables) and open the story's first page again. */
  function restartStory() {
    if (autoplay) return report(true, "Reached a “Restart the story” element.");
    var forward = new URLSearchParams(window.location.search);
    forward["delete"]("frame");
    forward.set("restart", "");
    write(session, fullscreenKey, isFullscreen());
    window.location.href = STORY.start_page + "?" + forward.toString();
  }

  function openLanguage(language) {
    var forward = new URLSearchParams(window.location.search);
    forward["delete"]("restart");
    forward["delete"]("frame");
    write(session, handoffKey, visit);
    write(session, fullscreenKey, isFullscreen());
    window.location.href = STORY.languages[language] + "/index.html?" + forward.toString();
  }

  function notice(text) {
    var box = document.getElementById("notice");
    box.textContent = text;
    box.hidden = false;
  }

  function finish(frame) {
    log("Story finished", {frame: frame.name});
    var url = STORY.finish_redirect_url ? STORY.finish_redirect_url.split("{ID}").join(encodeURIComponent(participantId)) : "";
    if (autoplay) return report(true, "Reached an “End story” element.", url);
    if (preview) return notice(url ? "Story finished. Participants would now go to: " + url : "Story finished (no redirect URL set).");
    if (!url) return notice("✓");
    whenLogged(function () { window.location.href = url; });
  }

  // ------------------------------------------------------------- zoom and drag (document frames)
  var viewer = null;
  var viewerBar = document.getElementById("viewer");

  /* Drag with one finger or the mouse, pinch with two fingers, or use the mouse wheel and the
     + / − buttons (hidden on phones). Zoom is between 1× (the frame as designed) and 8×.
     Pointer moves are watched on the document, not captured, so buttons on the frame still click. */
  function makeViewer(panel, frame) {
    var view = {x: 0, y: 0, zoom: 1};
    var pointers = {};
    var dragged = false;
    function apply() { panel.style.transform = "translate(" + view.x + "px, " + view.y + "px) scale(" + view.zoom + ")"; }
    function zoomBy(factor) { view.zoom = Math.min(Math.max(8, fit * 4), Math.max(1, view.zoom * factor)); apply(); }
    // Start with the document as large as the screen allows, fully visible: a portrait poster on a
    // phone then fills the height instead of sitting small inside the landscape frame.
    var box = contentBox(panel);
    var fit = box ? Math.min(window.innerWidth / (box.width * storyScale), window.innerHeight / (box.height * storyScale)) : 1;
    if (box) {
      view.zoom = Math.max(1, fit);
      view.x = (STORY.frame_width / 2 - box.x) * view.zoom;
      view.y = (STORY.frame_height / 2 - box.y) * view.zoom;
      apply();
    }
    function spread() {
      var ids = Object.keys(pointers);
      if (ids.length < 2) return 0;
      var a = pointers[ids[0]], b = pointers[ids[1]];
      return Math.sqrt((a.x - b.x) * (a.x - b.x) + (a.y - b.y) * (a.y - b.y));
    }
    function move(event) {
      var before = pointers[event.pointerId];
      if (!before) return;
      var pinch = spread();
      pointers[event.pointerId] = {x: event.clientX, y: event.clientY};
      if (pinch) return zoomBy(spread() / pinch);
      view.x += (event.clientX - before.x) / storyScale;
      view.y += (event.clientY - before.y) / storyScale;
      dragged = dragged || Math.abs(event.clientX - before.x) + Math.abs(event.clientY - before.y) > 3;
      apply();
    }
    panel.className += " zoomable";
    panel.addEventListener("wheel", function (event) { event.preventDefault(); zoomBy(event.deltaY < 0 ? 1.15 : 1 / 1.15); }, {passive: false});
    panel.addEventListener("pointerdown", function (event) {
      pointers[event.pointerId] = {x: event.clientX, y: event.clientY};
      dragged = false;
    });
    panel.addEventListener("click", function (event) { if (dragged) event.stopPropagation(); }, true);  // a drag is not a click
    viewerBar.querySelector("[data-close]").textContent = "\u00d7 " + (frame.close_text || "");
    viewerBar.hidden = false;
    return {zoomBy: zoomBy, frame: frame, move: move, release: function (event) { delete pointers[event.pointerId]; }};
  }

  /* The box around the document image (or, on an older frame, its elements), in frame pixels. */
  function contentBox(panel) {
    var image = panel.querySelector("img");
    if (image && image.offsetWidth) {
      return {x: STORY.frame_width / 2, y: STORY.frame_height / 2, width: image.offsetWidth, height: image.offsetHeight};
    }
    var items = panel.querySelectorAll(".story-element");
    if (!items.length) return null;
    var left = Infinity, top = Infinity, right = -Infinity, bottom = -Infinity;
    Array.prototype.forEach.call(items, function (item) {
      left = Math.min(left, item.offsetLeft - item.offsetWidth / 2);
      right = Math.max(right, item.offsetLeft + item.offsetWidth / 2);
      top = Math.min(top, item.offsetTop - item.offsetHeight / 2);
      bottom = Math.max(bottom, item.offsetTop + item.offsetHeight / 2);
    });
    return {x: (left + right) / 2, y: (top + bottom) / 2, width: right - left, height: bottom - top};
  }

  document.addEventListener("pointermove", function (event) { if (viewer) viewer.move(event); });
  document.addEventListener("pointerup", function (event) { if (viewer) viewer.release(event); });
  document.addEventListener("pointercancel", function (event) { if (viewer) viewer.release(event); });

  viewerBar.addEventListener("click", function (event) {
    var button = event.target.closest("button");
    if (!button || !viewer) return;
    if (button.dataset.zoom) return viewer.zoomBy(Number(button.dataset.zoom));
    viewerBar.hidden = true;
    if (!state.previous) return;
    log("choice", {frame: viewer.frame.name, element_id: null, component: "close", text: viewer.frame.close_text || null, target: state.previous});
    showFrame(state.previous);
  });

  // ------------------------------------------------------------- full screen
  /* The button appears with the first frame (not during the startup screen, where its few seconds would
     be over before the reader sees anything), fades away after a few seconds and comes back on a tap beside
     the frame (not on it, so it does not reappear at every click in the story).
     iPhones have no full-screen API: no button there.
     A page load (restart, choosing a language) always leaves full screen, so the page remembers it and
     re-enters at the reader's first tap, the earliest moment a browser allows it. */
  var fullscreenButton = document.getElementById("fullscreen");
  var fullscreenKey = prefix + "fullscreen";
  var fullscreenTimer = 0;
  var page = document.documentElement;
  var requestFullscreen = page.requestFullscreen || page.webkitRequestFullscreen;

  function isFullscreen() {
    return Boolean(document.fullscreenElement || document.webkitFullscreenElement);
  }
  function showFullscreenButton() {
    if (!fullscreenUsable) return;
    fullscreenButton.hidden = false;
    fullscreenButton.className = "";
    window.clearTimeout(fullscreenTimer);
    fullscreenTimer = window.setTimeout(function () { fullscreenButton.className = "faded"; }, 4000);
  }
  function enterFullscreen() {
    if (!isFullscreen()) requestFullscreen.call(page);
  }

  var fullscreenUsable = Boolean(requestFullscreen) && !inspect && !preview;  // the studio's preview is an iframe
  if (fullscreenUsable) {
    fullscreenButton.addEventListener("click", function () {
      if (isFullscreen()) (document.exitFullscreen || document.webkitExitFullscreen).call(document);
      else enterFullscreen();
      showFullscreenButton();
    });
    document.getElementById("viewport").addEventListener("click", function (event) {
      if (event.target === event.currentTarget) showFullscreenButton();
    });
    // A page load (restart, choosing a language) always leaves full screen and a browser only lets a page
    // back in from a gesture, so the first tap anywhere, also on the startup screen, restores it.
    if (read(session, fullscreenKey)) document.addEventListener("click", enterFullscreen, {once: true});
    forget(session, fullscreenKey);
  }

  // ------------------------------------------------------------- play-test robot
  var visits = {};
  var steps = 0;
  var reported = false;

  function report(ok, message, redirect) {
    if (reported) return;
    reported = true;
    log("Play-test ended", {ok: ok, message: message});
    window.parent.postMessage({
      tiltale: "playtest", ok: ok, message: message, redirect: redirect || "",
      participant_id: participantId, language: STORY.language,
      log_file: safeName(participantId) + "--" + safeName(visit.visit_id) + ".jsonl",
      unvisited: STORY.frames.map(function (f) { return f.name; }).filter(function (n) { return !visits[n]; })
    }, "*");
  }

  /* Prefer buttons it has not clicked whose frame it has not seen, then "End story", then the least
     visited; ties are broken at random, so every run may take another route. Documents are closed again. */
  var clicks = {};

  function robotStep(frame) {
    window.parent.postMessage({tiltale: "playtest", progress: frame.name}, "*");  // the studio's stall timer restarts
    visits[frame.name] = (visits[frame.name] || 0) + 1;
    steps += 1;
    if (steps > 400) return report(false, "Stopped after 400 frames: the story seems to loop without an end.");
    if (frame.kind === "document") return window.setTimeout(function () { viewerBar.querySelector("[data-close]").click(); }, 400);
    var options = frame.elements.filter(function (e) { return e.clickable && (e.target || e.language || e.ends_story || e.restarts_story); });
    if (!options.length) return report(true, "Stopped at " + frame.name + ": nothing on it leads further (treated as the end).");
    var score = function (e) {
      if (e.language) return 0;
      if (e.restarts_story) return 1000 + (clicks[e.id] || 0);  // a restart ends the run: only when nothing else is left
      return (e.target ? (visits[e.target] || 0) * 2 : 1) + (clicks[e.id] || 0) * 3 + Math.random();
    };
    var pick = options.slice().sort(function (a, b) { return score(a) - score(b); })[0];
    var target = pick.target && !frames[pick.target] ? pick.target : null;
    if (target) return report(false, frame.name + " links to a frame that is not in this build: " + target + ".");
    clicks[pick.id] = (clicks[pick.id] || 0) + 1;
    window.setTimeout(function () {
      var node = document.getElementById(frame.name + "--" + pick.id);
      if (node) { node.disabled = false; node.click(); }
    }, 250 + (pick.delay_mode === "none" ? 0 : STORY.default_delay_seconds * 1000));
  }

  if (autoplay) {
    window.addEventListener("error", function (event) { report(false, "JavaScript error: " + event.message); });
  }

  // ------------------------------------------------------------- start
  var loaded = {};  // image path -> blob: URL of the downloaded copy, kept in memory for the whole visit

  /* Downloads every image the story will show (the variant chooseSource picks for this screen) and keeps
     each in memory, so a lost connection while playing changes nothing. Browsers that offer Cache Storage
     (HTTPS) also keep them there, so a restart or a returning reader reuses them instead of downloading.
     Resolves to {bytes, cached_bytes}; an image that fails to download is simply shown from the server later. */
  function preloadImages(progress) {
    var chosen = {};
    STORY.frames.forEach(function (frame) {
      var lists = frame.elements.map(function (element) { return element.image; });  // undefined for components
      if (frame.background.type === "image") lists.push(frame.background.sources);
      lists.forEach(function (sources) {
        var source = frame.kind === "document" ? sources[sources.length - 1] : chooseSource(sources);  // documents: the sharpest
        if (source) chosen[source.path] = source;
      });
    });
    var sources = Object.keys(chosen).map(function (path) { return chosen[path]; });
    var total = sources.reduce(function (sum, source) { return sum + source.bytes; }, STORY.base_bytes);
    var done = STORY.base_bytes;  // the page itself is already here
    var cachedBytes = 0;
    progress(done / total);
    var storage = window.caches ? caches.open("tiltale-" + STORY.project).catch(function () { return null; }) : Promise.resolve(null);
    return storage.then(function (cache) {
      return Promise.all(sources.map(function (source) {
        var url = STORY.root + source.path;
        var fromCache = cache ? cache.match(url) : Promise.resolve(null);
        return fromCache.then(function (hit) {
          if (hit) cachedBytes += source.bytes;
          return hit || fetch(url).then(function (response) {
            if (!response.ok) throw new Error(response.status + " " + url);
            if (cache) cache.put(url, response.clone());
            return response;
          });
        }).then(function (response) { return response.blob(); }).then(function (blob) {
          loaded[source.path] = URL.createObjectURL(blob);
        }).catch(function () { /* shown from the server when its frame opens */ }).then(function () {
          done += source.bytes;
          progress(done / total);
        });
      }));
    }).then(function () { return {bytes: total, cached_bytes: cachedBytes}; });
  }

  function start() {
    var loading = document.getElementById("loading");
    scaleStory();
    window.addEventListener("resize", scaleStory);
    // Rotating the device: iOS reports the old size for a moment, so rescale twice.
    window.addEventListener("orientationchange", function () { window.setTimeout(scaleStory, 100); window.setTimeout(scaleStory, 500); });
    if (window.screen && window.screen.orientation) window.screen.orientation.addEventListener("change", scaleStory);
    document.addEventListener("gesturestart", function (event) { event.preventDefault(); });

    if (inspect) {
      document.body.className += " inspect";
      loading.hidden = true;
      storyNode.hidden = false;
      return showFrame(forcedFrame && frames[forcedFrame] ? forcedFrame : STORY.start_frame);
    }
    // Language picker: a participant who already chose a language continues there.
    if (!STORY.language && state.language && STORY.languages[state.language] && !restart && !forcedFrame) {
      log("Resumed", {language: state.language});
      return openLanguage(state.language);
    }
    if (STORY.language) {
      state.language = STORY.language;
      saveState();
    }
    if (window.location.protocol === "file:") notice("Opened from a file: logging is off. Serve /dist/ from a web server with PHP.");

    if (!handoff) log("visit", visitHeader());  // the first line of every log file: when, on what, in which browser
    log("Loading IDN – started", {event_type: "loading_started"});
    loading.hidden = Boolean(forcedFrame);  // the studio jumps straight to a frame, without the bouncing logo
    var minimum = new Promise(function (resolve) { window.setTimeout(resolve, forcedFrame ? 0 : 3000); });
    var images = preloadImages(function (fraction) {
      document.querySelector("#progress i").style.width = (fraction * 100) + "%";
      document.getElementById("progress-text").textContent = "Loading story\u2026 " + Math.round(fraction * 100) + "%";
    });
    Promise.all([images, minimum]).then(function (results) {
      var megabytes = function (bytes) { return (bytes / 1048576).toFixed(2) + " MB"; };
      var summary = megabytes(results[0].bytes) + (results[0].cached_bytes ? ", " + megabytes(results[0].cached_bytes) + " already on this device" : "");
      log("Loading IDN – completed (" + summary + ")", {event_type: "loading_completed", bytes: results[0].bytes, cached_bytes: results[0].cached_bytes});
      loading.hidden = true;
      storyNode.hidden = false;
      showFullscreenButton();  // now that there is something to look at: its few seconds start here
      var first = forcedFrame && frames[forcedFrame] ? forcedFrame : (frames[state.frame] ? state.frame : STORY.start_frame);
      if (!first) return notice("This story has no frames yet.");
      showFrame(first, {how: forcedFrame ? "studio-view" : (first === state.frame && first !== STORY.start_frame ? "resumed" : "start")});
    });
  }

  storyNode.style.width = STORY.frame_width + "px";
  storyNode.style.height = STORY.frame_height + "px";
  document.getElementById("viewport").style.background = STORY.letterbox_color;
  start();
}());
