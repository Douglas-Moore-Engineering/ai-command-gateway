"""Deterministic, local-only command validation and durable mock execution.

This module has no provider, network, PLC, or equipment interface. Actor names
are local demonstration labels, not authenticated identities. Protect the policy
and SQLite files with OS permissions; this library is not a security sandbox.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
import hashlib
import json
import math
from pathlib import Path
import sqlite3
from typing import Any
import uuid


class ValidationError(ValueError):
    pass


def _canonical(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)


def _hash(value: Any) -> str:
    return hashlib.sha256(_canonical(value).encode("utf-8")).hexdigest()


def _timestamp(value: Any) -> datetime:
    if not isinstance(value, str) or not value:
        raise ValidationError("Timestamp must be an ISO-8601 UTC string.")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValidationError("Timestamp must be an ISO-8601 UTC string.") from exc
    if parsed.tzinfo is None or parsed.utcoffset() != timedelta(0):
        raise ValidationError("Timestamp must explicitly use UTC (Z or +00:00).")
    return parsed


def _time(now: datetime | str | None) -> datetime:
    if now is None:
        return datetime.now(timezone.utc)
    if isinstance(now, str):
        return _timestamp(now)
    if not isinstance(now, datetime) or now.tzinfo is None or now.utcoffset() != timedelta(0):
        raise ValueError("now must be an aware UTC datetime or an ISO-8601 UTC string")
    return now


def _iso(value: datetime) -> str:
    return value.isoformat().replace("+00:00", "Z")


def _keys(value: Any, keys: set[str], label: str) -> None:
    if type(value) is not dict or set(value) != keys:
        raise ValidationError(f"{label} must contain exactly: {', '.join(sorted(keys))}.")


def _string(value: Any, label: str) -> None:
    if not isinstance(value, str) or not value.strip() or len(value) > 1024:
        raise ValidationError(f"{label} must be a nonempty string of at most 1024 characters.")


def _number(value: Any, label: str) -> None:
    if type(value) not in (int, float):
        raise ValidationError(f"{label} must be a finite number, not a boolean or string.")
    try:
        finite = math.isfinite(value)
    except OverflowError:
        finite = False
    if not finite:
        raise ValidationError(f"{label} must be a finite number.")


def _refs(value: Any, label: str) -> None:
    if type(value) is not list:
        raise ValidationError(f"{label} must be a list of versioned source references.")
    seen = set()
    for ref in value:
        _keys(ref, {"id", "version"}, label)
        _string(ref["id"], f"{label}.id")
        _string(ref["version"], f"{label}.version")
        key = (ref["id"], ref["version"])
        if key in seen:
            raise ValidationError(f"{label} cannot contain duplicates.")
        seen.add(key)


def _reject_duplicate_keys(pairs: list[tuple[str, Any]]) -> dict:
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValidationError(f"Duplicate JSON key: {key}.")
        result[key] = value
    return result


def _snapshot(value: Any) -> Any:
    """Preserve invalid JSON-like input in audit records without emitting NaN."""
    if type(value) is dict:
        return {str(key): _snapshot(item) for key, item in value.items()}
    if type(value) in (list, tuple):
        return [_snapshot(item) for item in value]
    if type(value) is float and not math.isfinite(value):
        return {"invalid_number": str(value)}
    if value is None or type(value) in (str, int, float, bool):
        return value
    return {"invalid_type": type(value).__name__}


class Gateway:
    """Validate requests, issue local mock approvals, and consume them once.

    Policy is reloaded on every call. Approvals bind the complete request,
    including its state snapshot, to the policy content hash and actor. A new
    state observation requires a new approval. ``now`` is for deterministic
    tests/replay; applications must use the real clock for current decisions.
    """

    def __init__(self, db_path: str | Path, policy_path: str | Path):
        self.db_path = Path(db_path)
        self.policy_path = Path(policy_path)

    def _connect(self) -> sqlite3.Connection:
        if str(self.db_path) == ":memory:":
            raise ValueError("A persistent file-backed audit database is required.")
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        connection = sqlite3.connect(self.db_path, timeout=5, isolation_level=None)
        try:
            connection.row_factory = sqlite3.Row
            connection.execute("PRAGMA synchronous=FULL")
            connection.execute("PRAGMA journal_mode=WAL")
            connection.execute("CREATE TABLE IF NOT EXISTS audit (id TEXT PRIMARY KEY, event_json TEXT NOT NULL)")
            connection.execute("""CREATE TABLE IF NOT EXISTS approvals (
                id TEXT PRIMARY KEY, proposal_id TEXT NOT NULL,
                binding TEXT NOT NULL, actor TEXT NOT NULL,
                expires_at TEXT NOT NULL, consumed_at TEXT)
            """)
            connection.execute("CREATE INDEX IF NOT EXISTS approvals_proposal ON approvals(proposal_id)")
            return connection
        except Exception:
            connection.close()
            raise

    def _policy(self, now: datetime) -> tuple[dict, str]:
        policy = json.loads(self.policy_path.read_text(encoding="utf-8"), object_pairs_hook=_reject_duplicate_keys)
        _keys(policy, {"schema_version", "id", "version", "status", "basis", "valid_from", "valid_until",
                       "max_state_age_seconds", "max_future_skew_seconds", "approval_ttl_seconds",
                       "approval_actors", "source_refs", "assets"}, "policy")
        for key in ("id", "version", "basis"):
            _string(policy[key], f"policy.{key}")
        if policy["schema_version"] != "1" or policy["status"] not in ("synthetic-demo", "unqualified"):
            raise ValidationError("Unsupported policy schema or qualification status.")
        start, end = _timestamp(policy["valid_from"]), _timestamp(policy["valid_until"])
        if end <= start or not start <= now < end:
            raise ValidationError("Policy is expired, not yet valid, or has an invalid validity interval.")
        for key in ("max_state_age_seconds", "max_future_skew_seconds", "approval_ttl_seconds"):
            _number(policy[key], f"policy.{key}")
            if policy[key] < 0 or policy[key] > 86400 or (key != "max_future_skew_seconds" and policy[key] == 0):
                raise ValidationError(f"policy.{key} is outside the local demonstration range.")
        if type(policy["approval_actors"]) is not list:
            raise ValidationError("policy.approval_actors must be a list.")
        for actor in policy["approval_actors"]:
            _string(actor, "policy.approval_actors")
        if len(set(policy["approval_actors"])) != len(policy["approval_actors"]):
            raise ValidationError("Duplicate approval actors.")
        _refs(policy["source_refs"], "policy.source_refs")
        if len({ref["id"] for ref in policy["source_refs"]}) != len(policy["source_refs"]):
            raise ValidationError("Policy cannot approve conflicting versions of one source.")
        if type(policy["assets"]) is not dict:
            raise ValidationError("policy.assets must be an object.")
        if policy["status"] == "synthetic-demo" and not all((policy["assets"], policy["source_refs"], policy["approval_actors"])):
            raise ValidationError("Synthetic demonstration policy requires assets, references, and actors.")
        for asset_id, asset in policy["assets"].items():
            _string(asset_id, "policy asset id")
            _keys(asset, {"actions", "state_limits"}, "policy asset")
            if type(asset["actions"]) is not dict or not asset["actions"]:
                raise ValidationError("Asset must have an explicit action whitelist.")
            if type(asset["state_limits"]) is not dict or not asset["state_limits"]:
                raise ValidationError("Asset must have explicit state limits.")
            for name, rule in asset["actions"].items():
                _string(name, "action name")
                _keys(rule, {"unit", "min", "max", "modes"}, "action rule")
                self._limit(rule)
                if type(rule["modes"]) is not list or not rule["modes"]:
                    raise ValidationError("Action must list allowed equipment modes.")
                for mode in rule["modes"]:
                    _string(mode, "equipment mode")
            for name, rule in asset["state_limits"].items():
                _string(name, "state variable")
                _keys(rule, {"unit", "min", "max"}, "state rule")
                self._limit(rule)
        return policy, _hash(policy)

    @staticmethod
    def _limit(rule: dict) -> None:
        _string(rule["unit"], "unit")
        _number(rule["min"], "minimum")
        _number(rule["max"], "maximum")
        if rule["min"] > rule["max"]:
            raise ValidationError("Minimum must not exceed maximum.")

    @staticmethod
    def _result(decision: str, code: str, message: str) -> dict:
        return {"decision": decision, "reasons": [{"code": code, "message": message}],
                "mock_only": True, "authority": "local-demo-actor-label; OS file permissions required"}

    def _assess(self, request: Any, now: datetime) -> tuple[dict, dict | None, str | None]:
        policy, policy_hash = None, None
        try:
            policy, policy_hash = self._policy(now)
        except (OSError, ValueError, TypeError, OverflowError) as exc:
            return self._result("escalate", "policy_unavailable", f"Policy cannot authorize a decision: {exc}"), None, None
        if policy["status"] != "synthetic-demo":
            return self._result("escalate", "policy_unqualified", "Authoritative engineering limits and source qualification are pending; request was not validated."), policy, policy_hash
        try:
            _keys(request, {"proposal", "state"}, "request")
            proposal, state = request["proposal"], request["state"]
            _keys(proposal, {"id", "asset_id", "action", "value", "unit", "model_version", "source_refs"}, "proposal")
            _keys(state, {"asset_id", "observed_at", "mode", "values"}, "state")
            for key in ("id", "asset_id", "action", "unit", "model_version"):
                _string(proposal[key], f"proposal.{key}")
            _number(proposal["value"], "proposal.value")
            _refs(proposal["source_refs"], "proposal.source_refs")
            _string(state["asset_id"], "state.asset_id")
            _string(state["mode"], "state.mode")
            observed_at = _timestamp(state["observed_at"])
            if type(state["values"]) is not dict or not state["values"]:
                raise ValidationError("state.values must contain measured values with explicit units.")
            for key, item in state["values"].items():
                _string(key, "state variable")
                _keys(item, {"value", "unit"}, "state value")
                _number(item["value"], "state value")
                _string(item["unit"], "state unit")
            # A canonical JSON round trip also rejects unsupported object types.
            _canonical(request)
        except (ValueError, TypeError, OverflowError) as exc:
            return self._result("block", "invalid_request", str(exc)), policy, policy_hash
        if proposal["asset_id"] != state["asset_id"]:
            return self._result("block", "asset_mismatch", "Proposal and observed state refer to different assets."), policy, policy_hash
        asset = policy["assets"].get(proposal["asset_id"])
        if asset is None:
            return self._result("block", "asset_unapproved", "Asset is not in the demonstration policy."), policy, policy_hash
        action = asset["actions"].get(proposal["action"])
        if action is None:
            return self._result("block", "action_unapproved", "Action is not in the explicit whitelist."), policy, policy_hash
        if proposal["unit"] != action["unit"]:
            return self._result("block", "command_unit_mismatch", "Command unit does not match the policy; no implicit conversion is performed."), policy, policy_hash
        if state["mode"] not in action["modes"]:
            return self._result("block", "mode_unapproved", "Equipment mode does not permit this demonstration action."), policy, policy_hash
        if not action["min"] <= proposal["value"] <= action["max"]:
            return self._result("block", "command_out_of_range", "Command violates a synthetic demonstration limit."), policy, policy_hash
        age = (now - observed_at).total_seconds()
        if age < -policy["max_future_skew_seconds"]:
            return self._result("escalate", "state_in_future", "State observation is ahead of the permitted clock skew."), policy, policy_hash
        if age > policy["max_state_age_seconds"]:
            return self._result("escalate", "state_stale", "State observation exceeds the policy's demonstration freshness limit."), policy, policy_hash
        if set(state["values"]) != set(asset["state_limits"]):
            return self._result("escalate", "state_incomplete", "State variables must match all required policy variables exactly."), policy, policy_hash
        for name, rule in asset["state_limits"].items():
            measured = state["values"][name]
            if measured["unit"] != rule["unit"]:
                return self._result("block", "state_unit_mismatch", f"State unit mismatch for {name}."), policy, policy_hash
            if not rule["min"] <= measured["value"] <= rule["max"]:
                return self._result("block", "state_out_of_range", f"{name} violates a synthetic demonstration limit."), policy, policy_hash
        approved_refs = {(ref["id"], ref["version"]) for ref in policy["source_refs"]}
        actual_refs = {(ref["id"], ref["version"]) for ref in proposal["source_refs"]}
        if len({ref[0] for ref in actual_refs}) != len(actual_refs):
            return self._result("escalate", "evidence_conflicting", "Proposal references conflicting versions of the same source."), policy, policy_hash
        if not actual_refs or not actual_refs <= approved_refs:
            return self._result("escalate", "evidence_unapproved", "Proposal needs version-matched policy-approved evidence references."), policy, policy_hash
        return self._result("allow", "synthetic_rules_satisfied", "Synthetic demonstration checks passed; physical operation is not authorized."), policy, policy_hash

    @staticmethod
    def _binding(request: dict, policy_hash: str) -> str:
        return _hash({"request": request, "policy_hash": policy_hash})

    def _event(self, connection: sqlite3.Connection, operation: str, request: Any, now: datetime,
               actor: str | None, result: dict, policy: dict | None, policy_hash: str | None,
               approval_id: str | None = None) -> str:
        snapshot = _snapshot(request)
        proposal = snapshot.get("proposal") if isinstance(snapshot, dict) else None
        state = snapshot.get("state") if isinstance(snapshot, dict) else None
        event_id = str(uuid.uuid4())
        event = {"event_id": event_id, "timestamp": _iso(now), "operation": operation,
                 "request": snapshot, "proposal": proposal,
                 "source_refs": proposal.get("source_refs") if isinstance(proposal, dict) else None,
                 "model_version": proposal.get("model_version") if isinstance(proposal, dict) else None,
                 "state_time": state.get("observed_at") if isinstance(state, dict) else None,
                 "policy_id": policy.get("id") if policy else None,
                 "policy_version": policy.get("version") if policy else None,
                 "policy_hash": policy_hash, "actor": actor, "approval_id": approval_id,
                 **result}
        connection.execute("INSERT INTO audit (id, event_json) VALUES (?, ?)", (event_id, _canonical(event)))
        return event_id

    def _perform(self, operation: str, request: Any, actor: str | None = None,
                 approval_id: str | None = None, now: datetime | str | None = None) -> dict:
        # Snapshot valid JSON input to prevent caller mutation during evaluation.
        request = _snapshot(request)
        connection = None
        issued_id = None
        try:
            connection = self._connect()
            connection.execute("BEGIN IMMEDIATE")
            # Acquire the write transaction before reading policy and time so
            # waiting for another executor cannot silently age the state check.
            instant = _time(now)
            result, policy, policy_hash = self._assess(request, instant)
            if operation != "evaluate" and result["decision"] == "allow":
                if type(actor) is not str or actor not in policy["approval_actors"]:
                    result = self._result("block", "actor_not_designated", "Actor label is not designated by the local demonstration policy.")
                elif connection.execute("SELECT id FROM approvals WHERE proposal_id = ? AND consumed_at IS NOT NULL", (request["proposal"]["id"],)).fetchone():
                    result = self._result("block", "proposal_already_executed", "This proposal id already completed mock execution.")
                elif operation == "approve":
                    issued_id = str(uuid.uuid4())
                    expires = min(instant + timedelta(seconds=policy["approval_ttl_seconds"]), _timestamp(policy["valid_until"]))
                    connection.execute("INSERT INTO approvals (id, proposal_id, binding, actor, expires_at) VALUES (?, ?, ?, ?, ?)",
                                       (issued_id, request["proposal"]["id"], self._binding(request, policy_hash), actor, _iso(expires)))
                    result.update(approval_id=issued_id, expires_at=_iso(expires))
                elif operation == "execute":
                    row = connection.execute("SELECT * FROM approvals WHERE id = ?", (approval_id if type(approval_id) is str else "",)).fetchone()
                    if row is None:
                        result = self._result("block", "approval_missing", "A matching durable local approval is required.")
                    elif row["consumed_at"] is not None:
                        result = self._result("block", "approval_consumed", "Approval was already consumed.")
                    elif row["actor"] != actor:
                        result = self._result("block", "approval_actor_mismatch", "Approval is bound to another local actor label.")
                    elif instant >= _timestamp(row["expires_at"]):
                        result = self._result("block", "approval_expired", "Approval has expired.")
                    elif row["binding"] != self._binding(request, policy_hash):
                        result = self._result("block", "approval_binding_mismatch", "Proposal, state, or policy changed after approval; obtain a new approval.")
                    else:
                        connection.execute("UPDATE approvals SET consumed_at = ? WHERE id = ? AND consumed_at IS NULL", (_iso(instant), approval_id))
                        result["mock_receipt"] = {"approval_id": approval_id, "proposal_id": request["proposal"]["id"],
                                                  "asset_id": request["proposal"]["asset_id"], "action": request["proposal"]["action"],
                                                  "value": request["proposal"]["value"], "unit": request["proposal"]["unit"]}
            outcome = {"evaluate": "evaluated", "approve": "approved", "execute": "mock_executed"}[operation]
            result["outcome"] = outcome if result["decision"] == "allow" else "refused"
            event_id = self._event(connection, operation, request, instant, actor, result, policy, policy_hash, issued_id or approval_id)
            connection.commit()
            return {**result, "event_id": event_id, "policy_hash": policy_hash,
                    "policy_version": policy.get("version") if policy else None}
        except (sqlite3.Error, OSError, ValueError, TypeError, OverflowError) as exc:
            if connection is not None:
                connection.rollback()
            refused = self._result("escalate", "audit_unavailable", f"Durable audit/approval transaction failed: {exc}")
            return {**refused, "outcome": "refused", "event_id": None}
        finally:
            if connection is not None:
                connection.close()

    def evaluate(self, request: dict, now: datetime | str | None = None) -> dict:
        return self._perform("evaluate", request, now=now)

    def approve(self, request: dict, actor: str, now: datetime | str | None = None) -> dict:
        return self._perform("approve", request, actor=actor, now=now)

    def execute(self, request: dict, approval_id: str, actor: str, now: datetime | str | None = None) -> dict:
        return self._perform("execute", request, actor=actor, approval_id=approval_id, now=now)

    def audit_records(self) -> list[dict]:
        """Read durable events in insertion order; surface storage errors to callers."""
        connection = self._connect()
        try:
            return [json.loads(row[0]) for row in connection.execute("SELECT event_json FROM audit ORDER BY rowid")]
        finally:
            connection.close()
