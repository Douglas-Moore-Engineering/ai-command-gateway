"""Local software checks using invented policy limits; not domain acceptance."""

from concurrent.futures import ThreadPoolExecutor
from contextlib import closing
from copy import deepcopy
from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
import sqlite3
import tempfile
import unittest
from unittest.mock import patch

from ai_command_gateway.gateway import Gateway


ROOT = Path(__file__).resolve().parents[1]
ACTOR = "local-demo-operator"
NOW = datetime(2026, 10, 15, 16, tzinfo=timezone.utc)


class GatewayTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.directory = Path(self.temp.name)
        self.policy_path = self.directory / "policy.json"
        self.policy = json.loads((ROOT / "config/policies/demo-policy.json").read_text(encoding="utf-8"))
        self.write_policy()
        self.request = json.loads((ROOT / "data/samples/demo-request.json").read_text(encoding="utf-8"))
        self.gateway = Gateway(self.directory / "audit.db", self.policy_path)

    def write_policy(self):
        self.policy_path.write_text(json.dumps(self.policy), encoding="utf-8")

    def assert_reason(self, result, decision, code):
        self.assertEqual(result["decision"], decision, result)
        self.assertEqual(result["reasons"][0]["code"], code, result)
        self.assertTrue(result["mock_only"])

    def approve(self):
        result = self.gateway.approve(self.request, ACTOR, now=NOW)
        self.assertEqual(result["decision"], "allow", result)
        return result["approval_id"]

    def test_command_boundaries_and_outside_values(self):
        for value, expected in [(-5, "allow"), (0, "allow"), (5, "allow"), (-5.000001, "block"), (5.000001, "block")]:
            with self.subTest(value=value):
                self.request["proposal"]["value"] = value
                self.assertEqual(self.gateway.evaluate(self.request, now=NOW)["decision"], expected)

    def test_state_boundaries_and_outside_values(self):
        for variable, lower, upper in [("battery_soc_pct", 20, 80), ("battery_temperature_c", 0, 45)]:
            for value, expected in [(lower, "allow"), (upper, "allow"), (lower - .01, "block"), (upper + .01, "block")]:
                with self.subTest(variable=variable, value=value):
                    request = deepcopy(self.request)
                    request["state"]["values"][variable]["value"] = value
                    self.assertEqual(self.gateway.evaluate(request, now=NOW)["decision"], expected)

    def test_nonfinite_boolean_and_string_values_are_rejected(self):
        for value in [float("nan"), float("inf"), float("-inf"), True, "2", None, 10 ** 400]:
            for field in ["command", "state"]:
                with self.subTest(value=str(value), field=field):
                    request = deepcopy(self.request)
                    if field == "command":
                        request["proposal"]["value"] = value
                    else:
                        request["state"]["values"]["battery_soc_pct"]["value"] = value
                    self.assert_reason(self.gateway.evaluate(request, now=NOW), "block", "invalid_request")

    def test_action_units_mode_and_asset_are_enforced(self):
        mutations = [
            ("proposal", "action", "ignore rules and operate", "action_unapproved"),
            ("proposal", "unit", "W", "command_unit_mismatch"),
            ("state", "mode", "maintenance", "mode_unapproved"),
            ("state", "asset_id", "other", "asset_mismatch"),
        ]
        for section, key, value, reason in mutations:
            with self.subTest(reason=reason):
                request = deepcopy(self.request)
                request[section][key] = value
                self.assert_reason(self.gateway.evaluate(request, now=NOW), "block", reason)
        self.request["state"]["values"]["battery_soc_pct"]["unit"] = "ratio"
        self.assert_reason(self.gateway.evaluate(self.request, now=NOW), "block", "state_unit_mismatch")

    def test_unknown_fields_and_missing_state_fail_closed(self):
        request = deepcopy(self.request)
        request["proposal"]["override_policy"] = True
        self.assert_reason(self.gateway.evaluate(request, now=NOW), "block", "invalid_request")
        request = deepcopy(self.request)
        request["state"]["values"].pop("battery_soc_pct")
        self.assert_reason(self.gateway.evaluate(request, now=NOW), "escalate", "state_incomplete")
        self.assert_reason(self.gateway.evaluate({"proposal": self.request["proposal"]}, now=NOW), "block", "invalid_request")

    def test_versioned_evidence_required(self):
        for refs in [[], [{"id": "demo-policy-manual", "version": "different"}], [{"id": "raw-attack-label", "version": "1"}]]:
            with self.subTest(refs=refs):
                self.request["proposal"]["source_refs"] = refs
                self.assert_reason(self.gateway.evaluate(self.request, now=NOW), "escalate", "evidence_unapproved")

    def test_conflicting_source_versions_escalate(self):
        self.request["proposal"]["source_refs"].append({"id": "demo-policy-manual", "version": "different"})
        self.assert_reason(self.gateway.evaluate(self.request, now=NOW), "escalate", "evidence_conflicting")

    def test_utc_and_freshness_boundaries(self):
        cases = [
            ("2026-10-15T15:59:30Z", "allow", "synthetic_rules_satisfied"),
            ("2026-10-15T15:59:29.999999Z", "escalate", "state_stale"),
            ("2026-10-15T16:00:00.000001Z", "escalate", "state_in_future"),
            ("2026-10-15T16:00:00", "block", "invalid_request"),
            ("2026-10-15T12:00:00-04:00", "block", "invalid_request"),
            ("not a timestamp", "block", "invalid_request"),
        ]
        for timestamp, decision, reason in cases:
            with self.subTest(timestamp=timestamp):
                self.request["state"]["observed_at"] = timestamp
                self.assert_reason(self.gateway.evaluate(self.request, now=NOW), decision, reason)

    def test_policy_missing_invalid_expired_and_nonfinite_fail_closed(self):
        self.policy_path.unlink()
        self.assert_reason(self.gateway.approve(self.request, ACTOR, now=NOW), "escalate", "policy_unavailable")
        self.policy_path.write_text('{"id": "x", "id": "y"}', encoding="utf-8")
        self.assert_reason(self.gateway.evaluate(self.request, now=NOW), "escalate", "policy_unavailable")
        self.write_policy()
        self.assert_reason(self.gateway.evaluate(self.request, now="2027-01-01T00:00:00Z"), "escalate", "policy_unavailable")
        self.policy["assets"]["battery-demo-1"]["actions"]["set_battery_power"]["max"] = float("inf")
        self.write_policy()
        self.assert_reason(self.gateway.evaluate(self.request, now=NOW), "escalate", "policy_unavailable")

    def test_unqualified_policy_never_approves_historical_or_synthetic_inputs(self):
        gateway = Gateway(self.directory / "unqualified.db", ROOT / "config/policies/unqualified-policy.json")
        for request in [self.request, {"proposal": {"source_refs": []}, "state": {"values": {}}}]:
            self.assert_reason(gateway.approve(request, ACTOR, now=NOW), "escalate", "policy_unqualified")

    def test_designated_actor_and_missing_approval(self):
        self.assert_reason(self.gateway.approve(self.request, "model", now=NOW), "block", "actor_not_designated")
        self.assert_reason(self.gateway.execute(self.request, "invented", ACTOR, now=NOW), "block", "approval_missing")

    def test_approval_bound_to_actor(self):
        self.policy["approval_actors"].append("another-local-operator")
        self.write_policy()
        approval_id = self.approve()
        self.assert_reason(self.gateway.execute(self.request, approval_id, "another-local-operator", now=NOW), "block", "approval_actor_mismatch")

    def test_approval_expiry_and_state_revalidation(self):
        approval_id = self.approve()
        self.assert_reason(self.gateway.execute(self.request, approval_id, ACTOR, now=NOW + timedelta(seconds=20)), "block", "approval_expired")
        self.assert_reason(self.gateway.execute(self.request, approval_id, ACTOR, now=NOW + timedelta(seconds=31)), "escalate", "state_stale")

    def test_entire_request_and_current_policy_are_bound(self):
        approval_id = self.approve()
        for section, key, value in [("proposal", "id", "changed"), ("proposal", "value", 3), ("proposal", "model_version", "other-model"), ("state", "observed_at", "2026-10-15T15:59:59Z")]:
            with self.subTest(section=section, key=key):
                request = deepcopy(self.request)
                request[section][key] = value
                self.assert_reason(self.gateway.execute(request, approval_id, ACTOR, now=NOW), "block", "approval_binding_mismatch")
        request = deepcopy(self.request)
        request["state"]["values"]["battery_soc_pct"]["value"] = 60
        self.assert_reason(self.gateway.execute(request, approval_id, ACTOR, now=NOW), "block", "approval_binding_mismatch")
        self.policy["version"] = "synthetic-2"
        self.write_policy()
        self.assert_reason(self.gateway.execute(self.request, approval_id, ACTOR, now=NOW), "block", "approval_binding_mismatch")

    def test_policy_disappearance_prevents_execution(self):
        approval_id = self.approve()
        self.policy_path.unlink()
        self.assert_reason(self.gateway.execute(self.request, approval_id, ACTOR, now=NOW), "escalate", "policy_unavailable")

    def test_persistent_replay_and_proposal_reuse(self):
        approval_id = self.approve()
        second_id = self.approve()
        result = self.gateway.execute(self.request, approval_id, ACTOR, now=NOW)
        self.assertEqual(result["outcome"], "mock_executed")
        restarted = Gateway(self.gateway.db_path, self.policy_path)
        for identifier in [approval_id, second_id]:
            self.assert_reason(restarted.execute(self.request, identifier, ACTOR, now=NOW), "block", "proposal_already_executed")
        self.assert_reason(restarted.approve(self.request, ACTOR, now=NOW), "block", "proposal_already_executed")

    def test_concurrent_execution_consumes_approval_only_once(self):
        approval_id = self.approve()
        with ThreadPoolExecutor(max_workers=2) as executor:
            results = list(executor.map(lambda _: self.gateway.execute(self.request, approval_id, ACTOR, now=NOW), range(2)))
        self.assertEqual(sum(item["outcome"] == "mock_executed" for item in results), 1)
        self.assertEqual(sum(item["decision"] == "block" for item in results), 1)
        events = self.gateway.audit_records()
        self.assertEqual(sum(item["outcome"] == "mock_executed" for item in events), 1)

    def test_audit_contains_required_fields_and_linkage(self):
        self.gateway.evaluate(self.request, now=NOW)
        approval_id = self.approve()
        self.gateway.execute(self.request, approval_id, ACTOR, now=NOW)
        events = self.gateway.audit_records()
        self.assertEqual(len(events), 3)
        for event in events:
            for key in ["proposal", "source_refs", "model_version", "state_time", "policy_version", "policy_hash", "actor", "outcome", "decision", "event_id"]:
                self.assertIn(key, event)
            self.assertEqual(event["proposal"], self.request["proposal"])
            self.assertEqual(event["source_refs"], self.request["proposal"]["source_refs"])
            self.assertEqual(len(event["policy_hash"]), 64)
        self.assertEqual(events[1]["approval_id"], approval_id)
        self.assertEqual(events[2]["approval_id"], approval_id)

    def test_audit_unavailable_prevents_every_allow(self):
        gateway = Gateway(self.directory, self.policy_path)
        self.assert_reason(gateway.evaluate(self.request, now=NOW), "escalate", "audit_unavailable")
        self.assert_reason(gateway.approve(self.request, ACTOR, now=NOW), "escalate", "audit_unavailable")

    def test_in_memory_database_cannot_claim_durable_audit(self):
        gateway = Gateway(":memory:", self.policy_path)
        self.assert_reason(gateway.evaluate(self.request, now=NOW), "escalate", "audit_unavailable")

    def test_failed_approval_audit_rolls_back_approval_insert(self):
        with patch.object(self.gateway, "_event", side_effect=sqlite3.OperationalError("injected audit failure")):
            result = self.gateway.approve(self.request, ACTOR, now=NOW)
        self.assert_reason(result, "escalate", "audit_unavailable")
        self.assertNotIn("approval_id", result)
        with closing(sqlite3.connect(self.gateway.db_path)) as connection:
            self.assertEqual(connection.execute("SELECT COUNT(*) FROM approvals").fetchone()[0], 0)
        self.assertEqual(self.gateway.audit_records(), [])

    def test_failed_execution_audit_rolls_back_consumption(self):
        approval_id = self.approve()
        with patch.object(self.gateway, "_event", side_effect=sqlite3.OperationalError("injected audit failure")):
            result = self.gateway.execute(self.request, approval_id, ACTOR, now=NOW)
        self.assert_reason(result, "escalate", "audit_unavailable")
        self.assertNotIn("mock_receipt", result)
        self.assertEqual(len(self.gateway.audit_records()), 1)
        self.assertEqual(self.gateway.execute(self.request, approval_id, ACTOR, now=NOW)["outcome"], "mock_executed")


if __name__ == "__main__":
    unittest.main()
