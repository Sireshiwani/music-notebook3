"""SQLite: add new columns to existing tables when upgrading (create_all does not alter)."""
from sqlalchemy import inspect, text


def ensure_sqlite_schema(db, app):
    """Add columns to `notes` if missing (SQLite)."""
    engine = db.engine
    if engine.dialect.name != "sqlite":
        return
    insp = inspect(engine)
    if "notes" not in insp.get_table_names():
        return
    cols = {c["name"] for c in insp.get_columns("notes")}
    statements = []
    if "school_id" not in cols:
        statements.append("ALTER TABLE notes ADD COLUMN school_id INTEGER REFERENCES schools(id)")
    if "school_term_id" not in cols:
        statements.append("ALTER TABLE notes ADD COLUMN school_term_id INTEGER REFERENCES school_terms(id)")
    if "calendar_period_id" not in cols:
        statements.append(
            "ALTER TABLE notes ADD COLUMN calendar_period_id INTEGER REFERENCES calendar_periods(id)"
        )
    if not statements:
        return
    with engine.begin() as conn:
        for stmt in statements:
            conn.execute(text(stmt))
