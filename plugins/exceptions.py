class DriverNotFound(Exception):
    """Raised when Selenium driver cannot be found in system"""
    pass

class RequestBlocked(Exception):
    """Raised when Animeheaven blocked the request for abuse"""
    pass

class DownloadError(Exception):
    """Raised when download fails"""
    pass

class InvalidURL(Exception):
    """Raised when URL is invalid"""
    pass
