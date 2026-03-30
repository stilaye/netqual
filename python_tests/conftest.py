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

import os
import pytest
import logging
import time
import ssl
import socket
from typing import Dict, Any, Generator
from pathlib import Path
import json

from utils.network_conditioner import ComcastConditioner, NLCConditioner


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
    config.addinivalue_line(
        "markers", "requires_sudo: tests that need sudo privileges (comcast/pfctl)"
    )
    
    # Set up logging — level overridable via --log-level or TEST_LOG_LEVEL env var
    log_level_str = os.getenv("TEST_LOG_LEVEL", "INFO").upper()
    log_level = getattr(logging, log_level_str, logging.INFO)
    logging.basicConfig(
        level=log_level,
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
    markers = [mark.name for mark in item.iter_markers()]

    # Skip network tests if --offline flag is present
    if "network" in markers:
        if item.config.getoption("--offline", default=False):
            pytest.skip("Skipping network test in offline mode")

    # Skip sudo-required tests if --no-sudo flag is present
    if "requires_sudo" in markers:
        if item.config.getoption("--no-sudo", default=False):
            pytest.skip("Skipping sudo-required test (--no-sudo)")


def pytest_addoption(parser):
    """
    Add custom command-line options to pytest.
    """
    parser.addoption(
        "--offline",
        action="store_true",
        default=os.getenv("TEST_OFFLINE", "").lower() == "true",
        help="Skip tests that require network connectivity [env: TEST_OFFLINE=true]"
    )
    parser.addoption(
        "--env",
        action="store",
        default=os.getenv("TEST_ENV", "test"),
        help="Target environment: test, staging, production [env: TEST_ENV]"
    )
    parser.addoption(
        "--generate-report",
        action="store_true",
        default=False,
        help="Generate detailed test report"
    )
    parser.addoption(
        "--no-sudo",
        action="store_true",
        default=os.getenv("TEST_NO_SUDO", "").lower() == "true",
        help="Skip tests that require sudo privileges [env: TEST_NO_SUDO=true]"
    )
    parser.addoption(
        "--test-log-level",
        action="store",
        default=os.getenv("TEST_LOG_LEVEL", "INFO"),
        help="Framework log level: DEBUG, INFO, WARNING, ERROR [env: TEST_LOG_LEVEL]"
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

    Resolution order (first match wins):
      1. External JSON file at path set by TEST_CONFIG_FILE env var
      2. Individual env var overrides (TEST_API_BASE_URL, TEST_TIMEOUT, etc.)
      3. Built-in defaults per environment

    Usage:
        def test_api(test_config):
            api_url = test_config['api_base_url']
    """
    defaults: Dict[str, Dict[str, Any]] = {
        "test": {
            "api_base_url":     "https://test-api.example.com",
            "timeout":          10,
            "network_timeout":  10,
            "retry_count":      3,
            "ssl_verify":       True,
        },
        "staging": {
            "api_base_url":     "https://staging-api.example.com",
            "timeout":          15,
            "network_timeout":  15,
            "retry_count":      2,
            "ssl_verify":       True,
        },
        "production": {
            "api_base_url":     "https://api.example.com",
            "timeout":          30,
            "network_timeout":  30,
            "retry_count":      5,
            "ssl_verify":       True,
        },
    }

    # 1. External config file
    config_file = Path(os.getenv("TEST_CONFIG_FILE", ""))
    if config_file.is_file():
        try:
            file_config = json.loads(config_file.read_text())
            if test_environment in file_config:
                return file_config[test_environment]
        except (json.JSONDecodeError, KeyError) as exc:
            logging.warning("Could not load TEST_CONFIG_FILE: %s", exc)

    # 2. Start from built-in defaults, apply env var overrides
    cfg = dict(defaults.get(test_environment, defaults["test"]))
    if os.getenv("TEST_API_BASE_URL"):
        cfg["api_base_url"] = os.environ["TEST_API_BASE_URL"]
    if os.getenv("TEST_TIMEOUT"):
        cfg["timeout"] = int(os.environ["TEST_TIMEOUT"])
        cfg["network_timeout"] = int(os.environ["TEST_TIMEOUT"])
    if os.getenv("TEST_NETWORK_TIMEOUT"):
        cfg["network_timeout"] = int(os.environ["TEST_NETWORK_TIMEOUT"])
    if os.getenv("TEST_RETRY_COUNT"):
        cfg["retry_count"] = int(os.environ["TEST_RETRY_COUNT"])
    return cfg


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

@pytest.fixture
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


# ============================================================
# Network Conditioning Fixtures
# ============================================================

@pytest.fixture
def comcast_conditioner() -> ComcastConditioner:
    """
    Provide a ComcastConditioner instance for system-wide network simulation.

    Wraps the `comcast` CLI (pfctl + dnctl under the hood) to apply 3G / 4G /
    5G / lossy / high-latency profiles to the entire machine interface.

    Requirements:
        brew install comcast   (one-time setup)
        sudo privileges at runtime

    Usage:
        @pytest.mark.requires_sudo
        @pytest.mark.network
        def test_airdrop_on_3g(comcast_conditioner):
            with comcast_conditioner.profile("3g"):
                # test runs under 1 Mbps / 200 ms / 2% loss
                ...
    """
    conditioner = ComcastConditioner()
    yield conditioner
    conditioner.restore()   # safety net — restores even if test forgot to


@pytest.fixture
def nlc_conditioner() -> NLCConditioner:
    """
    Provide an NLCConditioner instance for Network Link Conditioner profile
    generation and validation.

    NLC has no public CLI to toggle on/off, so this fixture handles profile
    creation and plist validation only. To apply a profile:
      1. Use nlc_conditioner.write_profile(PROFILES["3g"], path)
      2. Import the plist in the NLC preference pane and enable it manually.

    Usage:
        def test_nlc_profile_structure(nlc_conditioner, tmp_path):
            path = nlc_conditioner.write_profile(PROFILES["4g"], tmp_path / "4g.plist")
            assert nlc_conditioner.validate_profile(nlc_conditioner.load_profile(path))
    """
    return NLCConditioner()
