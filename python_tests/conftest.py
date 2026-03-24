"""
conftest.py
===========
Pytest configuration and shared fixtures for enterprise test framework.

This file is automatically discovered by pytest and provides:
- Shared fixtures across all test modules
- Custom pytest hooks for enhanced reporting
- Test environment configuration
- Reusable test utilities

Place this at the root of your test directory.
"""

import pytest
import logging
import time
import ssl
import socket
from typing import Dict, Any, Generator
from pathlib import Path
import json


# ============================================================
# Pytest Configuration Hooks
# ============================================================

def pytest_configure(config):
    """
    Configure pytest with custom markers and settings.
    Called once before test collection begins.
    """
    # Register custom markers
    config.addinivalue_line(
        "markers", "network: tests that require network connectivity"
    )
    config.addinivalue_line(
        "markers", "security: security-focused tests"
    )
    config.addinivalue_line(
        "markers", "protocol: low-level protocol tests"
    )
    config.addinivalue_line(
        "markers", "performance: performance benchmark tests"
    )
    config.addinivalue_line(
        "markers", "slow: tests that take significant time to run"
    )
    config.addinivalue_line(
        "markers", "integration: integration tests requiring multiple components"
    )
    
    # Set up logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )


def pytest_collection_modifyitems(config, items):
    """
    Modify test collection to add markers automatically based on test names.
    """
    for item in items:
        # Auto-mark slow tests
        if "slow" in item.nodeid.lower():
            item.add_marker(pytest.mark.slow)
        
        # Auto-mark integration tests
        if "integration" in item.nodeid.lower():
            item.add_marker(pytest.mark.integration)


def pytest_runtest_setup(item):
    """
    Hook called before each test runs.
    Use for environment validation or setup.
    """
    # Skip network tests if --offline flag is present
    if "network" in [mark.name for mark in item.iter_markers()]:
        if item.config.getoption("--offline", default=False):
            pytest.skip("Skipping network test in offline mode")


def pytest_addoption(parser):
    """
    Add custom command-line options to pytest.
    """
    parser.addoption(
        "--offline",
        action="store_true",
        default=False,
        help="Skip tests that require network connectivity"
    )
    parser.addoption(
        "--env",
        action="store",
        default="test",
        help="Test environment: test, staging, production"
    )
    parser.addoption(
        "--generate-report",
        action="store_true",
        default=False,
        help="Generate detailed test report"
    )


# ============================================================
# Session-Scoped Fixtures (Setup Once)
# ============================================================

@pytest.fixture(scope="session")
def test_environment(request) -> str:
    """
    Get test environment from command line or default to 'test'.
    
    Usage:
        def test_something(test_environment):
            if test_environment == "production":
                # Use production endpoints
    """
    return request.config.getoption("--env")


@pytest.fixture(scope="session")
def test_config(test_environment) -> Dict[str, Any]:
    """
    Load environment-specific configuration.
    
    Returns:
        Dictionary containing environment-specific config values.
    
    Usage:
        def test_api(test_config):
            api_url = test_config['api_base_url']
    """
    config = {
        "test": {
            "api_base_url": "https://test-api.example.com",
            "timeout": 10,
            "retry_count": 3,
            "ssl_verify": True,
        },
        "staging": {
            "api_base_url": "https://staging-api.example.com",
            "timeout": 15,
            "retry_count": 2,
            "ssl_verify": True,
        },
        "production": {
            "api_base_url": "https://api.example.com",
            "timeout": 30,
            "retry_count": 5,
            "ssl_verify": True,
        }
    }
    return config.get(test_environment, config["test"])


@pytest.fixture(scope="session")
def logger() -> logging.Logger:
    """
    Provide a configured logger for tests.
    
    Usage:
        def test_something(logger):
            logger.info("Test started")
            logger.debug(f"Variable value: {value}")
    """
    logger = logging.getLogger("pytest_framework")
    logger.setLevel(logging.DEBUG)
    return logger


# ============================================================
# Network & SSL Fixtures
# ============================================================

@pytest.fixture(scope="session")
def ssl_context() -> ssl.SSLContext:
    """
    Provide a secure SSL context with proper certificate validation.
    Reusable across all tests requiring SSL/TLS connections.
    
    Usage:
        def test_https_connection(ssl_context):
            with socket.create_connection(("apple.com", 443)) as sock:
                with ssl_context.wrap_socket(sock, server_hostname="apple.com"):
                    # Test logic here
    """
    context = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
    context.load_default_certs()
    context.minimum_version = ssl.TLSVersion.TLSv1_2
    context.check_hostname = True
    context.verify_mode = ssl.CERT_REQUIRED
    return context


@pytest.fixture
def tcp_socket() -> Generator[socket.socket, None, None]:
    """
    Provide a TCP socket with automatic cleanup.
    
    Usage:
        def test_connection(tcp_socket):
            tcp_socket.connect(("example.com", 80))
            # Socket is automatically closed after test
    """
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.settimeout(10)
    try:
        yield sock
    finally:
        sock.close()


@pytest.fixture
def udp_socket() -> Generator[socket.socket, None, None]:
    """
    Provide a UDP socket with automatic cleanup.
    
    Usage:
        def test_udp_communication(udp_socket):
            udp_socket.sendto(data, address)
    """
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    sock.settimeout(5)
    try:
        yield sock
    finally:
        sock.close()


@pytest.fixture
def http_client():
    """
    Provide an HTTP client with automatic cleanup.
    
    Usage:
        def test_api_endpoint(http_client):
            response = http_client.get("https://api.example.com/data")
            assert response.status_code == 200
    """
    try:
        import httpx
    except ImportError:
        pytest.skip("httpx not available")
    
    with httpx.Client(timeout=10, follow_redirects=True) as client:
        yield client


# ============================================================
# Test Data Fixtures
# ============================================================

@pytest.fixture
def sample_email_addresses():
    """
    Provide sample email addresses for contact hashing tests.
    """
    return [
        "alice@example.com",
        "bob@example.com",
        "charlie@example.com",
        "diana@example.com",
        "eve@example.com",
    ]


@pytest.fixture
def apple_test_domains():
    """
    Provide list of Apple domains for network tests.
    """
    return [
        "apple.com",
        "icloud.com",
        "me.com",
        "mac.com",
        "apple-cloudkit.com",
    ]


# ============================================================
# Performance Measurement Fixtures
# ============================================================

@pytest.fixture
def measure_time():
    """
    Measure execution time of test code blocks.
    
    Usage:
        def test_performance(measure_time):
            with measure_time("API Call") as timer:
                # Code to measure
                make_api_call()
            
            assert timer.elapsed_ms < 1000, f"Took {timer.elapsed_ms}ms"
    """
    class Timer:
        def __init__(self, name: str):
            self.name = name
            self.start_time = None
            self.elapsed_ms = None
        
        def __enter__(self):
            self.start_time = time.time()
            return self
        
        def __exit__(self, *args):
            self.elapsed_ms = (time.time() - self.start_time) * 1000
            logging.info(f"{self.name}: {self.elapsed_ms:.2f}ms")
    
    return Timer


# ============================================================
# Test Result Tracking Fixtures
# ============================================================

@pytest.fixture(autouse=True)
def test_result_tracker(request, logger):
    """
    Automatically track test results and execution time.
    Applied to all tests via autouse=True.
    """
    start_time = time.time()
    logger.info(f"Starting test: {request.node.name}")
    
    yield
    
    duration = (time.time() - start_time) * 1000
    logger.info(f"Completed test: {request.node.name} in {duration:.2f}ms")


# ============================================================
# Mock & Stub Fixtures
# ============================================================

@pytest.fixture
def mock_network_unavailable(monkeypatch):
    """
    Mock network unavailability for testing offline behavior.
    
    Usage:
        def test_offline_mode(mock_network_unavailable):
            # Network calls will raise ConnectionError
            with pytest.raises(ConnectionError):
                make_network_request()
    """
    def raise_connection_error(*args, **kwargs):
        raise ConnectionError("Network unavailable (mocked)")
    
    monkeypatch.setattr(socket, "create_connection", raise_connection_error)


# ============================================================
# Cleanup & Teardown Fixtures
# ============================================================

@pytest.fixture
def temp_test_directory(tmp_path):
    """
    Provide a temporary directory for test file operations.
    Automatically cleaned up after test.
    
    Usage:
        def test_file_operations(temp_test_directory):
            test_file = temp_test_directory / "test.txt"
            test_file.write_text("test data")
    """
    return tmp_path


@pytest.fixture(scope="session", autouse=True)
def session_cleanup():
    """
    Perform cleanup operations at the end of the test session.
    """
    yield
    # Cleanup code here (runs after all tests complete)
    logging.info("Test session completed - performing cleanup")


# ============================================================
# Conditional Skip Fixtures
# ============================================================

@pytest.fixture
def skip_if_no_network():
    """
    Skip test if network is unavailable.
    
    Usage:
        def test_online_feature(skip_if_no_network):
            # Test code that requires network
    """
    try:
        socket.create_connection(("8.8.8.8", 53), timeout=3)
    except OSError:
        pytest.skip("Network unavailable")


@pytest.fixture
def require_ssl_support():
    """
    Skip test if SSL/TLS support is insufficient.
    """
    try:
        context = ssl.create_default_context()
        if not hasattr(ssl, 'TLSVersion'):
            pytest.skip("Modern SSL/TLS support unavailable")
    except Exception as e:
        pytest.skip(f"SSL initialization failed: {e}")
