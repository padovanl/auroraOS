// Aurora OS website behaviour. Edit these two constants when publishing.
const REPO = "https://github.com/padovanl/aurora-os";
const VERSION = "0.1";

const iso = `aurora-os-${VERSION}-amd64.iso`;

// Links that point into the repository and its releases.
document.querySelectorAll("[data-repo-link]").forEach((a) => {
  a.href = REPO + (a.dataset.path || "");
});
document.querySelectorAll("[data-download]").forEach((a) => {
  a.href = `${REPO}/releases/latest/download/${iso}`;
});
document.querySelectorAll("[data-checksum]").forEach((a) => {
  a.href = `${REPO}/releases/latest/download/${iso}.sha256`;
});
document.querySelectorAll("[data-version]").forEach((el) => { el.textContent = VERSION; });

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

// Click a screenshot to see it full size.
const box = document.querySelector(".lightbox");
document.querySelectorAll("[data-zoom]").forEach((img) => {
  img.addEventListener("click", () => {
    box.querySelector("img").src = img.src;
    box.querySelector("img").alt = img.alt;
    box.hidden = false;
  });
});
box.addEventListener("click", () => { box.hidden = true; });
document.addEventListener("keydown", (e) => { if (e.key === "Escape") box.hidden = true; });

// Fade sections in as they scroll into view.
const io = new IntersectionObserver((entries) => {
  entries.forEach((e) => { if (e.isIntersecting) { e.target.classList.add("visible"); io.unobserve(e.target); } });
}, { threshold: 0.12 });
document.querySelectorAll(".reveal").forEach((el) => io.observe(el));
