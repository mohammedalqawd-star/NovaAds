from pathlib import Path
import sqlite3

from services.access_control import AccessDenied, approve_payment, consume, grant, refund


def setup_db(path: Path):
    with sqlite3.connect(path) as c:
        c.executescript(
            """
            CREATE TABLE users(id INTEGER PRIMARY KEY, username TEXT, credits INTEGER NOT NULL DEFAULT 0);
            CREATE TABLE services(key TEXT PRIMARY KEY, name TEXT, category TEXT, enabled INTEGER DEFAULT 1, credits INTEGER DEFAULT 1);
            CREATE TABLE payments(id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER, amount INTEGER, proof TEXT, status TEXT DEFAULT 'pending');
            INSERT INTO users VALUES (1, 'tester', 2);
            INSERT INTO services VALUES ('video', 'Video', 'video', 1, 1);
            INSERT INTO services VALUES ('disabled', 'Disabled', 'video', 0, 1);
            INSERT INTO payments(user_id, amount, proof, status) VALUES (1, 5, 'proof', 'pending');
            """
        )


def test_consume_debits_atomically(tmp_path):
    db = tmp_path / 'test.sqlite3'
    setup_db(db)
    r = consume(db, 1, 'video')
    assert r.allowed and r.credits_before == 2 and r.credits_after == 1
    r = consume(db, 1, 'video')
    assert r.allowed and r.credits_after == 0
    r = consume(db, 1, 'video')
    assert not r.allowed and r.credits_after == 0


def test_disabled_service_is_blocked(tmp_path):
    db = tmp_path / 'test.sqlite3'
    setup_db(db)
    r = consume(db, 1, 'disabled')
    assert not r.allowed
    assert 'متوقفة' in r.reason


def test_refund_and_grant(tmp_path):
    db = tmp_path / 'test.sqlite3'
    setup_db(db)
    assert refund(db, 1, 3) == 5
    assert grant(db, 1, 5) == 10


def test_payment_is_approved_once(tmp_path):
    db = tmp_path / 'test.sqlite3'
    setup_db(db)
    uid, credits = approve_payment(db, 1)
    assert (uid, credits) == (1, 5)
    try:
        approve_payment(db, 1)
    except AccessDenied:
        pass
    else:
        raise AssertionError('payment was approved twice')
