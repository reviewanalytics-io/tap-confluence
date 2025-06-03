class ConfluenceException(Exception):
    """Base class for all Confluence-related exceptions."""

    def __init__(self, message=None, response=None):
        super().__init__(message)
        self.message = message
        self.response = response
