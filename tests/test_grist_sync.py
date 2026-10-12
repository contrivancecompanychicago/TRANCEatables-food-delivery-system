import sqlite3

from tranceatables.grist_sync import GristClient, TABLE_MAPPINGS, TableMapping, _source_rows, sync_table


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


def test_order_event_mapping_matches_grist_schema():
    value = sqlite3.connect(":memory:")
    value.row_factory = sqlite3.Row
    value.execute("""CREATE TABLE order_events (
        event_id INTEGER, order_id TEXT, from_status TEXT, to_status TEXT,
        actor TEXT, reason TEXT, occurred_at TEXT, version INTEGER
    )""")
    value.execute(
        "INSERT INTO order_events VALUES (1, 'O-1', NULL, 'draft', 'system', "
        "'order_created', '2026-10-08T12:00:00+00:00', 0)"
    )
    mapping = next(item for item in TABLE_MAPPINGS if item.grist_table == "OrderEvents")
    row = _source_rows(value, mapping)[0]
    assert set(row) == {
        "EventId", "OrderId", "PreviousStatus", "NewStatus",
        "EventType", "Message", "OccurredAt",
    }
    assert row["EventType"] == "order_created"


def test_serving_audit_mappings_match_grist_schemas():
    value = sqlite3.connect(":memory:")
    value.row_factory = sqlite3.Row
    value.executescript(
        """
        CREATE TABLE food_serving_candidates (
            candidate_id TEXT, meal_plan_id TEXT, food_slot INTEGER,
            source TEXT, source_item_id TEXT, source_upc TEXT,
            brand_name TEXT, item_name TEXT, serving_quantity REAL,
            serving_unit_label TEXT, serving_weight_grams REAL,
            metric_quantity REAL, metric_unit TEXT, ontology_source TEXT,
            review_status TEXT, created_at TEXT, updated_at TEXT,
            simulation_only INTEGER
        );
        CREATE TABLE serving_candidate_reviews (
            review_id TEXT, candidate_id TEXT, decision TEXT,
            reviewer TEXT, notes TEXT, decided_at TEXT,
            simulation_only INTEGER
        );
        CREATE TABLE serving_candidate_revisions (
            revision_id TEXT, original_candidate_id TEXT,
            source_item_id TEXT, serving_quantity REAL,
            serving_unit_label TEXT, serving_weight_grams REAL,
            metric_quantity REAL, metric_unit TEXT, provenance TEXT,
            created_by TEXT, created_at TEXT, simulation_only INTEGER
        );
        CREATE TABLE serving_revision_reviews (
            review_id TEXT, revision_id TEXT, decision TEXT,
            reviewer TEXT, notes TEXT, decided_at TEXT,
            simulation_only INTEGER
        );

        INSERT INTO food_serving_candidates VALUES (
            'C-1', 'MP-1', 1, 'sheety', 'ITEM-1', '123',
            'Brand', 'Food', 1.0, 'cup', 100.0,
            100.0, 'g', 'tranceatables_internal',
            'structurally_valid', '2026-10-12T12:00:00+00:00',
            '2026-10-12T12:00:00+00:00', 1
        );
        INSERT INTO serving_candidate_reviews VALUES (
            'CR-1', 'C-1', 'approved', 'operator',
            'reviewed', '2026-10-12T12:01:00+00:00', 1
        );
        INSERT INTO serving_candidate_revisions VALUES (
            'R-1', 'C-1', 'ITEM-1', 1.0, 'cup', 101.0,
            100.0, 'g', 'verified_source', 'operator',
            '2026-10-12T12:02:00+00:00', 1
        );
        INSERT INTO serving_revision_reviews VALUES (
            'RR-1', 'R-1', 'approved', 'operator',
            'reviewed', '2026-10-12T12:03:00+00:00', 1
        );
        """
    )

    expected_columns = {
        "ServingCandidates": {
            "CandidateId", "MealPlanId", "FoodSlot", "Source",
            "SourceItemId", "SourceUpc", "BrandName", "ItemName",
            "ServingQuantity", "ServingUnitLabel", "ServingWeightGrams",
            "MetricQuantity", "MetricUnit", "OntologySource",
            "ReviewStatus", "CreatedAt", "UpdatedAt", "SimulationOnly",
        },
        "ServingCandidateReviews": {
            "ReviewId", "CandidateId", "Decision", "Reviewer", "Notes",
            "DecidedAt", "SimulationOnly",
        },
        "ServingCandidateRevisions": {
            "RevisionId", "OriginalCandidateId", "SourceItemId",
            "ServingQuantity", "ServingUnitLabel", "ServingWeightGrams",
            "MetricQuantity", "MetricUnit", "Provenance", "CreatedBy",
            "CreatedAt", "SimulationOnly",
        },
        "ServingRevisionReviews": {
            "ReviewId", "RevisionId", "Decision", "Reviewer", "Notes",
            "DecidedAt", "SimulationOnly",
        },
    }

    for table, columns in expected_columns.items():
        mapping = next(item for item in TABLE_MAPPINGS if item.grist_table == table)
        row = _source_rows(value, mapping)[0]
        assert set(row) == columns
        assert row["SimulationOnly"] is True

    revision = _source_rows(
        value,
        next(
            item
            for item in TABLE_MAPPINGS
            if item.grist_table == "ServingCandidateRevisions"
        ),
    )[0]
    assert revision["ServingWeightGrams"] == 101.0
    assert isinstance(revision["CreatedAt"], float)


def test_product_identity_audit_mappings_match_grist_schemas():
    value = sqlite3.connect(":memory:")
    value.row_factory = sqlite3.Row
    value.executescript(
        """
        CREATE TABLE product_identity_verifications (
            verification_id TEXT, candidate_id TEXT, source_system TEXT,
            local_item_id TEXT, verified_item_id TEXT, local_upc TEXT,
            verified_upc TEXT, brand_matches INTEGER,
            item_name_matches INTEGER, status TEXT, evidence_json TEXT,
            created_at TEXT, simulation_only INTEGER
        );
        CREATE TABLE product_identity_reviews (
            review_id TEXT, verification_id TEXT, decision TEXT,
            reviewer TEXT, notes TEXT, decided_at TEXT,
            simulation_only INTEGER
        );
        CREATE TABLE product_identity_corrections (
            correction_id TEXT, verification_id TEXT,
            corrected_item_id TEXT, provenance TEXT, created_by TEXT,
            created_at TEXT, simulation_only INTEGER
        );
        CREATE TABLE product_identity_correction_reviews (
            review_id TEXT, correction_id TEXT, decision TEXT,
            reviewer TEXT, notes TEXT, decided_at TEXT,
            simulation_only INTEGER
        );

        INSERT INTO product_identity_verifications VALUES (
            'IV-1', 'C-1', 'sheety', 'LOCAL-1', 'VERIFIED-1',
            '123', '123', 1, 1, 'identity_verified', '{}',
            '2026-10-12T12:00:00+00:00', 1
        );
        INSERT INTO product_identity_reviews VALUES (
            'IR-1', 'IV-1', 'approved', 'operator', 'reviewed',
            '2026-10-12T12:01:00+00:00', 1
        );
        INSERT INTO product_identity_corrections VALUES (
            'IC-1', 'IV-1', 'CORRECTED-1', 'sheety_upc_match',
            'operator', '2026-10-12T12:02:00+00:00', 1
        );
        INSERT INTO product_identity_correction_reviews VALUES (
            'ICR-1', 'IC-1', 'approved', 'operator', 'reviewed',
            '2026-10-12T12:03:00+00:00', 1
        );
        """
    )

    expected_columns = {
        "ProductIdentityVerifications": {
            "VerificationId", "CandidateId", "SourceSystem", "LocalItemId",
            "VerifiedItemId", "LocalUpc", "VerifiedUpc", "BrandMatches",
            "ItemNameMatches", "Status", "EvidenceJson", "CreatedAt",
            "SimulationOnly",
        },
        "ProductIdentityReviews": {
            "ReviewId", "VerificationId", "Decision", "Reviewer", "Notes",
            "DecidedAt", "SimulationOnly",
        },
        "ProductIdentityCorrections": {
            "CorrectionId", "VerificationId", "CorrectedItemId",
            "Provenance", "CreatedBy", "CreatedAt", "SimulationOnly",
        },
        "ProductIdentityCorrectionReviews": {
            "ReviewId", "CorrectionId", "Decision", "Reviewer", "Notes",
            "DecidedAt", "SimulationOnly",
        },
    }

    rows = {}
    for table, columns in expected_columns.items():
        mapping = next(item for item in TABLE_MAPPINGS if item.grist_table == table)
        rows[table] = _source_rows(value, mapping)[0]
        assert set(rows[table]) == columns
        assert rows[table]["SimulationOnly"] is True

    verification = rows["ProductIdentityVerifications"]
    assert verification["BrandMatches"] is True
    assert verification["ItemNameMatches"] is True
    assert isinstance(verification["CreatedAt"], float)
    assert isinstance(rows["ProductIdentityReviews"]["DecidedAt"], float)
    assert isinstance(rows["ProductIdentityCorrections"]["CreatedAt"], float)
    assert isinstance(
        rows["ProductIdentityCorrectionReviews"]["DecidedAt"], float
    )
