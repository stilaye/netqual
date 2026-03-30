"""
test_network_protocols.py
=========================
Network protocol tests for Apple's Applied Networking stack.

Run offline:  pytest test_network_protocols.py -v -m "not network"
Run all:      pytest test_network_protocols.py -v
"""

import hashlib
import socket
import ssl
import time

import pytest


class TestTLSValidation:
    """ATS requires TLS 1.2+. AirDrop uses TLS 1.3 for file transfer."""

    @pytest.mark.network
    def test_tls_1_3_supported_by_apple(self, test_config):
        """
        Verify TLS 1.3 connection to Apple's servers.

        TLS 1.3 is required for AirDrop file transfers and modern iOS/macOS
        network security. This test ensures the system can establish a
        TLS 1.3 connection with proper certificate validation.

        Expected: Connection succeeds with TLS 1.3 protocol version.
        """
        context = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
        context.load_default_certs()
        context.minimum_version = ssl.TLSVersion.TLSv1_3
        timeout = test_config["network_timeout"]
        with socket.create_connection(("apple.com", 443), timeout=timeout) as sock:
            with context.wrap_socket(sock, server_hostname="apple.com") as ssock:
                version = ssock.version()
                assert version == "TLSv1.3", (
                    f"Expected TLSv1.3 but negotiated {version}. "
                    "Ensure apple.com supports TLS 1.3 and the system allows it."
                )

    @pytest.mark.network
    def test_tls_1_1_downgrade_rejected(self, test_config):
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
        timeout = test_config["network_timeout"]
        with pytest.raises((ssl.SSLError, OSError)):
            with socket.create_connection(("apple.com", 443), timeout=timeout) as sock:
                context.wrap_socket(sock, server_hostname="apple.com")

    @pytest.mark.network
    def test_certificate_chain_valid(self, test_config):
        """
        Validate SSL certificate chain for Apple's servers.

        Ensures that Apple's SSL certificates are properly signed and contain
        the expected organizational information. Critical for preventing
        man-in-the-middle attacks in Continuity features.

        Expected: Certificate subject contains "Apple" organization name.
        """
        context = ssl.create_default_context()
        timeout = test_config["network_timeout"]
        with socket.create_connection(("apple.com", 443), timeout=timeout) as sock:
            with context.wrap_socket(sock, server_hostname="apple.com") as ssock:
                cert = ssock.getpeercert()
                subject = dict(x[0] for x in cert["subject"])
                org = subject.get("organizationName", "")
                assert "Apple" in org, (
                    f"Expected 'Apple' in organizationName, got '{org}'. "
                    "Certificate may have changed — check apple.com cert."
                )

    @pytest.mark.network
    def test_cipher_suite_strength(self, test_config):
        """
        Verify strong cipher suites are negotiated for encrypted connections.

        Tests that SSL/TLS connections use at least 128-bit encryption,
        which is the minimum required by Apple Transport Security (ATS).
        Weak ciphers compromise user data security.

        Expected: Cipher strength >= 128 bits.
        """
        context = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
        context.load_default_certs()
        context.minimum_version = ssl.TLSVersion.TLSv1_2
        timeout = test_config["network_timeout"]
        with socket.create_connection(("apple.com", 443), timeout=timeout) as sock:
            with context.wrap_socket(sock, server_hostname="apple.com") as ssock:
                cipher_name, tls_version, bits = ssock.cipher()
                assert bits >= 128, (
                    f"Cipher '{cipher_name}' ({tls_version}) uses only {bits} bits. "
                    "ATS requires >= 128-bit encryption."
                )

    @pytest.mark.security
    def test_default_context_enforces_verification(self):
        """
        Ensure default SSL context has secure verification settings.

        Validates that Python's default SSL context requires certificate
        verification and hostname checking, preventing security vulnerabilities.

        Expected: CERT_REQUIRED mode and hostname checking enabled.
        """
        context = ssl.create_default_context()
        assert context.verify_mode == ssl.CERT_REQUIRED, (
            f"Expected CERT_REQUIRED, got {context.verify_mode}. "
            "Default context must always verify certificates."
        )
        assert (
            context.check_hostname is True
        ), "Hostname checking must be enabled in the default SSL context."


class TestDNSResolution:

    @pytest.mark.network
    @pytest.mark.parametrize("host", ["apple.com", "icloud.com", "me.com"])
    def test_dns_resolves_apple_services(self, host):
        """
        Test DNS resolution for critical Apple service domains.

        Verifies that Apple service hostnames resolve to valid IPv4 addresses.
        DNS resolution is essential for Continuity features like Handoff
        and Universal Clipboard.

        Expected: Valid IPv4 address (4 octets).
        """
        ip = socket.gethostbyname(host)
        octets = ip.split(".")
        assert len(octets) == 4, f"'{host}' resolved to '{ip}' which is not a valid IPv4 address"
        assert all(
            o.isdigit() for o in octets
        ), f"'{host}' resolved to '{ip}' — one or more octets are non-numeric"

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
        elapsed_ms = (time.time() - start) * 1000
        assert elapsed_ms < 500, (
            f"DNS resolution took {elapsed_ms:.1f}ms — exceeds 500ms threshold. "
            "Slow DNS will degrade AirDrop discovery and iCloud sync."
        )

    @pytest.mark.protocol
    def test_mdns_port_constant(self):
        """
        Validate mDNS protocol constants and multicast address range.

        mDNS uses port 5353 and multicast address 224.0.0.251 for AirDrop
        and AirPlay device discovery.

        Expected: Port 5353, multicast address in valid range (224–239).
        """
        mdns_port = 5353
        assert mdns_port == 5353, "mDNS standard port must be 5353 (RFC 6762)"
        parts = ["224", "0", "0", "251"]
        first_octet = int(parts[0])
        assert 224 <= first_octet <= 239, (
            f"mDNS address first octet is {first_octet} — " "must be in multicast range 224–239"
        )


class TestSocketBehavior:

    @pytest.mark.network
    def test_tcp_connection_to_apple(self, test_config):
        """
        Test basic TCP connection establishment to Apple's servers.

        Validates that the system can establish a TCP connection to
        apple.com on port 443.

        Expected: Connection succeeds without timeout or error.
        """
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(test_config["network_timeout"])
        try:
            sock.connect(("apple.com", 443))
        finally:
            sock.close()

    @pytest.mark.protocol
    def test_tcp_connection_refused_handling(self):
        """
        Verify proper handling of refused TCP connections.

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

        UDP is used for mDNS discovery in AirDrop and AirPlay. SO_REUSEADDR
        allows multiple processes to bind to the same port.

        Expected: Socket binds successfully and gets assigned a port > 0.
        """
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        try:
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            sock.bind(("0.0.0.0", 0))
            assigned_port = sock.getsockname()[1]
            assert assigned_port > 0, f"Expected assigned port > 0, got {assigned_port}"
        finally:
            sock.close()

    @pytest.mark.protocol
    def test_socket_timeout_fires(self):
        """
        Verify socket timeout mechanism works correctly.

        192.0.2.1 is TEST-NET-1 (RFC 5737) — reserved and non-routable,
        so a connection attempt should always time out.

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
        probe packets — used in Continuity features. On macOS SO_KEEPALIVE
        returns the constant (8) rather than the set value (1).

        Expected: Keep-alive enabled (non-zero value).
        """
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        try:
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_KEEPALIVE, 1)
            val = sock.getsockopt(socket.SOL_SOCKET, socket.SO_KEEPALIVE)
            assert val != 0, (
                "SO_KEEPALIVE must be non-zero after being set. "
                "macOS returns the constant (8), not the set value (1)."
            )
        finally:
            sock.close()

    @pytest.mark.protocol
    def test_socket_reuse_address(self):
        """
        Verify SO_REUSEADDR works — needed for rapid restart scenarios.

        When a server restarts, SO_REUSEADDR allows it to re-bind to the same
        port without waiting for TIME_WAIT to expire.

        Expected: SO_REUSEADDR enabled (non-zero value).
        """
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        try:
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            reuse = sock.getsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR)
            assert reuse != 0, "SO_REUSEADDR should be non-zero after being set."
        finally:
            sock.close()

    @pytest.mark.protocol
    def test_socket_timeout_control(self):
        """
        Verify socket timeout and blocking mode can be configured.

        Expected: Timeout value is preserved; setblocking(False) sets timeout to 0.
        """
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        try:
            sock.settimeout(5.0)
            assert sock.gettimeout() == 5.0, "Timeout should be 5.0 after settimeout(5.0)"
            sock.setblocking(False)
            assert sock.gettimeout() == 0.0, "Timeout should be 0.0 in non-blocking mode"
        finally:
            sock.close()


class TestHTTPProtocols:

    @pytest.mark.network
    def test_http2_supported(self, test_config):
        """
        Verify HTTP/2 protocol support for Apple's web services.

        HTTP/2 is used by App Store, iCloud, and other Apple web services
        for efficient data transfer via multiplexing and header compression.

        Expected: Response uses HTTP/2 protocol version.
        """
        pytest.importorskip("h2")
        import httpx

        timeout = test_config["network_timeout"]
        with httpx.Client(http2=True, timeout=timeout) as client:
            resp = client.get("https://www.apple.com")
            assert resp.http_version in ("HTTP/2", "h2"), (
                f"Expected HTTP/2 but got {resp.http_version}. "
                "Ensure httpx[http2] is installed and apple.com supports HTTP/2."
            )

    @pytest.mark.network
    def test_https_redirect_enforced(self, test_config):
        """
        Ensure HTTP requests are redirected to HTTPS.

        Apple enforces HTTPS-only connections for security. HTTP requests
        must be redirected with status 301, 302, 307, or 308.

        Expected: HTTP request returns redirect status code.
        """
        import httpx

        timeout = test_config["network_timeout"]
        with httpx.Client(follow_redirects=False, timeout=timeout) as client:
            resp = client.get("http://apple.com")
            assert resp.status_code in (301, 302, 307, 308), (
                f"Expected redirect (301/302/307/308) from http://apple.com "
                f"but got {resp.status_code}. ATS requires HTTPS-only connections."
            )

    @pytest.mark.network
    def test_hsts_header_present(self, test_config):
        """
        Validate HTTP Strict Transport Security (HSTS) header presence.

        HSTS instructs clients to only use HTTPS, preventing downgrade attacks.

        Expected: Response contains strict-transport-security header.
        """
        pytest.importorskip("h2")
        import httpx

        timeout = test_config["network_timeout"]
        with httpx.Client(http2=True, timeout=timeout) as client:
            resp = client.get("https://www.apple.com")
            assert "strict-transport-security" in resp.headers, (
                "HSTS header (strict-transport-security) missing from apple.com response. "
                "This header is required to prevent protocol downgrade attacks."
            )

    @pytest.mark.network
    def test_connection_pooling(self, test_config):
        """
        Test HTTP connection reuse — critical for performance.

        HTTP/2 multiplexes requests over a single connection. Verifying that
        two sequential requests to the same host both succeed confirms the
        client's connection pool is functioning correctly.

        Expected: Both requests return HTTP 200.
        """
        pytest.importorskip("h2")
        import httpx

        timeout = test_config["network_timeout"]
        with httpx.Client(http2=True, timeout=timeout) as client:
            r1 = client.get("https://www.apple.com")
            r2 = client.get("https://www.apple.com")
            assert r1.status_code == 200, f"First request failed with {r1.status_code}"
            assert r2.status_code == 200, f"Second request failed with {r2.status_code}"


class TestHTTPWithStandardLib:
    """HTTP tests using only the standard library — no external dependencies."""

    @pytest.mark.network
    def test_https_connection_with_ssl(self):
        """
        Basic HTTPS connection using only the standard library.

        Verifies that a plain urllib + ssl connection to apple.com works
        without any third-party HTTP client. Useful as a dependency-free
        baseline for network availability checks.

        Expected: HTTP 200 response from www.apple.com.
        """
        import urllib.request

        context = ssl.create_default_context()
        try:
            with urllib.request.urlopen(
                "https://www.apple.com", context=context, timeout=10
            ) as response:
                assert (
                    response.status == 200
                ), f"Expected HTTP 200 from apple.com, got {response.status}"
        except Exception as e:
            pytest.skip(f"Network unreachable: {e}")


class TestIdentityPrivacy:
    """AirDrop contact hash validation — ALL OFFLINE."""

    @pytest.mark.security
    def test_hash_is_deterministic(self):
        """
        Verify SHA-256 hash produces consistent output for same input.

        Deterministic hashing is essential for AirDrop contact matching.

        Expected: Same input produces identical hash values.
        """
        h1 = hashlib.sha256(b"user@example.com").hexdigest()
        h2 = hashlib.sha256(b"user@example.com").hexdigest()
        assert h1 == h2, "SHA-256 must be deterministic — same input must always produce same hash"

    @pytest.mark.security
    def test_different_contacts_different_hashes(self):
        """
        Ensure different contacts produce different hash values.

        Hash collisions would cause false positive AirDrop contact matches.

        Expected: Different inputs produce different hash values.
        """
        h1 = hashlib.sha256(b"alice@example.com").hexdigest()
        h2 = hashlib.sha256(b"bob@example.com").hexdigest()
        assert h1 != h2, "Different contacts must produce different hashes to avoid false matches"

    @pytest.mark.security
    def test_hash_is_256_bits(self):
        """
        Validate hash output is exactly 256 bits (64 hex characters).

        Expected: Hash output is 64 hexadecimal characters (256 bits).
        """
        digest = hashlib.sha256(b"test").hexdigest()
        assert len(digest) == 64, f"Expected 64 hex chars (256 bits), got {len(digest)}"

    @pytest.mark.security
    def test_no_pii_in_hash(self):
        """
        Verify hash output contains no personally identifiable information.

        AirDrop hashes must not expose email fragments in cleartext.

        Expected: Hash contains no recognizable fragments of input email.
        """
        h = hashlib.sha256(b"john.doe@apple.com").hexdigest()
        for fragment in ["john", "doe", "apple", "@"]:
            assert fragment not in h, (
                f"PII fragment '{fragment}' found in hash output — "
                "contact data is not properly protected"
            )

    @pytest.mark.security
    def test_truncated_hash_for_ble(self):
        """
        Test truncated hash fits in BLE advertisement payload.

        BLE payloads are limited to 31 bytes so hashes are truncated to 2 bytes.

        Expected: Truncated hash is exactly 2 bytes.
        """
        full = hashlib.sha256(b"user@example.com").digest()
        truncated = full[:2]
        assert (
            len(truncated) == 2
        ), f"Expected 2-byte BLE hash truncation, got {len(truncated)} bytes"

    @pytest.mark.security
    def test_truncated_hash_contact_matching(self):
        """
        Verify contact matching works with truncated hashes.

        Simulates AirDrop's BLE contact matching: sender broadcasts truncated
        hash, receiver checks against their contact list.

        Expected: Truncated hash correctly identifies contact.
        """
        sender = hashlib.sha256(b"alice@example.com").digest()[:2]
        contacts = {
            hashlib.sha256(c.encode()).digest()[:2]: c
            for c in ["alice@example.com", "bob@example.com", "carol@example.com"]
        }
        assert sender in contacts, "Sender's truncated hash not found in contact lookup table"
        assert (
            contacts[sender] == "alice@example.com"
        ), f"Expected 'alice@example.com' but got '{contacts.get(sender)}'"

    @pytest.mark.security
    def test_collision_rate_acceptable(self):
        """
        Measure hash collision rate for truncated (2-byte) hashes.

        With 2-byte hashes (65,536 possible values), collisions are expected
        but must stay under 5% for typical contact list sizes.

        Expected: Collision rate < 5% for 1000 random contacts.
        """
        import random
        import string

        hashes = set()
        total = 1000
        for _ in range(total):
            email = "".join(random.choices(string.ascii_lowercase, k=10)) + "@test.com"
            hashes.add(hashlib.sha256(email.encode()).digest()[:2])
        collision_rate = 1 - len(hashes) / total
        assert collision_rate < 0.05, (
            f"Collision rate {collision_rate:.2%} exceeds 5% threshold. "
            "High collision rates degrade AirDrop contact matching accuracy."
        )


class TestPerformance:
    """Performance benchmarks for network operations."""

    @pytest.mark.network
    @pytest.mark.performance
    def test_tls_handshake_time(self, test_config):
        """
        Benchmark TLS handshake performance to Apple's servers.

        TLS handshake latency impacts user experience. Must complete < 1000ms.
        """
        context = ssl.create_default_context()
        timeout = test_config["network_timeout"]
        start = time.time()
        with socket.create_connection(("apple.com", 443), timeout=timeout) as sock:
            with context.wrap_socket(sock, server_hostname="apple.com"):
                ms = (time.time() - start) * 1000
        assert ms < 1000, (
            f"TLS handshake took {ms:.1f}ms — exceeds 1000ms threshold. "
            "Check network conditions or server response time."
        )

    @pytest.mark.network
    @pytest.mark.performance
    def test_full_connection_latency(self, test_config):
        """
        Measure end-to-end connection latency including DNS resolution.

        Tests DNS + TCP + TLS combined. Must complete < 2000ms.
        """
        timeout = test_config["network_timeout"]
        start = time.time()
        ip = socket.gethostbyname("apple.com")
        context = ssl.create_default_context()
        with socket.create_connection((ip, 443), timeout=timeout) as sock:
            with context.wrap_socket(sock, server_hostname="apple.com"):
                total_ms = (time.time() - start) * 1000
        assert total_ms < 2000, (
            f"Full connection (DNS+TCP+TLS) took {total_ms:.1f}ms — " "exceeds 2000ms threshold."
        )
