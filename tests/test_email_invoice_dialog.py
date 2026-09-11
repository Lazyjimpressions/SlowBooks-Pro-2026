"""The Email Invoice dialog's own payload was rejected (issue #140, mdornich).

`_EmailInvoiceRequest` is a StrictModel accepting `recipient` and `subject`.
The dialog in `app/static/js/invoices.js` has always also posted `message`,
so **every send from the interface failed validation with a 422** before
reaching any of the sending code. The Message box did not merely get
ignored; it broke the button it sat on.

No test caught it because every test called the endpoint with a payload the
endpoint accepted, rather than the payload the interface sends. That is the
same shape as 2.10.3's shadowed download route: a test of the handler is not
a test of what the page does.
"""

import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def invoice(client):
    cust = client.post(
        "/api/customers", json={"name": "Probe Co", "email": "a@b.com"}
    ).json()
    r = client.post(
        "/api/invoices",
        json={
            "customer_id": cust["id"],
            "date": "2026-06-01",
            "due_date": "2026-06-30",
            "lines": [
                {"description": "work", "quantity": 1, "rate": 100, "line_order": 0}
            ],
        },
    )
    assert r.status_code == 201, r.text
    return r.json()


def test_the_payload_the_dialog_actually_sends_is_accepted(
    client, seed_accounts, invoice
):
    """Not 422. SMTP is unconfigured in tests, so the honest outcome is a
    502 from the send itself — which means validation passed and the request
    reached the sending code."""
    r = client.post(
        f"/api/invoices/{invoice['id']}/email",
        json={
            "recipient": "a@b.com",
            "subject": f"Invoice #{invoice['invoice_number']} from us",
            "message": f"Please find attached Invoice #{invoice['invoice_number']}.",
        },
    )
    assert r.status_code != 422, r.text
    assert r.status_code == 502, r.text


def test_the_dialog_and_the_route_agree_on_their_fields():
    """The tripwire. These two drifted apart and nothing noticed, because
    they are in different languages in different files."""
    js = (ROOT / "app/static/js/invoices.js").read_text(encoding="utf-8")
    py = (ROOT / "app/routes/invoices/documents.py").read_text(encoding="utf-8")

    body = re.search(r"API\.post\(`/invoices/\$\{id\}/email`,\s*\{(.+?)\}\)", js, re.S)
    assert body, "could not find the dialog's email POST"
    sent = set(re.findall(r"(\w+):", body.group(1)))

    model = re.search(r"class _EmailInvoiceRequest\(StrictModel\):(.+?)\n\n", py, re.S)
    assert model, "could not find _EmailInvoiceRequest"
    accepted = set(re.findall(r"^\s{4}(\w+):", model.group(1), re.M))

    assert sent <= accepted, (
        f"the dialog posts {sorted(sent - accepted)} which the route rejects; "
        f"_EmailInvoiceRequest is a StrictModel so this is a 422, not an ignore"
    )


def test_the_operators_message_reaches_the_email_body(
    client, db_session, seed_accounts, invoice
):
    """The box says Message. It should be the message."""
    from app.models.invoices import Invoice
    from app.services.email_service import render_invoice_email
    from app.services.settings_service import get_all_settings as get_settings

    inv = db_session.query(Invoice).filter(Invoice.id == invoice["id"]).first()
    body = render_invoice_email(
        inv, get_settings(db_session), note="Ten days, as agreed."
    )
    assert "Ten days, as agreed." in body


def test_an_operator_message_is_escaped(client, db_session, seed_accounts, invoice):
    """It is operator-supplied text landing in an HTML email."""
    from app.models.invoices import Invoice
    from app.services.email_service import render_invoice_email
    from app.services.settings_service import get_all_settings as get_settings

    inv = db_session.query(Invoice).filter(Invoice.id == invoice["id"]).first()
    body = render_invoice_email(
        inv, get_settings(db_session), note="<script>x</script>"
    )
    assert "<script>x</script>" not in body
    assert "&lt;script&gt;" in body
