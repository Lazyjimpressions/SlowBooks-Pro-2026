"""Recover a database that was half-upgraded by `create_all()` (issue #132).

The damage, and why `alembic upgrade head` cannot undo it: a server started
against a database behind the migration head ran `Base.metadata.create_all()`,
which **creates** the tables a pending revision would add, does **not** alter
the ones it would change, and does **not** move `alembic_version`. The next
upgrade then fails on `table <x> already exists` and the file is stuck — the
newer tables are present and empty, the older ones are missing their new
columns, and the revision stamp is behind both.

Refusing to start (see `app.main._refuse_a_database_behind_head`) stops that
happening again. It does nothing for a file it has already happened to, and
telling that operator to run `alembic upgrade head` is advice that fails —
the same shape as an error saying "deactivate it instead" when nothing on the
page could deactivate (#139).

The repair is the manual one, automated and bounded: run the upgrade, and
when it fails because a table already exists, **verify the table is empty**,
drop it, and try again. Empty is the whole safety argument. `create_all()`
only ever creates; anything it made carries no rows. A table with rows in it
was made by something else and this refuses to touch it.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from pathlib import Path

from sqlalchemy import create_engine, inspect, text

logger = logging.getLogger(__name__)

ROOT = Path(__file__).resolve().parent.parent.parent

# "table vendor_credits already exists" (SQLite),
# 'relation "vendor_credits" already exists' (PostgreSQL)
_ALREADY_EXISTS = re.compile(
    r'(?:table|relation)\s+"?([A-Za-z_][A-Za-z0-9_]*)"?\s+already exists', re.I
)

# One drop per pending revision is already generous; this only bounds a
# pathological loop, it is not an expected number.
MAX_ROUNDS = 25


@dataclass
class RepairResult:
    ok: bool
    started_at: str | None = None
    now_at: str | None = None
    dropped: list[str] = field(default_factory=list)
    message: str = ""


def repair_script_path() -> str:
    """Where `repair-schema.py` actually is on this install.

    A frozen bundle puts data files under `sys._MEIPASS`, so the script lives
    at `_internal/scripts/repair-schema.py` rather than at `scripts/` — and
    the startup refusal that names it is read mostly by Server Edition
    operators, who may only have the bundle (#144). Falls back to the
    repo-relative path, which is right for a checkout and is also the least
    misleading thing to print if the file is missing entirely.
    """
    import sys

    base = getattr(sys, "_MEIPASS", None)
    if base:
        bundled = Path(base) / "scripts" / "repair-schema.py"
        if bundled.exists():
            return str(bundled)
    return str(
        (ROOT / "scripts" / "repair-schema.py").resolve()
        if (ROOT / "scripts" / "repair-schema.py").exists()
        else "scripts/repair-schema.py"
    )


def _alembic_cfg(url: str):
    from alembic.config import Config

    cfg = Config(str(ROOT / "alembic.ini"))
    cfg.set_main_option("script_location", str(ROOT / "migrations"))
    cfg.attributes["database_url"] = url
    return cfg


def _current_revision(engine) -> str | None:
    if not inspect(engine).has_table("alembic_version"):
        return None
    with engine.connect() as conn:
        row = conn.execute(text("SELECT version_num FROM alembic_version")).first()
    return row[0] if row else None


def _row_count(engine, table: str) -> int:
    with engine.connect() as conn:
        return conn.execute(text(f'SELECT COUNT(*) FROM "{table}"')).scalar() or 0


def repair(url: str, dry_run: bool = False) -> RepairResult:
    """Bring `url` to head, dropping only EMPTY tables that block the way.

    Returns a RepairResult rather than raising, so a caller can report the
    reason. The one thing it will not do is drop a table with rows in it.
    """
    from alembic import command

    engine = create_engine(url)
    try:
        started = _current_revision(engine)
        result = RepairResult(ok=False, started_at=started, now_at=started)

        for _ in range(MAX_ROUNDS):
            try:
                if dry_run:
                    result.ok = True
                    result.message = "dry run: would upgrade to head" + (
                        f", after dropping {result.dropped}" if result.dropped else ""
                    )
                    return result
                command.upgrade(_alembic_cfg(url), "head")
                result.ok = True
                result.now_at = _current_revision(engine)
                result.message = f"upgraded {started} -> {result.now_at}" + (
                    f"; dropped {len(result.dropped)} empty table(s) "
                    f"left behind by create_all: {', '.join(result.dropped)}"
                    if result.dropped
                    else ""
                )
                return result
            except Exception as exc:  # noqa: BLE001 — inspected below
                m = _ALREADY_EXISTS.search(str(exc))
                if not m:
                    result.message = f"upgrade failed for another reason: {exc}"
                    return result

                table = m.group(1)
                if not inspect(engine).has_table(table):
                    result.message = (
                        f"upgrade says '{table}' already exists but it is not "
                        f"there; not guessing further"
                    )
                    return result

                rows = _row_count(engine, table)
                if rows:
                    # The safety argument in one line. create_all() only ever
                    # creates, so anything it made is empty; a table with data
                    # was made by something else and dropping it loses records.
                    result.message = (
                        f"refusing to repair: '{table}' is in the way of the "
                        f"upgrade but holds {rows} row(s), so it was not left "
                        f"behind by create_all. This needs a person."
                    )
                    return result

                logger.warning("schema repair: dropping empty table %s", table)
                with engine.begin() as conn:
                    conn.execute(text(f'DROP TABLE "{table}"'))
                result.dropped.append(table)

        result.message = f"gave up after {MAX_ROUNDS} rounds; dropped {result.dropped}"
        return result
    finally:
        engine.dispose()


_CREATE_TABLE = re.compile(r"""op\.create_table\(\s*["']([A-Za-z_][A-Za-z0-9_]*)["']""")


def tables_pending_revisions_would_create(url: str, current: str) -> set[str]:
    """Table names the not-yet-applied revisions call `op.create_table` for.

    Read out of our own migration scripts. That is cheap, and it is precise in
    the way that matters: if a pending revision is going to create table X and
    X is already there, a `create_all()` put it there. The alternative —
    "behind head and has an empty table this build expects" — is true of
    almost every ordinary old file, because most tables are legitimately
    empty. That version told every upgrading user to run a repair script.
    """
    from alembic.script import ScriptDirectory

    sd = ScriptDirectory.from_config(_alembic_cfg(url))
    head = sd.get_current_head()
    names: set[str] = set()
    # walk_revisions goes head -> base; everything after `current` is pending.
    for rev in sd.walk_revisions(base=current or "base", head=head or "heads"):
        if rev.revision == current:
            continue
        try:
            names |= set(_CREATE_TABLE.findall(Path(rev.path).read_text()))
        except OSError:
            logger.warning("could not read migration %s", rev.path)
    return names


def looks_half_upgraded(engine) -> bool:
    """True when a table a PENDING revision would create is already present.

    That is the signature of `create_all()` having run against a database
    behind head, and it is the only case where `alembic upgrade head` cannot
    recover the file.

    Advisory only: it chooses which of two messages the startup refusal
    prints, never whether anything is dropped. `repair()` re-checks emptiness
    itself at the moment it acts.
    """
    try:
        current = _current_revision(engine)
        if current is None:
            return False
        url = str(engine.url)
        from alembic.script import ScriptDirectory

        head = ScriptDirectory.from_config(_alembic_cfg(url)).get_current_head()
        if not head or current == head:
            return False

        pending = tables_pending_revisions_would_create(url, current)
        if not pending:
            return False
        present = set(inspect(engine).get_table_names())
        return bool(pending & present)
    except Exception:
        logger.exception("could not tell whether the database is half-upgraded")
        return False
