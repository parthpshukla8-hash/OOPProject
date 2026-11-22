import logging

from django.db import DatabaseError, IntegrityError
from rest_framework.response import Response
from rest_framework.views import exception_handler

from .exceptions import ItsmError

logger = logging.getLogger(__name__)


def handle_api_exception(exc, context):
    """Turn domain exceptions into consistent JSON: {detail, code, ...extra}."""
    if isinstance(exc, ItsmError):
        return Response({"detail": exc.message, "code": exc.code, **exc.extra}, status=exc.status_code)
    if isinstance(exc, IntegrityError):
        return Response({"detail": "That conflicts with something that already exists.", "code": "conflict"},
                        status=409)
    if isinstance(exc, DatabaseError):
        logger.exception("Database failure")
        return Response({"detail": "The database is not available right now. Try again in a moment.",
                         "code": "database_unavailable"}, status=503)
    response = exception_handler(exc, context)
    if response is not None and isinstance(response.data, dict) and "code" not in response.data:
        response.data = {"code": "request_error", **response.data}
        if "detail" not in response.data:
            response.data["detail"] = "; ".join(
                f"{field}: {' '.join(map(str, messages)) if isinstance(messages, list) else messages}"
                for field, messages in response.data.items() if field != "code")
    return response
