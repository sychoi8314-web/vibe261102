(function () {
  "use strict";

  var site = window.SITE || {};
  var projects = window.PROJECTS || [];
  // 상세 페이지(portfolio/)에서는 상위 경로 기준으로 링크를 만든다
  var base = document.body.dataset.base || "";

  function escapeHtml(str) {
    return String(str).replace(/[&<>"']/g, function (ch) {
      return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[ch];
    });
  }

  /* ---------- Sample banner ---------- */
  if (site.sampleMode) {
    var banner = document.createElement("div");
    banner.className = "sample-banner";
    banner.textContent = "샘플 콘텐츠로 구성된 미리보기입니다. data/portfolio.js 와 index.html 의 내용을 실제 정보로 교체하세요.";
    var skip = document.querySelector(".skip-link");
    if (skip) skip.after(banner); else document.body.prepend(banner);
  }

  /* ---------- Mobile nav ---------- */
  var toggle = document.querySelector(".nav-toggle");
  var nav = document.getElementById("site-nav");
  if (toggle && nav) {
    toggle.addEventListener("click", function () {
      var open = toggle.getAttribute("aria-expanded") === "true";
      toggle.setAttribute("aria-expanded", String(!open));
      toggle.setAttribute("aria-label", open ? "메뉴 열기" : "메뉴 닫기");
      nav.classList.toggle("is-open", !open);
    });
    nav.addEventListener("click", function (e) {
      if (e.target.tagName === "A") {
        toggle.setAttribute("aria-expanded", "false");
        toggle.setAttribute("aria-label", "메뉴 열기");
        nav.classList.remove("is-open");
      }
    });
  }

  /* ---------- Toast ---------- */
  var toastEl = document.getElementById("toast");
  var toastTimer;
  function showToast(msg) {
    if (!toastEl) return;
    toastEl.textContent = msg;
    toastEl.classList.add("is-visible");
    clearTimeout(toastTimer);
    toastTimer = setTimeout(function () { toastEl.classList.remove("is-visible"); }, 2200);
  }

  /* ---------- Copy email ---------- */
  var copyBtn = document.getElementById("copy-email");
  if (copyBtn && site.email) {
    copyBtn.addEventListener("click", function () {
      var done = function () { showToast("이메일 주소를 복사했습니다"); };
      if (navigator.clipboard && window.isSecureContext) {
        navigator.clipboard.writeText(site.email).then(done, fallbackCopy);
      } else {
        fallbackCopy();
      }
      function fallbackCopy() {
        var ta = document.createElement("textarea");
        ta.value = site.email;
        ta.setAttribute("readonly", "");
        ta.style.position = "absolute";
        ta.style.left = "-9999px";
        document.body.appendChild(ta);
        ta.select();
        try { document.execCommand("copy"); done(); } catch (err) { showToast(site.email); }
        document.body.removeChild(ta);
      }
    });
  }

  /* ---------- Project cards ---------- */
  function cardHtml(p) {
    var hero = p.results && p.results[0];
    return (
      '<a class="project-card reveal" href="' + base + "portfolio/project.html?slug=" + encodeURIComponent(p.slug) + '"' +
      ' data-categories="' + escapeHtml(p.categories.join(",")) + '">' +
        '<div class="card-thumb" style="--c:' + escapeHtml(p.color) + '">' +
          (hero ? "<div><strong>" + escapeHtml(hero.value) + "</strong><small>" + escapeHtml(hero.label) + "</small></div>" : "") +
        "</div>" +
        '<div class="card-body">' +
          '<div class="card-tags">' + p.categories.map(function (c) { return "<span>" + escapeHtml(c) + "</span>"; }).join("") + "</div>" +
          "<h3>" + escapeHtml(p.title) + "</h3>" +
          "<p>" + escapeHtml(p.summary) + "</p>" +
          '<span class="card-more">자세히 보기 →</span>' +
        "</div>" +
      "</a>"
    );
  }

  var grid = document.getElementById("project-grid");
  if (grid) {
    grid.innerHTML = projects.map(cardHtml).join("");

    var filters = document.querySelectorAll(".filter");
    filters.forEach(function (btn) {
      btn.addEventListener("click", function () {
        var f = btn.dataset.filter;
        filters.forEach(function (b) {
          var active = b === btn;
          b.classList.toggle("is-active", active);
          b.setAttribute("aria-pressed", String(active));
        });
        grid.querySelectorAll(".project-card").forEach(function (card) {
          var cats = card.dataset.categories.split(",");
          card.hidden = f !== "all" && cats.indexOf(f) === -1;
        });
      });
    });
  }

  /* ---------- Project detail ---------- */
  var detail = document.getElementById("project-detail");
  if (detail) {
    var slug = new URLSearchParams(location.search).get("slug");
    var idx = -1;
    for (var i = 0; i < projects.length; i++) if (projects[i].slug === slug) idx = i;
    var p = projects[idx];

    if (!p) {
      detail.innerHTML =
        '<div class="container not-found"><h1 class="section-title">프로젝트를 찾을 수 없습니다</h1>' +
        "<p>주소가 잘못되었거나 삭제된 프로젝트입니다.</p>" +
        '<a class="btn btn-primary" href="' + base + 'index.html#portfolio">포트폴리오로 돌아가기</a></div>';
    } else {
      document.title = p.title + " | SY 포트폴리오";
      var list = function (items) {
        return '<ul class="check-list">' + items.map(function (t) { return "<li>" + escapeHtml(t) + "</li>"; }).join("") + "</ul>";
      };
      var section = function (en, ko, body) {
        return '<section class="detail-section reveal"><h2><small>' + en + "</small>" + ko + "</h2><div>" + body + "</div></section>";
      };
      var prev = projects[(idx - 1 + projects.length) % projects.length];
      var next = projects[(idx + 1) % projects.length];

      detail.innerHTML =
        '<header class="detail-hero" style="--c:' + escapeHtml(p.color) + '"><div class="container">' +
          '<a class="back-link" href="' + base + 'index.html#portfolio">← 포트폴리오 목록</a>' +
          '<div class="card-tags">' + p.categories.map(function (c) { return "<span>" + escapeHtml(c) + "</span>"; }).join("") + "</div>" +
          "<h1>" + escapeHtml(p.title) + "</h1>" +
          "<p>" + escapeHtml(p.summary) + "</p>" +
          '<dl class="meta-grid">' +
            "<div><dt>기간</dt><dd>" + escapeHtml(p.period) + "</dd></div>" +
            "<div><dt>소속</dt><dd>" + escapeHtml(p.org) + "</dd></div>" +
            "<div><dt>나의 역할</dt><dd>" + escapeHtml(p.role) + "</dd></div>" +
            "<div><dt>팀 구성</dt><dd>" + escapeHtml(p.team) + "</dd></div>" +
          "</dl>" +
        "</div></header>" +
        '<div class="container detail-body">' +
          section("Challenge", "과제", "<p>" + escapeHtml(p.challenge) + "</p>") +
          section("Insight &amp; Strategy", "전략", list(p.strategy)) +
          section("Execution", "실행", list(p.execution)) +
          section("Results", "성과",
            '<div class="result-grid">' + p.results.map(function (r) {
              return '<div class="result-card"><strong>' + escapeHtml(r.value) + "</strong><span>" + escapeHtml(r.label) + "</span></div>";
            }).join("") + "</div>") +
          section("Learnings", "배운 점", "<p>" + escapeHtml(p.learnings) + "</p>") +
          '<nav class="pager" aria-label="다른 프로젝트">' +
            '<a href="project.html?slug=' + encodeURIComponent(prev.slug) + '"><small>← 이전 프로젝트</small><strong>' + escapeHtml(prev.title) + "</strong></a>" +
            '<a class="next" href="project.html?slug=' + encodeURIComponent(next.slug) + '"><small>다음 프로젝트 →</small><strong>' + escapeHtml(next.title) + "</strong></a>" +
          "</nav>" +
        "</div>";
    }
  }

  /* ---------- Reveal on scroll ---------- */
  var revealEls = document.querySelectorAll(".reveal");
  var reduce = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
  if (reduce || !("IntersectionObserver" in window)) {
    revealEls.forEach(function (el) { el.classList.add("is-visible"); });
  } else {
    var io = new IntersectionObserver(function (entries) {
      entries.forEach(function (entry) {
        if (entry.isIntersecting) {
          entry.target.classList.add("is-visible");
          io.unobserve(entry.target);
        }
      });
    }, { threshold: 0.12 });
    revealEls.forEach(function (el) { io.observe(el); });
  }

  /* ---------- Footer year ---------- */
  var year = document.getElementById("year");
  if (year) year.textContent = new Date().getFullYear();
})();
