import sqlite3

from tranceatables.grist_sync import GristClient, TableMapping, sync_table


class FakeGrist(GristClient):
    def __init__(self, records):
        self.remote = records
        self.created = []
        self.updated = []

    def records(self, table):
        return self.remote

    def add(self, table, fields):
        self.created.extend(fields)

    def update(self, table, records):
        self.updated.extend(records)


def connection():
    value = sqlite3.connect(":memory:")
    value.row_factory = sqlite3.Row
    value.execute("CREATE TABLE robots (robot_id TEXT, status TEXT)")
    value.executemany("INSERT INTO robots VALUES (?, ?)", [("R-1", "available"), ("R-2", "assigned")])
    return value


MAPPING = TableMapping(
    "SELECT robot_id AS RobotId, status AS Status FROM robots ORDER BY robot_id",
    "Robots",
    "RobotId",
)


def test_dry_run_plans_without_writing():
    client = FakeGrist([{"id": 7, "fields": {"RobotId": "R-1", "Status": "available"}}])
    result = sync_table(connection(), client, MAPPING)
    assert (result.created, result.updated, result.unchanged, result.dry_run) == (1, 0, 1, True)
    assert client.created == []


def test_apply_creates_and_updates_by_stable_key():
    client = FakeGrist([{"id": 7, "fields": {"RobotId": "R-1", "Status": "offline"}}])
    result = sync_table(connection(), client, MAPPING, apply=True)
    assert (result.created, result.updated, result.unchanged, result.dry_run) == (1, 1, 0, False)
    assert client.created == [{"RobotId": "R-2", "Status": "assigned"}]
    assert client.updated == [{"id": 7, "fields": {"RobotId": "R-1", "Status": "available"}}]


def test_client_rejects_non_https_base_url():
    try:
        GristClient("http://example.test", "doc", "secret")
    except Exception as error:
        assert "https" in str(error)
    else:
        raise AssertionError("expected secure URL validation")
