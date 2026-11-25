# Website translation (trial)

The EnvGuard website has an **opt-in** translation trial powered by
[translate.js](https://github.com/xnx3/translate). This document is the audit
trail for that integration. The Python scanner in `envguard/` is not affected:
it has no network calls and no translation code.

## What actually happens

1. The page loads in English. **No translation script is fetched and no text
   is sent anywhere on page load.**
2. A visitor selects a language in the navigation `<select>`.
3. Only then does `website/assets/translate-init.js`:
   - fetch the vendored `website/vendor/translate.js` from this same origin,
   - verify its SHA-256 against `website/vendor/manifest.json`,
   - configure translate.js, and
   - call `translate.changeLanguage(...)`.
4. Selecting **English** calls `translate.reset()` and restores the original
   English text.

Only the public guide container `#docs-content` is passed to
`translate.setDocuments([...])`. It covers the advanced workflow explorer,
CLI reference prose, detector catalog descriptions, setup guidance, scope
notes and documentation links. The hero, animated scanner illustration,
navigation, theme toggle, language controls, privacy notice, workflow buttons,
command/code blocks, detector identifiers, search input, filter chips and
footer are outside that scope (or explicitly ignored) and are never translated.

## What is excluded from translation

- `pre` and `code` tags (ignored by translate.js by default, and also listed
  explicitly in `translate.ignore.tag`).
- Setup commands, command-console `pre` blocks, illustrative masked findings,
  detector rule names and exit-code snippets are marked with `class="sensitive"`
  in `website/index.html`.
- The workflow buttons, command tabs, copy buttons, filter chips and theme /
  navigation buttons are `button` elements and ignored by tag.
- The detector search field (`#detector-search`) is an `input` and ignored by tag.
- `translate.ignore.class.push('sensitive')` is set before `execute()`.
- `translate.ignore.text` / `translate.ignore.textRegex` keep the product name,
  URLs, email addresses, cloud token prefixes, private-key headers and similar
  identifiers untranslated.
- The language selector itself (`#language-controls`) is ignored by id, and
  `select`, `option`, `button`, `svg` and `input` tags are ignored by tag.

If you add a section containing commands, credentials, scan output, tokens or
identifiers, give it `class="sensitive"` (or keep it outside `#docs-content`).

## Network and privacy disclosure

Selecting a non-English language sends the translatable text in `#docs-content`
**to Microsoft Translator** over the network. `translate.js` is configured with
`translate.service.use('client.edge')`, which uses:

```
https://edge.microsoft.com/translate/translatetext?from={from}&to={to}&isEnterpriseClient=false
```

The initialization guards deliberately suppress all other background requests:

```js
translate.request.api.language = [...]; // static list, no language.json request
translate.request.api.ip = '';
translate.request.api.connectTest = '';
translate.request.api.init = '';
translate.request.api.host = [''];       // empty host: no zvo.cn fallback hosts
```

The initialization code also audits `translate.service.edge.api.translate`
before use and pins the exact URL. It clears `speedDetectionControl_hostQueue`,
`speedDetectionControl_hostQueueIndex` and `speedDetectionControl_lasttime`
from `localStorage` before configuring, so a stale queue from a previous visit
cannot re-enable a fallback host. **Self-hosting the JavaScript does not make
translation local** — it only pins the client code. The translation itself is
sent to Microsoft Translator. This is disclosed by name in the
`.translation-notice` paragraph above the documentation container (that notice
is outside `#docs-content`, so it is never sent to the translation service).

### Failure handling

A `translate.lifecycle.execute.translateNetworkAfter` hook inspects every
translation batch. `result !== 1` (HTTP, network or parse failure) switches the
UI to an error state, restores English and writes the detailed reason only to
the console. A 12-second timeout also refuses to report success if no network
result ever arrived and translate.js did not complete the work from its local
translation cache (`state === 0` plus an increased `executeNumber`). This avoids
two failure modes: reporting "Translated" after a failed request, and reporting
failure when a repeat selection was served entirely from cache.

The `#docs-content` node is re-resolved on every language switch and passed to
`setDocuments()` again, so a client-side route change cannot leave
translate.js watching a detached element.

The workflow explorer swaps its explanation text in place, the command console
reveals a different static panel, and the detector catalog filters cards with
the `hidden` attribute. `site.js` stays independent of translate.js and emits
`envguard:content-updated` for each of those changes. The translation layer
listens for that event and, when a non-English language is active, runs the
same clean reset / `changeLanguage()` pass used by a language switch. A plain
`execute()` can reuse translate.js's stale node map and leave newly revealed
prose in English, so the reset pass is deliberate. Only current public prose is
re-read; commands, identifiers and controls are still excluded.

## Pinned vendor copy

`website/vendor/translate.js` is a byte-for-byte copy of the official script:

| Field | Value |
| --- | --- |
| Version | `4.1.0.20260526` |
| Source | `https://res.zvo.cn/translate/translate.js` |
| SHA-256 | `89ec5abd84cac6c17f5133d5b4ff87798c0b67f2e48cffcebd20fa6bd9aa6cca` |
| License | MIT (see `website/vendor/LICENSE.translate.txt`) |

The browser verifies the SHA-256 with `crypto.subtle.digest` **before** the
script is executed, and checks `translate.version`. `tests/test_website_translation.py`
checks the same values in CI. The verified source is injected as an inline
`<script>`; if you add a strict Content-Security-Policy, switch to a static
`<script src="vendor/translate.js" integrity="sha256-...">` tag instead of
allowing `unsafe-inline`. To update the vendor copy:

1. Download the official script and confirm its upstream source/version.
2. Audit the new script for extra endpoints, `fetch`/XHR targets, dynamic script
   loading and `eval` usage.
3. Replace `website/vendor/translate.js`, update `website/vendor/manifest.json`,
   `website/assets/translate-init.js` and the test with the new version/hash.
4. Re-run the manual test checklist below.

## SEO caveat

Client-side DOM replacement is **not** multilingual SEO. Search engines see the
original English HTML source; the translated text exists only in the live DOM
after a visitor opts in. For real multilingual SEO you need server-rendered or
statically generated pages per language, `hreflang` links and translated URLs.
The upstream project offers a separate HTML-source translation / TCDN product
for that; it is not part of this trial.

## Manual test checklist

Run locally with `python3 -m http.server 8000 --directory website`, then open
`http://localhost:8000/` and check:

- [ ] Keyboard: Tab reaches the theme toggle, language selector and mobile menu;
      arrow keys change the language, Enter applies it, focus stays visible, and
      the skip link still works. Workflow steps and command tabs support arrow
      keys, Home and End.
- [ ] Layout: no nav overflow at ~375 px, 768 px and desktop widths; the mobile
      drawer opens, closes on `Escape` and closes after choosing a link.
- [ ] Theme: the toggle switches dark/light, persists after reload and updates
      the browser theme colour.
- [ ] Selection: English → 简体中文 → Deutsch → English restores the original text.
- [ ] Dynamic DOM: clicking a workflow choice translates the new explanation.
      Switching command tabs reveals a new command panel and translates its prose.
      Typing in the
      detector search or choosing a severity chip keeps commands and detector
      identifiers in English while translating the public descriptions.
- [ ] Routes/hash links: clicking `#workflow`, `#reference`, `#detectors` and
      `#start` keeps translation state consistent. Replacing `#docs-content`
      from the console and switching language again translates the new node, not
      the detached one.
- [ ] Network tab: no requests before opting in; after opting in, only the
      same-origin vendor script and the pinned Microsoft endpoint appear.
      No `language.json`, `ip.json`, `connectTest.json`, `init.json`,
      `translate.json` or `res.zvo.cn` requests.
- [ ] Request body: Microsoft receives only public guide prose; setup commands,
      command-console code, masked findings, detector rule names, URLs, button
      labels and the search query are absent.
- [ ] Failure path: block `edge.microsoft.com` in devtools, pick a language and
      confirm the UI says translation is unavailable and the console has the
      detailed reason.
- [ ] Sensitive content: commands, scanner illustration, detector identifiers,
      workflow buttons, command tabs, copy buttons, filter chips and the search
      field remain in English.

## Moving to a private backend later

For production with a self-hosted translation service, replace the
`client.edge` configuration in `translate-init.js` with:

```js
translate.service.use('translate.service');
translate.request.setHost(['https://translate.internal.example/']);
```

Re-audit initialization and fallback endpoints after the change: `setHost()`
switches channels and may reset speed-detection state, and a private deployment
should disable the public hosts rather than relying on ordering. Update this
document and the tests at the same time.
