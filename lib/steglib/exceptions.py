"""stegOS specific exceptions."""

class StegosError(Exception):
    """Base exception for all stegOS errors."""
    pass

class BackendError(StegosError):
    """Base exception for backend runtime errors."""
    def __init__(self, message, details=None):
        super().__init__(message)
        self.message = message
        self.details = details
        
    def __str__(self):
        return self.message

class InsufficientSpaceError(BackendError):
    """Raised when the backend runs out of disk space."""
    pass

class PortConflictError(BackendError):
    """Raised when the backend fails to bind a port due to a conflict."""
    pass

class NetworkNotFoundError(BackendError):
    """Raised when a required network is not found by the backend."""
    pass
