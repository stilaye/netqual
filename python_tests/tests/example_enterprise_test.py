"""
example_enterprise_test.py
==========================
Example test file demonstrating enterprise framework features.

This shows how to use:
- Fixtures from conftest.py
- Utilities from utils/
- Test data factories
- Custom markers
- Performance monitoring
- Proper docstrings
"""

import pytest
import socket
from utils.network_helpers import (
    ConnectionHelper, 
    SSLValidator,
    is_network_available,
    NetworkPerformanceMonitor
)
from utils.test_data_factory import ContactFactory, NetworkDataFactory


# ============================================================
# Example 1: Using Built-in Fixtures
# ============================================================

class TestUsingFixtures:
    """Demonstrate usage of fixtures from conftest.py."""
    
    @pytest.mark.network
    def test_with_ssl_context(self, ssl_context, logger):
        """
        Test using shared SSL context fixture.
        
        The ssl_context fixture is session-scoped and provides a
        properly configured SSL context with certificate validation.
        """
        logger.info("Testing SSL connection with shared fixture")
        
        with socket.create_connection(("apple.com", 443), timeout=10) as sock:
            with ssl_context.wrap_socket(sock, server_hostname="apple.com") as ssock:
                version = ssock.version()
                logger.info(f"Connected with {version}")
                assert version in ["TLSv1.3", "TLSv1.2"]
    
    def test_with_tcp_socket(self, tcp_socket, logger):
        """
        Test using TCP socket fixture with automatic cleanup.
        
        The tcp_socket fixture provides a socket that's automatically
        closed after the test completes.
        """
        logger.info("Testing TCP connection")
        tcp_socket.connect(("apple.com", 443))
        assert tcp_socket.getpeername()[1] == 443
    
    def test_with_environment_config(self, test_config, test_environment, logger):
        """
        Test using environment-specific configuration.
        
        Demonstrates how to access configuration that changes based on
        the --env command line flag (test/staging/production).
        """
        logger.info(f"Running in {test_environment} environment")
        api_url = test_config['api_base_url']
        timeout = test_config['timeout']
        
        assert api_url.startswith("https://")
        assert timeout > 0
        
        logger.debug(f"API URL: {api_url}, Timeout: {timeout}s")


# ============================================================
# Example 2: Using Network Helpers
# ============================================================

class TestNetworkHelpers:
    """Demonstrate network utility functions."""
    
    @pytest.mark.network
    def test_connection_with_retry(self, logger):
        """
        Test connection with automatic retry logic.
        
        The ConnectionHelper provides robust connection handling with
        configurable retry attempts and delays.
        """
        helper = ConnectionHelper(retry_count=3, retry_delay=1.0)
        
        success, sock, error = helper.connect_with_retry("apple.com", 443)
        
        assert success, f"Connection failed: {error}"
        assert sock is not None
        
        logger.info("Connection successful with retry logic")
        sock.close()
    
    @pytest.mark.network
    def test_managed_connection(self):
        """
        Test using managed connection context manager.
        
        Demonstrates automatic connection cleanup even if test fails.
        """
        helper = ConnectionHelper()
        
        with helper.managed_connection("apple.com", 443) as sock:
            # Socket is automatically managed
            peer = sock.getpeername()
            assert peer[0]  # Should have peer IP address
            assert peer[1] == 443
        
        # Socket is automatically closed here
    
    @pytest.mark.network
    def test_ssl_certificate_inspection(self, logger):
        """
        Test SSL certificate information retrieval.
        
        Shows how to inspect certificate details for validation.
        """
        cert_info = SSLValidator.get_certificate_info("apple.com")
        
        assert cert_info is not None
        assert "Apple" in cert_info['subject'].get('organizationName', '')
        assert cert_info['tls_version'] in ['TLSv1.3', 'TLSv1.2']
        
        logger.info(f"Certificate issuer: {cert_info['issuer']}")
        logger.info(f"TLS version: {cert_info['tls_version']}")
    
    @pytest.mark.network
    @pytest.mark.security
    def test_cipher_strength_validation(self):
        """
        Test cipher strength meets security requirements.
        
        Validates that connections use strong encryption (>= 128 bits).
        Critical for security compliance testing.
        """
        passes, cipher_info = SSLValidator.verify_cipher_strength(
            "apple.com",
            min_bits=128
        )
        
        assert passes, f"Weak cipher: {cipher_info}"
        assert cipher_info['bits'] >= 128
        assert cipher_info['tls_protocol'] in ['TLSv1.3', 'TLSv1.2']
    
    def test_with_network_check(self, skip_if_no_network):
        """
        Test that automatically skips if network is unavailable.
        
        Uses the skip_if_no_network fixture to gracefully handle
        offline environments.
        """
        # This test will be skipped if network is down
        result = is_network_available()
        assert result is True


# ============================================================
# Example 3: Using Test Data Factories
# ============================================================

class TestDataFactories:
    """Demonstrate test data generation utilities."""
    
    @pytest.mark.security
    @pytest.mark.skip(reason="skipped on request")
    def test_contact_hash_generation(self):
        """
        Test contact hashing using factory-generated data.
        
        Demonstrates generating realistic test contacts and validating
        hash properties for AirDrop contact matching.
        """
        # Generate 100 test contacts
        contacts = ContactFactory.create_contacts(100)
        
        assert len(contacts) == 100
        
        # Verify all contacts have valid email addresses
        for contact in contacts:
            assert "@" in contact.email
            assert "." in contact.email.split("@")[1]
        
        # Verify hashes are unique
        hashes = {contact.get_email_hash() for contact in contacts}
        assert len(hashes) == 100, "Hash collision detected in factory data"
    
    @pytest.mark.security
    def test_truncated_hash_collision_rate(self):
        """
        Test hash collision rate for truncated hashes.
        
        Simulates AirDrop's 2-byte truncated hash system and validates
        that collision rates remain acceptable.
        """
        from utils.test_data_factory import HashDataFactory
        
        # Generate hash collision test set
        hash_map = HashDataFactory.create_hash_collision_test_set(1000)
        
        # Calculate collision rate
        collision_rate = HashDataFactory.calculate_collision_rate(hash_map)
        
        # Should be less than 5% for 1000 contacts
        assert collision_rate < 0.05, \
            f"Collision rate too high: {collision_rate:.2%}"
    
    @pytest.mark.network
    def test_network_endpoint_generation(self, logger):
        """
        Test using factory-generated network endpoints.
        
        Shows how to use NetworkDataFactory for generating test endpoints.
        """
        # Generate Apple service endpoints
        apple_endpoints = NetworkDataFactory.create_apple_test_endpoints()
        
        assert len(apple_endpoints) > 0
        
        for endpoint in apple_endpoints:
            logger.debug(f"Testing endpoint: {endpoint}")
            assert endpoint.port == 443
            assert endpoint.protocol == "https"
            assert endpoint.expected_reachable is True


# ============================================================
# Example 4: Performance Monitoring
# ============================================================

class TestPerformanceMonitoring:
    """Demonstrate performance measurement capabilities."""
    
    @pytest.mark.network
    @pytest.mark.performance
    def test_with_performance_monitor(self, logger):
        """
        Test using NetworkPerformanceMonitor for operation tracking.
        
        Demonstrates how to measure and track performance of network
        operations with automatic statistics collection.
        """
        monitor = NetworkPerformanceMonitor()
        
        # Measure DNS lookup
        dns_result = monitor.measure_operation(
            "DNS Lookup",
            socket.gethostbyname,
            "apple.com"
        )
        
        assert dns_result['success']
        assert dns_result['duration_ms'] < 1000
        logger.info(f"DNS lookup took {dns_result['duration_ms']:.2f}ms")
        
        # Measure TCP connection
        def connect_tcp():
            sock = socket.create_connection(("apple.com", 443), timeout=10)
            sock.close()
        
        conn_result = monitor.measure_operation(
            "TCP Connection",
            connect_tcp
        )
        
        assert conn_result['success']
        logger.info(f"TCP connection took {conn_result['duration_ms']:.2f}ms")
        
        # Get statistics
        stats = monitor.get_statistics()
        logger.info(f"Performance statistics: {stats}")
        
        assert stats['total_operations'] == 2
        assert stats['successful_operations'] == 2
    
    @pytest.mark.performance
    def test_with_measure_time_fixture(self, measure_time, logger):
        """
        Test using measure_time fixture for timing code blocks.
        
        Shows simpler timing mechanism for individual operations.
        """
        import time
        
        with measure_time("Test Operation") as timer:
            # Simulate some work
            time.sleep(0.1)
        
        logger.info(f"Operation took {timer.elapsed_ms:.2f}ms")
        assert timer.elapsed_ms >= 100  # At least 100ms


# ============================================================
# Example 5: Parametrized Tests
# ============================================================

class TestParametrizedScenarios:
    """Demonstrate parametrized testing for multiple scenarios."""
    
    @pytest.mark.parametrize("host,port,should_connect", [
        ("apple.com", 443, True),
        ("icloud.com", 443, True),
        ("192.0.2.1", 80, False),  # TEST-NET-1, should be unreachable
    ])
    @pytest.mark.network
    def test_multiple_endpoints(self, host, port, should_connect, logger):
        """
        Test multiple endpoints with different expected outcomes.
        
        Parametrized testing allows testing multiple scenarios with
        the same test logic, improving coverage efficiency.
        """
        logger.info(f"Testing {host}:{port}")
        
        try:
            sock = socket.create_connection((host, port), timeout=5)
            sock.close()
            connected = True
        except (socket.timeout, OSError):
            connected = False
        
        assert connected == should_connect, \
            f"Connection to {host}:{port} {'failed' if should_connect else 'succeeded'} unexpectedly"
    
    @pytest.mark.parametrize("email", [
        "alice@example.com",
        "bob.smith@test.com",
        "charlie+tag@demo.org",
    ])
    @pytest.mark.security
    def test_hash_determinism(self, email):
        """
        Test hash determinism with various email formats.
        
        Ensures hashing is consistent across different input patterns.
        """
        import hashlib
        
        hash1 = hashlib.sha256(email.encode()).hexdigest()
        hash2 = hashlib.sha256(email.encode()).hexdigest()
        
        assert hash1 == hash2, "Hash function is not deterministic"


# ============================================================
# Example 6: Mock & Stub Testing
# ============================================================

class TestMockingFeatures:
    """Demonstrate mocking capabilities."""
    
    def test_with_mock_network_unavailable(self, mock_network_unavailable):
        """
        Test offline behavior using network mock.
        
        The mock_network_unavailable fixture simulates network failure
        without requiring actual network disconnection.
        """
        with pytest.raises(ConnectionError, match="Network unavailable"):
            socket.create_connection(("example.com", 80))
    
    def test_with_monkeypatch(self, monkeypatch):
        """
        Test using monkeypatch for runtime patching.
        
        Demonstrates how to temporarily replace functions for testing.
        """
        def mock_gethostbyname(hostname):
            return "192.0.2.1"
        
        monkeypatch.setattr(socket, "gethostbyname", mock_gethostbyname)
        
        result = socket.gethostbyname("any-hostname.com")
        assert result == "192.0.2.1"


# ============================================================
# Example 7: Test Organization & Markers
# ============================================================

@pytest.mark.smoke
@pytest.mark.network
def test_critical_connectivity():
    """
    Critical smoke test for basic connectivity.
    
    Part of smoke test suite that runs before full test suite.
    Marked as both 'smoke' and 'network' for flexible test selection.
    
    Run with: pytest -m smoke
    """
    sock = socket.create_connection(("8.8.8.8", 53), timeout=5)
    sock.close()


@pytest.mark.slow
@pytest.mark.integration
def test_full_integration_flow():
    """
    Slow integration test covering full workflow.
    
    Can be excluded from quick test runs using: pytest -m "not slow"
    """
    import time
    time.sleep(2)  # Simulate slow operation
    # ... full integration test logic


if __name__ == "__main__":
    # Allow running this file directly for quick testing
    pytest.main([__file__, "-v", "-s"])
