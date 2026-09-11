"""Wave import: the "Account Transactions" report is a plain export any
Wave user can pull with no plan restrictions, but its headers
("ACCOUNT NUMBER" for what is actually the account name on every data
row, "DEBIT (In Business Currency)" / "CREDIT (In Business Currency)"
for the money columns) didn't match parse_gl()'s alias list. Every row
silently parsed as account="" / debit=credit=0, so the dry-run
"balanced" on all-zero amounts and failed once, deduped, on the GL
account-name check ("GL references account '' not present in the
chart of accounts") — regardless of what the CSV actually contained.
"""

import io

COA_CSV = (
    "Name,Account Code,Account Type,Account Sub-Type,Currency Code,"
    "Is Archived,Description\n"
    "Checking,,Asset,Cash and Bank,USD,FALSE,\n"
    "Office Supplies,,Expense,Operating Expense,USD,FALSE,\n"
)

# Real column headers from Wave's Account Transactions report export.
ACCOUNT_TRANSACTIONS_REPORT_CSV = (
    "ACCOUNT NUMBER,DATE,DESCRIPTION,DEBIT (In Business Currency),"
    "CREDIT (In Business Currency),BALANCE (In Business Currency)\n"
    "Office Supplies,2024-01-15,Staples,$10.00,,\n"
    "Checking,2024-01-15,Staples,,$10.00,\n"
)


def _files(**named):
    return [
        ("files", (name, io.BytesIO(text.encode()), "text/csv"))
        for name, text in named.items()
    ]


def test_account_transactions_report_headers_parse(client, db_session, seed_accounts):
    resp = client.post(
        "/api/migration/wave/dry-run",
        files=_files(
            **{
                # Wave's actual export filenames for this bundle - not a
                # renamed workaround. "Account Transactions.csv" contains
                # both "account" and "transaction"; this must classify as
                # the GL file, not collide with the chart of accounts.
                "Chart of Accounts.csv": COA_CSV,
                "Account Transactions.csv": ACCOUNT_TRANSACTIONS_REPORT_CSV,
            }
        ),
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["ok"] is True, data
    assert data["errors"] == []
    assert data["accounts"] == 2
    assert data["journals"] == 1
