"""Engine, sessions and schema creation (including the integrity triggers)."""
from __future__ import annotations

from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from .models import Base

_SCHEMA_LOCK = 727002  # advisory-lock id so two instances do not migrate at once


def make_engine(url: str) -> Engine:
    return create_engine(url, pool_pre_ping=True, pool_size=5, max_overflow=10)


def make_session_factory(engine: Engine) -> sessionmaker[Session]:
    return sessionmaker(bind=engine, expire_on_commit=False, autoflush=True)


# --- integrity rules enforced inside PostgreSQL --------------------------------
# Each statement is executed on its own.  They are all idempotent.
INTEGRITY_SQL: list[str] = [
    # Hash used to chain audit rows together.  Timestamps are rendered in UTC so the
    # value does not depend on any session's TimeZone setting.
    """
    CREATE OR REPLACE FUNCTION audit_compute_hash(prev text, r audit_log) RETURNS text AS $$
        SELECT encode(sha256(convert_to(concat_ws('|',
            prev,
            r.seq::text,
            coalesce(r.ticket_id::text, ''),
            r.actor_type,
            coalesce(r.actor_id::text, ''),
            r.actor_name,
            r.action,
            r.details::text,
            to_char(r.occurred_at AT TIME ZONE 'UTC', 'YYYY-MM-DD"T"HH24:MI:SS.US'),
            to_char(r.recorded_at AT TIME ZONE 'UTC', 'YYYY-MM-DD"T"HH24:MI:SS.US')
        ), 'UTF8')), 'hex')
    $$ LANGUAGE sql STABLE
    """,
    # Chain order is decided by the database, one writer at a time.
    """
    CREATE OR REPLACE FUNCTION audit_before_insert() RETURNS trigger AS $$
    DECLARE
        last_seq bigint;
        last_hash text;
    BEGIN
        PERFORM pg_advisory_xact_lock(727001);
        SELECT seq, row_hash INTO last_seq, last_hash FROM audit_log ORDER BY seq DESC LIMIT 1;
        NEW.seq := coalesce(last_seq, 0) + 1;
        NEW.prev_hash := coalesce(last_hash, repeat('0', 64));
        NEW.recorded_at := clock_timestamp();
        NEW.row_hash := audit_compute_hash(NEW.prev_hash, NEW);
        RETURN NEW;
    END
    $$ LANGUAGE plpgsql
    """,
    "DROP TRIGGER IF EXISTS audit_log_chain ON audit_log",
    """
    CREATE TRIGGER audit_log_chain BEFORE INSERT ON audit_log
    FOR EACH ROW EXECUTE FUNCTION audit_before_insert()
    """,
    # Returns NULL when the chain is intact, else the first sequence number that fails.
    """
    CREATE OR REPLACE FUNCTION audit_verify() RETURNS bigint AS $$
    DECLARE
        r audit_log;
        prev text := repeat('0', 64);
        expected bigint := 0;
    BEGIN
        FOR r IN SELECT * FROM audit_log ORDER BY seq LOOP
            expected := expected + 1;
            IF r.seq <> expected OR r.prev_hash <> prev OR r.row_hash <> audit_compute_hash(prev, r) THEN
                RETURN r.seq;
            END IF;
            prev := r.row_hash;
        END LOOP;
        RETURN NULL;
    END
    $$ LANGUAGE plpgsql
    """,
    # Append-only tables: any UPDATE, DELETE or TRUNCATE is refused.
    """
    CREATE OR REPLACE FUNCTION forbid_change() RETURNS trigger AS $$
    BEGIN
        RAISE EXCEPTION USING
            ERRCODE = 'integrity_constraint_violation',
            MESSAGE = TG_TABLE_NAME || ' is append-only: ' || TG_OP || ' is not allowed';
    END
    $$ LANGUAGE plpgsql
    """,
    "DROP TRIGGER IF EXISTS audit_log_append_only ON audit_log",
    """
    CREATE TRIGGER audit_log_append_only BEFORE UPDATE OR DELETE ON audit_log
    FOR EACH ROW EXECUTE FUNCTION forbid_change()
    """,
    "DROP TRIGGER IF EXISTS audit_log_no_truncate ON audit_log",
    """
    CREATE TRIGGER audit_log_no_truncate BEFORE TRUNCATE ON audit_log
    FOR EACH STATEMENT EXECUTE FUNCTION forbid_change()
    """,
    "DROP TRIGGER IF EXISTS messages_append_only ON messages",
    """
    CREATE TRIGGER messages_append_only BEFORE UPDATE OR DELETE ON messages
    FOR EACH ROW EXECUTE FUNCTION forbid_change()
    """,
    "DROP TRIGGER IF EXISTS messages_no_truncate ON messages",
    """
    CREATE TRIGGER messages_no_truncate BEFORE TRUNCATE ON messages
    FOR EACH STATEMENT EXECUTE FUNCTION forbid_change()
    """,
    # Tickets are never deleted, and the facts about when they arrived and when they
    # were first answered can never be rewritten.
    """
    CREATE OR REPLACE FUNCTION tickets_guard() RETURNS trigger AS $$
    BEGIN
        IF TG_OP = 'DELETE' THEN
            RAISE EXCEPTION USING
                ERRCODE = 'integrity_constraint_violation',
                MESSAGE = 'tickets cannot be deleted';
        END IF;
        IF NEW.created_at <> OLD.created_at OR NEW.customer_id <> OLD.customer_id
           OR NEW.public_token <> OLD.public_token THEN
            RAISE EXCEPTION USING
                ERRCODE = 'integrity_constraint_violation',
                MESSAGE = 'ticket creation facts cannot be changed';
        END IF;
        IF OLD.first_response_at IS NOT NULL
           AND NEW.first_response_at IS DISTINCT FROM OLD.first_response_at THEN
            RAISE EXCEPTION USING
                ERRCODE = 'integrity_constraint_violation',
                MESSAGE = 'first_response_at cannot be changed once set';
        END IF;
        RETURN NEW;
    END
    $$ LANGUAGE plpgsql
    """,
    "DROP TRIGGER IF EXISTS tickets_guard_trg ON tickets",
    """
    CREATE TRIGGER tickets_guard_trg BEFORE UPDATE OR DELETE ON tickets
    FOR EACH ROW EXECUTE FUNCTION tickets_guard()
    """,
    "DROP TRIGGER IF EXISTS tickets_no_truncate ON tickets",
    """
    CREATE TRIGGER tickets_no_truncate BEFORE TRUNCATE ON tickets
    FOR EACH STATEMENT EXECUTE FUNCTION forbid_change()
    """,
    # A pause row may only be closed, once.
    """
    CREATE OR REPLACE FUNCTION sla_pauses_guard() RETURNS trigger AS $$
    BEGIN
        IF TG_OP = 'DELETE' THEN
            RAISE EXCEPTION USING
                ERRCODE = 'integrity_constraint_violation',
                MESSAGE = 'sla_pauses is append-only: DELETE is not allowed';
        END IF;
        IF OLD.ended_at IS NOT NULL OR NEW.ticket_id <> OLD.ticket_id
           OR NEW.started_at <> OLD.started_at OR NEW.reason <> OLD.reason THEN
            RAISE EXCEPTION USING
                ERRCODE = 'integrity_constraint_violation',
                MESSAGE = 'sla_pauses rows can only be closed, once';
        END IF;
        RETURN NEW;
    END
    $$ LANGUAGE plpgsql
    """,
    "DROP TRIGGER IF EXISTS sla_pauses_guard_trg ON sla_pauses",
    """
    CREATE TRIGGER sla_pauses_guard_trg BEFORE UPDATE OR DELETE ON sla_pauses
    FOR EACH ROW EXECUTE FUNCTION sla_pauses_guard()
    """,
    # The only door customer-facing code is allowed to use to read messages.
    "DROP VIEW IF EXISTS customer_messages",
    """
    CREATE VIEW customer_messages AS
        SELECT id, ticket_id, kind, author_type, body, created_at
        FROM messages
        WHERE visibility = 'public' AND kind <> 'internal_note'
    """,
]


# `create_all` only creates what is missing; it never alters an existing table.  These
# statements bring a database created by an earlier version up to date.  Idempotent.
MIGRATIONS: list[str] = [
    "ALTER TABLE customers ADD COLUMN IF NOT EXISTS password_hash VARCHAR(255)",
    # Customers can now act, so the audit log may name them as the actor.
    """
    DO $$
    BEGIN
        IF NOT EXISTS (
            SELECT 1 FROM pg_constraint
            WHERE conname = 'audit_actor_type_ck'
              AND strpos(pg_get_constraintdef(oid), 'customer') > 0
        ) THEN
            ALTER TABLE audit_log DROP CONSTRAINT IF EXISTS audit_actor_type_ck;
            ALTER TABLE audit_log ADD CONSTRAINT audit_actor_type_ck
                CHECK (actor_type IN ('agent', 'system', 'customer'));
        END IF;
    END
    $$
    """,
]


def init_db(engine: Engine) -> None:
    """Create tables, migrate older ones and add integrity rules.  Safe on every start-up."""
    with engine.begin() as conn:
        conn.execute(text("SELECT pg_advisory_xact_lock(:k)"), {"k": _SCHEMA_LOCK})
        Base.metadata.create_all(conn)
        for statement in MIGRATIONS:
            conn.exec_driver_sql(statement)
        for statement in INTEGRITY_SQL:
            conn.exec_driver_sql(statement)
