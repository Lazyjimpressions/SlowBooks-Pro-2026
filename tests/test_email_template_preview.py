"""Previewing a template edit before saving it.

#140 gave the send dialog a preview of the mail it is about to send. This is
the other half: the operator editing `invoice_email` under Settings -> Email
Templates could only see the result by saving over a working template and
mailing a real customer. The preview renders what is currently typed, against
a real invoice, without writing or sending anything.

It deliberately renders through `email_service.template_env()` — the same
environment the send uses — because a preview under different rules than the
mail is how the template and the send drifted apart in the first place.
"""

from datetime import date
from decimal import Decimal

import pytest

from app.models.email_log import EmailLog
from app.models.email_templates import EmailTemplate
from app.models.invoices import Invoice, InvoiceStatus
from app.models.transactions import Transaction


@pytest.fixture
def invoice(db_session, seed_customer):
    seed_customer.email = "client@example.com"
    inv = Invoice(
        invoice_number="PREV-1",
        customer_id=seed_customer.id,
        date=date(2026, 9, 1),
        due_date=date(2026, 9, 15),
        subtotal=Decimal("125"),
        total=Decimal("125"),
        balance_due=Decimal("125"),
        status=InvoiceStatus.SENT,
    )
    db_session.add(inv)
    db_session.commit()
    return inv


def _preview(client, invoice_id, subject="S", body="<p>B</p>"):
    return client.post(
        "/api/email-templates/preview",
        json={
            "invoice_id": invoice_id,
            "subject_template": subject,
            "body_template": body,
        },
    )


def test_preview_renders_unsaved_text_and_saves_nothing(client, db_session, invoice):
    before = (
        db_session.query(Transaction).count(),
        db_session.query(EmailLog).count(),
        db_session.query(EmailTemplate).count(),
    )
    r = _preview(
        client,
        invoice.id,
        subject="Draft {{ invoice.invoice_number }}",
        body="<p>{{ customer_name }} owes {{ invoice.total|currency }}</p>",
    )
    assert r.status_code == 200, r.text
    assert r.json()["subject"] == "Draft PREV-1"
    assert "$125.00" in r.json()["html_body"]
    assert before == (
        db_session.query(Transaction).count(),
        db_session.query(EmailLog).count(),
        db_session.query(EmailTemplate).count(),
    )


def test_preview_does_not_touch_the_saved_template(client, db_session, invoice):
    db_session.add(
        EmailTemplate(
            name="invoice_email",
            template_type="invoice",
            subject_template="Saved subject",
            body_template="<p>Saved body</p>",
        )
    )
    db_session.commit()

    assert (
        _preview(client, invoice.id, subject="Unsaved").json()["subject"] == "Unsaved"
    )
    saved = db_session.query(EmailTemplate).filter_by(name="invoice_email").one()
    assert saved.subject_template == "Saved subject"


def test_preview_escapes_customer_supplied_text(client, db_session, invoice):
    invoice.customer.name = "<img src=x onerror=alert(1)>"
    db_session.commit()
    body = _preview(client, invoice.id, body="<p>{{ customer_name }}</p>").json()[
        "html_body"
    ]
    assert "<img" not in body
    assert "&lt;img" in body


def test_preview_cannot_read_settings_secrets(client, db_session, invoice):
    """GHSA-c3v4-f43f-4wqm: the context is redacted at the point it is built,
    and this endpoint must be no exception."""
    from app.services.settings_service import set_setting

    set_setting(db_session, "smtp_password", "hunter2-SECRET")
    db_session.commit()

    body = _preview(
        client, invoice.id, body="<p>{{ company.smtp_password }}{{ company }}</p>"
    ).json()["html_body"]
    assert "hunter2-SECRET" not in body
    assert "********" in body


def test_preview_rejects_a_sandbox_escape(client, db_session, invoice):
    r = _preview(client, invoice.id, body="{{ invoice.__class__.__mro__ }}")
    assert r.status_code == 400


def test_preview_rejects_bad_input_as_400_not_500(client, db_session, invoice):
    """Syntax errors, unknown filters and arithmetic blowups are all just bad
    text from the client."""
    for bad in ("{% if %}", "{{ 1/0 }}", "{{ x | frobnicate }}"):
        r = _preview(client, invoice.id, body=bad)
        assert r.status_code == 400, f"{bad!r} gave {r.status_code}"


def test_preview_404s_for_an_unknown_invoice(client, db_session):
    assert _preview(client, 999999).status_code == 404
