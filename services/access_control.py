from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from pathlib import Path


class AccessDenied(RuntimeError):
    """Raised when a user cannot consume a paid service."""


@dataclass(frozen=True)
class AccessResult:
    allowed: bool
    credits_before: int
    credits_after: int
    reason: str = ""


def _connect(db: Path | str) -> sqlite3.Connection:
    conn = sqlite3.connect(db, timeout=10)
    conn.execute("PRAGMA busy_timeout=5000")
    return conn


def service_cost(db: Path | str, service: str, default: int = 1) -> int:
    with _connect(db) as conn:
        row = conn.execute(
            "SELECT credits, enabled FROM services WHERE key=?", (service,)
        ).fetchone()
    if row is None:
        return max(1, default)
    cost, enabled = int(row[0] or default), int(row[1])
    if not enabled:
        raise AccessDenied("الخدمة متوقفة مؤقتاً من المدير.")
    return max(1, cost)


def consume(db: Path | str, user_id: int, service: str, default_cost: int = 1) -> AccessResult:
    """Atomically verify service availability and debit credits.

    This prevents two concurrent requests from spending the same last credit.
    """
    with _connect(db) as conn:
        conn.execute("BEGIN IMMEDIATE")
        row = conn.execute(
            "SELECT credits FROM users WHERE id=?", (user_id,)
        ).fetchone()
        if row is None:
            return AccessResult(False, 0, 0, "المستخدم غير مسجل.")

        service_row = conn.execute(
            "SELECT credits, enabled FROM services WHERE key=?", (service,)
        ).fetchone()
        if service_row is not None and int(service_row[1]) == 0:
            return AccessResult(False, int(row[0]), int(row[0]), "الخدمة متوقفة مؤقتاً من المدير.")

        cost = max(1, int(service_row[0]) if service_row else default_cost)
        before = int(row[0])
        if before < cost:
            return AccessResult(False, before, before, "رصيدك غير كافٍ.")

        after = before - cost
        conn.execute("UPDATE users SET credits=? WHERE id=?", (after, user_id))
        conn.commit()
        return AccessResult(True, before, after)


def refund(db: Path | str, user_id: int, amount: int) -> int:
    amount = max(0, int(amount))
    with _connect(db) as conn:
        conn.execute("UPDATE users SET credits=credits+? WHERE id=?", (amount, user_id))
        row = conn.execute("SELECT credits FROM users WHERE id=?", (user_id,)).fetchone()
        return int(row[0]) if row else 0


def grant(db: Path | str, user_id: int, amount: int) -> int:
    amount = int(amount)
    if amount <= 0:
        raise ValueError("عدد العمليات يجب أن يكون أكبر من صفر.")
    with _connect(db) as conn:
        conn.execute("UPDATE users SET credits=credits+? WHERE id=?", (amount, user_id))
        row = conn.execute("SELECT credits FROM users WHERE id=?", (user_id,)).fetchone()
        if row is None:
            raise AccessDenied("المستخدم غير مسجل.")
        return int(row[0])


def approve_payment(db: Path | str, payment_id: int, default_credits: int = 20) -> tuple[int, int]:
    """Approve a pending payment exactly once and grant its recorded credit amount."""
    with _connect(db) as conn:
        conn.execute("BEGIN IMMEDIATE")
        row = conn.execute(
            "SELECT user_id, status, amount FROM payments WHERE id=?", (payment_id,)
        ).fetchone()
        if row is None:
            raise AccessDenied("طلب الدفع غير موجود.")
        user_id, status, amount = int(row[0]), row[1], int(row[2] or 0)
        if status != "pending":
            raise AccessDenied("تمت معالجة طلب الدفع مسبقاً.")

        # Keep the existing manual-payment model, but make the granted amount explicit.
        credits = max(1, amount) if amount > 0 else max(1, int(default_credits))
        conn.execute("UPDATE payments SET status='approved' WHERE id=?", (payment_id,))
        conn.execute("UPDATE users SET credits=credits+? WHERE id=?", (credits, user_id))
        conn.commit()
        return user_id, credits
