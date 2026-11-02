/* ============================================================
   MediTrust — Animations v3.2 "Smooth"
   rAF-driven magnetic · GPU reveal · tab-aware orb pause
   ============================================================ */

(function () {
  'use strict';

  var reduceMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
  var canHover     = window.matchMedia('(hover: hover) and (pointer: fine)').matches;

  /* ---------- 1. Scroll Reveal (delay via CSS, not setTimeout) ---------- */
  if (!reduceMotion && 'IntersectionObserver' in window) {
    var io = new IntersectionObserver(function (entries) {
      entries.forEach(function (entry) {
        if (entry.isIntersecting) {
          entry.target.classList.add('in');
          io.unobserve(entry.target);
        }
      });
    }, { threshold: 0.12, rootMargin: '0px 0px -40px 0px' });

    document.querySelectorAll('[data-reveal]').forEach(function (el) {
      var delay = parseInt(el.dataset.delay || '0', 10);
      if (delay) el.style.transitionDelay = delay + 'ms';
      io.observe(el);
    });
  } else {
    document.querySelectorAll('[data-reveal]').forEach(function (el) {
      el.classList.add('in');
    });
  }

  /* ---------- 2. Number Counters (rAF, eased) ---------- */
  if (!reduceMotion && 'IntersectionObserver' in window) {
    var counters = document.querySelectorAll('[data-counter]');
    if (counters.length) {
      var cio = new IntersectionObserver(function (entries) {
        entries.forEach(function (entry) {
          if (!entry.isIntersecting) return;
          var el = entry.target;
          var target = parseFloat(el.dataset.counter) || 0;
          var decimals = (String(target).split('.')[1] || '').length;
          var duration = 1200;
          var start = performance.now();

          function tick(now) {
            var p = Math.min((now - start) / duration, 1);
            var eased = 1 - Math.pow(1 - p, 4);       /* quartic ease-out */
            var val = target * eased;
            el.textContent = decimals ? val.toFixed(decimals) : Math.floor(val).toLocaleString();
            if (p < 1) requestAnimationFrame(tick);
            else el.textContent = decimals ? target.toFixed(decimals) : target.toLocaleString();
          }
          requestAnimationFrame(tick);
          cio.unobserve(el);
        });
      }, { threshold: 0.35 });
      counters.forEach(function (c) { cio.observe(c); });
    }
  }

  /* ---------- 3. Magnetic Buttons (rAF + spring return) ---------- */
  if (!reduceMotion && canHover) {
    var STRENGTH = 0.16;
    document.querySelectorAll('.magnetic').forEach(function (el) {
      var rafId = null;
      var tx = 0, ty = 0;      /* target offset */
      var cx = 0, cy = 0;      /* current offset */

      function tick() {
        cx += (tx - cx) * 0.22;
        cy += (ty - cy) * 0.22;
        el.style.transform = 'translate3d(' + cx.toFixed(2) + 'px, ' + cy.toFixed(2) + 'px, 0)';

        if (Math.abs(tx - cx) > 0.15 || Math.abs(ty - cy) > 0.15) {
          rafId = requestAnimationFrame(tick);
        } else {
          cx = tx; cy = ty;
          el.style.transform = tx === 0 && ty === 0 ? '' : 'translate3d(' + cx + 'px, ' + cy + 'px, 0)';
          rafId = null;
        }
      }

      function ensure() {
        if (rafId === null) rafId = requestAnimationFrame(tick);
      }

      el.addEventListener('mouseenter', ensure);
      el.addEventListener('mousemove', function (e) {
        var r = el.getBoundingClientRect();
        tx = (e.clientX - r.left - r.width  / 2) * STRENGTH;
        ty = (e.clientY - r.top  - r.height / 2) * STRENGTH;
        ensure();
      });
      el.addEventListener('mouseleave', function () {
        tx = 0; ty = 0;
        ensure();
      });
    });
  }

  /* ---------- 4. Ripple (soft) ---------- */
  document.querySelectorAll('.btn').forEach(function (btn) {
    btn.addEventListener('click', function (e) {
      if (reduceMotion) return;
      var r = this.getBoundingClientRect();
      var size = Math.max(r.width, r.height);
      var ripple = document.createElement('span');
      ripple.className = 'ripple';
      ripple.style.width  = ripple.style.height = size + 'px';
      ripple.style.left   = (e.clientX - r.left - size / 2) + 'px';
      ripple.style.top    = (e.clientY - r.top  - size / 2) + 'px';
      this.appendChild(ripple);
      setTimeout(function () { ripple.remove(); }, 700);
    });
  });

  /* ---------- 5. Header Scroll State (rAF-throttled) ---------- */
  var header = document.querySelector('.top');
  if (header) {
    var scrollQueued = false;
    function applyHeader() {
      header.classList.toggle('scrolled', window.scrollY > 20);
      scrollQueued = false;
    }
    window.addEventListener('scroll', function () {
      if (!scrollQueued) {
        scrollQueued = true;
        requestAnimationFrame(applyHeader);
      }
    }, { passive: true });
    applyHeader();
  }

  /* ---------- 6. Smooth In-page Anchors ---------- */
  document.querySelectorAll('a[href^="#"]').forEach(function (a) {
    a.addEventListener('click', function (e) {
      var id = a.getAttribute('href');
      if (!id || id.length < 2) return;
      var target = document.querySelector(id);
      if (!target) return;
      e.preventDefault();
      target.scrollIntoView({ behavior: reduceMotion ? 'auto' : 'smooth', block: 'start' });
    });
  });

  /* ---------- 7. Pause decorative animations when tab hidden ---------- */
  document.addEventListener('visibilitychange', function () {
    document.body.classList.toggle('tab-hidden', document.hidden);
  });

})();