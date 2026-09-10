"""Two CSS defects found by the marketing agent building the training videos
against the installed 2.10.3 bundle, and reproduced here behaviourally.

Both are guarded at the stylesheet, because both were invisible to every
test we had: the JS was correct in each case, and no assertion looked at
what the browser actually computed.
"""

from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
STYLE = (ROOT / "app/static/css/style.css").read_text(encoding="utf-8")
DARK = (ROOT / "app/static/css/dark.css").read_text(encoding="utf-8")


def test_a_generic_hidden_rule_exists():
    """The JS hides elements by adding `.hidden` in ten places across three
    files. There was no generic rule — only `.modal-overlay.hidden` and
    `.splash-overlay.hidden` — so everything else kept the class and stayed
    on screen. The global search dropdown never closed, and at rest it
    painted a 2 px sliver under the toolbar in every session."""
    import re

    assert re.search(r"^\.hidden\s*\{[^}]*display:\s*none", STYLE, re.M), (
        "no generic `.hidden` rule — an element hidden from JS will stay "
        "visible unless it happens to have its own .x.hidden rule"
    )


def test_every_element_hidden_from_js_is_actually_hideable():
    """The tripwire for the class, not the instance: whatever the JS hides
    must be covered by a rule that hides it."""
    import re

    js = ""
    for f in (ROOT / "app/static/js").glob("*.js"):
        js += f.read_text(encoding="utf-8")
    uses = re.findall(r"classList\.add\(['\"]hidden['\"]\)", js)
    assert uses, "no JS hides anything with .hidden any more — update this test"
    # a generic rule covers all of them at once
    assert re.search(r"^\.hidden\s*\{", STYLE, re.M)


def test_the_hidden_class_wins_over_a_component_display():
    """`.search-dropdown` sets its own box; without !important the utility
    loses to it and the trap is simply reset for the next component."""
    import re

    m = re.search(r"^\.hidden\s*\{([^}]*)\}", STYLE, re.M)
    assert m and "!important" in m.group(1)


def test_quick_entry_log_uses_a_theme_token_not_a_hardcoded_white():
    """It was `background: white`, which the dark theme could not override.
    The log text is near-white there, so the running confirmation of what you
    just saved was invisible — about 1.1:1 against a documented AA product."""
    import re

    m = re.search(r"#qe-log\s*\{([^}]*)\}", STYLE)
    assert m, "#qe-log rule is gone — update this test"
    body = m.group(1)
    assert "background: white" not in body and "background:#fff" not in body.replace(
        " ", ""
    )
    assert "var(--panel-bg)" in body, "the log background must follow the theme"
    assert "var(--text-primary)" in body, "and so must its text"


@pytest.mark.parametrize("token", ["--panel-bg", "--text-primary"])
def test_the_tokens_the_log_relies_on_are_themed(token):
    assert (
        token in STYLE and token in DARK
    ), f"{token} must be defined in both themes for #qe-log to follow them"
