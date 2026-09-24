"""
Pytest global fixtures for AI Face Analyzer test suite.
"""
import pytest
from app.security.rate_limiter import auth_limiter, scan_limiter


@pytest.fixture(autouse=True)
def reset_rate_limiters():
    """Ensure rate limiters are cleared before each individual test across all suites."""
    auth_limiter.reset()
    scan_limiter.reset()
    yield
    auth_limiter.reset()
    scan_limiter.reset()
