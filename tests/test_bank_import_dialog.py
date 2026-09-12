"""2.13.0 gate, owner + skytech: the import preview pane stayed empty for the
whole round trip and the button stayed live, so a second click put a second
parse in flight. And the dialog's own label — the one place a user is
choosing a file — did not name Bank of America in the release named for it.

String-level, deliberately: the handler is a template literal in a page
module with no test harness, and what is being pinned is that the three
things are present and in the right order."""

import re
from pathlib import Path

JS = (Path(__file__).resolve().parents[1] / "app/static/js/banking.js").read_text()


def _handler(name):
    m = re.search(rf"async {name}\(.*?\n    }},\n", JS, re.S)
    assert m, name
    return m.group(0)


def test_the_file_picker_names_every_format_the_parser_detects():
    label = re.search(
        r"<label>Select an OFX/QFX file, or a CSV export \((.*?)\)</label>", JS
    )
    assert label, "import dialog label not found"
    named = label.group(1)
    for bank in ("Bank of America", "Chase checking", "Chase credit", "PayPal"):
        assert bank in named, (bank, named)


def test_preview_says_something_before_the_fetch_and_takes_the_button_away():
    body = _handler("previewOFX")
    placeholder = body.index("Reading the file")
    disable = body.index("submit.disabled = true")
    fetch = body.index("await fetch(")
    assert (
        disable < fetch and placeholder < fetch
    ), "feedback must come before the round trip"
    assert (
        "finally" in body and "submit.disabled = false" in body.split("finally", 1)[1]
    )


def test_the_import_button_is_one_click_one_import():
    body = _handler("confirmOFXImport")
    assert body.index("importBtn.disabled = true") < body.index("await fetch(")
