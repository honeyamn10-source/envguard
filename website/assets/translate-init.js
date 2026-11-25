/* ============================================================
   envguard website — opt-in translate.js integration
   ------------------------------------------------------------
   Design goals (see docs/TRANSLATION.md):
   - English is the source language; nothing is translated or sent
     until a visitor explicitly picks another language.
   - Only the public #docs-content container is translated, and the
     container is re-resolved on every switch so route/DOM changes
     cannot leave a stale node reference behind.
   - Code, commands, terminal/scan output and identifiers are
     excluded via tags, classes and text rules.
   - The vendored script is hash-verified before it is executed,
     and only the pinned Microsoft translation endpoint is used.
   - Network failures are detected and reported honestly; internal
     error details stay in the console, not in the UI.
   The Python scanner in envguard/ is completely independent.
   ============================================================ */

(function () {
  'use strict';

  var SCRIPT_SRC = 'vendor/translate.js';
  var EXPECTED_VERSION = '4.1.0.20260526';
  var EXPECTED_SHA256 = '89ec5abd84cac6c17f5133d5b4ff87798c0b67f2e48cffcebd20fa6bd9aa6cca';
  var TRANSLATION_ENDPOINT = 'https://edge.microsoft.com/translate/translatetext?from={from}&to={to}&isEnterpriseClient=false';
  var ENDPOINT_HOST = 'edge.microsoft.com/translate/translatetext';
  var SOURCE_LANGUAGE = 'english';

  // UI value -> translate.js language id. English is the untranslated source.
  var LANGUAGES = Object.freeze({
    en: null,
    'zh-CN': 'chinese_simplified',
    ja: 'japanese',
    de: 'deutsch',
    es: 'spanish',
    fr: 'french'
  });

  var LABELS = Object.freeze({
    en: 'English',
    'zh-CN': 'Chinese (Simplified)',
    ja: 'Japanese',
    de: 'German',
    es: 'Spanish',
    fr: 'French'
  });

  var state = {
    phase: 'idle', // idle | loading | translating | ready | error
    language: 'en',
    scriptLoaded: false,
    configured: false,
    error: null,
    networkResults: 0,
    networkSuccesses: 0,
    networkFailure: null,
    executeNumberAtStart: -1
  };

  var select = null;
  var docs = null;
  var statusEl = null;
  var loadPromise = null;
  var busyTimer = null;

  function setStatus(message, isError) {
    if (!statusEl) return;
    statusEl.textContent = message || '';
    statusEl.classList.toggle('is-error', Boolean(isError));
  }

  function setBusy(busy) {
    if (docs) docs.setAttribute('aria-busy', busy ? 'true' : 'false');
    if (select) select.disabled = busy;
    if (busyTimer) {
      clearTimeout(busyTimer);
      busyTimer = null;
    }
  }

  function logError(scope, error) {
    if (window.console && typeof window.console.error === 'function') {
      window.console.error('[EnvGuard translation] ' + scope, error);
    }
  }

  /* Show a calm, generic message; keep internals in the console. */
  function safeMessage(error) {
    var message = error && error.message ? error.message : String(error);
    if (/hash|integrity/i.test(message)) {
      return 'The translation script failed its integrity check.';
    }
    if (/endpoint|version|unexpected translate/i.test(message)) {
      return 'The translation service configuration was rejected.';
    }
    if (/secure hashing|cannot load vendored|documentation container/i.test(message)) {
      return 'The translation script could not be loaded securely.';
    }
    if (/network|unavailable|did not respond|service/i.test(message)) {
      return 'The translation service is unavailable.';
    }
    return 'Translation is temporarily unavailable.';
  }

  function fail(error, scope) {
    var detail = error && error.message ? error.message : String(error);
    logError(scope || 'failure', detail);
    state.phase = 'error';
    state.error = detail;
    state.language = 'en';
    state.networkFailure = state.networkFailure || detail;
    setBusy(false);
    if (select) {
      select.value = 'en';
      select.disabled = false;
    }
    setStatus('Translation unavailable. Showing original English.', true);
  }

  function toHex(buffer) {
    return Array.prototype.map.call(new Uint8Array(buffer), function (byte) {
      return byte.toString(16).padStart(2, '0');
    }).join('');
  }

  /* Fetch -> verify SHA-256 -> execute. This happens once, on first use. */
  function loadVerifiedScript() {
    if (state.scriptLoaded) return Promise.resolve();
    if (loadPromise) return loadPromise;

    loadPromise = (async function () {
      if (!window.crypto || !window.crypto.subtle || typeof TextEncoder === 'undefined') {
        throw new Error('secure hashing is unavailable');
      }

      var response = await fetch(SCRIPT_SRC, { cache: 'no-cache' });
      if (!response.ok) throw new Error('cannot load vendored script (' + response.status + ')');

      var source = await response.text();
      var digest = await window.crypto.subtle.digest('SHA-256', new TextEncoder().encode(source));
      if (toHex(digest) !== EXPECTED_SHA256) {
        throw new Error('vendored script hash mismatch');
      }

      var script = document.createElement('script');
      script.textContent = source;
      document.head.appendChild(script);

      var t = window.translate;
      if (!t || typeof t !== 'object' || t.version !== EXPECTED_VERSION) {
        // A partially executed script must not block a later retry: the
        // vendor script has its own duplicate-load guard.
        script.remove();
        window.translate = undefined;
        throw new Error('unexpected translate.js version');
      }

      state.scriptLoaded = true;
    })().catch(function (error) {
      loadPromise = null; // allow a retry
      throw error;
    });

    return loadPromise;
  }

  /* Re-resolve the scope every time. A client-side router can replace the
     container; translate.js must never keep translating a detached node. */
  function resolveDocs(t) {
    var current = document.getElementById('docs-content');
    if (!current) throw new Error('documentation container missing');
    if (current !== docs) {
      docs = current;
      if (t) t.setDocuments([docs]);
    }
    return docs;
  }

  /* All translate.js settings must be applied before execute()/changeLanguage(). */
  function configureOnce(t) {
    if (state.configured) return;

    resolveDocs(t);
    t.language.setLocal(SOURCE_LANGUAGE);
    t.selectLanguageTag.show = false; // this site provides its own labelled <select>
    t.selectLanguageTag.languages = Object.keys(LANGUAGES)
      .filter(function (key) { return key !== 'en'; })
      .map(function (key) { return LANGUAGES[key]; })
      .join(',');

    // Translate only the public documentation container.
    t.setDocuments([docs]);

    // Belt-and-braces exclusions: pre/code are ignored by default, but we also
    // mark commands, scan output and identifiers with .sensitive in the HTML.
    t.ignore.class.push('sensitive', null);
    t.ignore.id.push('language-controls');
    t.ignore.tag.push('pre', 'code', 'select', 'option', 'button', 'svg');
    t.ignore.text.push('envguard');
    t.ignore.textRegex.push(
      /(?:AKIA|ASIA)[0-9A-Z]{16}/,
      /(?:ghp|gho|ghu|ghs|ghr)_[A-Za-z0-9]{20,}/,
      /sk-[A-Za-z0-9_-]{20,}/,
      /-----BEGIN [A-Z ]*PRIVATE KEY-----/,
      /https?:\/\/[^\s]+/,
      /\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b/i
    );

    // No background network calls: static language list, no IP lookup,
    // no node speed test, no init probe.
    t.request.api.language = Object.keys(LANGUAGES)
      .filter(function (key) { return key !== 'en'; })
      .map(function (key) {
        return { id: LANGUAGES[key], name: key };
      });
    t.request.api.ip = '';
    t.request.api.connectTest = '';
    t.request.api.init = '';

    // client.edge sends translatable text directly to Microsoft Translator.
    // Audit the configured channel and pin the exact endpoint before use.
    t.service.use('client.edge');
    var edgeApi = t.service && t.service.edge && t.service.edge.api;
    if (t.service.name !== 'client.edge' || !edgeApi || !edgeApi.translate ||
        edgeApi.translate.indexOf(ENDPOINT_HOST) === -1) {
      throw new Error('translation endpoint audit failed');
    }
    edgeApi.translate = TRANSLATION_ENDPOINT;
    t.request.api.translate = TRANSLATION_ENDPOINT;

    // translate.js still calls getHost() for client.edge; an empty-string host
    // satisfies that internal check without enabling any zvo.cn fallback host.
    // Stale speed-detection keys in localStorage can override api.host, so
    // clear both the in-memory queue and the persisted values.
    t.request.api.host = [''];
    t.storage.set('speedDetectionControl_hostQueue', '');
    t.storage.set('speedDetectionControl_hostQueueIndex', 0);
    t.storage.set('speedDetectionControl_lasttime', Date.now());
    t.request.speedDetectionControl.hostQueue = [];
    t.request.speedDetectionControl.hostQueueIndex = 0;
    t.request.speedDetectionControl.state = 0;
    t.storage.set('to', '');

    if (t.request.api.translate !== TRANSLATION_ENDPOINT ||
        edgeApi.translate !== TRANSLATION_ENDPOINT ||
        t.request.api.host.length !== 1 || t.request.api.host[0] !== '') {
      throw new Error('translation endpoint audit failed');
    }

    // translate.js reports result !== 1 for HTTP/network/parse failures.
    // Without this hook the UI could claim success after a failed request.
    if (t.lifecycle && t.lifecycle.execute && t.lifecycle.execute.translateNetworkAfter) {
      t.lifecycle.execute.translateNetworkAfter.push(function (event) {
        state.networkResults += 1;
        if (!event || event.result !== 1) {
          state.networkFailure = event && event.info
            ? String(event.info)
            : 'translation request failed';
          if (window.console && typeof window.console.warn === 'function') {
            window.console.warn('[EnvGuard translation] request failed', state.networkFailure);
          }
          fail({ message: state.networkFailure }, 'network');
        } else {
          state.networkSuccesses += 1;
        }
      });
    }

    t.listener.renderTaskFinish = function () {
      if (state.phase !== 'translating') return;
      if (state.networkFailure) {
        fail({ message: state.networkFailure }, 'network');
        return;
      }
      // translate.js can fire renderTaskFinish before the network callback.
      // Stay busy and keep the fallback timer alive until a result arrives,
      // unless the work was satisfied entirely from translate.js's local cache.
      if (state.networkResults === 0 && !translationCompleted(t)) return;
      finishSuccess();
    };

    state.configured = true;
  }

  function finishSuccess() {
    setBusy(false);
    state.phase = 'ready';
    state.error = null;
    state.networkFailure = null;
    setStatus('Translated to ' + (LABELS[state.language] || state.language) +
      '. Original English is unchanged.');
  }

  /* Cached translations finish without an HTTP request. translate.js sets
     state back to 0 and increments executeNumber when that happens. */
  function translationCompleted(t) {
    return Boolean(t && t.state === 0 && typeof t.executeNumber === 'number' &&
      t.executeNumber > state.executeNumberAtStart);
  }

  async function selectLanguage(value) {
    var languageId = LANGUAGES[value];
    if (!languageId) return;

    setBusy(true);
    state.phase = 'loading';
    state.error = null;
    state.networkResults = 0;
    state.networkSuccesses = 0;
    state.networkFailure = null;
    setStatus('Preparing translation…');

    try {
      await loadVerifiedScript();
      var t = window.translate;
      configureOnce(t);
      resolveDocs(t); // in case the container was replaced after first setup

      state.phase = 'translating';
      state.language = value;
      state.executeNumberAtStart = typeof t.executeNumber === 'number' ? t.executeNumber : 0;
      setStatus('Translating documentation…');
      t.changeLanguage(languageId); // resets prior translation and calls execute()
      t.listener.start(); // changeLanguage() resets the listener, so restart it

      // Guard against translate.js skipping renderTaskFinish. If no network
      // result arrived by then, do not claim a success that did not happen.
      busyTimer = setTimeout(function () {
        if (state.phase !== 'translating') return;
        if (state.networkFailure) {
          fail({ message: state.networkFailure }, 'network');
        } else if (state.networkResults === 0 && !translationCompleted(t)) {
          fail({ message: 'translation service did not respond' }, 'timeout');
        } else {
          finishSuccess();
        }
      }, 12000);
    } catch (error) {
      fail(error, 'selection');
    }
  }

  function restoreEnglish() {
    if (!state.scriptLoaded || !window.translate) {
      state.language = 'en';
      state.phase = 'ready';
      state.error = null;
      state.networkFailure = null;
      state.executeNumberAtStart = -1;
      setBusy(false);
      setStatus('Showing original English text.');
      return;
    }
    try {
      resolveDocs(window.translate);
      window.translate.reset({
        selectLanguageRefreshRender: false,
        notTranslateTip: false
      });
      window.translate.storage.set('to', SOURCE_LANGUAGE);
      state.language = 'en';
      state.phase = 'ready';
      state.error = null;
      state.networkFailure = null;
      state.executeNumberAtStart = -1;
      setBusy(false);
      setStatus('Showing original English text.');
    } catch (error) {
      fail(error, 'reset');
    }
  }

  function init() {
    select = document.getElementById('language-select');
    statusEl = document.getElementById('translation-status');

    try {
      docs = resolveDocs(null);
    } catch (error) {
      if (select) select.disabled = true;
      setStatus('Translation container missing; translation disabled.', true);
      logError('init', error);
      return;
    }

    select.addEventListener('change', function () {
      if (state.phase === 'loading' || state.phase === 'translating') return;
      if (select.value === 'en') {
        restoreEnglish();
      } else {
        selectLanguage(select.value);
      }
    });

    // The workflow explorer swaps explanation text in place. Site behaviour
    // stays independent of translate.js: it only announces that public guide
    // text changed, and we re-run translation when a language is active.
    document.addEventListener('envguard:content-updated', function () {
      if (state.language === 'en' || state.phase !== 'ready' || !state.scriptLoaded) return;
      var t = window.translate;
      if (!t) return;
      try {
        resolveDocs(t);
        state.networkResults = 0;
        state.networkFailure = null;
        t.execute();
        t.listener.start();
      } catch (error) {
        logError('dynamic-content', error);
      }
    });

    // Small read-only surface for manual QA / automated checks.
    window.EnvGuardTranslation = {
      languages: LANGUAGES,
      expectedVersion: EXPECTED_VERSION,
      expectedSha256: EXPECTED_SHA256,
      endpoint: TRANSLATION_ENDPOINT,
      state: function () {
        return Object.assign({}, state);
      }
    };
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }
})();
