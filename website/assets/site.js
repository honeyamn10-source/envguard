/* ============================================================
   envguard website — progressive interactions
   ------------------------------------------------------------
   Dependency-free UI behaviour for the advanced product site.
   Dynamic public text changes announce `envguard:content-updated`
   so the opt-in translation layer can re-run when appropriate.
   ============================================================ */

(function () {
  'use strict';

  var root = document.documentElement;
  root.classList.add('js');

  function announce(source) {
    try {
      document.dispatchEvent(new CustomEvent('envguard:content-updated', {
        detail: { source: 'site.js', id: source }
      }));
    } catch (error) {
      // CustomEvent is unavailable only in very old browsers; UI still works.
      if (window.console && typeof window.console.warn === 'function') {
        window.console.warn('[EnvGuard UI] could not announce content update', error);
      }
    }
  }

  function setTheme(theme) {
    root.setAttribute('data-theme', theme);
    var isLight = theme === 'light';
    var toggle = document.getElementById('theme-toggle');
    var icon = document.getElementById('theme-icon');
    var meta = document.querySelector('meta[name="theme-color"]');

    if (toggle) {
      toggle.setAttribute('aria-label', isLight ? 'Switch to dark theme' : 'Switch to light theme');
      toggle.setAttribute('aria-pressed', String(isLight));
    }
    if (icon) icon.textContent = isLight ? '☾' : '☀';
    if (meta) meta.setAttribute('content', isLight ? '#f5f8f2' : '#0b0f10');

    try {
      window.localStorage.setItem('envguard-theme', theme);
    } catch (error) {
      // Storage can be disabled; the in-memory theme still works.
    }
  }

  function initTheme() {
    var stored = null;
    try {
      stored = window.localStorage.getItem('envguard-theme');
    } catch (error) {
      stored = null;
    }
    setTheme(stored === 'light' ? 'light' : 'dark');

    var toggle = document.getElementById('theme-toggle');
    if (toggle) {
      toggle.addEventListener('click', function () {
        setTheme(root.getAttribute('data-theme') === 'light' ? 'dark' : 'light');
      });
    }
  }

  function initNavigation() {
    var header = document.querySelector('.site-header');
    var burger = document.getElementById('nav-burger');
    var nav = document.getElementById('primary-nav');
    if (!header || !burger || !nav) return;

    function closeMenu() {
      header.classList.remove('nav-open');
      burger.setAttribute('aria-expanded', 'false');
      burger.setAttribute('aria-label', 'Open navigation');
    }

    burger.addEventListener('click', function () {
      var open = !header.classList.contains('nav-open');
      header.classList.toggle('nav-open', open);
      burger.setAttribute('aria-expanded', String(open));
      burger.setAttribute('aria-label', open ? 'Close navigation' : 'Open navigation');
    });

    nav.addEventListener('click', function (event) {
      if (event.target.closest('a')) closeMenu();
    });

    document.addEventListener('click', function (event) {
      if (!header.contains(event.target)) closeMenu();
    });

    document.addEventListener('keydown', function (event) {
      if (event.key === 'Escape') closeMenu();
    });

    window.addEventListener('resize', function () {
      if (window.innerWidth > 640) closeMenu();
    });
  }

  function initScrollIndicators() {
    var progress = document.getElementById('scroll-progress');
    var toTop = document.getElementById('to-top');
    var ticking = false;

    function update() {
      var max = document.documentElement.scrollHeight - window.innerHeight;
      var ratio = max > 0 ? Math.min(1, Math.max(0, window.scrollY / max)) : 0;
      if (progress) progress.style.width = (ratio * 100).toFixed(2) + '%';
      if (toTop) toTop.hidden = window.scrollY < 520;
      ticking = false;
    }

    window.addEventListener('scroll', function () {
      if (ticking) return;
      ticking = true;
      window.requestAnimationFrame(update);
    }, { passive: true });

    window.addEventListener('resize', update);
    update();

    if (toTop) {
      toTop.addEventListener('click', function () {
        window.scrollTo({ top: 0, behavior: 'smooth' });
      });
    }
  }

  function initActiveNav() {
    var links = Array.prototype.slice.call(document.querySelectorAll('.primary-nav a[href^="#"]'));
    if (!links.length || !('IntersectionObserver' in window)) return;

    var sections = links
      .map(function (link) { return document.querySelector(link.getAttribute('href')); })
      .filter(Boolean);
    if (!sections.length) return;

    var observer = new IntersectionObserver(function (entries) {
      entries.forEach(function (entry) {
        if (!entry.isIntersecting) return;
        links.forEach(function (link) {
          link.classList.toggle('active', link.getAttribute('href') === '#' + entry.target.id);
        });
      });
    }, { rootMargin: '-45% 0px -45% 0px' });

    sections.forEach(function (section) { observer.observe(section); });
  }

  function initReveal() {
    var items = Array.prototype.slice.call(document.querySelectorAll('.reveal'));
    if (!items.length) return;
    if (!('IntersectionObserver' in window)) {
      items.forEach(function (item) { item.classList.add('visible'); });
      return;
    }
    var observer = new IntersectionObserver(function (entries) {
      entries.forEach(function (entry) {
        if (!entry.isIntersecting) return;
        entry.target.classList.add('visible');
        observer.unobserve(entry.target);
      });
    }, { threshold: 0.12 });
    items.forEach(function (item) { observer.observe(item); });
  }

  function initWorkflow() {
    var choices = Array.prototype.slice.call(document.querySelectorAll('[data-choice]'));
    var title = document.getElementById('explore-title');
    var text = document.getElementById('explore-text');
    var index = document.getElementById('explore-index');
    if (!choices.length || !title || !text || !index) return;

    function activate(button) {
      choices.forEach(function (item) {
        item.setAttribute('aria-pressed', String(item === button));
      });
      title.textContent = button.dataset.title || '';
      text.textContent = button.dataset.detail || '';
      var position = choices.indexOf(button) + 1;
      index.textContent = String(position).padStart(2, '0') + ' / ' + String(choices.length).padStart(2, '0');
      announce('workflow');
    }

    choices.forEach(function (button, position) {
      button.addEventListener('click', function () { activate(button); });
      button.addEventListener('keydown', function (event) {
        var next = null;
        if (event.key === 'ArrowDown' || event.key === 'ArrowRight') {
          next = (position + 1) % choices.length;
        } else if (event.key === 'ArrowUp' || event.key === 'ArrowLeft') {
          next = (position - 1 + choices.length) % choices.length;
        } else if (event.key === 'Home') {
          next = 0;
        } else if (event.key === 'End') {
          next = choices.length - 1;
        }
        if (next === null) return;
        event.preventDefault();
        choices[next].focus();
        activate(choices[next]);
      });
    });
  }

  function initCommandConsole() {
    var tabs = Array.prototype.slice.call(document.querySelectorAll('[data-command-tab]'));
    var panels = Array.prototype.slice.call(document.querySelectorAll('[data-command-panel]'));
    var title = document.getElementById('console-title');
    var copyButton = document.getElementById('copy-command');
    if (!tabs.length || !panels.length) return;

    var titles = {
      scan: 'Scan for likely secrets',
      check: 'Check environment files',
      exit: 'Exit-code contract'
    };

    function activePanel() {
      return panels.find(function (panel) {
        return panel.getAttribute('data-command-panel') === activeName;
      });
    }

    var activeName = tabs.find(function (tab) {
      return tab.getAttribute('aria-selected') === 'true';
    });
    activeName = activeName ? activeName.getAttribute('data-command-tab') : tabs[0].getAttribute('data-command-tab');

    function activate(name, focusTab) {
      activeName = name;
      tabs.forEach(function (tab) {
        var selected = tab.getAttribute('data-command-tab') === name;
        tab.setAttribute('aria-selected', String(selected));
        tab.tabIndex = selected ? 0 : -1;
        if (selected && focusTab) tab.focus();
      });
      panels.forEach(function (panel) {
        panel.hidden = panel.getAttribute('data-command-panel') !== name;
      });
      if (title) title.textContent = titles[name] || name;
      if (copyButton) copyButton.setAttribute('aria-label', 'Copy active ' + name + ' command');
      announce('command-panel');
    }

    tabs.forEach(function (tab, position) {
      tab.addEventListener('click', function () {
        activate(tab.getAttribute('data-command-tab'), false);
      });
      tab.addEventListener('keydown', function (event) {
        var next = null;
        if (event.key === 'ArrowRight' || event.key === 'ArrowDown') {
          next = (position + 1) % tabs.length;
        } else if (event.key === 'ArrowLeft' || event.key === 'ArrowUp') {
          next = (position - 1 + tabs.length) % tabs.length;
        } else if (event.key === 'Home') {
          next = 0;
        } else if (event.key === 'End') {
          next = tabs.length - 1;
        }
        if (next === null) return;
        event.preventDefault();
        activate(tabs[next].getAttribute('data-command-tab'), true);
      });
    });

    activate(activeName, false); // normalise tabindex without announcing on load

    if (copyButton) {
      copyButton.addEventListener('click', function () {
        var panel = activePanel();
        var source = panel && panel.querySelector('[data-copy-source]');
        if (source) copyText(source.textContent, copyButton);
      });
    }
  }

  async function copyText(text, button) {
    var original = button.textContent;
    try {
      if (navigator.clipboard && navigator.clipboard.writeText) {
        await navigator.clipboard.writeText(text);
      } else {
        var area = document.createElement('textarea');
        area.value = text;
        area.setAttribute('readonly', '');
        area.style.position = 'fixed';
        area.style.opacity = '0';
        document.body.appendChild(area);
        area.select();
        document.execCommand('copy');
        area.remove();
      }
      button.textContent = 'Copied';
    } catch (error) {
      button.textContent = 'Select code to copy';
    }
    window.setTimeout(function () { button.textContent = original; }, 2200);
  }

  function initCopyButtons() {
    document.querySelectorAll('[data-copy]').forEach(function (button) {
      button.addEventListener('click', function () {
        var target = document.getElementById(button.getAttribute('data-copy'));
        if (target) copyText(target.textContent, button);
      });
    });
  }

  function initDetectorCatalog() {
    var cards = Array.prototype.slice.call(document.querySelectorAll('.detector-card'));
    var search = document.getElementById('detector-search');
    var chips = Array.prototype.slice.call(document.querySelectorAll('[data-filter]'));
    var count = document.getElementById('detector-count');
    if (!cards.length) return;

    var filter = 'all';

    function apply() {
      var query = search ? search.value.trim().toLowerCase() : '';
      var visible = 0;
      cards.forEach(function (card) {
        var severityMatch = filter === 'all' || card.dataset.severity === filter;
        var textMatch = !query || card.textContent.toLowerCase().indexOf(query) !== -1;
        var show = severityMatch && textMatch;
        card.hidden = !show;
        if (show) visible += 1;
      });
      chips.forEach(function (chip) {
        var selected = chip.dataset.filter === filter;
        chip.classList.toggle('active', selected);
        chip.setAttribute('aria-pressed', String(selected));
      });
      if (count) {
        count.textContent = 'Showing ' + visible + ' of ' + cards.length + ' detectors';
      }
      announce('detector-filter');
    }

    chips.forEach(function (chip) {
      chip.addEventListener('click', function () {
        filter = chip.dataset.filter || 'all';
        apply();
      });
    });

    if (search) {
      var timer = null;
      search.addEventListener('input', function () {
        if (timer) window.clearTimeout(timer);
        timer = window.setTimeout(apply, 140);
      });
    }
  }

  function init() {
    initTheme();
    initNavigation();
    initScrollIndicators();
    initActiveNav();
    initReveal();
    initWorkflow();
    initCommandConsole();
    initCopyButtons();
    initDetectorCatalog();
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }
})();
