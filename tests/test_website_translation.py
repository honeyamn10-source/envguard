"""Static checks for the opt-in website translation integration.

These guard the security-relevant wiring of translate.js without needing a
browser. The Python scanner itself is deliberately untouched.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
WEBSITE = ROOT / "website"
INDEX = WEBSITE / "index.html"
INIT_JS = WEBSITE / "assets" / "translate-init.js"
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

    # Only the guide sections are translated; hero and notice stay outside.
    hero_at = html.index('class="hero"')
    notice_at = html.index('class="translation-notice"')
    docs_at = html.index('id="docs-content"')
    assert hero_at < notice_at < docs_at

    # Setup commands and workflow controls are explicitly excluded.
    assert html.count('<pre class="sensitive">') == 1
    assert html.count('class="choice sensitive"') == 3
    assert html.count('class="copy sensitive"') == 1

    # Privacy notice names the vendor and stays outside the translated scope.
    notice_end = html.index("</p>", notice_at)
    assert "Microsoft Translator" in html[notice_at:notice_end]

    # No third-party <script> tag: the vendored file is loaded by translate-init.js.
    assert "res.zvo.cn/translate/translate.js" not in html
    assert 'src="assets/translate-init.js?v=3"' in html


def test_translate_init_configures_before_executing():
    js = INIT_JS.read_text(encoding="utf-8")

    for required in (
        "t.setDocuments([docs])",
        "t.ignore.class.push('sensitive', null)",
        "t.ignore.tag.push('pre', 'code', 'select', 'option', 'button', 'svg')",
        "t.ignore.id.push('language-controls')",
        "t.request.api.connectTest = ''",
        "t.request.api.host = ['']",
        "t.service.use('client.edge')",
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
    site_js = (WEBSITE / "assets" / "site.js").read_text(encoding="utf-8")
    assert "envguard:content-updated" in site_js


def test_translation_ui_styles_are_responsive_and_theme_aware():
    css = (WEBSITE / "assets" / "site.css").read_text(encoding="utf-8")

    for required in (
        ".language-controls",
        ".lang-select",
        ".translation-status",
        ".translation-notice",
        "#docs-content[aria-busy=true]",
        ".sr-only",
        "@media(max-width:550px)",
        "@media(max-width:380px)",
    ):
        assert required in css
