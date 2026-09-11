/* Bubble bodies and tails for components with "tail" in their component.json.
 * Shared by the generated story (tiltale.js) and the studio's frame editor (app.js).
 *
 * These SVGs have no viewBox: everything is drawn in element pixels, so strokes,
 * corners, bumps and spikes keep their size at any width or height. The tail tip
 * is stored per element as --tail-x / --tail-y, in pixels from the element's center.
 *
 * Same browser target as tiltale.js: ES5 only.
 */
var TilTaleBubbles = (function () {
  "use strict";

  var NUDGE = 6;  // the tail's base starts this far inside the body, hiding the body's stroke there

  /* Bumps, dots and tail bases grow with the bubble (1x at 150px, up to 2.5x), so big frames get big clouds. */
  function unit(width, height) {
    return Math.min(2.5, Math.max(1, Math.min(width, height) / 150));
  }

  function sign(value) { return value < 0 ? -1 : 1; }
  function point(x, y) { return x.toFixed(1) + " " + y.toFixed(1); }

  /* Where the tail should be when the element has none yet. */
  function defaultTail(width, height) {
    return {x: -width / 4, y: height / 2 + 90};
  }

  /* The point where the line from the box center to the tip leaves the box,
     with the outward normal of that edge. Null while the tip is inside. */
  function edgePoint(width, height, tip) {
    var dx = tip.x - width / 2 || 0.001;
    var dy = tip.y - height / 2 || 0.001;
    var tx = width / 2 / Math.abs(dx);
    var ty = height / 2 / Math.abs(dy);
    var t = Math.min(tx, ty);
    if (t >= 1) return null;
    var vertical = ty < tx;  // leaves through the top or bottom edge
    return {x: width / 2 + dx * t, y: height / 2 + dy * t, nx: vertical ? 0 : sign(dx), ny: vertical ? sign(dy) : 0};
  }

  /* Two base points `half` apart on each side of the edge point, `offset` along the outward normal
     (negative: inside the body), kept clear of the corners. */
  function base(edge, width, height, half, corner, offset) {
    var along = edge.nx ? "y" : "x";
    var limit = (edge.nx ? height : width) - corner;
    var center = Math.min(Math.max(edge[along], corner + half), limit - half);
    var first = {x: edge.x + edge.nx * offset, y: edge.y + edge.ny * offset};
    var second = {x: first.x, y: first.y};
    first[along] = center - half;
    second[along] = center + half;
    return [first, second];
  }

  /* A filled triangle whose base sits inside the body (covering the body's stroke there), and the
     outline of its two flanks, which starts at the outer edge of that stroke so no line enters the bubble. */
  function pointer(width, height, tip, half, corner, stroke) {
    var edge = edgePoint(width, height, tip);
    if (!edge) return {fill: "", line: ""};
    var inner = base(edge, width, height, half, corner, -NUDGE);
    var outer = base(edge, width, height, half, corner, stroke / 2);
    return {
      fill: "M" + point(inner[0].x, inner[0].y) + "L" + point(tip.x, tip.y) + "L" + point(inner[1].x, inner[1].y) + "Z",
      line: "M" + point(outer[0].x, outer[0].y) + "L" + point(tip.x, tip.y) + "L" + point(outer[1].x, outer[1].y)
    };
  }

  function circle(x, y, r) {
    return "M" + point(x - r, y) + "a" + r + " " + r + " 0 1 0 " + 2 * r + " 0a" + r + " " + r + " 0 1 0 " + -2 * r + " 0";
  }

  /* Three shrinking circles between the body and the tip. */
  function dots(width, height, tip) {
    var edge = edgePoint(width, height, tip);
    if (!edge) return "";
    var length = Math.sqrt(Math.pow(tip.x - edge.x, 2) + Math.pow(tip.y - edge.y, 2));
    var scale = unit(width, height) * Math.min(1, length / (150 * unit(width, height)));
    var path = "";
    [[0.2, 22], [0.52, 15], [0.85, 9]].forEach(function (step) {
      path += circle(edge.x + (tip.x - edge.x) * step[0], edge.y + (tip.y - edge.y) * step[0], step[1] * scale);
    });
    return path;
  }

  /* Corners of a box inset by `inset`, clockwise from the top-left. */
  function corners(width, height, inset) {
    return [[inset, inset], [width - inset, inset], [width - inset, height - inset], [inset, height - inset]];
  }

  /* Calls `step(edge, i, x, y, chord)` for an even number of evenly spaced points along each edge. */
  function walk(width, height, inset, spacing, step) {
    var box = corners(width, height, inset);
    box.forEach(function (from, edge) {
      var to = box[(edge + 1) % 4];
      var length = Math.abs(to[0] - from[0] + to[1] - from[1]);
      var n = 2 * Math.max(1, Math.round(length / spacing / 2));
      for (var i = 0; i < n; i += 1) step(edge, i, from[0] + (to[0] - from[0]) * i / n, from[1] + (to[1] - from[1]) * i / n, length / n);
    });
  }

  /* A rounded box with a bump on every step of its outline. */
  function cloud(width, height) {
    var path = "";
    var last = null;
    var inset = 8 * unit(width, height);
    walk(width, height, inset, 30 * unit(width, height), function (edge, i, x, y, chord) {
      var r = (chord * 0.62).toFixed(1);
      path += last === null ? "M" + point(x, y) : "A" + r + " " + r + " 0 0 1 " + point(x, y);
      last = {x: x, y: y, r: r};
    });
    return path + "A" + last.r + " " + last.r + " 0 0 1 " + point(inset, inset) + "Z";
  }

  /* A box whose outline zigzags between the edge and 22px inside it. */
  function burst(width, height) {
    var points = [];
    walk(width, height, 2, 16, function (edge, i, x, y) {
      var depth = i % 2 ? 16 + ((i * 7 + edge * 3) % 5) * 2 : 0;  // odd points go inward, unevenly
      var inward = [[0, 1], [-1, 0], [0, -1], [1, 0]][edge];
      points.push(point(x + inward[0] * depth, y + inward[1] * depth));
    });
    return "M" + points.join("L") + "Z";
  }

  var BODIES = {thought: cloud, scream: burst};
  var TAILS = {  // each returns {fill, line}: the .bubble-tail path and, when the SVG has one, the .bubble-tail-line path
    speech: function (w, h, tip, stroke) { return pointer(w, h, tip, 20 * unit(w, h), 30, stroke); },
    thought: function (w, h, tip) { return {fill: dots(w, h, tip), line: ""}; },
    scream: function (w, h, tip, stroke) { return pointer(w, h, tip, 8 * unit(w, h), 12, stroke); }
  };

  function tailOf(node, width, height) {
    var x = parseFloat(node.style.getPropertyValue("--tail-x"));
    var y = parseFloat(node.style.getPropertyValue("--tail-y"));
    var tail = isNaN(x) || isNaN(y) ? defaultTail(width, height) : {x: x, y: y};
    return {x: width / 2 + tail.x, y: height / 2 + tail.y};
  }

  /* Draws one element with a data-tail attribute. */
  function drawOne(node) {
    var svg = node.querySelector("svg");
    var kind = node.getAttribute("data-tail");
    var width = svg.clientWidth;
    var height = svg.clientHeight;
    if (!width || !height) return;  // not laid out yet (hidden); the next draw() call does it
    var body = svg.querySelector(".bubble-body");
    var tail = svg.querySelector(".bubble-tail");
    var line = svg.querySelector(".bubble-tail-line");
    if (body && BODIES[kind]) body.setAttribute("d", BODIES[kind](width, height));
    if (!tail || !TAILS[kind]) return;
    var stroke = parseFloat(window.getComputedStyle(body).strokeWidth) || 0;
    var shapes = TAILS[kind](width, height, tailOf(node, width, height), stroke);
    tail.setAttribute("d", shapes.fill);
    if (line) line.setAttribute("d", shapes.line);
  }

  /* Draws `root` itself when it has a tail, and every element with one inside it. */
  function draw(root) {
    if (root.hasAttribute("data-tail")) return drawOne(root);
    Array.prototype.forEach.call(root.querySelectorAll("[data-tail]"), drawOne);
  }

  return {draw: draw, defaultTail: defaultTail};
}());
