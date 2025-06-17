from dataclasses import dataclass
from enum import Enum
from requests import Response


class ConfluenceClientException(Exception):
    def __init__(self, message: str, response: Response | None = None):
        super().__init__(message)
        self.message = message
        self.response = response
        self.status_code = response.status_code if response else None


class ConfluenceRefreshCredentialsException(ConfluenceClientException):
    pass


class ConfluenceForbiddenException(ConfluenceClientException):
    pass


class ConfluenceBadRequestException(ConfluenceClientException):
    pass


class ConfluenceUnauthorizedException(ConfluenceClientException):
    pass


class ConfluenceNotFoundException(ConfluenceClientException):
    pass


class ConfluenceConflictException(ConfluenceClientException):
    pass


class ConfluenceRateLimitException(ConfluenceClientException):
    pass


class ConfluenceSubRequestFailedException(ConfluenceClientException):
    pass


class ConfluenceInternalServerException(ConfluenceClientException):
    pass


class ConfluenceNotImplementedException(ConfluenceClientException):
    pass


class ConfluenceBadGatewayException(ConfluenceClientException):
    pass


class ConfluenceServiceUnavailableException(ConfluenceClientException):
    pass


class ConfluenceGatewayTimeoutException(ConfluenceClientException):
    pass


@dataclass(frozen=True)
class ErrorMapping:
    exception_class: type[ConfluenceClientException]
    default_message: str


class ConfluenceErrorCode(Enum):
    BAD_REQUEST = 400
    UNAUTHORIZED = 401
    FORBIDDEN = 403
    NOT_FOUND = 404
    CONFLICT = 409
    RATE_LIMIT = 429
    SUB_REQUEST_FAILED = 449
    INTERNAL_SERVER_ERROR = 500
    NOT_IMPLEMENTED = 501
    BAD_GATEWAY = 502
    SERVICE_UNAVAILABLE = 503
    GATEWAY_TIMEOUT = 504


ERROR_MAPPINGS = {
    ConfluenceErrorCode.BAD_REQUEST: ErrorMapping(
        ConfluenceBadRequestException, "A validation exception has occurred."
    ),
    ConfluenceErrorCode.UNAUTHORIZED: ErrorMapping(
        ConfluenceUnauthorizedException, "Invalid authorization credentials."
    ),
    ConfluenceErrorCode.FORBIDDEN: ErrorMapping(
        ConfluenceForbiddenException,
        "User does not have permission to access the resource.",
    ),
    ConfluenceErrorCode.NOT_FOUND: ErrorMapping(
        ConfluenceNotFoundException,
        "The resource you have specified cannot be found.",
    ),
    ConfluenceErrorCode.CONFLICT: ErrorMapping(
        ConfluenceConflictException,
        "The request does not match our state in some way.",
    ),
    ConfluenceErrorCode.RATE_LIMIT: ErrorMapping(
        ConfluenceRateLimitException,
        "The API rate limit for your organisation/application pairing has been exceeded.",
    ),
    ConfluenceErrorCode.SUB_REQUEST_FAILED: ErrorMapping(
        ConfluenceSubRequestFailedException,
        "The API was unable to process every part of the request.",
    ),
    ConfluenceErrorCode.INTERNAL_SERVER_ERROR: ErrorMapping(
        ConfluenceInternalServerException,
        "The server encountered an unexpected condition which prevented it from fulfilling the request.",
    ),
    ConfluenceErrorCode.NOT_IMPLEMENTED: ErrorMapping(
        ConfluenceNotImplementedException,
        "The server does not support the functionality required to fulfill the request.",
    ),
    ConfluenceErrorCode.BAD_GATEWAY: ErrorMapping(
        ConfluenceBadGatewayException, "Server received an invalid response."
    ),
    ConfluenceErrorCode.SERVICE_UNAVAILABLE: ErrorMapping(
        ConfluenceServiceUnavailableException,
        "API service is currently unavailable.",
    ),
    ConfluenceErrorCode.GATEWAY_TIMEOUT: ErrorMapping(
        ConfluenceGatewayTimeoutException,
        "API service time out, please check Confluence server.",
    ),
}


def raise_for_error(response: Response) -> None:
    if response.status_code < 400:
        return

    try:
        error_code = ConfluenceErrorCode(response.status_code)
        error_mapping = ERROR_MAPPINGS[error_code]
    except ValueError:
        # Unknown status code, use generic exception
        error_mapping = ErrorMapping(
            ConfluenceClientException, "Unknown error occurred."
        )

    try:
        response_json = response.json()
        error_messages = response_json.get("errorMessages", [])
        api_error_message = error_messages[0] if error_messages else None
    except Exception:  # pylint:disable=broad-except
        api_error_message = None

    message = (
        f"HTTP Code: {response.status_code}, "
        f"Error: {api_error_message or error_mapping.default_message}"
    )

    raise error_mapping.exception_class(message, response)
