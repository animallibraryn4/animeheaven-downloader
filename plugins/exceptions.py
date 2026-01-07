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

# Add the missing exceptions that are imported in scraper.py
class SourceError(Exception):
    """Raised when there's an error with an anime source"""
    pass

class NoResultsFound(Exception):
    """Raised when no search results are found"""
    pass
