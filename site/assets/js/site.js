/* Lifeline site — vertical wheel drives horizontal travel along the lifeline.
   Progressive enhancement: the content is real HTML and works (stacked) without JS. */
(function () {
  "use strict";
  var track = document.getElementById("track");
  if (!track) return;

  var panels = Array.prototype.slice.call(track.querySelectorAll(".panel"));
  var fill = document.getElementById("fill");
  var dotsWrap = document.getElementById("dots");
  var hint = document.getElementById("hint");
  var isStacked = function () { return window.matchMedia("(max-width: 860px)").matches; };

  /* short labels for the side-nav dots */
  var labels = ["intro", "problem", "→ 0", "layers", "laws", "loop", "bootstrap", "mcp", "docs"];
  panels.forEach(function (p, i) {
    var b = document.createElement("button");
    b.setAttribute("data-label", labels[i] || ("0" + (i + 1)));
    b.setAttribute("aria-label", "Go to section " + (i + 1));
    b.addEventListener("click", function () {
      if (isStacked()) p.scrollIntoView({ behavior: "smooth", block: "start" });
      else track.scrollTo({ left: p.offsetLeft, behavior: "smooth" });
    });
    dotsWrap.appendChild(b);
  });
  var dots = Array.prototype.slice.call(dotsWrap.children);

  /* snap to the nearest panel once travel settles (crisp landing without mandatory snap,
     which would revert every wheel increment and freeze the horizontal travel) */
  var snapTimer = null;
  function nearestPanel() {
    var best = panels[0], min = Infinity;
    panels.forEach(function (p) {
      var d = Math.abs(p.offsetLeft - track.scrollLeft);
      if (d < min) { min = d; best = p; }
    });
    return best;
  }
  function scheduleSnap() {
    if (isStacked()) return;
    clearTimeout(snapTimer);
    snapTimer = setTimeout(function () {
      var p = nearestPanel();
      if (Math.abs(p.offsetLeft - track.scrollLeft) > 2) track.scrollTo({ left: p.offsetLeft, behavior: "smooth" });
    }, 140);
  }

  /* vertical wheel → horizontal scroll (desktop only) */
  track.addEventListener("wheel", function (e) {
    if (isStacked()) return;                       // native vertical scroll when stacked
    var dy = Math.abs(e.deltaY) > Math.abs(e.deltaX) ? e.deltaY : e.deltaX;
    if (dy === 0) return;
    e.preventDefault();
    track.scrollLeft += dy * 1.6;
    scheduleSnap();
  }, { passive: false });

  /* progress thread + active dot, throttled with rAF */
  var ticking = false;
  function onScroll() {
    if (ticking) return;
    ticking = true;
    requestAnimationFrame(function () {
      if (!isStacked()) {
        var max = track.scrollWidth - track.clientWidth;
        var pct = max > 0 ? (track.scrollLeft / max) * 100 : 0;
        if (fill) fill.style.width = pct + "%";
      }
      ticking = false;
    });
  }
  track.addEventListener("scroll", onScroll, { passive: true });
  window.addEventListener("resize", onScroll);

  /* reveal panels + sync active dot when centered */
  var io = new IntersectionObserver(function (entries) {
    entries.forEach(function (en) {
      var i = panels.indexOf(en.target);
      if (en.isIntersecting) {
        en.target.classList.add("seen");
        if (en.intersectionRatio > 0.5) {
          dots.forEach(function (d, j) { d.classList.toggle("active", j === i); });
        }
      }
    });
  }, { root: isStacked() ? null : track, threshold: [0.25, 0.55] });
  panels.forEach(function (p) { io.observe(p); });
  if (dots[0]) dots[0].classList.add("active");

  /* keyboard travel */
  window.addEventListener("keydown", function (e) {
    if (isStacked()) return;
    var cur = 0, min = Infinity;
    panels.forEach(function (p, i) {
      var d = Math.abs(p.offsetLeft - track.scrollLeft);
      if (d < min) { min = d; cur = i; }
    });
    var to = null;
    if (e.key === "ArrowRight" || e.key === "PageDown") to = Math.min(cur + 1, panels.length - 1);
    if (e.key === "ArrowLeft" || e.key === "PageUp") to = Math.max(cur - 1, 0);
    if (e.key === "Home") to = 0;
    if (e.key === "End") to = panels.length - 1;
    if (to !== null) { e.preventDefault(); track.scrollTo({ left: panels[to].offsetLeft, behavior: "smooth" }); }
  });

  /* hide the scroll hint after first travel */
  var hid = false;
  function hideHint() {
    if (hid || !hint) return;
    if ((isStacked() ? window.scrollY : track.scrollLeft) > 40) { hint.style.opacity = "0"; hid = true; }
  }
  track.addEventListener("scroll", hideHint, { passive: true });
  window.addEventListener("scroll", hideHint, { passive: true });

  /* copy the install command */
  var copy = document.getElementById("copy-install");
  if (copy) {
    copy.addEventListener("click", function () {
      var ic = document.getElementById("copy-ic");
      navigator.clipboard && navigator.clipboard.writeText("pip install lifeline-context").then(function () {
        if (ic) { ic.textContent = "copied ✓"; setTimeout(function () { ic.textContent = "copy"; }, 1600); }
      });
    });
  }
})();
