"""Scan worker (Product v1 roadmap Phase 4 item 11, Worker Queue v1).

Standalone process, its own docker-compose service (infra/docker/
docker-compose.yml's scan-worker) -- the roadmap's own recommendation for
v1: "Postgres-backed queue + one worker container". Polls scan_jobs
(scan_jobs.py) for status='queued' work, claims one at a time
(claim_next_queued_job -- race-safe, so running more than one worker
container is safe too, not just tolerated), and runs it via main.run_scan_job,
which reuses api-gateway's normal request-time logic (auth/audit/scan-scope
repositories, the same _ingest_scan evidence-ingestion pipeline) --
importing main.py here (rather than duplicating that logic) is what makes
that reuse possible; the unused FastAPI app object it also builds is a
negligible one-time startup cost.

Run directly: `python worker.py` (see the docker-compose service's `command`).
"""
from __future__ import annotations

import logging
import os
import time

import main

logging.basicConfig(level=logging.INFO, format="%(asctime)s scan-worker %(message)s")
logger = logging.getLogger("scan-worker")

POLL_INTERVAL_SECONDS = float(os.getenv("SCAN_WORKER_POLL_INTERVAL_SECONDS", "2"))


def run_forever() -> None:
    logger.info("scan-worker started (poll interval=%ss, max retries=%s)", POLL_INTERVAL_SECONDS, main.MAX_SCAN_JOB_RETRIES)
    while True:
        job = main.scan_job_repository.claim_next_queued_job()
        if job is None:
            time.sleep(POLL_INTERVAL_SECONDS)
            continue

        actor_role = None
        if job.created_by:
            creator = main.auth_repository.get_user_by_id(job.created_by)
            actor_role = creator.role if creator else None

        logger.info("running job %s (scan_type=%s, targets=%s)", job.id, job.scan_type, job.targets)
        try:
            main.run_scan_job(job.id, job.scan_type, job.workspace_id, job.created_by, actor_role)
        except Exception:
            # A bug in run_scan_job itself (not a scan/scope/downstream
            # failure, which run_scan_job already handles and retries) --
            # log and keep polling rather than crashing the whole worker
            # process over one bad job.
            logger.exception("unexpected error processing job %s", job.id)


if __name__ == "__main__":
    run_forever()
