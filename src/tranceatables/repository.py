"""SQLite persistence and append-only audit events for Stage 1."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import sqlite3

from .models import DeliveryRequest, FoodHandling
from .order_state import InvalidTransition, Order, OrderStatus, transition_order


class DuplicateOrderError(ValueError):
    pass


class OrderNotFoundError(LookupError):
    pass


class ConcurrentUpdateError(RuntimeError):
    pass


@dataclass(frozen=True)
class OrderEvent:
    event_id: int
    order_id: str
    from_status: OrderStatus | None
    to_status: OrderStatus
    actor: str
    reason: str | None
    occurred_at: str
    version: int


class SQLiteOrderRepository:
    def __init__(self, database_path: str | Path) -> None:
        self.database_path = str(database_path)
        self._initialize()

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.database_path)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        return connection

    def _initialize(self) -> None:
        with self._connect() as connection:
            connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS orders (
                    order_id TEXT PRIMARY KEY,
                    distance_km REAL NOT NULL CHECK(distance_km >= 0),
                    payload_kg REAL NOT NULL CHECK(payload_kg >= 0),
                    handling TEXT NOT NULL,
                    packaging_verified INTEGER NOT NULL,
                    customer_handoff_required INTEGER NOT NULL,
                    status TEXT NOT NULL,
                    version INTEGER NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS order_events (
                    event_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    order_id TEXT NOT NULL REFERENCES orders(order_id),
                    from_status TEXT,
                    to_status TEXT NOT NULL,
                    actor TEXT NOT NULL,
                    reason TEXT,
                    occurred_at TEXT NOT NULL,
                    version INTEGER NOT NULL,
                    UNIQUE(order_id, version)
                );
                """
            )

    def create(self, order: Order, *, actor: str) -> Order:
        try:
            with self._connect() as connection:
                connection.execute(
                    """INSERT INTO orders VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                    (
                        order.order_id,
                        order.request.distance_km,
                        order.request.payload_kg,
                        order.request.handling.value,
                        int(order.request.packaging_verified),
                        int(order.request.customer_handoff_required),
                        order.status.value,
                        order.version,
                        order.created_at,
                        order.updated_at,
                    ),
                )
                connection.execute(
                    """INSERT INTO order_events
                    (order_id, from_status, to_status, actor, reason, occurred_at, version)
                    VALUES (?, NULL, ?, ?, ?, ?, ?)""",
                    (order.order_id, order.status.value, actor, "order_created", order.created_at, order.version),
                )
        except sqlite3.IntegrityError as error:
            raise DuplicateOrderError(f"order already exists: {order.order_id}") from error
        return order

    def get(self, order_id: str) -> Order:
        with self._connect() as connection:
            row = connection.execute("SELECT * FROM orders WHERE order_id = ?", (order_id,)).fetchone()
        if row is None:
            raise OrderNotFoundError(order_id)
        return self._row_to_order(row)

    def transition(
        self,
        order_id: str,
        target: OrderStatus,
        *,
        actor: str,
        reason: str | None,
        occurred_at: str,
        expected_version: int | None = None,
    ) -> Order:
        with self._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            row = connection.execute("SELECT * FROM orders WHERE order_id = ?", (order_id,)).fetchone()
            if row is None:
                raise OrderNotFoundError(order_id)
            current = self._row_to_order(row)
            if expected_version is not None and current.version != expected_version:
                raise ConcurrentUpdateError(
                    f"expected version {expected_version}, found {current.version}"
                )
            updated = transition_order(current, target, occurred_at=occurred_at)
            result = connection.execute(
                """UPDATE orders SET status = ?, version = ?, updated_at = ?
                WHERE order_id = ? AND version = ?""",
                (updated.status.value, updated.version, updated.updated_at, order_id, current.version),
            )
            if result.rowcount != 1:
                raise ConcurrentUpdateError(f"order changed during update: {order_id}")
            connection.execute(
                """INSERT INTO order_events
                (order_id, from_status, to_status, actor, reason, occurred_at, version)
                VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (
                    order_id,
                    current.status.value,
                    updated.status.value,
                    actor,
                    reason,
                    occurred_at,
                    updated.version,
                ),
            )
        return updated

    def events(self, order_id: str) -> tuple[OrderEvent, ...]:
        self.get(order_id)
        with self._connect() as connection:
            rows = connection.execute(
                "SELECT * FROM order_events WHERE order_id = ? ORDER BY version", (order_id,)
            ).fetchall()
        return tuple(
            OrderEvent(
                event_id=row["event_id"],
                order_id=row["order_id"],
                from_status=OrderStatus(row["from_status"]) if row["from_status"] else None,
                to_status=OrderStatus(row["to_status"]),
                actor=row["actor"],
                reason=row["reason"],
                occurred_at=row["occurred_at"],
                version=row["version"],
            )
            for row in rows
        )

    @staticmethod
    def _row_to_order(row: sqlite3.Row) -> Order:
        request = DeliveryRequest(
            order_id=row["order_id"],
            distance_km=row["distance_km"],
            payload_kg=row["payload_kg"],
            handling=FoodHandling(row["handling"]),
            packaging_verified=bool(row["packaging_verified"]),
            customer_handoff_required=bool(row["customer_handoff_required"]),
        )
        return Order(
            request=request,
            status=OrderStatus(row["status"]),
            version=row["version"],
            created_at=row["created_at"],
            updated_at=row["updated_at"],
        )
