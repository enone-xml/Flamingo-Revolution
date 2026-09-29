/* RnB / BnB page: builds each cell up level by level when it scrolls into view,
   counts the numbers up, and checks for new accusations every minute. */
(() => {
  "use strict";
  // The full page (.rnb__grid) or the homepage teaser (.rnb-teaser).
  const grid = document.querySelector(".rnb__grid");
  if (!grid && !document.querySelector(".rnb-teaser")) return;
  const T = JSON.parse(document.getElementById("rnb-i18n").textContent);
  const reduced = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
  const fmt = (str, vars) => str.replace(/\{(\w+)\}/g, (_, k) => (k in vars ? vars[k] : ""));
  const sides = Array.from(document.querySelectorAll(".rnb__grid .rnb__side, .rnb-teaser .rnb__side"));
  const max = T.names.length;

  const secs = (side) => Array.from(side.querySelectorAll(".sec"));
  const svg = (side) => side.querySelector(".rnb__cell");

  function shake(side) {
    const el = svg(side);
    el.classList.remove("shake");
    void el.getBoundingClientRect(); // restart the animation
    el.classList.add("shake");
  }

  // Show levels from..to (1-based), one after another, with animation.
  function addLevels(side, from, to, gap = 650) {
    for (let n = from; n <= to; n++) {
      const g = side.querySelector(`.sec-${n}`);
      if (!g) continue;
      setTimeout(() => {
        g.classList.add("on", "play");
        if (n === 2 || n === 8) setTimeout(() => shake(side), n === 2 ? 450 : 650);
      }, (n - from) * gap);
    }
  }

  function countUp(el, from, to, ms = 1200) {
    if (reduced || from === to) { el.textContent = to; return; }
    const start = performance.now();
    const step = (now) => {
      const p = Math.min(1, (now - start) / ms);
      el.textContent = Math.round(from + (to - from) * (1 - Math.pow(1 - p, 3)));
      if (p < 1) requestAnimationFrame(step);
    };
    requestAnimationFrame(step);
  }

  function describe(side, d) {
    const items = T.names.slice(0, d.level);
    svg(side).setAttribute("aria-label", fmt(T.cell, {
      name: T.people[side.dataset.side], n: d.level, max, items: items.length ? items.join(", ") : T.open,
    }));
    if (!side.querySelector("[data-week]")) return; // the homepage teaser shows only the number
    side.querySelector("[data-week]").textContent = fmt(T.week, { n: d.week });
    side.querySelector("[data-level-text]").textContent =
      fmt(T.level, { n: d.level, max }) + " · " + (d.next ? fmt(T.next, { n: d.next - d.total }) : T.maxed);
    side.querySelector(".rnb__meter").value = d.progress;
  }

  // First view: an open cell that locks up to today's level.
  if (!reduced && "IntersectionObserver" in window) {
    sides.forEach((side) => {
      secs(side).forEach((g) => g.classList.remove("on"));
      side.querySelector(".rnb__num").textContent = "0";
    });
    const io = new IntersectionObserver((entries) => {
      entries.forEach((e) => {
        if (!e.isIntersecting) return;
        io.unobserve(e.target);
        const side = e.target;
        const num = side.querySelector(".rnb__num");
        countUp(num, 0, Number(num.dataset.count));
        setTimeout(() => addLevels(side, 1, Number(side.dataset.level)), 400);
      });
    }, { threshold: 0.35 });
    sides.forEach((s) => io.observe(s));
  }

  // Live updates: the page's data file is refreshed every 10 minutes.
  async function poll() {
    if (document.hidden) return;
    try {
      const res = await fetch(grid.dataset.src, { cache: "no-cache" });
      if (!res.ok) return;
      const data = await res.json();
      sides.forEach((side) => {
        const d = data[side.dataset.side];
        if (!d) return;
        const num = side.querySelector(".rnb__num");
        const before = Number(num.dataset.count), oldLevel = Number(side.dataset.level);
        if (d.total !== before) {
          num.dataset.count = d.total;
          countUp(num, before, d.total, 800);
          if (!reduced) { num.classList.remove("bump"); void num.offsetWidth; num.classList.add("bump"); }
        }
        if (d.level > oldLevel) {
          side.dataset.level = d.level;
          if (reduced) secs(side).forEach((g) => g.classList.toggle("on", Number(g.dataset.lvl) <= d.level));
          else addLevels(side, oldLevel + 1, d.level);
        }
        describe(side, d);
      });
    } catch (_) { /* offline: try again next time */ }
  }
  if (grid) setInterval(poll, 60000); // the homepage refreshes as a whole
  if (grid) document.addEventListener("visibilitychange", () => { if (!document.hidden) poll(); });
})();
