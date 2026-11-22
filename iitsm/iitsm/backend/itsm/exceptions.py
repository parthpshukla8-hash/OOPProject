"""Custom exception hierarchy + DRF handler (maps domain errors to HTTP codes)."""
from django.db import DatabaseError
from rest_framework import status
from rest_framework.exceptions import APIException
from rest_framework.response import Response
from rest_framework.views import exception_handler as drf_handler


class ITSMError(APIException):
    status_code = status.HTTP_400_BAD_REQUEST
    default_code = "itsm_error"
    default_detail = "Request could not be processed."


class InvalidInput(ITSMError):
    default_code = "invalid_input"


class InvalidStateTransition(ITSMError):
    status_code = status.HTTP_409_CONFLICT
    default_code = "invalid_state_transition"


class UnauthorizedOperation(ITSMError):
    status_code = status.HTTP_403_FORBIDDEN
    default_code = "unauthorized_operation"


class TechnicianUnavailable(ITSMError):
    status_code = status.HTTP_409_CONFLICT
    default_code = "technician_unavailable"


class WorkloadExceeded(ITSMError):
    status_code = status.HTTP_409_CONFLICT
    default_code = "workload_exceeded"


class ServiceNotFound(ITSMError):
    status_code = status.HTTP_404_NOT_FOUND
    default_code = "service_not_found"


class MissingSLAConfiguration(ITSMError):
    status_code = 422
    default_code = "missing_sla_configuration"


class DuplicateIncident(ITSMError):
    status_code = status.HTTP_409_CONFLICT
    default_code = "duplicate_incident"


def handler(exc, context):
    if isinstance(exc, DatabaseError):
        return Response({"detail": "Database temporarily unavailable.", "code": "database_error"},
                        status=status.HTTP_503_SERVICE_UNAVAILABLE)
    response = drf_handler(exc, context)
    if response is not None and isinstance(exc, ITSMError):
        response.data = {"detail": str(exc.detail), "code": exc.default_code}
    return response
