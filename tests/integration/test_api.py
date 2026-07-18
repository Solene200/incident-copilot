"""HTTP-level tests for liveness and unified error responses."""

from fastapi import Query
from fastapi.testclient import TestClient

from incident_copilot.core.config import RuntimeEnvironment, Settings
from incident_copilot.core.exceptions import DomainValidationError
from incident_copilot.main import create_app


def test_health_endpoint_needs_no_external_services_or_key() -> None:
    settings = Settings(environment=RuntimeEnvironment.TEST, _env_file=None)
    app = create_app(settings)

    with TestClient(app) as client:
        response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {
        "status": "ok",
        "service": "IncidentCopilot",
        "version": "0.1.0",
        "environment": "test",
    }


def test_application_exception_uses_stable_error_envelope() -> None:
    app = create_app(Settings(environment=RuntimeEnvironment.TEST, _env_file=None))

    @app.get("/_test/domain-error")
    async def raise_domain_error() -> None:
        raise DomainValidationError("invalid incident", details={"field": "start_time"})

    with TestClient(app) as client:
        response = client.get("/_test/domain-error", headers={"X-Request-ID": "req_test"})

    assert response.status_code == 400
    assert response.json() == {
        "error": {
            "code": "domain_validation_error",
            "message": "invalid incident",
            "details": {"field": "start_time"},
        },
        "request_id": "req_test",
    }


def test_application_exception_redacts_accidental_secrets() -> None:
    app = create_app(Settings(environment=RuntimeEnvironment.TEST, _env_file=None))

    @app.get("/_test/sensitive-domain-error")
    async def raise_sensitive_domain_error() -> None:
        raise DomainValidationError(
            "invalid token=secret-value",
            details={"api_key": "another-secret", "input_tokens": 3},
        )

    with TestClient(app) as client:
        response = client.get("/_test/sensitive-domain-error")

    assert response.status_code == 400
    assert "secret-value" not in response.text
    assert "another-secret" not in response.text
    assert response.json()["error"]["details"] == {
        "api_key": "***REDACTED***",
        "input_tokens": 3,
    }


def test_request_validation_does_not_echo_input() -> None:
    app = create_app(Settings(environment=RuntimeEnvironment.TEST, _env_file=None))

    @app.get("/_test/validation")
    async def validate_limit(limit: int = Query(gt=0)) -> dict[str, int]:
        return {"limit": limit}

    with TestClient(app) as client:
        response = client.get("/_test/validation", params={"limit": "secret-input"})

    payload = response.json()
    assert response.status_code == 422
    assert payload["error"]["code"] == "request_validation_error"
    assert "secret-input" not in response.text


def test_unexpected_exception_is_logged_but_not_exposed() -> None:
    app = create_app(Settings(environment=RuntimeEnvironment.TEST, _env_file=None))

    @app.get("/_test/internal-error")
    async def raise_internal_error() -> None:
        raise RuntimeError("sensitive implementation detail")

    with TestClient(app, raise_server_exceptions=False) as client:
        response = client.get("/_test/internal-error", headers={"X-Request-ID": "req_internal"})

    assert response.status_code == 500
    assert response.json() == {
        "error": {"code": "internal_error", "message": "Internal server error", "details": {}},
        "request_id": "req_internal",
    }
    assert "sensitive implementation detail" not in response.text
