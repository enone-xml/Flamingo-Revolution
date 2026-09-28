/* Flamingo Watch front end. Plain JS; GSAP/ScrollTrigger/Lenis are optional extras. */
(() => {
  "use strict";

  const doc = document.documentElement;
  const reduced = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
  const finePointer = window.matchMedia("(hover: hover) and (pointer: fine)").matches;
  const hasGsap = typeof window.gsap !== "undefined";
  const motion = hasGsap && !reduced;
  const I18N = JSON.parse(document.getElementById("i18n").textContent);

  doc.classList.add("js");
  if (motion) {
    doc.classList.add("motion");
    gsap.registerPlugin(ScrollTrigger);
  }

  // ------------------------------------------------------------ helpers
  const $ = (sel, root = document) => root.querySelector(sel);
  const $$ = (sel, root = document) => Array.from(root.querySelectorAll(sel));
  const fmt = (str, vars) => str.replace(/\{(\w+)\}/g, (_, k) => (k in vars ? vars[k] : ""));

  function ago(iso) {
    if (!iso) return I18N.updated_never;
    const mins = Math.floor((Date.now() - Date.parse(iso)) / 60000);
    if (mins < 1) return I18N.just_now;
    if (mins < 60) return fmt(I18N.min_ago, { n: mins });
    if (mins < 1440) return fmt(I18N.h_ago, { n: Math.floor(mins / 60) });
    return fmt(I18N.d_ago, { n: Math.floor(mins / 1440) });
  }

  // Build DOM safely (text only, never innerHTML with feed data).
  function h(tag, attrs = {}, ...children) {
    const el = document.createElement(tag);
    for (const [k, v] of Object.entries(attrs)) {
      if (v === null || v === undefined || v === false) continue;
      if (k === "class") el.className = v;
      else if (k === "text") el.textContent = v;
      else el.setAttribute(k, v === true ? "" : v);
    }
    for (const c of children.flat()) if (c) el.append(c.nodeType ? c : document.createTextNode(c));
    return el;
  }

  function refreshTimes(root = document) {
    $$("time[data-ago]", root).forEach((t) => { t.textContent = ago(t.getAttribute("datetime")); });
    $$("[data-updated]", root).forEach((el) => { el.textContent = ago(el.dataset.updated); });
  }

  // ------------------------------------------------------------ smooth scroll
  let lenis = null;
  if (motion && finePointer && typeof window.Lenis !== "undefined") {
    lenis = new Lenis({ lerp: 0.12, smoothWheel: true });
    lenis.on("scroll", ScrollTrigger.update);
    gsap.ticker.add((time) => lenis.raf(time * 1000));
    gsap.ticker.lagSmoothing(0);
    // In-page anchors go through Lenis so they stay smooth.
    document.addEventListener("click", (e) => {
      const a = e.target.closest('a[href^="#"]');
      if (!a) return;
      const target = $(a.getAttribute("href"));
      if (!target) return;
      e.preventDefault();
      lenis.scrollTo(target, { offset: -60 });
      target.focus({ preventScroll: true });
    });
  }

  // ------------------------------------------------------------ menu overlay
  const menu = $("#menu");
  const menuBtn = $(".menu-btn");
  let lastFocus = null;

  function openMenu() {
    lastFocus = document.activeElement;
    menu.hidden = false;
    document.body.classList.add("menu-open");
    doc.classList.add("menu-open");
    menuBtn.setAttribute("aria-expanded", "true");
    $(".menu-btn__label").textContent = menuBtn.dataset.close || "×";
    if (lenis) lenis.stop();
    if (motion) {
      gsap.fromTo(menu, { clipPath: "inset(0 0 100% 0)" }, { clipPath: "inset(0 0 0% 0)", duration: 0.6, ease: "expo.inOut" });
      gsap.fromTo($$(".menu__text", menu), { yPercent: 110 }, { yPercent: 0, duration: 0.8, ease: "expo.out", stagger: 0.06, delay: 0.25 });
    }
    $("a", menu).focus();
  }

  function closeMenu() {
    const done = () => {
      menu.hidden = true;
      document.body.classList.remove("menu-open");
      doc.classList.remove("menu-open");
      if (lenis) lenis.start();
      (lastFocus || menuBtn).focus();
    };
    menuBtn.setAttribute("aria-expanded", "false");
    $(".menu-btn__label").textContent = menuBtn.dataset.open;
    if (motion) gsap.to(menu, { clipPath: "inset(100% 0 0 0)", duration: 0.45, ease: "expo.inOut", onComplete: done });
    else done();
  }

  if (menu && menuBtn) {
    menuBtn.dataset.open = $(".menu-btn__label").textContent;
    menuBtn.dataset.close = I18N.lang === "sq" ? "Mbyll" : "Close";
    menuBtn.addEventListener("click", () => (menu.hidden ? openMenu() : closeMenu()));
    menu.addEventListener("click", (e) => { if (e.target.closest("a")) closeMenu(); });
    document.addEventListener("keydown", (e) => {
      if (menu.hidden) return;
      if (e.key === "Escape") closeMenu();
      if (e.key === "Tab") { // keep focus inside the menu (plus the close button)
        const items = [menuBtn, ...$$("a", menu)];
        const i = items.indexOf(document.activeElement);
        if (e.shiftKey && i <= 0) { e.preventDefault(); items[items.length - 1].focus(); }
        else if (!e.shiftKey && i === items.length - 1) { e.preventDefault(); items[0].focus(); }
      }
    });
  }

  // ------------------------------------------------------------ page transitions
  const curtain = $(".transition");
  if (motion && curtain) {
    gsap.fromTo(curtain, { scaleY: 1, transformOrigin: "top" }, { scaleY: 0, duration: 0.6, ease: "expo.inOut" });
    document.addEventListener("click", (e) => {
      const a = e.target.closest("a");
      if (!a || a.target === "_blank" || e.metaKey || e.ctrlKey || e.shiftKey || e.button !== 0) return;
      const url = new URL(a.href, location.href);
      if (url.origin !== location.origin || url.pathname.startsWith("/api") || url.pathname.endsWith(".xml")) return;
      if (url.pathname === location.pathname && url.hash) return; // same-page anchor
      e.preventDefault();
      gsap.fromTo(curtain, { scaleY: 0, transformOrigin: "bottom" }, {
        scaleY: 1, duration: 0.45, ease: "expo.inOut", onComplete: () => { location.href = url.href; },
      });
    });
    window.addEventListener("pageshow", (e) => { if (e.persisted) gsap.set(curtain, { scaleY: 0 }); });
  }

  // ------------------------------------------------------------ hero + reveals
  function splitChars(el) {
    const text = el.textContent;
    el.textContent = "";
    el.append(h("span", { class: "sr-only" }, text));
    [...text].forEach((ch) => el.append(h("span", { class: "ch", "aria-hidden": "true" }, ch === " " ? " " : ch)));
    return $$(".ch", el);
  }

  if (motion) {
    const words = $$("[data-split]");
    const tl = gsap.timeline({ delay: 0.35 });
    words.forEach((w, i) => {
      tl.from(splitChars(w), { yPercent: 115, rotate: 6, duration: 1.05, ease: "expo.out", stagger: 0.045 }, i * 0.12);
    });
    tl.from(".hero__kicker, .hero__tagline, .hero__coords", { y: 20, opacity: 0, duration: 0.8, ease: "power3.out", stagger: 0.08 }, 0.5)
      .from(".hero__stats", { y: 24, opacity: 0, duration: 0.8, ease: "power3.out" }, 0.7)
      .from(".hero__tape", { xPercent: -30, opacity: 0, duration: 1, ease: "expo.out" }, 0.8);

    // Count-up numbers.
    $$(".hero__stats [data-count]").forEach((el) => {
      const end = parseInt(el.dataset.count, 10) || 0;
      const obj = { v: 0 };
      tl.to(obj, { v: end, duration: 1.4, ease: "power2.out", onUpdate: () => { el.textContent = Math.round(obj.v); } }, 0.8);
    });

    // Draw the flamingo line by line.
    const paths = $$(".hero__bird-draw path");
    paths.forEach((p) => {
      const len = p.getTotalLength();
      gsap.set(p, { strokeDasharray: len, strokeDashoffset: len });
    });
    tl.to(paths, { strokeDashoffset: 0, duration: 1.6, ease: "power2.inOut", stagger: 0.18 }, 0.4);

    // Parallax on scroll: title drifts up, bird drifts down.
    if ($(".hero") && window.innerWidth >= 960) {
      gsap.to(".hero__title", { yPercent: -18, ease: "none", scrollTrigger: { trigger: ".hero", start: "top top", end: "bottom top", scrub: true } });
      gsap.to(".hero__bird-draw", { yPercent: 12, rotate: -4, ease: "none", scrollTrigger: { trigger: ".hero", start: "top top", end: "bottom top", scrub: true } });
    }

    // Generic reveal on scroll.
    ScrollTrigger.batch("[data-reveal]", {
      start: "top 88%",
      onEnter: (els) => gsap.to(els, { opacity: 1, y: 0, duration: 0.9, ease: "power3.out", stagger: 0.08, overwrite: true }),
    });
  }

  function revealCards(cards) {
    if (!motion || !cards.length) return;
    cards.forEach((c) => c.classList.add("pre-reveal"));
    ScrollTrigger.batch(cards, {
      start: "top 92%",
      once: true,
      onEnter: (els) => gsap.to(els, {
        opacity: 1, y: 0, duration: 0.8, ease: "power3.out", stagger: 0.07,
        onComplete: () => els.forEach((e) => { e.classList.remove("pre-reveal"); e.style.transform = ""; }),
      }),
    });
    scheduleRefresh();
  }

  let refreshQueued = false;
  function scheduleRefresh() {
    if (refreshQueued) return;
    refreshQueued = true;
    requestAnimationFrame(() => { refreshQueued = false; ScrollTrigger.refresh(); });
  }

  // ------------------------------------------------------------ particles (desktop only)
  const canvas = $(".hero__particles");
  const strongDevice = (navigator.hardwareConcurrency || 2) >= 4 && !(navigator.connection && navigator.connection.saveData);
  if (canvas && motion && finePointer && strongDevice && window.innerWidth >= 960) {
    const ctx = canvas.getContext("2d");
    let w, h2, dots = [], visible = true, raf;
    const dpr = Math.min(window.devicePixelRatio || 1, 2);
    const resize = () => {
      w = canvas.clientWidth; h2 = canvas.clientHeight;
      canvas.width = w * dpr; canvas.height = h2 * dpr;
      ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
      dots = Array.from({ length: Math.round((w * h2) / 16000) }, () => ({
        x: Math.random() * w, y: Math.random() * h2,
        r: Math.random() * 1.8 + 0.4, vy: -(Math.random() * 0.25 + 0.05), vx: (Math.random() - 0.5) * 0.15,
        a: Math.random() * 0.6 + 0.15, g: Math.random() < 0.04,
      }));
    };
    let mx = -999, my = -999;
    canvas.parentElement.addEventListener("pointermove", (e) => {
      const r = canvas.getBoundingClientRect(); mx = e.clientX - r.left; my = e.clientY - r.top;
    });
    const tick = () => {
      ctx.clearRect(0, 0, w, h2);
      for (const d of dots) {
        d.x += d.vx; d.y += d.vy;
        const dx = d.x - mx, dy = d.y - my, dist = dx * dx + dy * dy;
        if (dist < 9000) { d.x += dx * 0.02; d.y += dy * 0.02; }
        if (d.y < -5) { d.y = h2 + 5; d.x = Math.random() * w; }
        ctx.beginPath();
        ctx.arc(d.x, d.y, d.r, 0, Math.PI * 2);
        ctx.fillStyle = d.g ? `rgba(39,245,138,${d.a})` : `rgba(255,62,165,${d.a})`;
        ctx.fill();
      }
      if (visible) raf = requestAnimationFrame(tick);
    };
    new IntersectionObserver(([entry]) => {
      visible = entry.isIntersecting;
      if (visible) { cancelAnimationFrame(raf); raf = requestAnimationFrame(tick); }
    }).observe(canvas);
    const start = () => { resize(); raf = requestAnimationFrame(tick); };
    ("requestIdleCallback" in window) ? requestIdleCallback(start) : setTimeout(start, 400);
    window.addEventListener("resize", () => { clearTimeout(canvas._t); canvas._t = setTimeout(resize, 200); });
  }

  // ------------------------------------------------------------ custom cursor (desktop only)
  const cursor = $(".cursor");
  if (cursor && finePointer && !reduced) {
    doc.classList.add("has-cursor");
    let cx = -100, cy = -100, tx = -100, ty = -100;
    window.addEventListener("pointermove", (e) => { tx = e.clientX; ty = e.clientY; }, { passive: true });
    document.addEventListener("pointerover", (e) => {
      cursor.classList.toggle("is-link", !!e.target.closest("a, button, label, select"));
    });
    const loop = () => {
      cx += (tx - cx) * 0.22; cy += (ty - cy) * 0.22;
      cursor.style.transform = `translate3d(${cx}px, ${cy}px, 0)`;
      requestAnimationFrame(loop);
    };
    loop();
  }

  // ------------------------------------------------------------ feed
  const cards = $(".cards");
  if (!cards) { refreshTimes(); return; }

  const ui = cards.dataset.ui;
  const form = $(".filters");
  const newBtn = $(".new-items");
  let page = 1;
  let maxId = parseInt(cards.dataset.maxId, 10) || 0;

  function filterParams() {
    const fd = new FormData(form);
    const p = new URLSearchParams();
    for (const [k, v] of fd.entries()) if (v) p.set(k, v);
    return p;
  }

  function cardEl(g, featured) {
    const a = g.lead;
    const count = g.sources.length;
    const tags = g.tags.length
      ? h("ul", { class: "card__tags" }, g.tags.map((t) => h("li", { class: `tag tag--${t.toLowerCase()}` }, I18N.tags[t] || t)))
      : null;
    const el = h("article", { class: `card${a.ai ? "" : " card--plain"}${featured ? " card--featured" : ""}`, "data-max-id": g.max_id },
      h("div", { class: "card__meta" },
        h("span", { class: "card__source" }, a.source),
        h("time", { datetime: a.published_at, "data-ago": true }, ago(a.published_at)),
        count > 1 ? h("span", { class: "card__count" }, fmt(I18N.n_sources, { n: count })) : null),
      h("h3", { class: "card__title" }, h("a", { href: a.url, rel: "noopener", target: "_blank", hreflang: a.lang }, a.title)),
      a.summary ? h("p", { class: "card__summary" }, a.summary) : h("p", { class: "card__note" }, I18N.no_summary),
      a.ai && a.original_title && a.original_title !== a.title
        ? h("p", { class: "card__orig", lang: a.lang }, h("span", {}, I18N.original_headline + ":"), " " + a.original_title) : null,
      h("div", { class: "card__foot" }, tags,
        h("a", { class: "card__read", href: a.url, rel: "noopener", target: "_blank" }, fmt(I18N.read_original, { source: a.source }) + " ", h("span", { "aria-hidden": "true" }, "↗"))),
    );
    if (g.articles.length > 1) {
      const id = `grp-${g.max_id}`;
      el.append(
        h("button", { class: "card__toggle", type: "button", "aria-expanded": "false", "aria-controls": id },
          h("span", {}, I18N.show_sources), " ", h("span", { class: "card__toggle-n" }, `(${g.articles.length})`)),
        h("ul", { class: "card__group", id, hidden: true }, g.articles.map((o) =>
          h("li", {}, h("a", { href: o.url, rel: "noopener", target: "_blank" },
            h("span", { class: "card__group-src" }, o.source), " ",
            h("span", { class: "card__group-title", lang: o.lang }, o.original_title || o.title), " ",
            h("time", { datetime: o.published_at, "data-ago": true }, ago(o.published_at)))))),
      );
    }
    return el;
  }

  function markFeatured() {
    const first = $(".card", cards);
    if (first && window.innerWidth >= 960) first.classList.add("card--featured");
  }

  // ---- data source: live API (server) or pre-built JSON files (static site)
  const STATIC = document.body.dataset.static === "1";
  const RANGES = { "24h": 864e5, "7d": 7 * 864e5, "30d": 30 * 864e5 };

  const cache = {};  // file name -> { data, at }
  async function staticData(file, fresh) {
    const c = cache[file];
    if (c && !fresh && Date.now() - c.at < 55000) return c.data;  // reuse between filter clicks
    const res = await fetch(`/data/${file}`, { cache: "no-cache" });
    if (!res.ok) throw new Error(res.status);
    const data = await res.json();
    cache[file] = { data, at: Date.now() };
    return data;
  }

  async function staticQuery(p, sinceId) {
    const tag = p.get("tag"), source = p.get("source"), lang = p.get("lang"), range = p.get("range") || "7d";
    // 24h/7d use the small file; 30 days and "all" use the 30-day file.
    const long = range === "30d" || range === "all";
    const all = await staticData(`articles-${ui}${long ? "-30d" : ""}.json`, !!sinceId);
    const since = RANGES[range] ? Date.now() - RANGES[range] : 0;
    const keep = (a) => (!tag || a.tags.includes(tag)) && (!source || a.source === source)
      && (!lang || a.lang === lang) && Date.parse(a.published_at) >= since;
    const groups = [];
    for (const g of all.groups) {
      const arts = g.articles.filter(keep);
      if (!arts.length) continue;
      groups.push({
        ...g, articles: arts, lead: arts[0],
        max_id: Math.max(...arts.map((a) => a.id)),
        sources: [...new Set(arts.map((a) => a.source))].sort(),
        tags: [...new Set(arts.flatMap((a) => a.tags))].sort(),
      });
    }
    const per = parseInt(p.get("per_page") || "20", 10), pg = parseInt(p.get("page") || "1", 10);
    return {
      groups: groups.slice((pg - 1) * per, pg * per),
      has_more: pg * per < groups.length,
      new_since: sinceId ? groups.filter((g) => g.max_id > sinceId).length : 0,
      stats: all.stats,
    };
  }

  async function query(p, sinceId) {
    if (STATIC) return staticQuery(p, sinceId);
    if (sinceId) p.set("since_id", String(sinceId));
    const res = await fetch(`/api/articles?${p}`, { headers: { Accept: "application/json" } });
    if (!res.ok) throw new Error(res.status);
    return res.json();
  }

  async function load({ append = false } = {}) {
    const p = filterParams();
    p.set("ui", ui);
    p.set("page", String(page));
    cards.setAttribute("aria-busy", "true");
    try {
      const data = await query(p);
      if (!append) cards.replaceChildren();
      const els = data.groups.map((g, i) => cardEl(g, !append && i === 0 && window.innerWidth >= 960));
      if (!append && !els.length) cards.append(h("p", { class: "cards__empty" }, I18N.empty));
      cards.append(...els);
      revealCards(els);
      const more = $(".load-more");
      if (more) more.hidden = !data.has_more;
      maxId = Math.max(maxId, data.stats.max_id);
      updateStats(data.stats);
    } catch (err) {
      console.warn("feed load failed", err);
    } finally {
      cards.setAttribute("aria-busy", "false");
    }
  }

  function updateStats(st) {
    $$("[data-updated]").forEach((el) => { el.dataset.updated = st.last_updated || ""; });
    const today = $("#stat-today");
    if (today && !today.closest(".hero__stats").matches(":hover")) today.textContent = st.articles_today;
    refreshTimes();
  }

  // Expand/collapse "N sources".
  cards.addEventListener("click", (e) => {
    const btn = e.target.closest(".card__toggle");
    if (!btn) return;
    const list = document.getElementById(btn.getAttribute("aria-controls"));
    const open = btn.getAttribute("aria-expanded") === "true";
    btn.setAttribute("aria-expanded", String(!open));
    $("span", btn).textContent = open ? I18N.show_sources : I18N.hide_sources;
    list.hidden = open;
    if (!open && motion) gsap.from($$("li", list), { opacity: 0, x: -12, duration: 0.4, stagger: 0.04, ease: "power2.out" });
    if (motion) scheduleRefresh();
  });

  // Filters apply instantly; the URL is kept in sync so it can be shared.
  form.addEventListener("change", () => {
    page = 1;
    const p = filterParams();
    history.replaceState(null, "", `${location.pathname}${p.toString() ? "?" + p : ""}#feed`);
    newBtn.hidden = true;
    load();
  });
  form.addEventListener("submit", (e) => { e.preventDefault(); form.dispatchEvent(new Event("change")); });
  const reset = $(".btn--ghost", form);
  if (reset) reset.addEventListener("click", (e) => {
    e.preventDefault();
    form.reset();
    $$('input[name="tag"]', form)[0].checked = true;
    $$("select", form).forEach((s) => { s.selectedIndex = s.name === "range" ? 1 : 0; });
    form.dispatchEvent(new Event("change"));
  });

  const moreBtn = $(".load-more");
  if (moreBtn) moreBtn.addEventListener("click", (e) => { e.preventDefault(); page += 1; load({ append: true }); });

  // Poll every 60s for new stories; show a button instead of jumping the page.
  async function poll() {
    if (document.hidden) return;
    const p = filterParams();
    p.set("ui", ui); p.set("per_page", "1");
    try {
      if (STATIC) { // cheap check first: only download articles when something is new
        const res = await fetch("/data/stats.json", { cache: "no-cache" });
        if (!res.ok) return;
        const st = await res.json();
        updateStats(st);
        if (st.max_id <= maxId) return;
      }
      const data = await query(p, maxId);
      updateStats(data.stats);
      if (data.new_since > 0) {
        newBtn.textContent = fmt(I18N.new_items, { n: data.new_since });
        newBtn.hidden = false;
        if (motion) gsap.fromTo(newBtn, { y: -20, opacity: 0 }, { y: 0, opacity: 1, duration: 0.5, ease: "back.out(2)" });
      }
    } catch (_) { /* offline: try again next time */ }
  }
  newBtn.addEventListener("click", () => {
    newBtn.hidden = true; page = 1;
    load().then(() => (lenis ? lenis.scrollTo("#feed", { offset: -60 }) : $("#feed").scrollIntoView()));
  });
  setInterval(poll, 60000);
  setInterval(() => refreshTimes(), 30000);
  document.addEventListener("visibilitychange", () => { if (!document.hidden) poll(); });

  markFeatured();
  revealCards($$(".card", cards));
  refreshTimes();

  // A static host ignores ?tag=... in the URL, so apply shared filter links here.
  if (STATIC) {
    const q = new URLSearchParams(location.search);
    let changed = false;
    for (const [k, v] of q.entries()) {
      const field = form.elements[k];
      if (!field || !v) continue;
      if (field instanceof RadioNodeList) {
        const r = [...field].find((x) => x.value === v);
        if (r) { r.checked = true; changed = true; }
      } else if ([...(field.options || [])].some((o) => o.value === v)) { field.value = v; changed = true; }
    }
    if (changed) load();
  }
})();
