"""Kubernetes-style health endpoints.

/healthz (liveness): the process can serve HTTP. Never checks dependencies,
    otherwise a database outage would make the orchestrator restart every pod.
/readyz (readiness): the process can do useful work right now, so it checks the
    database. A failure takes the instance out of load balancing without restarting it.
"""

import logging

from django.db import connection
from django.http import HttpRequest, JsonResponse
from django.views.decorators.http import require_GET

logger = logging.getLogger(__name__)


@require_GET
def healthz(request: HttpRequest) -> JsonResponse:
    return JsonResponse({"status": "ok"})


@require_GET
def readyz(request: HttpRequest) -> JsonResponse:
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
            cursor.fetchone()
    except Exception:
        logger.exception("readiness check failed: database unreachable")
        return JsonResponse({"status": "unavailable", "checks": {"database": "fail"}}, status=503)
    return JsonResponse({"status": "ready", "checks": {"database": "ok"}})
