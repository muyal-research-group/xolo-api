"""Unit tests for the gap-filling additions to XoloClient.

All tests mock `requests.request` so no live server is required.
"""
import json
from unittest.mock import patch

import pytest
import requests

from xolo.client import errors as E
from xolo.client import models as M
from xolo.client.client import XoloClient


# ── Helpers ───────────────────────────────────────────────────────────────────

def _response(payload=None, status_code: int = 200) -> requests.Response:
    response = requests.Response()
    response.status_code = status_code
    response.url = "http://localhost/test"
    response.headers = {}
    if payload is None:
        response._content = b""
    else:
        response._content = json.dumps(payload).encode()
        response.headers["Content-Type"] = "application/json"
    return response


def _client(api_key: str = "api-key", admin_token: str = "admin-token") -> XoloClient:
    return XoloClient(
        account_id="acct-1",
        api_key=api_key,
        api_url="http://localhost:10000/api/v4",
        admin_token=admin_token,
    )


BASE = "http://localhost:10000/api/v4/accounts/acct-1"


# ── ABAC model changes ────────────────────────────────────────────────────────

class TestABACModelChanges:
    def test_geo_point_dto_accepts_lat_lng(self):
        pt = M.GeoPointDTO(lat=19.43, lng=-99.13)
        assert pt.lat == 19.43
        assert pt.lng == -99.13

    def test_geo_zone_dto_accepts_lat_lng_radius(self):
        zone = M.GeoZoneDTO(lat=19.43, lng=-99.13, radius_km=2.5)
        assert zone.radius_km == 2.5

    def test_geo_zone_dto_rejects_radius_above_max(self):
        with pytest.raises(Exception):
            M.GeoZoneDTO(lat=0.0, lng=0.0, radius_km=10.0)

    def test_geo_zone_dto_rejects_zero_radius(self):
        with pytest.raises(Exception):
            M.GeoZoneDTO(lat=0.0, lng=0.0, radius_km=0.0)

    def test_time_window_mode_values(self):
        assert M.TimeWindowMode.WILDCARD == "wildcard"
        assert M.TimeWindowMode.DATETIME == "datetime"
        assert M.TimeWindowMode.TIME_OF_DAY == "time_of_day"
        assert M.TimeWindowMode.DATE == "date"

    def test_create_abac_event_dto_location_defaults_to_none(self):
        event = M.CreateABACEventDTO(subject="Doctor", resource="Chart", action="read")
        assert event.location is None

    def test_create_abac_event_dto_time_mode_defaults_to_wildcard(self):
        event = M.CreateABACEventDTO(subject="Doctor", resource="Chart", action="read")
        assert event.time_mode == M.TimeWindowMode.WILDCARD

    def test_create_abac_event_dto_accepts_geo_zone(self):
        zone = M.GeoZoneDTO(lat=19.43, lng=-99.13, radius_km=1.0)
        event = M.CreateABACEventDTO(subject="Doctor", resource="Chart", action="read", location=zone)
        assert event.location == zone

    def test_abac_evaluate_dto_location_defaults_to_none(self):
        dto = M.ABACEvaluateDTO(subject="Doctor", resource="Chart", action="read")
        assert dto.location is None

    def test_abac_evaluate_dto_accepts_geo_point(self):
        pt = M.GeoPointDTO(lat=19.43, lng=-99.13)
        dto = M.ABACEvaluateDTO(subject="Doctor", resource="Chart", action="read", location=pt)
        assert dto.location == pt

    def test_abac_event_record_dto_location_defaults_to_none(self):
        record = M.ABACEventRecordDTO(
            event_id="e-1",
            subject="Doctor",
            resource="Chart",
            action="read",
        )
        assert record.location is None

    def test_abac_event_record_dto_accepts_time_dict(self):
        record = M.ABACEventRecordDTO(
            event_id="e-1",
            subject="Doctor",
            resource="Chart",
            action="read",
            time={"mode": "wildcard", "start": None, "end": None},
        )
        assert record.time["mode"] == "wildcard"


# ── evaluate_abac ─────────────────────────────────────────────────────────────

class TestEvaluateAbac:
    def test_sends_none_location_as_null(self):
        client = _client()
        decision_payload = {"allowed": True, "matched_policy": "p-1", "matched_event": "e-1", "reason": "matched"}

        with patch("xolo.client.client.R.request", return_value=_response(decision_payload)) as req:
            result = client.evaluate_abac(
                subject="Doctor",
                resource="Chart",
                action="read",
                token="bearer-1",
                temporal_secret="temp-1",
            )

        assert result.is_ok
        body = req.call_args.kwargs["json"]
        assert "location" not in body or body["location"] is None

    def test_sends_geo_point_when_provided(self):
        client = _client()
        decision_payload = {"allowed": True, "matched_policy": None, "matched_event": None, "reason": "no match"}

        with patch("xolo.client.client.R.request", return_value=_response(decision_payload)) as req:
            result = client.evaluate_abac(
                subject="Doctor",
                resource="Chart",
                action="read",
                token="bearer-1",
                temporal_secret="temp-1",
                location=M.GeoPointDTO(lat=19.43, lng=-99.13),
            )

        assert result.is_ok
        body = req.call_args.kwargs["json"]
        assert body["location"] == {"lat": 19.43, "lng": -99.13}

    def test_uses_correct_url_and_auth_headers(self):
        client = _client()
        decision_payload = {"allowed": False, "matched_policy": None, "matched_event": None, "reason": "denied"}

        with patch("xolo.client.client.R.request", return_value=_response(decision_payload)) as req:
            client.evaluate_abac(
                subject="s", resource="r", action="a",
                token="bearer-1", temporal_secret="temp-1",
            )

        kwargs = req.call_args.kwargs
        assert kwargs["url"] == f"{BASE}/abac/evaluate"
        assert kwargs["method"] == "POST"
        assert "Authorization" in kwargs["headers"]


# ── rotate_license ────────────────────────────────────────────────────────────

class TestRotateLicense:
    def test_calls_correct_endpoint(self):
        client = _client()
        payload = {"ok": True, "expires_at": "2026-06-01T00:00:00"}

        with patch("xolo.client.client.R.request", return_value=_response(payload)) as req:
            result = client.rotate_license(username="alice", scope="READ", expires_in="7d")

        assert result.is_ok
        kwargs = req.call_args.kwargs
        assert kwargs["method"] == "POST"
        assert kwargs["url"] == f"{BASE}/licenses/rotate"

    def test_sends_correct_body(self):
        client = _client()
        payload = {"ok": True, "expires_at": "2026-06-01T00:00:00"}

        with patch("xolo.client.client.R.request", return_value=_response(payload)) as req:
            client.rotate_license(username="alice", scope="READ", expires_in="7d")

        body = req.call_args.kwargs["json"]
        assert body["username"] == "alice"
        assert body["scope"] == "READ"
        assert body["expires_in"] == "7d"

    def test_uses_admin_token_header(self):
        client = _client(admin_token="admin-secret")
        payload = {"ok": True, "expires_at": "2026-06-01T00:00:00"}

        with patch("xolo.client.client.R.request", return_value=_response(payload)) as req:
            client.rotate_license(username="alice", scope="READ", expires_in="7d")

        assert req.call_args.kwargs["headers"] == {"X-Admin-Token": "admin-secret"}

    def test_returns_assign_license_response_dto(self):
        client = _client()
        payload = {"ok": True, "expires_at": "2026-06-01T00:00:00"}

        with patch("xolo.client.client.R.request", return_value=_response(payload)):
            result = client.rotate_license(username="alice", scope="READ", expires_in="7d")

        assert result.is_ok
        dto = result.unwrap()
        assert isinstance(dto, M.AssignLicenseResponseDTO)
        assert dto.ok is True
        assert dto.expires_at == "2026-06-01T00:00:00"

    def test_requires_admin_token(self):
        client = XoloClient(account_id="acct-1", api_key="api-key", api_url="http://localhost:10000/api/v4")

        with patch("xolo.client.client.R.request") as req:
            result = client.rotate_license(username="alice", scope="READ", expires_in="7d")

        assert result.is_err
        assert not req.called


# ── list_users_discovery ──────────────────────────────────────────────────────

class TestListUsersDiscovery:
    def test_calls_users_list_endpoint(self):
        client = _client()
        users = [
            {"key": "u-1", "username": "alice", "first_name": "Alice", "last_name": "A", "email": "a@x.com", "profile_photo": ""},
        ]

        with patch("xolo.client.client.R.request", return_value=_response(users)) as req:
            result = client.list_users_discovery()

        assert result.is_ok
        kwargs = req.call_args.kwargs
        assert kwargs["url"] == f"{BASE}/users/list"
        assert kwargs["method"] == "GET"

    def test_uses_admin_token_header(self):
        client = _client(admin_token="admin-1")

        with patch("xolo.client.client.R.request", return_value=_response([])) as req:
            client.list_users_discovery()

        assert req.call_args.kwargs["headers"] == {"X-Admin-Token": "admin-1"}

    def test_returns_user_dtos(self):
        client = _client()
        users = [
            {"key": "u-1", "username": "alice", "first_name": "Alice", "last_name": "A", "email": "a@x.com", "profile_photo": ""},
            {"key": "u-2", "username": "bob", "first_name": "Bob", "last_name": "B", "email": "b@x.com", "profile_photo": ""},
        ]

        with patch("xolo.client.client.R.request", return_value=_response(users)):
            result = client.list_users_discovery()

        assert result.is_ok
        items = result.unwrap()
        assert len(items) == 2
        assert all(isinstance(u, M.UserDTO) for u in items)


# ── Discovery endpoints ───────────────────────────────────────────────────────

class TestDiscoveryEndpoints:
    """All discovery methods follow the same pattern: GET /<module>/<resource>/list
    with X-API-Key header, returning a list (possibly empty)."""

    _discovery_cases = [
        ("list_scopes_discovery",              f"{BASE}/scopes/list"),
        ("list_acl_groups_discovery",          f"{BASE}/acl/groups/list"),
        ("list_acl_principals_discovery",      f"{BASE}/acl/principals/list"),
        ("list_acl_resources_discovery",       f"{BASE}/acl/resources/list"),
        ("list_abac_policies_discovery",       f"{BASE}/abac/policies/list"),
        ("list_abac_subjects_discovery",       f"{BASE}/abac/subjects/list"),
        ("list_abac_resources_discovery",      f"{BASE}/abac/resources/list"),
        ("list_abac_locations_discovery",      f"{BASE}/abac/locations/list"),
        ("list_ngac_nodes_discovery",          f"{BASE}/ngac/nodes/list"),
        ("list_ngac_assignments_discovery",    f"{BASE}/ngac/assignments/list"),
        ("list_ngac_associations_discovery",   f"{BASE}/ngac/associations/list"),
        ("list_rbac_roles_discovery",          f"{BASE}/rbac/roles/list"),
        ("list_rbac_permissions_discovery",    f"{BASE}/rbac/permissions/list"),
    ]

    @pytest.mark.parametrize("method_name,expected_url", _discovery_cases)
    def test_calls_correct_url(self, method_name, expected_url):
        client = _client()

        with patch("xolo.client.client.R.request", return_value=_response([])) as req:
            result = getattr(client, method_name)()

        assert result.is_ok
        assert req.call_args.kwargs["url"] == expected_url
        assert req.call_args.kwargs["method"] == "GET"

    @pytest.mark.parametrize("method_name,_", _discovery_cases)
    def test_sends_api_key_header(self, method_name, _):
        client = _client(api_key="my-key")

        with patch("xolo.client.client.R.request", return_value=_response([])) as req:
            getattr(client, method_name)()

        assert req.call_args.kwargs["headers"] == {"X-API-Key": "my-key"}

    @pytest.mark.parametrize("method_name,_", _discovery_cases)
    def test_returns_list(self, method_name, _):
        client = _client()
        items = [{"id": "x-1", "name": "Thing"}]

        with patch("xolo.client.client.R.request", return_value=_response(items)):
            result = getattr(client, method_name)()

        assert result.is_ok
        assert result.unwrap() == items

    @pytest.mark.parametrize("method_name,_", _discovery_cases)
    def test_requires_api_key(self, method_name, _):
        client = XoloClient(account_id="acct-1", api_key="", api_url="http://localhost:10000/api/v4")

        with patch("xolo.client.client.R.request") as req:
            result = getattr(client, method_name)()

        assert result.is_err
        assert not req.called


# ── RotateLicenseDTO model ────────────────────────────────────────────────────

class TestRotateLicenseDTO:
    def test_accepts_required_fields(self):
        dto = M.RotateLicenseDTO(username="alice", scope="READ", expires_in="7d")
        assert dto.username == "alice"
        assert dto.scope == "READ"
        assert dto.expires_in == "7d"
