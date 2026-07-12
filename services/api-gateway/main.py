from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from typing import Any
from urllib import error, parse, request

from fastapi import BackgroundTasks, Body, Cookie, Depends, FastAPI, HTTPException, Query, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.append(str(REPO_ROOT))

from tools.graph_projection.graph_snapshot_loader import (
    GraphSnapshotLoaderError,
    load_graph_snapshot,
    summarize_graph_snapshot,
)

import auth
import audit
import demo_seed
import scan_jobs
import scan_scope

app = FastAPI(title="API Gateway", version="0.2.0")

# Allow the local web-ui (a browser frontend) to call the gateway. Configurable
# via CORS_ALLOW_ORIGINS (comma-separated); defaults to permissive for local dev.
# allow_credentials=True is required for the session cookie (see auth.py) to be
# sent/read cross-origin; Starlette handles allow_origins=["*"] + credentials by
# reflecting the actual request Origin instead of a literal "*", which is what
# browsers require, so this doesn't change the permissive local-dev default.
_cors_origins = [o.strip() for o in os.getenv("CORS_ALLOW_ORIGINS", "*").split(",") if o.strip()]
app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins or ["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Shared API key gate for exposing the gateway outside a trusted local network (e.g. a
# public demo). Disabled by default (QRP_API_KEY unset) so local dev/CI need no header.
# /health and CORS preflight (OPTIONS) stay open -- Docker healthchecks and browser
# preflight requests never carry the key.
QRP_API_KEY = os.getenv("QRP_API_KEY") or None


def _cors_headers(request: Request) -> dict[str, str]:
    # A 401 short-circuited here bypasses CORSMiddleware's own response handling (it
    # never reaches call_next), so the browser can't read it at all without this --
    # it shows up as an opaque CORS failure instead of a readable 401.
    if "*" in _cors_origins:
        return {"Access-Control-Allow-Origin": "*"}
    origin = request.headers.get("origin")
    return {"Access-Control-Allow-Origin": origin} if origin in _cors_origins else {}


@app.middleware("http")
async def require_api_key(request: Request, call_next):
    if QRP_API_KEY and request.method != "OPTIONS" and request.url.path != "/health":
        if request.headers.get("X-API-Key") != QRP_API_KEY:
            return JSONResponse(
                status_code=401,
                content={"detail": "Invalid or missing API key"},
                headers=_cors_headers(request),
            )
    return await call_next(request)


# Public Demo Safety Mode: for a live demo reachable by anyone (not just
# operators holding QRP_API_KEY), restrict the gateway to a fixed allowlist so
# visitors can browse/seed the canned demo dataset but can't ingest arbitrary
# scans or otherwise mutate persisted state. Disabled by default -- unrelated
# to and independent of QRP_API_KEY (a deployment can use either, both, or
# neither). GET/HEAD are always allowed (every gateway GET route is read-only,
# confirmed by inspection -- no route mutates state on GET); POST is allowed
# only for this explicit list of routes that either don't persist anything
# (stateless compute/query endpoints) or are the controlled, idempotent,
# bounded demo-seeding endpoint itself -- not "arbitrary" ingest.
QRP_DEMO_MODE = os.getenv("QRP_DEMO_MODE", "").strip().lower() in ("1", "true", "yes")

DEMO_MODE_ALLOWED_POST_PATHS = {
    "/api/demo/load",
    "/api/copilot/query",
    "/api/scenarios/run",
    "/api/policies/evaluate",
    "/api/fingerprint",
    "/api/normalize",
    "/api/pqc-readiness",
    "/api/assess",
    "/api/attribute",
    "/api/graph/blast-radius",
    "/api/graph/trust-chain",
    "/api/graph/neighbors",
    "/api/graph/evidence-path",
    "/api/integrations/dry-run",
}


@app.middleware("http")
async def enforce_demo_mode_allowlist(request: Request, call_next):
    if QRP_DEMO_MODE and request.method not in ("GET", "HEAD", "OPTIONS"):
        if request.url.path not in DEMO_MODE_ALLOWED_POST_PATHS:
            return JSONResponse(
                status_code=403,
                content={"detail": "This route is disabled in public demo mode"},
                headers=_cors_headers(request),
            )
    return await call_next(request)


INVENTORY_BASE_URL = os.getenv("INVENTORY_SERVICE_URL", "http://inventory-service:8000")
RISK_BASE_URL = os.getenv("RISK_ENGINE_URL", "http://risk-engine:8000")
COPILOT_BASE_URL = os.getenv("COPILOT_SERVICE_URL", "http://copilot-service:8000")
SCENARIO_ENGINE_BASE_URL = os.getenv("SCENARIO_ENGINE_URL", "http://scenario-engine:8000")
POLICY_ENGINE_BASE_URL = os.getenv("POLICY_ENGINE_URL", "http://policy-engine:8000")
CRYPTO_FINGERPRINT_BASE_URL = os.getenv("CRYPTO_FINGERPRINT_URL", "http://crypto-fingerprint-service:8000")
EVIDENCE_NORMALIZER_BASE_URL = os.getenv("EVIDENCE_NORMALIZER_URL", "http://evidence-normalizer:8000")
INTEGRATION_SERVICE_BASE_URL = os.getenv("INTEGRATION_SERVICE_URL", "http://integration-service:8000")
PQC_READINESS_BASE_URL = os.getenv("PQC_READINESS_URL", "http://pqc-readiness-service:8000")
GRAPH_SERVICE_BASE_URL = os.getenv("GRAPH_SERVICE_URL", "http://graph-service:8000")
FINDING_ATTRIBUTION_BASE_URL = os.getenv("FINDING_ATTRIBUTION_URL", "http://finding-attribution-service:8000")
GRAPH_SNAPSHOT_DEFAULT_PATH = "reports/graph/latest/graph-snapshot.json"


@app.get("/health")
def health() -> dict[str, Any]:
    return {"status": "ok", "service": "api-gateway", "demo_mode": QRP_DEMO_MODE}


# --- Local authentication (Product v1 roadmap Phase 3 item 6, see auth.py) ---
# Real per-user login/session, alongside (not replacing) QRP_API_KEY -- see
# docs/adr/0001-product-v1-architecture.md. Route-level RBAC enforcement (who
# is allowed to call what) is a separate, later roadmap task; these routes
# only prove identity and maintain a session.
auth_repository = auth.AuthRepository()
SESSION_COOKIE_NAME = "qrp_session"
# Secure requires HTTPS (e.g. behind the Caddy `public` profile, see
# infra/docker/README.md) -- off by default so bare-metal/local-dev http still
# gets the cookie back from the browser.
SESSION_COOKIE_SECURE = os.getenv("QRP_SESSION_COOKIE_SECURE", "").strip().lower() in ("1", "true", "yes")

# --- Audit log foundation (Product v1 roadmap Phase 3 item 8, see audit.py) ---
audit_repository = audit.AuditRepository()

# --- Scan scope manager (Product v1 roadmap Phase 4 item 9, see scan_scope.py) ---
scan_scope_repository = scan_scope.ScanScopeRepository()

# --- Scan job model (Product v1 roadmap Phase 4 item 10, see scan_jobs.py) ---
scan_job_repository = scan_jobs.ScanJobRepository()


def _client_ip(request: Request) -> str | None:
    return request.client.host if request.client else None


def get_current_user(qrp_session: str | None = Cookie(default=None)) -> auth.User | None:
    if not qrp_session:
        return None
    return auth_repository.get_session_user(qrp_session)


def _require_current_user(current_user: auth.User | None) -> auth.User:
    if current_user is None:
        raise HTTPException(status_code=401, detail="Not authenticated")
    return current_user


@app.post("/api/auth/bootstrap", response_model=auth.User, status_code=201)
def bootstrap_admin(payload: auth.BootstrapRequest, request: Request) -> auth.User:
    """Creates the first Admin user -- only while no users exist yet. Run this
    immediately after first deploying the stack, before exposing it beyond a
    trusted network, so nobody else can win the race to become the first
    admin (see services/api-gateway/README.md)."""
    if auth_repository.count_users() > 0:
        raise HTTPException(status_code=409, detail="An admin user already exists")
    user = auth_repository.create_user(payload.username, payload.password, role="admin")
    audit_repository.record(
        action="user.create", result="success", actor_user_id=user.id, actor_role=user.role,
        resource_type="user", resource_id=user.id, source_ip=_client_ip(request),
        summary=f"bootstrap admin username={user.username}",
    )
    return user


@app.post("/api/auth/login", response_model=auth.User)
def login(payload: auth.LoginRequest, response: Response, request: Request) -> auth.User:
    user = auth_repository.verify_credentials(payload.username, payload.password)
    if user is None:
        audit_repository.record(
            action="login", result="failure", source_ip=_client_ip(request),
            summary=f"username={payload.username}",
        )
        raise HTTPException(status_code=401, detail="Invalid username or password")
    token = auth_repository.create_session(user.id)
    response.set_cookie(
        SESSION_COOKIE_NAME,
        token,
        httponly=True,
        samesite="lax",
        secure=SESSION_COOKIE_SECURE,
        max_age=int(auth.SESSION_TTL.total_seconds()),
    )
    audit_repository.record(
        action="login", result="success", actor_user_id=user.id, actor_role=user.role,
        resource_type="user", resource_id=user.id, source_ip=_client_ip(request),
    )
    return user


@app.post("/api/auth/logout", status_code=204, response_model=None)
def logout(response: Response, request: Request, qrp_session: str | None = Cookie(default=None)) -> None:
    if qrp_session:
        user = auth_repository.get_session_user(qrp_session)
        auth_repository.delete_session(qrp_session)
        if user is not None:
            audit_repository.record(
                action="logout", result="success", actor_user_id=user.id, actor_role=user.role,
                resource_type="user", resource_id=user.id, source_ip=_client_ip(request),
            )
    response.delete_cookie(SESSION_COOKIE_NAME)


@app.get("/api/auth/me", response_model=auth.User)
def me(current_user: auth.User | None = Depends(get_current_user)) -> auth.User:
    return _require_current_user(current_user)


@app.post("/api/auth/password", status_code=204, response_model=None)
def change_password(payload: auth.PasswordChangeRequest, request: Request, current_user: auth.User | None = Depends(get_current_user)) -> None:
    user = _require_current_user(current_user)
    if auth_repository.verify_credentials(user.username, payload.current_password) is None:
        audit_repository.record(
            action="user.update", result="failure", actor_user_id=user.id, actor_role=user.role,
            resource_type="user", resource_id=user.id, source_ip=_client_ip(request),
            summary="password change: wrong current password",
        )
        raise HTTPException(status_code=401, detail="Current password is incorrect")
    auth_repository.update_password(user.id, payload.new_password)
    audit_repository.record(
        action="user.update", result="success", actor_user_id=user.id, actor_role=user.role,
        resource_type="user", resource_id=user.id, source_ip=_client_ip(request),
        summary="password changed",
    )


@app.get("/api/users", response_model=list[auth.User])
def list_users() -> list[auth.User]:
    """Admin-only (enforced by enforce_rbac below, see ADMIN_ONLY_PREFIXES)."""
    return auth_repository.list_users()


@app.post("/api/users", response_model=auth.User, status_code=201)
def create_user(payload: auth.UserCreateRequest, request: Request, current_user: auth.User | None = Depends(get_current_user)) -> auth.User:
    """Admin-only (enforced by enforce_rbac below, see ADMIN_ONLY_PREFIXES) --
    lets an Admin onboard the other three roles once the first admin exists
    (bootstrap only ever creates one Admin, see /api/auth/bootstrap)."""
    if auth_repository.get_user_by_username(payload.username) is not None:
        raise HTTPException(status_code=409, detail="Username already exists")
    user = auth_repository.create_user(payload.username, payload.password, role=payload.role)
    audit_repository.record(
        action="user.create", result="success",
        actor_user_id=current_user.id if current_user else None,
        actor_role=current_user.role if current_user else None,
        resource_type="user", resource_id=user.id, source_ip=_client_ip(request),
        summary=f"created username={user.username} role={user.role}",
    )
    return user


@app.get("/api/audit-log", response_model=list[audit.AuditEvent])
def list_audit_log(limit: int = Query(default=200, le=1000)) -> list[audit.AuditEvent]:
    """Admin/Auditor-only (enforced by enforce_rbac below, see
    AUDIT_LOG_READ_ROLES) -- read-only, no route exists to mutate audit events."""
    return audit_repository.list_events(limit=limit)


# --- Scan scope manager (Product v1 roadmap Phase 4 item 9, see scan_scope.py) ---
@app.post("/api/scan-scopes", response_model=scan_scope.ScanScope, status_code=201)
def create_scan_scope(payload: scan_scope.ScanScopeCreate, request: Request, current_user: auth.User | None = Depends(get_current_user)) -> scan_scope.ScanScope:
    """Admin/Security Architect-only (enforced by enforce_rbac below, see
    PRIVILEGED_WRITE_PREFIXES) -- rejects internet-wide CIDRs (0.0.0.0/0,
    ::/0) outright, see scan_scope._validate_cidr."""
    created = scan_scope_repository.create_scope(payload, created_by=current_user.id if current_user else None)
    audit_repository.record(
        action="scan_scope.create", result="success",
        actor_user_id=current_user.id if current_user else None,
        actor_role=current_user.role if current_user else None,
        workspace_id=created.workspace_id, resource_type="scan_scope", resource_id=created.id,
        source_ip=_client_ip(request),
        summary=f"cidrs={created.allowed_cidr_ranges} domains={created.allowed_domains} excluded={created.excluded_targets}",
    )
    return created


@app.get("/api/scan-scopes", response_model=list[scan_scope.ScanScope])
def list_scan_scopes(workspace_id: str | None = Query(default=None)) -> list[scan_scope.ScanScope]:
    return scan_scope_repository.list_scopes(workspace_id=workspace_id)


# --- Scan job model (Product v1 roadmap Phase 4 item 10, see scan_jobs.py) ---
def _run_scan_job(job_id: str, scan_type: str, workspace_id: str | None, actor_user_id: str | None, actor_role: str | None) -> None:
    """Runs as a FastAPI background task, after the response to POST
    /api/scan-jobs has already been sent -- see scan_jobs.py's module
    docstring for why this is in-process rather than a separate worker
    container (that's roadmap item 11, Worker Queue v1, a separate task)."""
    if not scan_job_repository.mark_running(job_id):
        return  # already cancelled before the worker got to it
    job_input = scan_job_repository.get_job_input(job_id)
    if job_input is None:
        return
    payload, scenario = job_input
    try:
        result = _ingest_scan(scan_type, payload, scenario, workspace_id=workspace_id)
        scan_job_repository.mark_finished(
            job_id, status="succeeded",
            result_summary=json.dumps({"created": result.get("created"), "scan_id": result.get("scan_id"), "workspace_id": result.get("workspace_id")}),
            log_line=f"succeeded: created={result.get('created')}",
        )
        audit_repository.record(
            action="scan.ingest", result="success",
            actor_user_id=actor_user_id, actor_role=actor_role,
            workspace_id=result.get("workspace_id"), resource_type="scan", resource_id=result.get("scan_id"),
            summary=f"scan_job={job_id} source={scan_type} created={result.get('created')}",
        )
    except HTTPException as exc:
        scan_job_repository.mark_finished(
            job_id, status="failed", result_summary=str(exc.detail), log_line=f"failed: {exc.detail}",
        )
        audit_repository.record(
            action="scan.ingest", result="failure",
            actor_user_id=actor_user_id, actor_role=actor_role,
            workspace_id=workspace_id, resource_type="scan", resource_id=job_id,
            summary=f"scan_job={job_id} source={scan_type}: {exc.detail}",
        )


@app.post("/api/scan-jobs", response_model=scan_jobs.ScanJob, status_code=202)
def create_scan_job(payload: scan_jobs.ScanJobCreate, request: Request, background_tasks: BackgroundTasks, current_user: auth.User | None = Depends(get_current_user)) -> scan_jobs.ScanJob:
    """Admin/Security Architect-only (enforced by enforce_rbac below, see
    PRIVILEGED_WRITE_PREFIXES) -- queues a scan (status=queued) and returns
    immediately; a background task performs the actual evidence ingestion
    (including scan scope enforcement) and updates status/logs/result_summary."""
    if not payload.targets:
        payload = payload.model_copy(update={"targets": _evidence_targets(payload.payload)})
    job = scan_job_repository.create_job(payload, created_by=current_user.id if current_user else None)
    audit_repository.record(
        action="scan_job.create", result="success",
        actor_user_id=current_user.id if current_user else None,
        actor_role=current_user.role if current_user else None,
        workspace_id=job.workspace_id, resource_type="scan_job", resource_id=job.id,
        source_ip=_client_ip(request), summary=f"scan_type={job.scan_type} targets={job.targets}",
    )
    background_tasks.add_task(
        _run_scan_job, job.id, job.scan_type, job.workspace_id,
        current_user.id if current_user else None, current_user.role if current_user else None,
    )
    return job


@app.get("/api/scan-jobs", response_model=list[scan_jobs.ScanJob])
def list_scan_jobs(workspace_id: str | None = Query(default=None)) -> list[scan_jobs.ScanJob]:
    return scan_job_repository.list_jobs(workspace_id=workspace_id)


@app.get("/api/scan-jobs/{job_id}", response_model=scan_jobs.ScanJob)
def get_scan_job(job_id: str) -> scan_jobs.ScanJob:
    job = scan_job_repository.get_job(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Scan job not found")
    return job


@app.post("/api/scan-jobs/{job_id}/cancel", response_model=scan_jobs.ScanJob)
def cancel_scan_job(job_id: str, request: Request, current_user: auth.User | None = Depends(get_current_user)) -> scan_jobs.ScanJob:
    """Admin/Security Architect-only. Only succeeds while the job hasn't
    finished yet (queued or running) -- see scan_jobs.ScanJobRepository.cancel_job."""
    cancelled = scan_job_repository.cancel_job(job_id)
    if cancelled is None:
        existing = scan_job_repository.get_job(job_id)
        if existing is None:
            raise HTTPException(status_code=404, detail="Scan job not found")
        raise HTTPException(status_code=409, detail=f"Job already {existing.status}, cannot cancel")
    audit_repository.record(
        action="scan_job.cancel", result="success",
        actor_user_id=current_user.id if current_user else None,
        actor_role=current_user.role if current_user else None,
        workspace_id=cancelled.workspace_id, resource_type="scan_job", resource_id=job_id,
        source_ip=_client_ip(request),
    )
    return cancelled


# --- RBAC v1 (Product v1 roadmap Phase 3 item 7) ---
# Roles: Admin, Security Architect, Operator, Auditor (docs/product-v1-roadmap.md).
# Enforcement only activates once at least one user has been bootstrapped --
# before that, the gateway stays open, matching every other env-var-gated safety
# layer's "unconfigured = open for local dev" default (QRP_API_KEY, QRP_DEMO_MODE)
# so bootstrap itself, and every existing local-dev/CI/demo flow that never calls
# it, keep working unchanged. A valid QRP_API_KEY header bypasses RBAC entirely --
# it is a separate, orthogonal machine-trust mechanism (see
# docs/adr/0001-product-v1-architecture.md), not tied to any one role.
#
# GET/HEAD (read) is open to any authenticated role, matching every role's
# "view"/"read-only" permission in the roadmap. Only mutating routes are
# restricted further, via prefix match (several routes carry path parameters,
# e.g. /api/assets/{id}, so exact-match like DEMO_MODE_ALLOWED_POST_PATHS above
# doesn't fit here).
#
# Operator's roadmap permissions ("view assigned tasks, update task status,
# attach validation notes") have no corresponding gateway route yet --
# workflow-service's task/approval routes aren't proxied here (roadmap item 18,
# Migration Task Workflow, is a separate, later phase) -- so Operator is
# read-only in this cut, same as Auditor, until that phase adds real
# task-mutation routes to restrict to Operator+Admin instead.
ADMIN_ONLY_PREFIXES = ("/api/users",)
PRIVILEGED_WRITE_ROLES = {"admin", "security_architect"}
PRIVILEGED_WRITE_PREFIXES = (
    "/api/scans/",
    "/api/demo/load",
    "/api/workspaces",
    "/api/scan-scopes",
    "/api/scan-jobs",
    "/api/scenarios/run",
    "/api/policies/evaluate",
    "/api/fingerprint",
    "/api/normalize",
    "/api/pqc-readiness",
    "/api/assess",
    "/api/attribute",
    "/api/graph/blast-radius",
    "/api/graph/trust-chain",
    "/api/graph/neighbors",
    "/api/graph/evidence-path",
    "/api/integrations/dry-run",
    "/api/copilot/query",
)
# Audit Log Foundation (roadmap item 8): narrower than the general "any
# authenticated role can GET" default -- only Admin/Auditor may read it,
# matching the roadmap's own "[PASS] audit log се вижда в UI за Admin/Auditor".
AUDIT_LOG_READ_ROLES = {"admin", "auditor"}
AUDIT_LOG_PREFIXES = ("/api/audit-log",)
RBAC_PUBLIC_PATHS = {"/health", "/api/auth/bootstrap", "/api/auth/login"}


def _log_access_denied(request: Request, current_user: auth.User | None, reason: str) -> None:
    audit_repository.record(
        action="access_denied",
        result="failure",
        actor_user_id=current_user.id if current_user else None,
        actor_role=current_user.role if current_user else None,
        resource_type="route",
        resource_id=request.url.path,
        source_ip=_client_ip(request),
        summary=f"{request.method} {request.url.path}: {reason}",
    )


@app.middleware("http")
async def enforce_rbac(request: Request, call_next):
    if request.method == "OPTIONS" or request.url.path in RBAC_PUBLIC_PATHS:
        return await call_next(request)
    if auth_repository.count_users() == 0:
        return await call_next(request)  # setup mode: no admin bootstrapped yet
    if QRP_API_KEY and request.headers.get("X-API-Key") == QRP_API_KEY:
        return await call_next(request)  # trusted machine access, RBAC doesn't apply

    token = request.cookies.get(SESSION_COOKIE_NAME)
    current_user = auth_repository.get_session_user(token) if token else None
    if current_user is None:
        _log_access_denied(request, None, "not authenticated")
        return JSONResponse(status_code=401, content={"detail": "Not authenticated"}, headers=_cors_headers(request))

    path = request.url.path
    if any(path.startswith(prefix) for prefix in ADMIN_ONLY_PREFIXES) and current_user.role != "admin":
        _log_access_denied(request, current_user, "admin role required")
        return JSONResponse(status_code=403, content={"detail": "Admin role required"}, headers=_cors_headers(request))

    if any(path.startswith(prefix) for prefix in AUDIT_LOG_PREFIXES) and current_user.role not in AUDIT_LOG_READ_ROLES:
        _log_access_denied(request, current_user, "admin or auditor role required")
        return JSONResponse(status_code=403, content={"detail": "Admin or Auditor role required"}, headers=_cors_headers(request))

    if request.method not in ("GET", "HEAD") and any(path.startswith(prefix) for prefix in PRIVILEGED_WRITE_PREFIXES):
        if current_user.role not in PRIVILEGED_WRITE_ROLES:
            _log_access_denied(request, current_user, "insufficient role for this action")
            return JSONResponse(status_code=403, content={"detail": "Insufficient role for this action"}, headers=_cors_headers(request))

    return await call_next(request)


def _audit_scan_ingest(request: Request, current_user: auth.User | None, source: str, result: dict[str, Any]) -> None:
    audit_repository.record(
        action="scan.ingest",
        result="success",
        actor_user_id=current_user.id if current_user else None,
        actor_role=current_user.role if current_user else None,
        workspace_id=result.get("workspace_id"),
        resource_type="scan",
        resource_id=result.get("scan_id"),
        source_ip=_client_ip(request),
        summary=f"source={source} created={result.get('created')}",
    )


@app.post("/api/scans/host")
def ingest_host_scan(payload: dict[str, Any], request: Request, scenario: str = Query(default="public_timeline"), workspace_id: str | None = Query(default=None), current_user: auth.User | None = Depends(get_current_user)) -> dict[str, Any]:
    result = _ingest_scan("host", payload, scenario, workspace_id=workspace_id, request=request, current_user=current_user)
    _audit_scan_ingest(request, current_user, "host", result)
    return result


@app.post("/api/scans/network")
def ingest_network_scan(payload: dict[str, Any], request: Request, scenario: str = Query(default="public_timeline"), workspace_id: str | None = Query(default=None), current_user: auth.User | None = Depends(get_current_user)) -> dict[str, Any]:
    result = _ingest_scan("network", payload, scenario, workspace_id=workspace_id, request=request, current_user=current_user)
    _audit_scan_ingest(request, current_user, "network", result)
    return result


@app.post("/api/scans/repo")
def ingest_repo_scan(payload: dict[str, Any], request: Request, scenario: str = Query(default="public_timeline"), workspace_id: str | None = Query(default=None), current_user: auth.User | None = Depends(get_current_user)) -> dict[str, Any]:
    result = _ingest_scan("repo", payload, scenario, workspace_id=workspace_id, request=request, current_user=current_user)
    _audit_scan_ingest(request, current_user, "repo", result)
    return result


@app.post("/api/scans/windows")
def ingest_windows_scan(payload: dict[str, Any], request: Request, scenario: str = Query(default="public_timeline"), current_user: auth.User | None = Depends(get_current_user)) -> dict[str, Any]:
    """Persist a Windows host evidence document (from the windows-host-agent).

    The raw redacted/aggregate document is forwarded as-is; the inventory service
    maps it to the ingest contract (source is fixed to "host" there)."""
    endpoint = f"{INVENTORY_BASE_URL}/scans/ingest/windows?{parse.urlencode({'scenario': scenario, 'auto_score': 'true'})}"
    result = _request_json("POST", endpoint, payload=payload)
    _audit_scan_ingest(request, current_user, "windows", result)
    return result


@app.post("/api/demo/load")
def demo_load(request: Request, current_user: auth.User | None = Depends(get_current_user)) -> dict[str, Any]:
    """Seeds the small, realistic demo dataset (host/network/repo evidence +
    a vendor document) into the currently-running stack for the web-ui's
    "Load Demo" button. See demo_seed.py. Best-effort: each step is recorded
    independently so a single failure doesn't hide the others. Idempotent:
    an asset that's already present is skipped rather than re-ingested, so
    clicking "Load Demo" twice doesn't create duplicate scans/findings.

    Uses the workspace model (services/inventory-service/README.md): a new
    workspace is created only if there's actually something new to ingest
    (so idempotent re-clicks that skip everything don't leave empty
    workspaces behind), and all newly-ingested scans join it, so the demo's
    findings and report are all groupable under one workspace_id."""
    steps: list[dict[str, Any]] = []

    try:
        existing_assets = _request_json("GET", f"{INVENTORY_BASE_URL}/assets")
    except HTTPException:
        existing_assets = []
    existing_names = {a.get("name") for a in existing_assets} if isinstance(existing_assets, list) else set()

    payloads = demo_seed.load_demo_scan_payloads()
    needs_ingest = any(asset_name not in existing_names for _, asset_name, _ in payloads)

    workspace_id: str | None = None
    if needs_ingest:
        try:
            workspace = _request_json("POST", f"{INVENTORY_BASE_URL}/workspaces", payload={"source": "product-demo"})
            workspace_id = workspace.get("id")
        except HTTPException:
            workspace_id = None  # fall back to per-scan auto-workspace if this fails

    for source, asset_name, payload in payloads:
        if asset_name in existing_names:
            steps.append({"step": f"ingest_{source}", "status": "skipped", "asset_name": asset_name, "detail": "already loaded"})
            continue
        try:
            _ingest_scan(source, payload, "public_timeline", workspace_id=workspace_id, request=request, current_user=current_user)
            steps.append({"step": f"ingest_{source}", "status": "ok", "asset_name": asset_name})
        except HTTPException as exc:
            steps.append({"step": f"ingest_{source}", "status": "error", "asset_name": asset_name, "detail": str(exc.detail)})

    try:
        demo_seed.write_demo_doc_index()
        steps.append({"step": "doc_index", "status": "ok"})
    except OSError as exc:
        steps.append({"step": "doc_index", "status": "error", "detail": str(exc)})

    graph_path = Path(os.getenv("GRAPH_SNAPSHOT_PATH", demo_seed.GRAPH_SNAPSHOT_DEFAULT_PATH))
    graph_ok, graph_message = demo_seed.build_demo_graph_snapshot(graph_path)
    steps.append({"step": "graph_snapshot", "status": "ok" if graph_ok else "error", "detail": graph_message})

    overall = "ok" if all(s["status"] in ("ok", "skipped") for s in steps) else "partial"
    audit_repository.record(
        action="scan.ingest",
        result="success" if overall == "ok" else "failure",
        actor_user_id=current_user.id if current_user else None,
        actor_role=current_user.role if current_user else None,
        workspace_id=workspace_id,
        resource_type="workspace",
        resource_id=workspace_id,
        source_ip=_client_ip(request),
        summary=f"demo load: {overall}",
    )
    return {"overall": overall, "steps": steps, "workspace_id": workspace_id}


@app.get("/api/demo/status")
def demo_status() -> dict[str, Any]:
    """Whether the demo dataset (see /api/demo/load) currently appears
    loaded in the running stack -- used by the web-ui to decide whether to
    show "Load Demo" or a status summary."""
    try:
        assets = _request_json("GET", f"{INVENTORY_BASE_URL}/assets")
    except HTTPException:
        assets = []
    assets_by_name = {a.get("name"): a for a in assets} if isinstance(assets, list) else {}
    asset_names = set(assets_by_name)
    present = [name for name in demo_seed.DEMO_ASSET_NAMES if name in asset_names]
    missing = [name for name in demo_seed.DEMO_ASSET_NAMES if name not in asset_names]

    # Representative workspace_id for the demo dataset: the first present
    # demo asset's workspace_id (they all join the same workspace when
    # seeded together by one /api/demo/load call).
    workspace_id = next((assets_by_name[name].get("workspace_id") for name in present if assets_by_name[name].get("workspace_id")), None)

    graph_path = Path(os.getenv("GRAPH_SNAPSHOT_PATH", demo_seed.GRAPH_SNAPSHOT_DEFAULT_PATH))
    return {
        "loaded": len(missing) == 0,
        "assets_present": present,
        "assets_missing": missing,
        "asset_count_total": len(asset_names),
        "graph_snapshot_present": graph_path.exists(),
        "doc_index_present": demo_seed.DOC_INDEX_DEFAULT_PATH.exists(),
        "workspace_id": workspace_id,
    }


@app.get("/api/assets")
def list_assets(workspace_id: str | None = Query(default=None)) -> list[dict[str, Any]]:
    endpoint = f"{INVENTORY_BASE_URL}/assets"
    if workspace_id:
        endpoint += f"?{parse.urlencode({'workspace_id': workspace_id})}"
    return _request_json("GET", endpoint)


@app.get("/api/assets/{asset_id}")
def get_asset(asset_id: str) -> dict[str, Any]:
    return _request_json("GET", f"{INVENTORY_BASE_URL}/assets/{asset_id}")


@app.get("/api/assets/{asset_id}/history")
def get_asset_history(asset_id: str) -> dict[str, Any]:
    """Chronological risk trend for an asset across persisted scans."""
    return _request_json("GET", f"{INVENTORY_BASE_URL}/assets/{asset_id}/history")


# --- Workspace model (services/inventory-service/README.md) ---
@app.post("/api/workspaces")
def create_workspace(request: Request, payload: dict[str, Any] = Body(default_factory=dict), current_user: auth.User | None = Depends(get_current_user)) -> dict[str, Any]:
    result = _request_json("POST", f"{INVENTORY_BASE_URL}/workspaces", payload=payload)
    audit_repository.record(
        action="workspace.create", result="success",
        actor_user_id=current_user.id if current_user else None,
        actor_role=current_user.role if current_user else None,
        workspace_id=result.get("id"), resource_type="workspace", resource_id=result.get("id"),
        source_ip=_client_ip(request),
    )
    return result


@app.get("/api/workspaces")
def list_workspaces() -> list[dict[str, Any]]:
    return _request_json("GET", f"{INVENTORY_BASE_URL}/workspaces")


@app.get("/api/workspaces/{workspace_id}")
def get_workspace(workspace_id: str) -> dict[str, Any]:
    """Rollup: the workspace plus its scans, risks (findings), and reports."""
    return _request_json("GET", f"{INVENTORY_BASE_URL}/workspaces/{workspace_id}")


@app.post("/api/workspaces/{workspace_id}/reports")
def create_workspace_report(workspace_id: str, request: Request, payload: dict[str, Any] = Body(default_factory=dict), current_user: auth.User | None = Depends(get_current_user)) -> dict[str, Any]:
    result = _request_json("POST", f"{INVENTORY_BASE_URL}/workspaces/{workspace_id}/reports", payload=payload)
    audit_repository.record(
        action="report.generate", result="success",
        actor_user_id=current_user.id if current_user else None,
        actor_role=current_user.role if current_user else None,
        workspace_id=workspace_id, resource_type="report", resource_id=result.get("id"),
        source_ip=_client_ip(request),
    )
    return result


@app.get("/api/reports/{report_id}")
def get_report(report_id: str) -> dict[str, Any]:
    return _request_json("GET", f"{INVENTORY_BASE_URL}/reports/{report_id}")


@app.get("/api/reports")
def list_reports(workspace_id: str | None = Query(default=None)) -> list[dict[str, Any]]:
    endpoint = f"{INVENTORY_BASE_URL}/reports"
    if workspace_id:
        endpoint += f"?{parse.urlencode({'workspace_id': workspace_id})}"
    return _request_json("GET", endpoint)


@app.get("/api/assets/{asset_id}/risk")
def get_asset_risk(asset_id: str, scenario: str = Query(default="public_timeline")) -> dict[str, Any]:
    asset = _request_json("GET", f"{INVENTORY_BASE_URL}/assets/{asset_id}")
    risk_payload = _build_risk_payload_from_asset(asset, scenario)
    score = _request_json("POST", f"{RISK_BASE_URL}/score", payload=risk_payload)
    return {"asset_id": asset_id, "asset_name": asset.get("name"), "risk": score}


@app.post("/api/scenarios/run")
def run_scenario(payload: dict[str, Any]) -> dict[str, Any]:
    return _request_json("POST", f"{SCENARIO_ENGINE_BASE_URL}/run", payload=payload)


@app.get("/graph/snapshot")
def get_graph_snapshot() -> dict[str, Any]:
    snapshot = _load_graph_snapshot_or_raise()
    response = {
        "graph_schema_version": snapshot["graph_schema_version"],
        "nodes": snapshot["nodes"],
        "edges": snapshot["edges"],
        "warnings": snapshot["warnings"],
    }
    if "metadata" in snapshot:
        response["metadata"] = snapshot["metadata"]
    return response


@app.get("/graph/summary")
def get_graph_summary() -> dict[str, Any]:
    snapshot = _load_graph_snapshot_or_raise()
    return dict(summarize_graph_snapshot(snapshot))


@app.get("/graph/nodes")
def get_graph_nodes(node_type: str | None = Query(default=None)) -> dict[str, Any]:
    snapshot = _load_graph_snapshot_or_raise()
    nodes = snapshot["nodes"]
    if node_type:
        nodes = [node for node in nodes if node.get("type") == node_type]
    return {"nodes": nodes}


@app.get("/graph/edges")
def get_graph_edges(edge_type: str | None = Query(default=None)) -> dict[str, Any]:
    snapshot = _load_graph_snapshot_or_raise()
    edges = snapshot["edges"]
    if edge_type:
        edges = [edge for edge in edges if edge.get("type") == edge_type]
    return {"edges": edges}


@app.get("/graph/warnings")
def get_graph_warnings() -> dict[str, Any]:
    snapshot = _load_graph_snapshot_or_raise()
    return {"warnings": snapshot["warnings"]}




@app.post("/api/policies/evaluate")
def evaluate_policy(payload: dict[str, Any]) -> dict[str, Any]:
    return _request_json("POST", f"{POLICY_ENGINE_BASE_URL}/evaluate", payload=payload)


@app.get("/api/algorithms")
def list_algorithms() -> dict[str, Any]:
    return _request_json("GET", f"{CRYPTO_FINGERPRINT_BASE_URL}/algorithms")


@app.post("/api/fingerprint")
def fingerprint(payload: dict[str, Any]) -> dict[str, Any]:
    return _request_json("POST", f"{CRYPTO_FINGERPRINT_BASE_URL}/fingerprint", payload=payload)


@app.post("/api/normalize")
def normalize_evidence(payload: dict[str, Any]) -> dict[str, Any]:
    return _request_json("POST", f"{EVIDENCE_NORMALIZER_BASE_URL}/normalize", payload=payload)


@app.get("/api/readiness-states")
def readiness_states() -> dict[str, Any]:
    return _request_json("GET", f"{PQC_READINESS_BASE_URL}/readiness-states")


@app.post("/api/pqc-readiness")
def pqc_readiness(payload: dict[str, Any]) -> dict[str, Any]:
    return _request_json("POST", f"{PQC_READINESS_BASE_URL}/classify", payload=payload)


@app.post("/api/assess")
def assess(payload: dict[str, Any]) -> dict[str, Any]:
    """Chain the deterministic analysis pipeline for one asset:
    crypto-fingerprint -> pqc-readiness -> (optional) risk-engine."""
    asset_name = payload.get("asset_name") or "asset"

    fingerprint_request: dict[str, Any] = {"asset_name": asset_name}
    for key in ("algorithms", "tls_metadata", "crypto_evidence"):
        if key in payload:
            fingerprint_request[key] = payload[key]
    fingerprint = _request_json(
        "POST", f"{CRYPTO_FINGERPRINT_BASE_URL}/fingerprint", payload=fingerprint_request
    )

    readiness = _request_json(
        "POST",
        f"{PQC_READINESS_BASE_URL}/classify",
        payload={
            "asset_name": asset_name,
            "findings": fingerprint.get("findings", []),
            "vendor_blocked": payload.get("vendor_blocked", False),
            "hybrid_supported": payload.get("hybrid_supported", False),
        },
    )

    result: dict[str, Any] = {
        "asset_name": asset_name,
        "fingerprint": {"summary": fingerprint.get("summary"), "findings": fingerprint.get("findings", [])},
        "pqc_readiness": readiness,
        "risk": None,
        "pipeline": ["crypto-fingerprint-service", "pqc-readiness-service"],
    }

    attribution_request: dict[str, Any] = {
        "asset_name": asset_name,
        "application": payload.get("application"),
        "findings": fingerprint.get("findings", []),
    }
    for key in ("tls_metadata", "crypto_evidence", "network_evidence", "host_evidence"):
        if key in payload:
            attribution_request[key] = payload[key]
    attribution = _request_json(
        "POST", f"{FINDING_ATTRIBUTION_BASE_URL}/attribute", payload=attribution_request
    )
    result["attribution"] = attribution
    result["pipeline"].append("finding-attribution-service")

    risk_factors = payload.get("risk_factors")
    if isinstance(risk_factors, dict) and risk_factors:
        risk_request: dict[str, Any] = {"asset_name": asset_name, "vendor_blocked": payload.get("vendor_blocked", False)}
        risk_request.update(risk_factors)
        for key in ("tls_metadata", "crypto_evidence", "scenario", "dependency_count", "environment"):
            if key in payload:
                risk_request[key] = payload[key]
        result["risk"] = _request_json("POST", f"{RISK_BASE_URL}/score", payload=risk_request)
        result["pipeline"].append("risk-engine")

    return result


@app.post("/api/attribute")
def attribute_findings(payload: dict[str, Any]) -> dict[str, Any]:
    return _request_json("POST", f"{FINDING_ATTRIBUTION_BASE_URL}/attribute", payload=payload)


@app.get("/api/graph/queries")
def graph_queries() -> dict[str, Any]:
    return _request_json("GET", f"{GRAPH_SERVICE_BASE_URL}/queries")


@app.post("/api/graph/blast-radius")
def graph_blast_radius(payload: dict[str, Any]) -> dict[str, Any]:
    return _request_json("POST", f"{GRAPH_SERVICE_BASE_URL}/blast-radius", payload=payload)


@app.post("/api/graph/trust-chain")
def graph_trust_chain(payload: dict[str, Any]) -> dict[str, Any]:
    return _request_json("POST", f"{GRAPH_SERVICE_BASE_URL}/trust-chain", payload=payload)


@app.post("/api/graph/neighbors")
def graph_neighbors(payload: dict[str, Any]) -> dict[str, Any]:
    return _request_json("POST", f"{GRAPH_SERVICE_BASE_URL}/neighbors", payload=payload)


@app.post("/api/graph/evidence-path")
def graph_evidence_path(payload: dict[str, Any]) -> dict[str, Any]:
    return _request_json("POST", f"{GRAPH_SERVICE_BASE_URL}/evidence-path", payload=payload)


@app.get("/api/integrations")
def list_integrations() -> dict[str, Any]:
    return _request_json("GET", f"{INTEGRATION_SERVICE_BASE_URL}/integrations")


@app.post("/api/integrations/dry-run")
def integrations_dry_run(payload: dict[str, Any]) -> dict[str, Any]:
    return _request_json("POST", f"{INTEGRATION_SERVICE_BASE_URL}/dry-run", payload=payload)

@app.post("/api/copilot/query")
def copilot_query(payload: dict[str, Any]) -> dict[str, Any]:
    return _request_json("POST", f"{COPILOT_BASE_URL}/query", payload=payload)


@app.get("/api/copilot/narrate/{asset_name:path}")
def copilot_narrate(asset_name: str) -> dict[str, Any]:
    return _request_json("GET", f"{COPILOT_BASE_URL}/narrate/{asset_name}")


@app.get("/api/copilot/change-plan/{asset_name:path}")
def copilot_change_plan(asset_name: str) -> dict[str, Any]:
    return _request_json("GET", f"{COPILOT_BASE_URL}/change-plan/{asset_name}")


@app.get("/api/copilot/discover")
def copilot_discover() -> dict[str, Any]:
    return _request_json("GET", f"{COPILOT_BASE_URL}/discover")


@app.get("/api/copilot/vendor-intelligence")
def copilot_vendor_intelligence() -> dict[str, Any]:
    return _request_json("GET", f"{COPILOT_BASE_URL}/vendor-intelligence")


@app.get("/api/copilot/migration-plan")
def copilot_migration_plan() -> dict[str, Any]:
    return _request_json("GET", f"{COPILOT_BASE_URL}/migration-plan")


@app.get("/api/copilot/plan-summary")
def copilot_plan_summary() -> dict[str, Any]:
    return _request_json("GET", f"{COPILOT_BASE_URL}/plan-summary")


@app.get("/api/copilot/workflow-summary")
def copilot_workflow_summary() -> dict[str, Any]:
    return _request_json("GET", f"{COPILOT_BASE_URL}/workflow-summary")


@app.get("/api/copilot/operational-summary")
def copilot_operational_summary() -> dict[str, Any]:
    return _request_json("GET", f"{COPILOT_BASE_URL}/operational-summary")


def _load_graph_snapshot_or_raise() -> dict[str, Any]:
    snapshot_path = os.getenv("GRAPH_SNAPSHOT_PATH", GRAPH_SNAPSHOT_DEFAULT_PATH)
    try:
        return load_graph_snapshot(snapshot_path)
    except GraphSnapshotLoaderError as exc:
        raise HTTPException(status_code=400, detail={"error": exc.code}) from exc


def _evidence_targets(payload: dict[str, Any]) -> list[str]:
    targets = []
    for key in ("tls_evidence", "ssh_evidence", "ipsec_evidence"):
        block = payload.get(key)
        if isinstance(block, dict) and block.get("target"):
            targets.append(str(block["target"]))
    return targets


def _enforce_scan_scope(
    payload: dict[str, Any],
    workspace_id: str | None,
    request: Request | None,
    current_user: auth.User | None,
) -> None:
    """A workspace with no ScanScope defined stays open -- see scan_scope.py's
    module docstring for why. Only checks targets carried in network-facing
    evidence blocks (tls/ssh/ipsec); host/repo evidence has no network
    target to authorize."""
    if not workspace_id or not scan_scope_repository.has_scope(workspace_id):
        return
    scope = scan_scope_repository.list_scopes(workspace_id=workspace_id)[0]
    for target in _evidence_targets(payload):
        allowed, reason = scan_scope.check_target(scope, target)
        if not allowed:
            if request is not None:
                audit_repository.record(
                    action="scan.rejected", result="failure",
                    actor_user_id=current_user.id if current_user else None,
                    actor_role=current_user.role if current_user else None,
                    workspace_id=workspace_id, resource_type="scan_scope", resource_id=scope.id,
                    source_ip=_client_ip(request), summary=f"target={target}: {reason}",
                )
            raise HTTPException(status_code=403, detail=f"target {target!r} rejected by scan scope: {reason}")


def _ingest_scan(
    source: str,
    payload: dict[str, Any],
    scenario: str,
    workspace_id: str | None = None,
    request: Request | None = None,
    current_user: auth.User | None = None,
) -> dict[str, Any]:
    _enforce_scan_scope(payload, workspace_id, request, current_user)
    request_payload = dict(payload)
    request_payload["source"] = source
    query = {"scenario": scenario, "auto_score": "true"}
    if workspace_id:
        query["workspace_id"] = workspace_id
    endpoint = f"{INVENTORY_BASE_URL}/scans/ingest?{parse.urlencode(query)}"
    return _request_json("POST", endpoint, payload=request_payload)


def _build_risk_payload_from_asset(asset: dict[str, Any], scenario: str) -> dict[str, Any]:
    criticality = float(asset.get("criticality") or 3)
    vendor_lock_in = 3.0 if asset.get("vendor") else 1.0
    confidentiality_lifetime = 4.0 if (asset.get("lifecycle_years") or 0) >= 7 else 3.0
    blast_radius = 4.0 if asset.get("environment") == "production" else 3.0

    return {
        "criticality": criticality,
        "confidentiality_lifetime": confidentiality_lifetime,
        "quantum_exposure": 3.0,
        "blast_radius": blast_radius,
        "vendor_lock_in": vendor_lock_in,
        "migration_difficulty": 3.0,
        "scenario": scenario,
    }


def _request_json(method: str, url: str, payload: dict[str, Any] | None = None) -> Any:
    body = None
    headers = {"Accept": "application/json"}

    if payload is not None:
        body = json.dumps(payload).encode("utf-8")
        headers["Content-Type"] = "application/json"

    req = request.Request(url=url, method=method, data=body, headers=headers)

    try:
        with request.urlopen(req, timeout=10) as response:
            data = response.read().decode("utf-8")
            return json.loads(data) if data else {}
    except error.HTTPError as exc:
        detail = exc.read().decode("utf-8")
        raise HTTPException(status_code=exc.code, detail=detail or "Upstream service error") from exc
    except error.URLError as exc:
        raise HTTPException(status_code=502, detail=f"Upstream unavailable: {exc.reason}") from exc
