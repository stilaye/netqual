"""
test_bonjour_discovery.py
=========================
Tests for Bonjour/mDNS service discovery — the protocol that powers
AirDrop device detection, AirPlay, and Handoff proximity awareness.

Apple devices advertise themselves as mDNS services on the local network.
AirDrop uses: _airdrop._tcp.local.
AirPlay uses: _airplay._tcp.local.

Run: pytest test_bonjour_discovery.py -v
"""

import hashlib
import socket
import struct

import pytest

from utils.mdns_helpers import MDNS_ADDR, MDNS_PORT, MDNSHelper

# ============================================================
# Service Registration / Advertisement Tests
# ============================================================


class TestServiceAdvertisement:
    """
    Test mDNS service registration — simulates how Apple devices
    advertise AirDrop, AirPlay, Handoff availability.
    """

    def test_mdns_query_packet_format(self):
        """Verify our mDNS query packet is correctly formatted."""
        query = MDNSHelper.build_query("_airdrop._tcp.local")

        assert len(query) > 12, f"Query too short: {len(query)} bytes — header alone is 12 bytes"
        assert query[0:2] == b"\x00\x00", "mDNS transaction ID must be 0x0000 (RFC 6762 §6)"
        assert (query[2] & 0x80) == 0, "QR bit must be 0 for a query (bit 15 of flags word)"
        assert (
            struct.unpack("!H", query[4:6])[0] == 1
        ), "QDCOUNT must be 1 — this query has exactly one question"

    @pytest.mark.parametrize(
        ("service", "label"),
        [
            ("_airdrop._tcp.local", b"_airdrop"),
            ("_airplay._tcp.local", b"_airplay"),
            ("_companion-link._tcp.local", b"_companion-link"),
            ("_services._dns-sd._udp.local", b"_services"),
        ],
    )
    def test_mdns_query_encodes_service_label(self, service, label):
        """
        Query packet must contain the encoded service label so that mDNS
        responders on the network can match it against their advertised types.
        """
        query = MDNSHelper.build_query(service)
        assert label in query, f"Expected label {label!r} not found in query for '{service}'"

    def test_mdns_query_for_airdrop_service(self):
        """Build and validate an AirDrop service discovery query."""
        query = MDNSHelper.build_query("_airdrop._tcp.local")
        assert b"_airdrop" in query, "AirDrop service label missing from query"
        assert b"_tcp" in query, "_tcp protocol label missing from query"
        assert b"local" in query, "local domain missing from query"

    def test_mdns_query_for_airplay_service(self):
        """Build and validate an AirPlay service discovery query."""
        query = MDNSHelper.build_query("_airplay._tcp.local")
        assert b"_airplay" in query, "AirPlay service label missing from query"

    def test_mdns_query_for_companion_link(self):
        """Companion Link is used for Handoff between iPhone and Mac."""
        query = MDNSHelper.build_query("_companion-link._tcp.local")
        assert (
            b"_companion-link" in query
        ), "Companion Link service label missing — Handoff discovery will fail"

    def test_services_discovery_query(self):
        """Meta-query to discover all available service types on the network."""
        query = MDNSHelper.build_query("_services._dns-sd._udp.local")
        assert b"_services" in query, "_services label missing"
        assert b"_dns-sd" in query, "_dns-sd label missing"

    def test_mdns_multicast_send(self):
        """Verify we can send to the mDNS multicast address without error."""
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)
        try:
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            query = MDNSHelper.build_query("_airdrop._tcp.local")
            bytes_sent = sock.sendto(query, (MDNS_ADDR, MDNS_PORT))
            assert bytes_sent > 0, f"Expected > 0 bytes sent, got {bytes_sent}"
        except PermissionError:
            pytest.skip("Need elevated permissions for multicast")
        finally:
            sock.close()


# ============================================================
# Service Discovery Response Tests
# ============================================================


class TestServiceDiscovery:
    """
    Test mDNS response parsing — validates we can correctly interpret
    device discovery responses (as AirDrop/Handoff receivers do).
    """

    def test_parse_valid_response(self):
        """Parse a well-formed mDNS response."""
        # Header: ID=0, QR=1 (response), AA=1, ANCOUNT=1
        header = struct.pack("!HHHHHH", 0, 0x8400, 0, 1, 0, 0)
        answer = b"\x00" + struct.pack("!HHIH", 1, 1, 60, 4) + b"\x7f\x00\x00\x01"
        data = header + answer

        result = MDNSHelper.parse_response(data)
        assert result["valid"] is True, "Expected valid=True for well-formed packet"
        assert result["is_response"] is True, "QR=1 must set is_response=True"
        assert result["answers"] == 1, f"Expected 1 answer, got {result['answers']}"

    def test_parse_invalid_short_packet(self):
        """Short packets should be rejected gracefully — no crashes."""
        result = MDNSHelper.parse_response(b"\x00\x01")
        assert result["valid"] is False, "2-byte packet must be rejected (header is 12 bytes)"

    def test_parse_empty_response(self):
        """Empty data should be handled gracefully."""
        result = MDNSHelper.parse_response(b"")
        assert result["valid"] is False, "Empty packet must be rejected"

    def test_parse_query_vs_response(self):
        """Distinguish queries from responses — receiver should ignore queries."""
        query = MDNSHelper.build_query("_airdrop._tcp.local")
        result = MDNSHelper.parse_response(query)
        assert result["valid"] is True, "Built query must parse as valid"
        assert (
            result["is_response"] is False
        ), "A query packet must have is_response=False (QR bit=0)"

    def test_scan_local_network_services(self):
        """
        Scan the local network for mDNS services.
        On a network with Apple devices, you'll see _airdrop, _airplay, etc.
        The test validates the mechanism runs without errors — responses are
        optional depending on what devices are present.
        """
        responses = MDNSHelper.send_query("_services._dns-sd._udp.local", timeout=2.0)
        print(f"\n  Found {len(responses)} mDNS response(s) on local network")
        for resp in responses[:5]:
            print(
                f"    Source: {resp.get('source_ip', 'unknown')}, "
                f"Answers: {resp.get('answers', 0)}"
            )
        assert isinstance(
            responses, list
        ), "send_query must always return a list (empty list on no response)"


# ============================================================
# BLE Advertisement Simulation Tests
# ============================================================


class TestBLEAdvertisementFormat:
    """
    AirDrop and NameDrop use BLE advertisements for device discovery.
    The BLE payload contains a truncated hash of the sender's identity.

    These tests validate the data format, not actual BLE hardware.
    """

    @staticmethod
    def build_airdrop_ble_payload(contact_hash: bytes, action: int = 0x05) -> bytes:
        """
        Simulate AirDrop BLE advertisement payload structure.

        Layout:
          [0]       Length byte  (covers type + company ID + action + hash)
          [1]       0xFF         Manufacturer Specific Data type
          [2:4]     0x4C 0x00    Apple Company ID (little-endian)
          [4]       action       0x05=AirDrop, 0x14=NameDrop
          [5:]      contact_hash Truncated SHA-256 (2 bytes)
        """
        apple_company_id = b"\x4c\x00"
        payload = (
            bytes([2 + len(apple_company_id) + 1 + len(contact_hash)])
            + bytes([0xFF])
            + apple_company_id
            + bytes([action])
            + contact_hash
        )
        return payload

    def test_ble_payload_size_within_limit(self):
        """BLE advertisement payload must be <= 31 bytes (BLE spec limit)."""
        contact_hash = b"\xab\xcd"
        payload = self.build_airdrop_ble_payload(contact_hash)
        assert (
            len(payload) <= 31
        ), f"BLE payload is {len(payload)} bytes — exceeds 31-byte BLE limit"

    def test_ble_payload_contains_apple_company_id(self):
        """Apple Company ID (0x004C) must be in the advertisement."""
        payload = self.build_airdrop_ble_payload(b"\x12\x34")
        assert b"\x4c\x00" in payload, "Apple Company ID (0x4C 0x00) missing from BLE advertisement"

    def test_ble_payload_different_per_contact(self):
        """Different contacts should produce different BLE payloads."""
        hash1 = hashlib.sha256(b"user1@example.com").digest()[:2]
        hash2 = hashlib.sha256(b"user2@example.com").digest()[:2]
        payload1 = self.build_airdrop_ble_payload(hash1)
        payload2 = self.build_airdrop_ble_payload(hash2)
        assert (
            payload1 != payload2
        ), "Different contacts must produce different BLE payloads for correct matching"

    def test_namedrop_proximity_payload(self):
        """NameDrop uses a different action byte (0x14) than AirDrop (0x05)."""
        contact_hash = b"\xab\xcd"
        airdrop_payload = self.build_airdrop_ble_payload(contact_hash, action=0x05)
        namedrop_payload = self.build_airdrop_ble_payload(contact_hash, action=0x14)
        assert (
            airdrop_payload != namedrop_payload
        ), "AirDrop (0x05) and NameDrop (0x14) action bytes must differ"
        assert len(airdrop_payload) == len(
            namedrop_payload
        ), "AirDrop and NameDrop payloads must be the same length"
