/* Flamingo Watch: turn a story or a daily digest into a 1080x1920 picture
   (Instagram Stories / WhatsApp Status size). Everything happens in the
   browser; loaded by site.js only when someone taps "Image". */
(() => {
  "use strict";

  const W = 1080, H = 1920, PAD = 84;
  const C = { bg: "#0A0A0A", card: "#141414", line: "#2A2A2A", pink: "#FF3EA5", green: "#27F58A", blue: "#3EA5FF", text: "#F5F5F0", muted: "#9A9A94", soft: "#D8D8D2" };
  // Same drawing as the site's flamingo logo (viewBox 120x200).
  const BIRD = [
    "M40 92C30 70 62 58 84 70c16 8 20 26 2 34-16 8-38 4-46-12z",
    "M44 86C30 70 30 52 44 42c14-10 16-22 6-30-6-5-14-2-14 6",
    "M36 12c-6 2-9 8-8 14 1 3 3 5 5 6",
    "M66 106v84m0 0-8 4m8-4 8 4",
    "m72 106 4 34-14-12",
  ];
  const REED = "M92 196c2-24 6-42 14-56";

  function wrap(ctx, text, maxWidth, maxLines) {
    const words = String(text || "").split(/\s+/).filter(Boolean);
    const lines = [];
    let line = "";
    for (const w of words) {
      const test = line ? line + " " + w : w;
      if (ctx.measureText(test).width <= maxWidth) { line = test; continue; }
      if (line) lines.push(line);
      line = w;
      if (lines.length === maxLines) break;
    }
    if (lines.length < maxLines && line) lines.push(line);
    if (lines.length === maxLines && words.join(" ") !== lines.join(" ")) {
      let last = lines[maxLines - 1];
      while (last && ctx.measureText(last + "…").width > maxWidth) last = last.slice(0, -1);
      lines[maxLines - 1] = last.replace(/[\s,.;:]+$/, "") + "…";
    }
    return lines;
  }

  function text(ctx, lines, x, y, lineHeight) {
    lines.forEach((l, i) => ctx.fillText(l, x, y + i * lineHeight));
    return y + lines.length * lineHeight;
  }

  function bird(ctx, x, y, scale, alpha) {
    ctx.save();
    ctx.globalAlpha = alpha;
    ctx.translate(x, y);
    ctx.scale(scale, scale);
    ctx.lineCap = "round"; ctx.lineJoin = "round";
    ctx.strokeStyle = C.pink; ctx.lineWidth = 4;
    BIRD.forEach((d) => ctx.stroke(new Path2D(d)));
    ctx.strokeStyle = C.green; ctx.lineWidth = 2.5;
    ctx.stroke(new Path2D(REED));
    ctx.restore();
  }

  function background(ctx) {
    ctx.fillStyle = C.bg; ctx.fillRect(0, 0, W, H);
    ctx.strokeStyle = C.line; ctx.globalAlpha = 0.35; ctx.lineWidth = 1;
    for (let x = 0; x <= W; x += 72) { ctx.beginPath(); ctx.moveTo(x, 0); ctx.lineTo(x, H); ctx.stroke(); }
    for (let y = 0; y <= H; y += 72) { ctx.beginPath(); ctx.moveTo(0, y); ctx.lineTo(W, y); ctx.stroke(); }
    ctx.globalAlpha = 1;
    bird(ctx, W - 470, H - 1020, 3.6, 0.16);   // large faint flamingo behind the text
  }

  function header(ctx, kicker) {
    ctx.fillStyle = C.pink; ctx.fillRect(0, 0, W, 12);
    bird(ctx, PAD, 72, 0.42, 1);
    ctx.fillStyle = C.text; ctx.font = "400 64px Anton, Impact, sans-serif"; ctx.textBaseline = "alphabetic";
    ctx.fillText("FLAMINGO WATCH", PAD + 70, 140);
    ctx.fillStyle = C.pink; ctx.beginPath(); ctx.arc(PAD + 10, 228, 10, 0, Math.PI * 2); ctx.fill();
    ctx.fillStyle = C.muted; ctx.font = "600 30px 'IBM Plex Sans', sans-serif";
    ctx.fillText(kicker.toUpperCase(), PAD + 34, 239);
  }

  function footer(ctx, url) {
    ctx.save();
    ctx.translate(0, H - 150);
    ctx.rotate(-0.035);
    ctx.fillStyle = C.pink; ctx.fillRect(-40, 0, W + 80, 92);
    ctx.fillStyle = C.bg; ctx.font = "400 44px Anton, Impact, sans-serif";
    ctx.fillText("FLAMINGO-WATCH.COM", PAD, 62);
    ctx.fillStyle = C.green; ctx.fillText("✦", PAD + 520, 62);
    ctx.restore();
    if (url) linkSticker(ctx, url.replace(/^https?:\/\//, ""), H - 262);
  }

  // Looks like Instagram's link sticker, so people know where to tap. The real,
  // tappable sticker is added in Instagram (the link is already on the clipboard).
  function linkSticker(ctx, short, y) {
    ctx.font = "600 30px 'IBM Plex Sans', sans-serif";
    if (short.length > 44) short = short.slice(0, 43) + "…";
    const w = Math.min(W - PAD * 2, ctx.measureText(short).width + 110), h = 68;
    ctx.save();
    ctx.shadowColor = "rgba(0,0,0,.5)"; ctx.shadowBlur = 18; ctx.shadowOffsetY = 6;
    ctx.fillStyle = "#FFFFFF";
    ctx.beginPath(); ctx.roundRect(PAD, y, w, h, 16); ctx.fill();
    ctx.restore();
    // chain-link icon
    ctx.save();
    ctx.strokeStyle = C.pink; ctx.lineWidth = 5; ctx.lineCap = "round";
    ctx.translate(PAD + 42, y + h / 2); ctx.rotate(-Math.PI / 4);
    ctx.beginPath(); ctx.roundRect(-20, -8, 22, 16, 8); ctx.stroke();
    ctx.beginPath(); ctx.roundRect(-2, -8, 22, 16, 8); ctx.stroke();
    ctx.restore();
    ctx.fillStyle = "#0A0A0A";
    ctx.fillText(short, PAD + 78, y + 45);
  }

  function drawStory(ctx, d) {
    background(ctx);
    header(ctx, d.kicker);
    let y = 400;
    ctx.fillStyle = C.text; ctx.font = "600 70px 'IBM Plex Sans', sans-serif";
    y = text(ctx, wrap(ctx, d.title, W - PAD * 2, 7), PAD, y, 86) + 30;
    ctx.fillStyle = C.pink; ctx.fillRect(PAD, y, 120, 8); y += 80;
    if (d.summary) {
      ctx.fillStyle = C.soft; ctx.font = "400 44px 'IBM Plex Sans', sans-serif";
      y = text(ctx, wrap(ctx, d.summary, W - PAD * 2, 9), PAD, y, 62) + 40;
    }
    if (d.sources) {
      ctx.fillStyle = C.pink; ctx.font = "600 32px 'IBM Plex Sans', sans-serif";
      text(ctx, wrap(ctx, d.sources.toUpperCase(), W - PAD * 2, 2), PAD, Math.min(y + 10, H - 380), 42);
    }
    footer(ctx, d.url);
  }

  function drawDigest(ctx, d) {
    background(ctx);
    header(ctx, d.kicker);
    let y = 360;
    ctx.fillStyle = C.pink; ctx.font = "400 104px Anton, Impact, sans-serif";
    y = text(ctx, wrap(ctx, d.title.toUpperCase(), W - PAD * 2, 2), PAD, y + 40, 108) + 50;
    const points = d.points.slice(0, 5);
    const bottom = H - 290;  // keep clear of the link sticker and the pink tape
    // Pick the largest text size at which every point fits above the footer.
    let size = 30;
    for (const s of [44, 40, 36, 33, 30]) {
      ctx.font = `400 ${s}px 'IBM Plex Sans', sans-serif`;
      const need = points.reduce((sum, p) => sum + s + wrap(ctx, p, W - PAD * 2 - 70, 6).length * s * 1.35 + 34, 0);
      if (y + need <= bottom) { size = s; break; }
    }
    for (let i = 0; i < points.length; i++) {
      ctx.fillStyle = C.pink; ctx.font = `400 ${size + 12}px Anton, Impact, sans-serif`;
      ctx.fillText(String(i + 1), PAD, y + size);
      ctx.fillStyle = C.text; ctx.font = `400 ${size}px 'IBM Plex Sans', sans-serif`;
      y = text(ctx, wrap(ctx, points[i], W - PAD * 2 - 70, 6), PAD + 70, y + size, size * 1.35) + 34;
    }
    footer(ctx, d.url);
  }

  function loadSvg(markup) {
    return new Promise((resolve, reject) => {
      const url = URL.createObjectURL(new Blob([markup], { type: "image/svg+xml" }));
      const img = new Image();
      img.onload = () => { URL.revokeObjectURL(url); resolve(img); };
      img.onerror = (e) => { URL.revokeObjectURL(url); reject(e); };
      img.src = url;
    });
  }

  // RnBBnB Meter: both cells side by side with their numbers.
  function drawMeter(ctx, d, imgs) {
    background(ctx);
    header(ctx, d.kicker);
    ctx.fillStyle = C.pink; ctx.font = "400 150px Anton, Impact, sans-serif";
    ctx.fillText(d.title, PAD, 470);
    const colW = (W - PAD * 2 - 40) / 2, cellH = colW * 380 / 300;
    d.sides.forEach((s, i) => {
      const x = PAD + i * (colW + 40), color = s.side === "berisha" ? C.blue : C.pink;
      const top = 520 + cellH;
      ctx.drawImage(imgs[i], x, 520, colW, cellH);
      ctx.fillStyle = color; ctx.font = "400 110px Anton, Impact, sans-serif";
      ctx.fillText(s.sign, x, top + 115);
      ctx.fillStyle = C.muted; ctx.font = "600 30px 'IBM Plex Sans', sans-serif";
      ctx.fillText(s.name.toUpperCase(), x, top + 160);
      ctx.fillStyle = color; ctx.font = "400 170px Anton, Impact, sans-serif";
      ctx.fillText(String(s.total), x, top + 380);
    });
    ctx.fillStyle = C.soft; ctx.font = "400 34px 'IBM Plex Sans', sans-serif";
    text(ctx, wrap(ctx, d.summary || "", W - PAD * 2, 3), PAD, H - 375, 46);
    footer(ctx, d.url);
  }

  async function make(d) {
    await Promise.all([
      document.fonts.load("400 64px Anton"),
      document.fonts.load("600 48px 'IBM Plex Sans'"),
      document.fonts.load("400 48px 'IBM Plex Sans'"),
    ]).catch(() => {});
    const canvas = document.createElement("canvas");
    canvas.width = W; canvas.height = H;
    const ctx = canvas.getContext("2d");
    if (d.kind === "meter") drawMeter(ctx, d, await Promise.all(d.sides.map((s) => loadSvg(s.svg))));
    else (d.points ? drawDigest : drawStory)(ctx, d);
    return new Promise((resolve) => canvas.toBlob(resolve, "image/png"));
  }

  // Share the picture (phones) or download it (computers).
  async function shareImage(d) {
    const blob = await make(d);
    const file = new File([blob], `flamingo-watch-${d.name || "story"}.png`, { type: "image/png" });
    if (navigator.canShare && navigator.canShare({ files: [file] })) {
      try { await navigator.share({ files: [file], title: d.title }); return "shared"; }
      catch (e) { if (e && e.name === "AbortError") return "cancelled"; }
    }
    const a = document.createElement("a");
    a.href = URL.createObjectURL(blob);
    a.download = file.name;
    document.body.append(a); a.click(); a.remove();
    setTimeout(() => URL.revokeObjectURL(a.href), 10000);
    return "downloaded";
  }

  window.FlamingoImage = { make, shareImage };
})();
