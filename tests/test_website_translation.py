"""Static checks for the advanced, opt-in website translation integration.

These guard the security-relevant wiring of translate.js and the advanced UI
without needing a browser. The Python scanner itself is deliberately untouched.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
WEBSITE = ROOT / "website"
INDEX = WEBSITE / "index.html"
INIT_JS = WEBSITE / "assets" / "translate-init.js"
SITE_JS = WEBSITE / "assets" / "site.js"
SITE_CSS = WEBSITE / "assets" / "site.css"
VENDOR = WEBSITE / "vendor" / "translate.js"
MANIFEST = WEBSITE / "vendor" / "manifest.json"


def test_vendor_script_matches_pinned_manifest():
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    digest = hashlib.sha256(VENDOR.read_bytes()).hexdigest()

    assert digest == manifest["sha256"]
    assert manifest["version"] == "4.1.0.20260526"
    assert manifest["license"] == "MIT"
    assert (VENDOR.parent / manifest["license_file"]).is_file()

    # The browser checks the same hash and version before executing the script.
    init_js = INIT_JS.read_text(encoding="utf-8")
    assert digest in init_js
    assert manifest["version"] in init_js


def test_index_defines_public_guide_scope_and_sensitive_exclusions():
    html = INDEX.read_text(encoding="utf-8")

    assert 'id="docs-content"' in html
    assert 'id="language-select"' in html
    assert 'id="translation-status"' in html
    assert 'id="language-controls"' in html
    assert 'id="theme-toggle"' in html
    assert 'id="nav-burger"' in html

    # Only the guide sections are translated; hero, notice and header stay out.
    hero_at = html.index('class="hero"')
    notice_at = html.index('class="translation-notice"')
    docs_at = html.index('id="docs-content"')
    assert hero_at < notice_at < docs_at

    for section in ("workflow", "reference", "detectors", "start", "scope"):
        assert f'id="{section}"' in html[docs_at:]

    # Commands, scan output, identifiers, controls and the search field are
    # explicitly excluded from the translated prose.
    assert html.count('<pre class="sensitive">') >= 4
    assert html.count('class="detector-card"') == 14
    assert 'data-choice' in html
    assert 'data-command-tab' in html
    assert 'data-filter' in html
    assert 'id="detector-search"' in html
    assert 'class="copy-button sensitive"' in html

    # Privacy notice names the vendor and stays outside the translated scope.
    notice_end = html.index("</p>", notice_at)
    assert "Microsoft Translator" in html[notice_at:notice_end]
    assert "CLI itself stays fully offline" in html[notice_at:notice_end]

    # No third-party <script> tag and no stale asset cache busting.
    assert "res.zvo.cn/translate/translate.js" not in html
    assert 'src="assets/translate-init.js?v=4"' in html
    assert 'href="assets/site.css?v=4"' in html
    assert 'src="assets/site.js?v=4"' in html


def test_translate_init_configures_before_executing():
    js = INIT_JS.read_text(encoding="utf-8")

    for required in (
        "var TRANSLATION_ENDPOINT = 'https://edge.microsoft.com/translate/translatetext?from={from}&to={to}&isEnterpriseClient=false'",
        "t.setDocuments([docs])",
        "t.ignore.class.push('sensitive', null)",
        "t.ignore.tag.push('pre', 'code', 'select', 'option', 'button', 'svg', 'input')",
        "t.ignore.id.push('language-controls')",
        "t.request.api.connectTest = ''",
        "t.request.api.host = ['']",
        "t.service.use('client.edge')",
        "edgeApi.translate = TRANSLATION_ENDPOINT",
        "t.changeLanguage(languageId)",
        "t.listener.start()",
        "window.translate.reset(",
        "t.storage.set('speedDetectionControl_hostQueue', '')",
        "t.storage.set('speedDetectionControl_hostQueueIndex', 0)",
        "t.storage.set('speedDetectionControl_lasttime', Date.now())",
        "t.lifecycle.execute.translateNetworkAfter.push(",
        "resolveDocs(t)",
        "window.translate = undefined;",
        "safeMessage(error)",
        "function resetTranslationDom()",
        "resetTranslationDom();",
        "function translationCompleted(t)",
        "state.executeNumberAtStart",
    ):
        assert required in js

    set_documents = js.index("t.setDocuments([docs])")
    change_language = js.index("t.changeLanguage(languageId)")
    assert set_documents < change_language
    assert js.index("resolveDocs(t)") < set_documents

    # Opt-in: the script is only fetched on a non-English selection.
    assert "if (state.scriptLoaded) return Promise.resolve();" in js
    assert "if (!languageId) return;" in js

    # Failures must never be reported as success, and internal details stay
    # in the console rather than in the status region.
    assert "Translation unavailable. Showing original English." in js
    assert "event.result !== 1" in js
    assert "state.networkResults === 0" in js
    assert "!translationCompleted(t)" in js
    assert "logError(scope || 'failure', detail)" in js
    assert "envguard:content-updated" in js


def test_site_js_implements_advanced_interactions_and_announces_changes():
    js = SITE_JS.read_text(encoding="utf-8")

    for required in (
        "root.classList.add('js')",
        "envguard-theme",
        "data-theme",
        "nav-open",
        "aria-expanded",
        "scroll-progress",
        "IntersectionObserver",
        "data-choice",
        "data-command-tab",
        "data-copy-source",
        "detector-search",
        "data-filter",
        "aria-pressed",
        "envguard:content-updated",
        "announce('workflow')",
        "announce('command-panel')",
        "announce('detector-filter')",
    ):
        assert required in js


def test_styles_support_themes_layout_and_translation_ui():
    css = SITE_CSS.read_text(encoding="utf-8")

    for required in (
        "html[data-theme=\"dark\"]",
        "html[data-theme=\"light\"]",
        ".scroll-progress",
        ".site-header",
        ".nav-burger",
        ".site-header.nav-open .primary-nav",
        "html.js .reveal",
        "html.js .reveal.visible",
        ".language-controls",
        ".lang-select",
        ".translation-status",
        ".translation-notice",
        '#docs-content[aria-busy="true"]',
        ".sr-only",
        ".detector-card[hidden]",
        ".console-panel[hidden]",
        "@media (max-width: 1080px)",
        "@media (max-width: 900px)",
        "@media (max-width: 640px)",
        "@media (prefers-reduced-motion: reduce)",
    ):
        assert required in css


def test_documentation_discloses_privacy_and_seo_limits():
    doc = (ROOT / "docs" / "TRANSLATION.md").read_text(encoding="utf-8")

    assert "No translation script is fetched and no text" in doc
    assert "edge.microsoft.com/translate/translatetext" in doc
    assert "Client-side DOM replacement is **not** multilingual SEO" in doc
    assert "detector catalog" in doc
    assert "detector-search" in doc
    assert "command-tabs" in doc or "command panel" in doc
