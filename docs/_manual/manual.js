// Aurora OS Documentation: search, theme switch, mobile menu, copy buttons and
// the "On this page" highlight. No dependencies.
(function () {
  "use strict";
  var root = document.documentElement;

  // Light or dark: the system's choice until the reader picks one.
  var themeButton = document.querySelector(".theme");
  if (themeButton) {
    themeButton.addEventListener("click", function () {
      var dark = root.dataset.theme
        ? root.dataset.theme === "dark"
        : window.matchMedia("(prefers-color-scheme: dark)").matches;
      root.dataset.theme = dark ? "light" : "dark";
      try { localStorage.setItem("aurora-docs-theme", root.dataset.theme); } catch (e) {}
    });
  }

  var menu = document.querySelector(".menu");
  if (menu) {
    menu.addEventListener("click", function () {
      var open = document.body.classList.toggle("nav-open");
      menu.setAttribute("aria-expanded", open ? "true" : "false");
    });
  }

  // Copy buttons on code blocks.
  document.querySelectorAll("pre").forEach(function (pre) {
    var button = document.createElement("button");
    button.className = "copy";
    button.type = "button";
    button.textContent = "Copy";
    button.addEventListener("click", function () {
      var text = pre.querySelector("code") ? pre.querySelector("code").innerText : pre.innerText;
      navigator.clipboard.writeText(text.trim()).then(function () {
        button.textContent = "Copied";
        setTimeout(function () { button.textContent = "Copy"; }, 1400);
      });
    });
    pre.appendChild(button);
  });

  // "On this page": highlight the section being read.
  var tocLinks = Array.prototype.slice.call(document.querySelectorAll(".toc a"));
  if (tocLinks.length && "IntersectionObserver" in window) {
    var byId = {};
    tocLinks.forEach(function (a) { byId[a.getAttribute("href").slice(1)] = a; });
    var observer = new IntersectionObserver(function (entries) {
      entries.forEach(function (entry) {
        if (entry.isIntersecting) {
          tocLinks.forEach(function (a) { a.classList.remove("active"); });
          var link = byId[entry.target.id];
          if (link) link.classList.add("active");
        }
      });
    }, { rootMargin: "-70px 0px -70% 0px" });
    Object.keys(byId).forEach(function (id) {
      var el = document.getElementById(id);
      if (el) observer.observe(el);
    });
  }

  // Search: a small index of every page, scored by title, headings and text.
  var input = document.getElementById("q");
  var box = document.getElementById("results");
  var index = null;
  var active = -1;

  function load(done) {
    if (index) return done();
    fetch("search.json").then(function (r) { return r.json(); }).then(function (data) {
      index = data;
      done();
    }).catch(function () { index = []; done(); });
  }

  function escapeHtml(s) {
    return s.replace(/[&<>"]/g, function (c) {
      return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c];
    });
  }

  function snippet(text, words) {
    var lower = text.toLowerCase();
    var at = -1;
    words.forEach(function (w) { var i = lower.indexOf(w); if (i >= 0 && (at < 0 || i < at)) at = i; });
    if (at < 0) return "";
    var start = Math.max(0, at - 50);
    var piece = (start ? "…" : "") + text.slice(start, at + 110) + "…";
    var safe = escapeHtml(piece);
    words.forEach(function (w) {
      if (!w) return;
      safe = safe.replace(new RegExp("(" + w.replace(/[.*+?^${}()|[\]\\]/g, "\\$&") + ")", "ig"), "<mark>$1</mark>");
    });
    return safe;
  }

  function run() {
    var q = input.value.trim().toLowerCase();
    if (q.length < 2) { box.classList.remove("open"); box.innerHTML = ""; return; }
    var words = q.split(/\s+/);
    var scored = [];
    index.forEach(function (page) {
      var score = 0;
      var title = page.t.toLowerCase();
      var heads = page.h.join(" ").toLowerCase();
      var text = page.x.toLowerCase();
      var all = true;
      words.forEach(function (w) {
        var s = 0;
        if (title.indexOf(w) >= 0) s += 10;
        if (heads.indexOf(w) >= 0) s += 5;
        if (page.d.toLowerCase().indexOf(w) >= 0) s += 3;
        if (text.indexOf(w) >= 0) s += 1;
        if (!s) all = false;
        score += s;
      });
      if (all && score) scored.push({ page: page, score: score });
    });
    scored.sort(function (a, b) { return b.score - a.score; });
    active = -1;
    if (!scored.length) {
      box.innerHTML = '<a><small>No results for “' + escapeHtml(q) + '”.</small></a>';
    } else {
      box.innerHTML = scored.slice(0, 12).map(function (r) {
        var hit = r.page.h.filter(function (h) {
          return words.every(function (w) { return h.toLowerCase().indexOf(w) >= 0; });
        })[0];
        var href = r.page.u + (hit ? "#" + hit.toLowerCase().replace(/<[^>]+>/g, "").replace(/[^a-z0-9]+/g, "-").replace(/^-|-$/g, "") : "");
        return '<a href="' + href + '"><strong>' + escapeHtml(r.page.t) + '</strong>' +
          (hit ? ' › ' + escapeHtml(hit) : '') +
          '<small>' + escapeHtml(r.page.s) + ' · ' + (snippet(r.page.x, words) || escapeHtml(r.page.d)) + '</small></a>';
      }).join("");
    }
    box.classList.add("open");
  }

  if (input) {
    input.addEventListener("input", function () { load(run); });
    input.addEventListener("focus", function () { load(run); });
    input.addEventListener("keydown", function (e) {
      var links = box.querySelectorAll("a[href]");
      if (e.key === "ArrowDown" || e.key === "ArrowUp") {
        e.preventDefault();
        if (!links.length) return;
        active = (active + (e.key === "ArrowDown" ? 1 : -1) + links.length) % links.length;
        links.forEach(function (a, i) { a.classList.toggle("active", i === active); });
      } else if (e.key === "Enter") {
        var target = links[active >= 0 ? active : 0];
        if (target) window.location.href = target.getAttribute("href");
      } else if (e.key === "Escape") {
        box.classList.remove("open");
        input.blur();
      }
    });
    document.addEventListener("click", function (e) {
      if (!e.target.closest(".search")) box.classList.remove("open");
    });
    document.addEventListener("keydown", function (e) {
      if (e.key === "/" && document.activeElement !== input &&
          !/input|textarea/i.test(document.activeElement.tagName)) {
        e.preventDefault();
        input.focus();
      }
    });
  }
})();
