"""Domain exceptions. Each maps to one HTTP status in api_errors.py."""


class ItsmError(Exception):
    status_code = 400
    code = "itsm_error"
    default_message = "Something went wrong."

    def __init__(self, message: str | None = None, **extra):
        super().__init__(message or self.default_message)
        self.message = message or self.default_message
        self.extra = extra


class InvalidUserInput(ItsmError):
    code = "invalid_input"
    default_message = "Some of the information provided is not valid."


class InvalidCredentials(ItsmError):
    status_code = 401
    code = "invalid_credentials"
    default_message = "The username or password is incorrect."


class UnauthorizedOperation(ItsmError):
    status_code = 403
    code = "unauthorized"
    default_message = "You are not allowed to do that."


class IncidentNotFound(ItsmError):
    status_code = 404
    code = "incident_not_found"
    default_message = "That incident does not exist."


class ServiceNotFound(ItsmError):
    status_code = 404
    code = "service_not_found"
    default_message = "That service does not exist."


class InvalidStateTransition(ItsmError):
    status_code = 409
    code = "invalid_transition"
    default_message = "That step is not allowed from the incident's current status."


class TechnicianUnavailable(ItsmError):
    status_code = 409
    code = "technician_unavailable"
    default_message = "No technician is available for this incident."


class TechnicianWorkloadExceeded(ItsmError):
    status_code = 409
    code = "workload_exceeded"
    default_message = "That technician is already at their workload limit."


class MissingSlaConfiguration(ItsmError):
    status_code = 422
    code = "missing_sla"
    default_message = "No SLA policy is configured for this priority."


class DuplicateIncident(ItsmError):
    status_code = 409
    code = "duplicate_incident"
    default_message = "You already reported something very similar that is still open."


class DependencyCycle(ItsmError):
    code = "dependency_cycle"
    default_message = "That dependency would create a cycle between services."
