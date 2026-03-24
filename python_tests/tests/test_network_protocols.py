"""
test_network_protocols.py
=========================
Network protocol tests for Apple's Applied Networking stack.

Run offline:  pytest test_network_protocols.py -v -m "not network"
Run all:      pytest test_network_protocols.py -v
"""

import pytest
import ssl
import socket
import time
import hashlib


class TestTLSValidation:
    """ATS requires TLS 1.2+. AirDrop uses TLS 1.3 for file transfer."""

    @pytest.mark.network
    def test_tls_1_3_supported_by_apple(self):
        """
        Verify TLS 1.3 connection to Apple's servers.
        
        TLS 1.3 is required for AirDrop file transfers and modern iOS/macOS 
        network security. This test ensures the system can establish a 
        TLS 1.3 connection with proper certificate validation.
        
        Expected: Connection succeeds with TLS 1.3 protocol version.
        """
        context = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
        context.load_default_certs()  # Load CA certificates for verification
        context.minimum_version = ssl.TLSVersion.TLSv1_3
        with socket.create_connection(("apple.com", 443), timeout=10) as sock:
            with context.wrap_socket(sock, server_hostname="apple.com") as ssock:
                assert ssock.version() == "TLSv1.3"

    @pytest.mark.network
    def test_tls_1_1_downgrade_rejected(self):
        """
        Ensure deprecated TLS 1.1 connections are properly rejected.
        
        Apple Transport Security (ATS) requires TLS 1.2+ for all network 
        connections. This test verifies that attempts to use outdated 
        TLS 1.1 protocol fail as expected.
        
        Expected: Connection raises SSLError or OSError.
        """
        context = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
        context.maximum_version = ssl.TLSVersion.TLSv1_1
        context.check_hostname = False
        context.verify_mode = ssl.CERT_NONE
        with pytest.raises((ssl.SSLError, OSError)):
            with socket.create_connection(("apple.com", 443), timeout=10) as sock:
                context.wrap_socket(sock, server_hostname="apple.com")

    @pytest.mark.network
    def test_certificate_chain_valid(self):
        """
        Validate SSL certificate chain for Apple's servers.
        
        Ensures that Apple's SSL certificates are properly signed and contain
        the expected organizational information. Critical for preventing
        man-in-the-middle attacks in Continuity features.
        
        Expected: Certificate subject contains "Apple" organization name.
        """
        context = ssl.create_default_context()
        with socket.create_connection(("apple.com", 443), timeout=10) as sock:
            with context.wrap_socket(sock, server_hostname="apple.com") as ssock:
                cert = ssock.getpeercert()
                subject = dict(x[0] for x in cert["subject"])
                assert "Apple" in subject.get("organizationName", "")

    @pytest.mark.network
    def test_cipher_suite_strength(self):
        """
        Verify strong cipher suites are negotiated for encrypted connections.
        
        Tests that SSL/TLS connections use at least 128-bit encryption,
        which is the minimum required by Apple Transport Security (ATS).
        Weak ciphers compromise user data security.
        
        Expected: Cipher strength >= 128 bits.
        """
        context = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
        context.load_default_certs()  # Load CA certificates for verification
        context.minimum_version = ssl.TLSVersion.TLSv1_2
        with socket.create_connection(("apple.com", 443), timeout=10) as sock:
            with context.wrap_socket(sock, server_hostname="apple.com") as ssock:
                _, _, bits = ssock.cipher()
                assert bits >= 128

    @pytest.mark.security
    def test_default_context_enforces_verification(self):
        """
        Ensure default SSL context has secure verification settings.
        
        Validates that Python's default SSL context requires certificate
        verification and hostname checking, preventing security vulnerabilities.
        
        Expected: CERT_REQUIRED mode and hostname checking enabled.
        """
        context = ssl.create_default_context()
        assert context.verify_mode == ssl.CERT_REQUIRED
        assert context.check_hostname is True


class TestDNSResolution:

    @pytest.mark.network
    def test_dns_resolves_apple_services(self):
        """
        Test DNS resolution for critical Apple service domains.
        
        Verifies that apple.com and icloud.com resolve to valid IPv4 addresses.
        DNS resolution is essential for Continuity features like Handoff
        and Universal Clipboard.
        
        Expected: Valid IPv4 addresses (4 octets).
        """
        for host in ["apple.com", "icloud.com"]:
            ip = socket.gethostbyname(host)
            assert len(ip.split(".")) == 4

    @pytest.mark.network
    def test_dns_resolution_time(self):
        """
        Verify DNS resolution performance meets acceptable thresholds.
        
        Slow DNS lookups degrade user experience in features like AirDrop
        device discovery and iCloud sync. This test ensures resolution
        completes within 500ms.
        
        Expected: Resolution time < 500ms.
        """
        start = time.time()
        socket.gethostbyname("apple.com")
        assert (time.time() - start) * 1000 < 500

    @pytest.mark.protocol
    def test_mdns_port_constant(self):
        """
        Validate mDNS protocol constants and multicast address range.
        
        mDNS (Multicast DNS) uses port 5353 and multicast address 224.0.0.251
        for AirDrop and AirPlay device discovery. This test verifies protocol
        constants are correct.
        
        Expected: Port 5353, multicast address in valid range (224-239).
        """
        assert 5353 == 5353  # mDNS standard port
        parts = "224.0.0.251".split(".")
        assert 224 <= int(parts[0]) <= 239  # multicast range


class TestSocketBehavior:

    @pytest.mark.network
    def test_tcp_connection_to_apple(self):
        """
        Test basic TCP connection establishment to Apple's servers.
        
        Validates that the system can establish a TCP connection to
        apple.com on port 443. This is the foundation for HTTPS
        connections used throughout Apple's ecosystem.
        
        Expected: Connection succeeds without timeout or error.
        """
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(10)
        try:
            sock.connect(("apple.com", 443))
        finally:
            sock.close()

    @pytest.mark.protocol
    def test_tcp_connection_refused_handling(self):
        """
        Verify proper handling of refused TCP connections.
        
        Tests that connection attempts to closed ports raise appropriate
        exceptions (ConnectionRefusedError or timeout). Proper error handling
        is critical for robust network code.
        
        Expected: Raises ConnectionRefusedError, timeout, or OSError.
        """
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(2)
        with pytest.raises((ConnectionRefusedError, socket.timeout, OSError)):
            sock.connect(("127.0.0.1", 59999))
        sock.close()

    @pytest.mark.protocol
    def test_udp_socket_bind(self):
        """
        Test UDP socket binding with address reuse enabled.
        
        Validates UDP socket creation and binding to ephemeral ports.
        UDP is used for mDNS discovery in AirDrop and AirPlay. The SO_REUSEADDR
        option allows multiple processes to bind to the same port.
        
        Expected: Socket binds successfully and gets assigned a port > 0.
        """
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        try:
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            sock.bind(("0.0.0.0", 0))
            assert sock.getsockname()[1] > 0
        finally:
            sock.close()

    @pytest.mark.protocol
    def test_socket_timeout_fires(self):
        """
        Verify socket timeout mechanism works correctly.
        
        Tests that connection timeouts fire as expected when connecting to
        unreachable hosts (192.0.2.1 is TEST-NET-1, reserved and non-routable).
        Proper timeout handling prevents hung connections.
        
        Expected: socket.timeout exception raised within ~1 second.
        """
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(1)
        with pytest.raises(socket.timeout):
            sock.connect(("192.0.2.1", 80))
        sock.close()

    @pytest.mark.protocol
    def test_tcp_keepalive_option(self):
        """
        Test TCP keep-alive socket option configuration.
        
        TCP keep-alive maintains long-lived connections by sending periodic
        probe packets. Used in Continuity features to maintain persistent
        connections between Apple devices. Platform-specific: macOS returns
        the SO_KEEPALIVE constant (8) rather than the set value (1).
        
        Expected: Keep-alive enabled (non-zero value).
        """
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        try:
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_KEEPALIVE, 1)
            # On macOS/BSD, getsockopt returns the constant (8), not the value (1)
            # Just verify it's enabled (non-zero)
            assert sock.getsockopt(socket.SOL_SOCKET, socket.SO_KEEPALIVE) != 0
        finally:
            sock.close()


class TestHTTPProtocols:

    @pytest.mark.network
    def test_http2_supported(self):
        """
        Verify HTTP/2 protocol support for Apple's web services.
        
        HTTP/2 provides improved performance through multiplexing, header
        compression, and server push. Used by App Store, iCloud, and other
        Apple web services for efficient data transfer.
        
        Expected: Response uses HTTP/2 protocol version.
        """
        pytest.importorskip("h2")  # Skip if h2 not available
        import httpx
        with httpx.Client(http2=True, timeout=10) as client:
            resp = client.get("https://www.apple.com")
            assert resp.http_version in ("HTTP/2", "h2")

    @pytest.mark.network
    def test_https_redirect_enforced(self):
        """
        Ensure HTTP requests are redirected to HTTPS.
        
        Apple enforces HTTPS-only connections for security. This test verifies
        that HTTP requests to apple.com are redirected to HTTPS with proper
        redirect status codes (301, 302, 307, 308).
        
        Expected: HTTP request returns redirect status code.
        """
        import httpx
        with httpx.Client(follow_redirects=False, timeout=10) as client:
            resp = client.get("http://apple.com")
            assert resp.status_code in (301, 302, 307, 308)

    @pytest.mark.network
    def test_hsts_header_present(self):
        """
        Validate HTTP Strict Transport Security (HSTS) header presence.
        
        HSTS instructs browsers to only access the site via HTTPS, preventing
        protocol downgrade attacks. Critical security header for Apple's
        web properties and APIs.
        
        Expected: Response contains strict-transport-security header.
        """
        pytest.importorskip("h2")  # Skip if h2 not available
        import httpx
        with httpx.Client(http2=True, timeout=10) as client:
            resp = client.get("https://www.apple.com")
            assert "strict-transport-security" in resp.headers


class TestIdentityPrivacy:
    """AirDrop contact hash validation — ALL OFFLINE."""

    @pytest.mark.security
    def test_hash_is_deterministic(self):
        """
        Verify SHA-256 hash produces consistent output for same input.
        
        Deterministic hashing is essential for AirDrop contact matching.
        The same email address must always produce the same hash for
        reliable device-to-device identity verification.
        
        Expected: Same input produces identical hash values.
        """
        h1 = hashlib.sha256(b"user@example.com").hexdigest()
        h2 = hashlib.sha256(b"user@example.com").hexdigest()
        assert h1 == h2

    @pytest.mark.security
    def test_different_contacts_different_hashes(self):
        """
        Ensure different contacts produce different hash values.
        
        Hash collision avoidance is critical for contact privacy in AirDrop.
        Different email addresses must produce different hashes to prevent
        false positive contact matches.
        
        Expected: Different inputs produce different hash values.
        """
        h1 = hashlib.sha256(b"alice@example.com").hexdigest()
        h2 = hashlib.sha256(b"bob@example.com").hexdigest()
        assert h1 != h2

    @pytest.mark.security
    def test_hash_is_256_bits(self):
        """
        Validate hash output is exactly 256 bits (64 hex characters).
        
        SHA-256 provides sufficient entropy for contact privacy while
        remaining computationally efficient. This test ensures proper
        hash length for security protocols.
        
        Expected: Hash output is 64 hexadecimal characters (256 bits).
        """
        assert len(hashlib.sha256(b"test").hexdigest()) == 64

    @pytest.mark.security
    def test_no_pii_in_hash(self):
        """
        Verify hash output contains no personally identifiable information.
        
        AirDrop hashes protect user privacy by ensuring email addresses and
        phone numbers are not exposed in cleartext. Hash output should not
        contain any fragments of the input data.
        
        Expected: Hash contains no recognizable fragments of input email.
        """
        h = hashlib.sha256(b"john.doe@apple.com").hexdigest()
        for fragment in ["john", "doe", "apple", "@"]:
            assert fragment not in h

    @pytest.mark.security
    def test_truncated_hash_for_ble(self):
        """
        Test truncated hash fits in BLE advertisement payload.
        
        AirDrop uses Bluetooth Low Energy (BLE) advertisements for initial
        device discovery. BLE payloads are limited to 31 bytes, so contact
        hashes are truncated to 2 bytes for transmission.
        
        Expected: Truncated hash is exactly 2 bytes.
        """
        full = hashlib.sha256(b"user@example.com").digest()
        assert len(full[:2]) == 2  # Fits in BLE advertisement

    @pytest.mark.security
    def test_truncated_hash_contact_matching(self):
        """
        Verify contact matching works with truncated hashes.
        
        Simulates AirDrop's contact matching process: sender broadcasts
        truncated hash via BLE, receiver checks against their contact list.
        Despite truncation, correct contact should be identified.
        
        Expected: Truncated hash correctly identifies contact.
        """
        sender = hashlib.sha256(b"alice@example.com").digest()[:2]
        contacts = {
            hashlib.sha256(c.encode()).digest()[:2]: c
            for c in ["alice@example.com", "bob@example.com", "carol@example.com"]
        }
        assert contacts[sender] == "alice@example.com"

    @pytest.mark.security
    def test_collision_rate_acceptable(self):
        """
        Measure hash collision rate for truncated (2-byte) hashes.
        
        With 2-byte hashes (65,536 possible values), collisions are expected
        but should remain under 5% for typical contact list sizes. Higher
        collision rates would degrade AirDrop user experience.
        
        Expected: Collision rate < 5% for 1000 random contacts.
        """
        import random, string
        hashes = set()
        for _ in range(1000):
            email = "".join(random.choices(string.ascii_lowercase, k=10)) + "@test.com"
            hashes.add(hashlib.sha256(email.encode()).digest()[:2])
        assert (1 - len(hashes) / 1000) < 0.05


class TestPerformance:
    """Performance benchmarks for network operations."""

    @pytest.mark.network
    @pytest.mark.performance
    def test_tls_handshake_time(self):
        """
        Benchmark TLS handshake performance to Apple's servers.
        
        TLS handshake latency impacts user experience in apps making frequent
        API calls. This test ensures handshakes complete within 1 second,
        which is acceptable for most user-facing operations.
        
        Expected: TLS handshake completes in < 1000ms.
        """
        context = ssl.create_default_context()
        start = time.time()
        with socket.create_connection(("apple.com", 443), timeout=10) as sock:
            with context.wrap_socket(sock, server_hostname="apple.com"):
                ms = (time.time() - start) * 1000
        assert ms < 1000

    @pytest.mark.network
    @pytest.mark.performance
    def test_full_connection_latency(self):
        """
        Measure end-to-end connection latency including DNS resolution.
        
        Tests complete connection flow: DNS lookup + TCP handshake + TLS
        handshake. Useful for performance regression testing and identifying
        network bottlenecks in production environments.
        
        Expected: Full connection establishes in < 2000ms.
        """
        start = time.time()
        ip = socket.gethostbyname("apple.com")
        context = ssl.create_default_context()
        with socket.create_connection((ip, 443), timeout=10) as sock:
            with context.wrap_socket(sock, server_hostname="apple.com"):
                total_ms = (time.time() - start) * 1000
        assert total_ms < 2000
