"""Recovering a half-upgraded database (issue #132, second half).

The guard added in this release refuses to start against a database behind
head, which stops the damage happening again. It does nothing for a file it
has already happened to — and @skytech pointed out the distinction while
gating 2.12.0:

    `alembic upgrade head` recovers an *ordinary* old file and can never
    recover a *half-upgraded* one, because the tables the next revision
    creates already exist.

Measured before building this: a file at `e7f8a9b0c1d2` that a server touched
gains three empty tables, keeps its revision, and then

    alembic upgrade head
    -> OperationalError: table vendor_credits already exists

So the refusal was printing advice that fails for exactly the people who hit
it — the same shape as #139's delete error saying "deactivate it instead"
when nothing on the page could deactivate.
"""

from pathlib import Path

import pytest
from sqlalchemy import create_engine, inspect, text

ROOT = Path(__file__).resolve().parents[1]


def _cfg(db):
    from alembic.config import Config

    cfg = Config(str(ROOT / "alembic.ini"))
    cfg.set_main_option("script_location", str(ROOT / "migrations"))
    cfg.attributes["database_url"] = "sqlite:///" + Path(db).as_posix()
    return cfg


def _head():
    from alembic.script import ScriptDirectory

    return ScriptDirectory.from_config(_cfg("/tmp/x.db")).get_current_head()


def _half_upgraded(tmp_path, name="halfup.db", at="e7f8a9b0c1d2"):
    """A file at an older revision that a server has started against — the
    exact damage, produced the way it actually happens."""
    from alembic import command

    from app.database import Base
    import app.models  # noqa: F401  — registers every table

    db = tmp_path / name
    command.upgrade(_cfg(db), at)
    engine = create_engine(f"sqlite:///{db}")
    before = set(inspect(engine).get_table_names())
    Base.metadata.create_all(bind=engine)  # what a server start does
    added = set(inspect(engine).get_table_names()) - before
    engine.dispose()
    assert added, "the fixture did not reproduce the damage"
    return db, added


def test_the_damage_really_blocks_an_ordinary_upgrade(tmp_path):
    """The premise. If this ever stops being true the repair is unnecessary."""
    from alembic import command

    db, _ = _half_upgraded(tmp_path)
    with pytest.raises(Exception) as e:
        command.upgrade(_cfg(db), "head")
    assert "already exists" in str(e.value)


def test_repair_drops_the_empty_tables_and_reaches_head(tmp_path):
    from app.services.schema_repair import repair

    db, added = _half_upgraded(tmp_path)
    result = repair(f"sqlite:///{db}")

    assert result.ok, result.message
    assert result.now_at == _head()
    assert set(result.dropped) <= added
    # And the file is genuinely usable afterwards, not merely stamped.
    engine = create_engine(f"sqlite:///{db}")
    tables = set(inspect(engine).get_table_names())
    assert added <= tables, "the dropped tables were not recreated by the upgrade"
    cols = {c["name"] for c in inspect(engine).get_columns("accounts")}
    assert "bank_kind" in cols, "an ALTER that create_all could not do is still missing"
    engine.dispose()


def test_repair_refuses_to_drop_a_table_with_rows(tmp_path):
    """The whole safety argument. `create_all()` only ever creates, so
    anything it left behind is empty; a table with data in it was made by
    something else and dropping it loses records."""
    from app.services.schema_repair import repair

    db, added = _half_upgraded(tmp_path)
    # Pick the table the upgrade hits first and give it a row that satisfies
    # its NOT NULL columns, so the refusal is about data rather than about a
    # constraint.
    victim = "vendor_credits"
    assert victim in added
    engine = create_engine(f"sqlite:///{db}")
    with engine.begin() as conn:
        conn.execute(
            text(
                'INSERT INTO "vendor_credits" '
                "(credit_number, vendor_id, date) VALUES ('VC-X', 1, '2026-01-01')"
            )
        )
    engine.dispose()

    result = repair(f"sqlite:///{db}")
    assert not result.ok
    assert "row(s)" in result.message and victim in result.message
    assert "needs a person" in result.message
    # And it left the table alone.
    engine = create_engine(f"sqlite:///{db}")
    assert inspect(engine).has_table(victim)
    engine.dispose()


def test_repair_is_a_no_op_on_a_healthy_file(tmp_path):
    from alembic import command

    from app.services.schema_repair import repair

    db = tmp_path / "healthy.db"
    command.upgrade(_cfg(db), "head")
    result = repair(f"sqlite:///{db}")
    assert result.ok and result.dropped == []


def test_repair_also_upgrades_an_ordinary_old_file(tmp_path):
    """It replaces `alembic upgrade head` rather than sitting beside it, so an
    operator does not have to work out which situation they are in."""
    from alembic import command

    from app.services.schema_repair import repair

    db = tmp_path / "old.db"
    command.upgrade(_cfg(db), "e7f8a9b0c1d2")
    result = repair(f"sqlite:///{db}")
    assert result.ok and result.now_at == _head() and result.dropped == []


def test_dry_run_changes_nothing(tmp_path):
    from app.services.schema_repair import repair

    db, added = _half_upgraded(tmp_path)
    before = _rev(db)
    result = repair(f"sqlite:///{db}", dry_run=True)
    assert "dry run" in result.message
    assert _rev(db) == before
    engine = create_engine(f"sqlite:///{db}")
    assert added <= set(inspect(engine).get_table_names())
    engine.dispose()


def _rev(db):
    engine = create_engine(f"sqlite:///{db}")
    try:
        with engine.connect() as conn:
            return conn.execute(
                text("SELECT version_num FROM alembic_version")
            ).scalar()
    finally:
        engine.dispose()


def test_the_startup_refusal_names_the_repair_for_a_half_upgraded_file(
    tmp_path, monkeypatch
):
    """The message is the only way an operator finds out which situation they
    are in, so it has to differ."""
    import app.main as main

    db, _ = _half_upgraded(tmp_path)
    monkeypatch.setattr(main, "engine", create_engine(f"sqlite:///{db}"))
    with pytest.raises(RuntimeError) as e:
        main._refuse_a_database_behind_head()
    assert "repair-schema.py" in str(e.value)
    assert "will fail" in str(e.value)


def test_the_startup_refusal_still_says_upgrade_for_an_ordinary_old_file(
    tmp_path, monkeypatch
):
    from alembic import command

    import app.main as main

    db = tmp_path / "ordinary.db"
    command.upgrade(_cfg(db), "e7f8a9b0c1d2")
    monkeypatch.setattr(main, "engine", create_engine(f"sqlite:///{db}"))
    with pytest.raises(RuntimeError) as e:
        main._refuse_a_database_behind_head()
    detail = str(e.value)
    assert "alembic upgrade head" in detail
    assert "repair-schema.py" not in detail


# ── #144: the message must name a path that exists ───────────────────────


def test_the_refusal_names_a_path_that_exists():
    """Found during check 0 on the published v2.12.0 artifact.

    The guard printed `scripts/repair-schema.py`, and that file was **not in
    the bundle** — `scripts/` ships selectively and the zip carried only the
    three Server Edition PowerShell files. Server Edition is precisely the
    deployment shape the half-upgraded branch exists for, so the operator
    most likely to read the message was the one least likely to have the
    file. An error naming a path the reader cannot reach is the same defect
    as #139's "deactivate it instead" with no deactivate control.
    """
    from pathlib import Path

    from app.services.schema_repair import repair_script_path

    assert Path(
        repair_script_path()
    ).exists(), "the startup refusal names a script that is not there"


def test_both_specs_ship_the_repair_script():
    """The other half: it has to be IN the bundle for the resolved path to
    find it. Guarded in the spec rather than trusted, because the only way
    to notice it was missing was to unzip a released artifact."""
    from pathlib import Path

    root = Path(__file__).resolve().parents[1]
    for spec in (
        "packaging/windows/SlowBooksPro.spec",
        "packaging/macos/SlowBooksPro-mac.spec",
    ):
        src = (root / spec).read_text(encoding="utf-8")
        assert "repair-schema.py" in src, f"{spec} does not ship the repair script"


def test_the_frozen_path_is_preferred_when_it_exists(tmp_path, monkeypatch):
    """A bundle resolves to its own copy, not to a repo path that will not be
    there on an installed machine."""
    import sys

    from app.services import schema_repair

    fake = tmp_path / "scripts"
    fake.mkdir()
    (fake / "repair-schema.py").write_text("# bundled copy\n")
    monkeypatch.setattr(sys, "_MEIPASS", str(tmp_path), raising=False)

    got = schema_repair.repair_script_path()
    assert got == str(fake / "repair-schema.py")
