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

  var stateKey = prefix + "state:" + participantId;  // {language, frame, previous}: resume after a crash
  if (restart) forget(local, stateKey);
  var state = read(local, stateKey) || {};
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

  // ------------------------------------------------------------- logging
  var queueKey = prefix + "unsent";

  function send(payload) {
    if (window.location.protocol === "file:") return keep(payload);
    return fetch(STORY.root + "log.php", {
      method: "POST",
      headers: {"Content-Type": "application/json"},
      body: JSON.stringify(payload),
      keepalive: true
    }).then(function (response) {
      if (!response.ok) keep(payload);
      else flushUnsent();
    }, function () { keep(payload); });
  }

  /* Events that could not be sent (offline, server error) wait in localStorage
     and are retried after the next successful send or when the device is online. */
  function keep(payload) {
    var unsent = read(local, queueKey) || [];
    unsent.push(payload);
    write(local, queueKey, unsent.slice(-2000));
  }
  function flushUnsent() {
    var unsent = read(local, queueKey);
    if (!unsent || !unsent.length) return;
    forget(local, queueKey);
    unsent.forEach(send);
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
    send(payload);
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

  function makeText(value) {
    var text = document.createElement("span");
    text.className = "component-text";
    text.textContent = value;
    return text;
  }

  function makeImage(sources) {
    var image = document.createElement("img");
    var source = chooseSource(sources);
    image.alt = "";
    if (source) image.src = STORY.root + source.path;
    return image;
  }

  function showFrame(name, details) {
    var frame = frames[name];
    if (!frame) return;
    var panel = document.createElement("section");
    panel.className = "story-frame" + (frame.fade_in ? " frame-fade" : "");
    panel.id = frame.name;
    if (frame.background.type === "solid") panel.style.backgroundColor = frame.background.color;
    var source = frame.background.type === "image" ? chooseSource(frame.background.sources) : null;
    if (source) panel.style.backgroundImage = "url(\"" + STORY.root + source.path + "\")";
    var box = frame.background.box;  // without one, style.css makes the image cover the frame
    if (box) {
      panel.style.backgroundSize = box.width + "px " + box.height + "px";
      panel.style.backgroundPosition = (box.x - box.width / 2) + "px " + (box.y - box.height / 2) + "px";
    }
    frame.elements.forEach(function (element) { panel.appendChild(makeElement(frame, element)); });
    storyNode.innerHTML = "";
    storyNode.appendChild(panel);
    if (window.TilTaleBubbles) TilTaleBubbles.draw(panel);  // needs the elements' final size, so after they are in the page
    viewerBar.hidden = true;
    viewer = frame.zoomable && !inspect ? makeViewer(panel, frame) : null;
    storyNode.className = viewer ? "document" : "";  // let the zoomed document spill past the frame's letterbox
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
    if (!element.target && !element.language && !element.ends_story) return;
    log("choice", {
      frame: frame.name,
      element_id: element.id,
      component: element.component,
      content_id: element.content_id,
      text: element.text || null,
      target: element.ends_story ? "end" : (element.target || element.language)
    });
    if (element.ends_story) finish(frame);
    else if (element.language) openLanguage(element.language);
    else showFrame(element.target);
  }

  function openLanguage(language) {
    var forward = new URLSearchParams(window.location.search);
    forward["delete"]("restart");
    forward["delete"]("frame");
    write(session, handoffKey, visit);
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
    window.setTimeout(function () { window.location.href = url; }, 400);  // let the last log leave first
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
    // Start with the document (everything placed on the frame) as large as the screen allows, fully visible:
    // a portrait poster on a phone then fills the height instead of sitting small inside the landscape frame.
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

  /* The smallest box around the frame's elements, in frame pixels (elements are positioned by their centre). */
  function contentBox(panel) {
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

  /* Prefer unvisited frames, then "End story", then the least visited frame. */
  function robotStep(frame) {
    window.parent.postMessage({tiltale: "playtest", progress: frame.name}, "*");  // the studio's stall timer restarts
    visits[frame.name] = (visits[frame.name] || 0) + 1;
    steps += 1;
    if (steps > 400) return report(false, "Stopped after 400 frames: the story seems to loop without an end.");
    var options = frame.elements.filter(function (e) { return e.clickable && (e.target || e.language || e.ends_story); });
    if (!options.length) return report(true, "Stopped at " + frame.name + ": nothing on it leads further (treated as the end).");
    var score = function (e) { return e.language ? 0 : e.target ? (visits[e.target] || 0) * 2 : 1; };
    var pick = options.slice().sort(function (a, b) { return score(a) - score(b); })[0];
    var target = pick.target && !frames[pick.target] ? pick.target : null;
    if (target) return report(false, frame.name + " links to a frame that is not in this build: " + target + ".");
    window.setTimeout(function () {
      var node = document.getElementById(frame.name + "--" + pick.id);
      if (node) { node.disabled = false; node.click(); }
    }, 250 + (pick.delay_mode === "none" ? 0 : STORY.default_delay_seconds * 1000));
  }

  if (autoplay) {
    window.addEventListener("error", function (event) { report(false, "JavaScript error: " + event.message); });
  }

  // ------------------------------------------------------------- start
  function preloadImages() {
    var chosen = {};
    STORY.frames.forEach(function (frame) {
      var lists = frame.elements.map(function (element) { return element.image; });  // undefined for components
      if (frame.background.type === "image") lists.push(frame.background.sources);
      lists.forEach(function (sources) {
        var source = chooseSource(sources);
        if (source) chosen[source.path] = source;
      });
    });
    var sources = Object.keys(chosen).map(function (path) { return chosen[path]; });
    return Promise.all(sources.map(function (source) {
      return new Promise(function (resolve) {
        var image = new Image();
        image.onload = image.onerror = resolve;
        image.src = STORY.root + source.path;
      });
    })).then(function () {
      return sources.reduce(function (total, source) { return total + source.bytes; }, STORY.base_bytes);
    });
  }

  function start() {
    var loading = document.getElementById("loading");
    scaleStory();
    window.addEventListener("resize", scaleStory);
    window.addEventListener("orientationchange", function () { window.setTimeout(scaleStory, 100); });
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

    log("Loading IDN – started", {event_type: "loading_started"});
    loading.hidden = Boolean(forcedFrame);  // the studio jumps straight to a frame, without the bouncing logo
    var minimum = new Promise(function (resolve) { window.setTimeout(resolve, forcedFrame ? 0 : 3000); });
    var images = preloadImages();
    Promise.all([images, minimum]).then(function (results) {
      var megabytes = (results[0] / 1048576).toFixed(2);
      log("Loading IDN – completed (" + megabytes + " MB)", {event_type: "loading_completed", bytes: results[0]});
      loading.hidden = true;
      storyNode.hidden = false;
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
