"""Centralized application error handling."""

import logging

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from sqlalchemy.exc import SQLAlchemyError, TimeoutError as SQLAlchemyTimeoutError
from starlette.exceptions import HTTPException

logger = logging.getLogger(__name__)


class AppError(Exception):
    """Base class for application-specific errors."""
    def __init__(
        self,
        status: int,
        message: str,
        code: str = "APPLICATION_ERROR",
    ) -> None:
        super().__init__(message)
        self.status = status
        self.message = message
        self.code = code


class ErrorHandler:
    """Centralized error handler for the FastAPI application."""
    @staticmethod
    def register(app: FastAPI) -> None:
        """Register global exception handlers."""

        app.add_exception_handler(AppError, ErrorHandler.application)
        app.add_exception_handler(RequestValidationError, ErrorHandler.validation)
        app.add_exception_handler(HTTPException, ErrorHandler.http)
        app.add_exception_handler(SQLAlchemyError, ErrorHandler.database)
        app.add_exception_handler(Exception, ErrorHandler.unexpected)

    @staticmethod
    async def application( _: Request, error: Exception ) -> JSONResponse:
        """Handle application-specific errors."""

        # Ensure the error is an instance of AppError before handling it
        if not isinstance(error, AppError):
            raise error

        logger.error( "Application error: %s", type(error).__name__ )
        
        # Set the WWW-Authenticate header for 401 Unauthorized errors if needed
        headers = (
            {"WWW-Authenticate": "Bearer"}
            if error.status == 401
                else None
        )

        return JSONResponse(
            { "code": error.code, "message": error.message },
            status_code=error.status,
            headers=headers,
        )

    @staticmethod
    async def validation( _ : Request, error: Exception ) -> JSONResponse:
        """Handle request validation errors."""

        # Ensure the error is an instance of RequestValidationError before handling it
        if not isinstance(error, RequestValidationError):
            raise error

        logger.error( "Validation error: %s", type(error).__name__ )

        # Extract validation error details for the response
        details = [
            { "location": list(item["loc"]), "code": item["type"] }
            for item in error.errors()
        ]

        return JSONResponse(
            {
                "code": "VALIDATION_ERROR",
                "message": "Validation failed",
                "errors": details,
            },
            status_code=422,
        )

    @staticmethod
    async def http( _: Request, error: Exception ) -> JSONResponse:
        """Handle HTTP exceptions."""

        # Ensure the error is an instance of HTTPException before handling it
        if not isinstance(error, HTTPException):
            raise error

        logger.error( "HTTP error: %s", type(error).__name__ )

        codes = {
            400: "BAD_REQUEST",
            401: "UNAUTHORIZED",
            403: "FORBIDDEN",
            404: "NOT_FOUND",
            405: "METHOD_NOT_ALLOWED",
            409: "CONFLICT",
            429: "TOO_MANY_REQUESTS",
        }

        return JSONResponse(
            {
                "code": codes.get(error.status_code, "HTTP_ERROR"),
                "message": (
                    error.detail
                    if isinstance(error.detail, str)
                    else "HTTP request failed"
                ),
            },
            status_code=error.status_code,
            headers=error.headers,
        )

    @staticmethod
    async def database( _: Request, error: Exception ) -> JSONResponse:
        """Handle database errors."""

        if isinstance(error, SQLAlchemyTimeoutError):
            logger.error( "Database unavailable error: %s", type(error).__name__ )
            return JSONResponse(
                {
                    "code": "DATABASE_UNAVAILABLE",
                    "message": "Database temporarily unavailable",
                },
                status_code=503,
            )

        # Ensure the error is an instance of SQLAlchemyError before handling it
        if not isinstance(error, SQLAlchemyError):
            raise error

        logger.error( "Database error: %s", type(error).__name__ )

        return JSONResponse(
            { "code": "DATABASE_ERROR", "message": "Internal server error" },
            status_code=500,
        )

    @staticmethod
    async def unexpected(_: Request, error: Exception ) -> JSONResponse:
        """Handle unexpected errors."""
        logger.error( "Unhandled application error: %s", type(error).__name__ )

        return JSONResponse(
            { "code": "INTERNAL_ERROR", "message": "Internal server error" },
            status_code=500,
        )

