// Aurora OS website behaviour.
const REPO = "https://github.com/padovanl/auroraOS";
const VERSION = "latest";

const releasePage = `${REPO}/releases/latest`;

// Links that point into the repository and its releases.
document.querySelectorAll("[data-repo-link]").forEach((a) => {
  a.href = REPO + (a.dataset.path || "");
});
document.querySelectorAll("[data-download]").forEach((a) => {
  a.href = releasePage;
});
document.querySelectorAll("[data-checksum]").forEach((a) => {
  a.href = releasePage;
});
document.querySelectorAll("[data-version]").forEach((el) => { el.textContent = VERSION; });

fetch("https://api.github.com/repos/padovanl/auroraOS/releases/latest")
  .then((response) => {
    if (!response.ok) throw new Error(`GitHub returned ${response.status}`);
    return response.json();
  })
  .then((release) => {
    const iso = release.assets.find((asset) => /^aurora-os-(.+)-amd64\.iso$/.test(asset.name));
    if (!iso) return;

    const version = iso.name.match(/^aurora-os-(.+)-amd64\.iso$/)[1];
    const checksum = release.assets.find((asset) => asset.name === `${iso.name}.sha256`);
    document.querySelectorAll("[data-download]").forEach((a) => { a.href = iso.browser_download_url; });
    document.querySelectorAll("[data-checksum]").forEach((a) => {
      a.href = checksum ? checksum.browser_download_url : release.html_url;
    });
    document.querySelectorAll("[data-version]").forEach((el) => { el.textContent = version; });
    document.querySelectorAll("[data-copy^='sha256sum -c aurora-os-']").forEach((button) => {
      button.dataset.copy = `sha256sum -c ${iso.name}.sha256`;
    });
  })
  .catch((error) => console.warn("Could not load the latest Aurora OS release", error));

// Layout switcher.
const captions = {
  "desktop": "Menu bar on top, a floating dock with magnification, round colored window buttons.",
  "layout-classic": "A full-width taskbar at the bottom and classic window buttons on the right.",
  "layout-studio": "A dock along the left edge and the clock in the middle, like Ubuntu.",
  "layout-minimal": "A dock that hides until you need it: all screen, no clutter.",
};
const layoutImg = document.getElementById("layout-img");
document.querySelectorAll("[data-layout]").forEach((tab) => {
  tab.addEventListener("click", () => {
    document.querySelectorAll("[data-layout]").forEach((t) => t.classList.toggle("active", t === tab));
    layoutImg.style.opacity = 0;
    setTimeout(() => {
      layoutImg.src = `screenshots/${tab.dataset.layout}.png`;
      layoutImg.alt = `${tab.textContent} layout`;
      layoutImg.style.opacity = 1;
    }, 200);
    document.querySelector("[data-caption]").textContent = captions[tab.dataset.layout];
  });
});

// "Write the USB" tabs.
document.querySelectorAll("[data-os]").forEach((tab) => {
  tab.addEventListener("click", () => {
    document.querySelectorAll("[data-os]").forEach((t) => t.classList.toggle("active", t === tab));
    document.querySelectorAll("[data-panel]").forEach((p) => { p.hidden = p.dataset.panel !== tab.dataset.os; });
  });
});

// Copy buttons.
document.querySelectorAll("[data-copy]").forEach((btn) => {
  btn.addEventListener("click", async () => {
    try {
      await navigator.clipboard.writeText(btn.dataset.copy.replaceAll("0.1", VERSION));
      btn.textContent = "Copied";
      setTimeout(() => { btn.textContent = "Copy"; }, 1500);
    } catch (e) { /* clipboard unavailable (e.g. plain http) */ }
  });
});

// Click any screenshot to see it full size: it grows out of its place on the
// page into the middle of the screen, and shrinks back into place on close.
const box = document.querySelector(".lightbox") || (() => {
  const el = document.createElement("div");
  el.className = "lightbox";
  el.hidden = true;
  el.innerHTML = '<img alt="">';
  document.body.append(el);
  return el;
})();
const big = box.querySelector("img");
const ZOOM_MS = 420;
const EASE = "cubic-bezier(.2,.8,.2,1)";
let source = null;

// The transform that puts the full-size image exactly over the thumbnail.
function fromThumb(thumb) {
  const a = thumb.getBoundingClientRect();
  const b = big.getBoundingClientRect();
  if (!a.width || !b.width) return "scale(.85)";
  const dx = a.left + a.width / 2 - (b.left + b.width / 2);
  const dy = a.top + a.height / 2 - (b.top + b.height / 2);
  return `translate(${dx}px, ${dy}px) scale(${a.width / b.width}, ${a.height / b.height})`;
}

function openPhoto(img) {
  source = img;
  big.src = img.currentSrc || img.src;
  big.alt = img.alt;
  box.hidden = false;
  const grow = () => {
    img.style.visibility = "hidden";
    big.animate([{ transform: fromThumb(img), borderRadius: "6px" }, { transform: "none" }],
                { duration: ZOOM_MS, easing: EASE });
    box.animate([{ backgroundColor: "rgba(5,3,10,0)" }, { backgroundColor: "rgba(5,3,10,0.9)" }],
                { duration: ZOOM_MS, easing: "ease-out" });
  };
  if (big.complete && big.naturalWidth) grow(); else big.addEventListener("load", grow, { once: true });
}

function closePhoto() {
  if (box.hidden || box.dataset.closing) return;
  box.dataset.closing = "1";
  const img = source;
  const done = () => {
    box.hidden = true;
    delete box.dataset.closing;
    if (img) img.style.visibility = "";
  };
  const visible = img && img.getBoundingClientRect().bottom > 0 &&
    img.getBoundingClientRect().top < innerHeight;
  const to = visible ? fromThumb(img) : "scale(.85)";
  const shrink = big.animate([{ transform: "none" }, { transform: to, opacity: visible ? 1 : 0 }],
                             { duration: ZOOM_MS, easing: EASE, fill: "forwards" });
  box.animate([{ backgroundColor: "rgba(5,3,10,0.9)" }, { backgroundColor: "rgba(5,3,10,0)" }],
              { duration: ZOOM_MS, easing: "ease-in", fill: "forwards" });
  shrink.onfinish = () => { done(); shrink.cancel(); box.getAnimations().forEach((a) => a.cancel()); };
}

document.addEventListener("click", (e) => {
  const img = e.target.closest("img[data-zoom], img[src*='screenshots/']");
  if (img && !box.contains(img)) { e.preventDefault(); openPhoto(img); }
});
box.addEventListener("click", closePhoto);
document.addEventListener("keydown", (e) => { if (e.key === "Escape") closePhoto(); });

// Fade sections in as they scroll into view.
const io = new IntersectionObserver((entries) => {
  entries.forEach((e) => { if (e.isIntersecting) { e.target.classList.add("visible"); io.unobserve(e.target); } });
}, { threshold: 0.12 });
document.querySelectorAll(".reveal").forEach((el) => io.observe(el));

// ---------------------------------------------------------------------------
// Motion: the aurora sky, hero tilt, counters, rotating words, pointer glow,
// staggered reveals, the typing terminal and the scroll progress bar.
// The site animates the same for every visitor, whatever the browser's motion setting.
// ---------------------------------------------------------------------------
const still = false;

// Scroll progress.
const bar = document.createElement("div");
bar.className = "progress";
document.body.prepend(bar);
const onScroll = () => {
  const h = document.documentElement;
  bar.style.transform = `scaleX(${h.scrollTop / Math.max(1, h.scrollHeight - h.clientHeight)})`;
};
document.addEventListener("scroll", onScroll, { passive: true });
onScroll();

// The aurora sky: drifting ribbons and twinkling stars.
function sky(host) {
  const el = document.createElement("div");
  el.className = "sky";
  el.setAttribute("aria-hidden", "true");
  el.innerHTML = '<canvas></canvas><div class="ribbon"></div><div class="ribbon"></div><div class="ribbon"></div>';
  host.prepend(el);
  const canvas = el.querySelector("canvas");
  const ctx = canvas.getContext("2d");
  let stars = [];
  const resize = () => {
    const r = window.devicePixelRatio || 1;
    canvas.width = el.clientWidth * r;
    canvas.height = el.clientHeight * r;
    ctx.setTransform(r, 0, 0, r, 0, 0);
    stars = Array.from({ length: Math.round(el.clientWidth * el.clientHeight / 9000) }, () => ({
      x: Math.random() * el.clientWidth, y: Math.random() * el.clientHeight * 0.8,
      r: Math.random() * 1.2 + 0.2, p: Math.random() * Math.PI * 2, s: 0.4 + Math.random() * 1.4,
    }));
  };
  const draw = (t) => {
    ctx.clearRect(0, 0, el.clientWidth, el.clientHeight);
    for (const s of stars) {
      const a = still ? 0.7 : 0.35 + 0.65 * Math.abs(Math.sin(s.p + t / 1000 * s.s));
      ctx.globalAlpha = a;
      ctx.fillStyle = "#fff";
      ctx.beginPath();
      ctx.arc(s.x, s.y, s.r, 0, Math.PI * 2);
      ctx.fill();
    }
    if (!still) requestAnimationFrame(draw);
  };
  resize();
  window.addEventListener("resize", resize);
  requestAnimationFrame(draw);
}
const hero = document.querySelector(".hero");
if (hero) sky(hero);
else {
  const first = document.querySelector("main > .section");
  if (first) { first.classList.add("page-sky"); sky(first); }
}
document.querySelectorAll(".final-cta").forEach(sky);

// The hero screenshot straightens up as you scroll and leans toward the pointer.
const shot = document.querySelector(".hero-stage .hero-shot");
if (shot && !still) {
  let turn = 0;
  const update = () => {
    const p = Math.min(1, window.scrollY / (window.innerHeight * 0.6));
    shot.style.setProperty("--tilt", `${18 * (1 - p)}deg`);
    shot.style.setProperty("--zoom", `${0.94 + 0.06 * p}`);
    shot.style.setProperty("--turn", `${turn}deg`);
  };
  document.addEventListener("scroll", update, { passive: true });
  document.querySelector(".hero").addEventListener("pointermove", (e) => {
    turn = (e.clientX / window.innerWidth - 0.5) * 6;
    update();
  });
  update();
}

// Rotating words in the headline.
document.querySelectorAll("[data-rotate]").forEach((el) => {
  const words = el.dataset.rotate.split("|");
  let i = 0;
  if (still) return;
  setInterval(() => {
    i = (i + 1) % words.length;
    el.innerHTML = `<span class="word">${words[i]}</span>`;
  }, 2600);
});

// Numbers count up when they come into view.
const counter = new IntersectionObserver((entries) => {
  entries.forEach((e) => {
    if (!e.isIntersecting) return;
    counter.unobserve(e.target);
    const el = e.target;
    const target = parseFloat(el.dataset.count);
    const suffix = el.dataset.suffix || "";
    if (still) { el.textContent = target + suffix; return; }
    const start = performance.now();
    const tick = (now) => {
      const k = Math.min(1, (now - start) / 1400);
      const eased = 1 - Math.pow(1 - k, 3);
      el.textContent = Math.round(target * eased) + suffix;
      if (k < 1) requestAnimationFrame(tick);
    };
    requestAnimationFrame(tick);
  });
}, { threshold: 0.6 });
document.querySelectorAll("[data-count]").forEach((el) => counter.observe(el));

// A soft glow follows the pointer over cards and tiles.
document.querySelectorAll(".card, .tile, .download-card").forEach((el) => {
  el.addEventListener("pointermove", (e) => {
    const r = el.getBoundingClientRect();
    el.style.setProperty("--mx", `${e.clientX - r.left}px`);
    el.style.setProperty("--my", `${e.clientY - r.top}px`);
  });
});

// Items in the same group appear one after another.
document.querySelectorAll(".app-groups, .bento, .grid-2, .steps, .faq").forEach((group) => {
  group.querySelectorAll(":scope > .reveal").forEach((el, i) => el.style.setProperty("--i", i % 8));
});

// The terminal types its session when it comes into view.
document.querySelectorAll(".terminal pre").forEach((pre) => {
  if (still) return;
  const lines = pre.innerHTML.split("\n");
  pre.innerHTML = lines.map((l) => `<span class="line" hidden>${l || " "}</span>`).join("");
  const spans = [...pre.querySelectorAll(".line")];
  const caret = document.createElement("span");
  caret.className = "caret";
  const run = () => {
    let i = 0;
    const next = () => {
      if (i >= spans.length) { spans[spans.length - 1].append(caret); return; }
      const line = spans[i++];
      line.hidden = false;
      line.append(caret);
      const typed = line.textContent.includes("❯");
      setTimeout(next, typed ? 650 : 140);
    };
    next();
  };
  const seen = new IntersectionObserver((entries) => {
    if (entries.some((e) => e.isIntersecting)) { seen.disconnect(); run(); }
  }, { threshold: 0.4 });
  seen.observe(pre);
});

// The icon marquees on the home page (each row twice, for a seamless loop).
const MARQUEE = {
  apps: ["org.gnome.Geary", "org.gnome.Calendar", "org.gnome.Weather", "aurora-assistant",
    "org.gnome.Maps", "org.gnome.clocks", "org.gnome.Calculator", "aurora-devhub",
    "org.gnome.Loupe", "org.gnome.Rhythmbox3", "io.github.celluloid_player.Celluloid",
    "org.gnome.Snapshot", "org.gnome.Software", "org.gnome.Ptyxis", "aurora-gamehub",
    "system-file-manager", "preferences-system", "org.gnome.SystemMonitor", "org.gnome.baobab",
    "org.gnome.seahorse.Application", "org.gnome.Characters", "org.gnome.font-viewer",
    "timeshift", "org.gnome.DejaDup", "org.gnome.Firmware", "org.gnome.TextEditor",
    "org.gnome.Papers", "org.gnome.SoundRecorder"],
  files: ["folder", "application-pdf", "user-home", "text-x-python", "folder-download",
    "image-x-generic", "folder-music", "package-x-generic", "folder-pictures",
    "x-office-document", "folder-videos", "x-office-spreadsheet", "folder-documents",
    "text-html", "folder-development", "application-json", "text-markdown", "application-x-deb",
    "audio-x-generic", "video-x-generic", "text-x-rust", "text-x-go", "application-javascript",
    "user-trash"],
};
document.querySelectorAll("[data-marquee]").forEach((row) => {
  const names = MARQUEE[row.dataset.marquee] || [];
  const html = names.map((n) => `<img src="assets/icons/${n}.svg" alt="" loading="lazy">`).join("");
  row.innerHTML = html + html;
});

// Documentation: filter topics on the index, and highlight the section in view.
const docSearch = document.querySelector("[data-doc-search]");
if (docSearch) {
  const results = document.querySelector("[data-doc-results]");
  const cards = document.querySelector(".doc-cards");
  docSearch.addEventListener("input", () => {
    const q = docSearch.value.trim().toLowerCase();
    results.hidden = !q;
    cards.style.display = q ? "none" : "";
    results.querySelectorAll("a").forEach((a) => {
      a.hidden = !a.dataset.topic.includes(q) && !a.textContent.toLowerCase().includes(q);
    });
  });
}
const docHeads = [...document.querySelectorAll(".doc-body h2[id]")];
if (docHeads.length) {
  const links = [...document.querySelectorAll(".doc-toc a, .doc-sub a")];
  let pinned = null;  // the section just clicked, until the scroll settles
  let settle = 0;
  const mark = (id) => links.forEach((a) => a.classList.toggle("current", a.getAttribute("href") === `#${id}`));
  const spy = () => {
    if (pinned) return mark(pinned);
    let current = docHeads[0].id;
    for (const h of docHeads) if (h.getBoundingClientRect().top < 160) current = h.id;
    // At the very bottom the last sections can't reach the top: pick the last one.
    if (window.innerHeight + window.scrollY >= document.documentElement.scrollHeight - 4) {
      current = docHeads[docHeads.length - 1].id;
    }
    mark(current);
  };
  links.forEach((a) => a.addEventListener("click", () => {
    pinned = a.getAttribute("href").slice(1);
    mark(pinned);
  }));
  document.addEventListener("scroll", () => {
    clearTimeout(settle);
    settle = setTimeout(() => { pinned = null; }, 250);
    spy();
  }, { passive: true });
  if (location.hash) pinned = location.hash.slice(1);
  spy();
  setTimeout(() => { pinned = null; }, 1200);
}

// Expandable answers open and close smoothly.
document.querySelectorAll("details").forEach((d) => {
  const summary = d.querySelector("summary");
  if (!summary) return;  // user-triggered and short: animated even with reduced motion
  let anim = null;
  const finish = (open) => {
    d.open = open;
    d.style.height = d.style.overflow = "";
    anim = null;
  };
  summary.addEventListener("click", (e) => {
    e.preventDefault();
    if (anim) anim.cancel();
    const start = `${d.offsetHeight}px`;
    if (!d.open) {
      d.open = true;
      d.classList.add("opening");
      const end = `${d.offsetHeight}px`;
      requestAnimationFrame(() => d.classList.remove("opening"));
      anim = d.animate({ height: [start, end] }, { duration: 480, easing: "cubic-bezier(.2,.8,.2,1)" });
      anim.onfinish = () => finish(true);
    } else {
      const end = `${summary.offsetHeight + parseFloat(getComputedStyle(d).paddingTop) +
        parseFloat(getComputedStyle(d).paddingBottom) + 2}px`;
      d.classList.add("opening");
      anim = d.animate({ height: [start, end] }, { duration: 360, easing: "cubic-bezier(.4,0,.2,1)" });
      anim.onfinish = () => { d.classList.remove("opening"); finish(false); };
    }
  });
});

// Links to a place on the same page glide there (user-triggered, so even with
// reduced motion), stopping just under the sticky navigation bar.
function glideTo(target, hash) {
  const nav = document.querySelector(".nav");
  const offset = (nav ? nav.offsetHeight : 0) + 12;
  const startY = window.scrollY;
  const endY = Math.max(0, target.getBoundingClientRect().top + startY - offset);
  const distance = endY - startY;
  const duration = Math.min(1100, 380 + Math.abs(distance) * 0.25);
  const t0 = performance.now();
  const ease = (t) => (t < 0.5 ? 4 * t * t * t : 1 - Math.pow(-2 * t + 2, 3) / 2);
  const step = (now) => {
    const k = Math.min(1, (now - t0) / duration);
    window.scrollTo(0, startY + distance * ease(k));
    if (k < 1) requestAnimationFrame(step);
    else history.replaceState(null, "", hash);
  };
  requestAnimationFrame(step);
}
document.addEventListener("click", (e) => {
  const a = e.target.closest('a[href*="#"]');
  if (!a || e.defaultPrevented || e.button !== 0 || e.metaKey || e.ctrlKey || e.shiftKey) return;
  const url = new URL(a.href, location.href);
  if (url.pathname !== location.pathname || !url.hash || url.hash === "#") return;
  const target = document.getElementById(decodeURIComponent(url.hash.slice(1)));
  if (!target) return;
  e.preventDefault();
  glideTo(target, url.hash);
});

// Back to top: a round arrow in the bottom-right corner once you have scrolled
// down a screen or so, gliding smoothly up.
(() => {
  const top = document.createElement("button");
  top.className = "to-top";
  top.type = "button";
  top.setAttribute("aria-label", "Back to top");
  top.title = "Back to top";
  top.innerHTML = '<svg viewBox="0 0 24 24" width="22" height="22" aria-hidden="true">' +
    '<path d="M12 19V5M5 12l7-7 7 7" fill="none" stroke="currentColor" stroke-width="2.4" ' +
    'stroke-linecap="round" stroke-linejoin="round"/></svg>';
  document.body.append(top);
  const update = () => top.classList.toggle("shown", window.scrollY > window.innerHeight * 0.8);
  window.addEventListener("scroll", update, { passive: true });
  update();
  top.addEventListener("click", () => {
    const startY = window.scrollY;
    const duration = Math.min(1100, 380 + startY * 0.2);
    const t0 = performance.now();
    const ease = (t) => (t < 0.5 ? 4 * t * t * t : 1 - Math.pow(-2 * t + 2, 3) / 2);
    const step = (now) => {
      const k = Math.min(1, (now - t0) / duration);
      window.scrollTo(0, startY * (1 - ease(k)));
      if (k < 1) requestAnimationFrame(step);
    };
    requestAnimationFrame(step);
  });
})();

// The home page's first screen is sized to the window minus the menu bar.
(() => {
  const nav = document.querySelector(".nav");
  if (!nav) return;
  const set = () => document.documentElement.style.setProperty("--nav-h", `${nav.offsetHeight}px`);
  set();
  window.addEventListener("resize", set);
})();
