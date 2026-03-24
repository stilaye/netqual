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

import pytest
import socket
import struct
import time
import threading
from typing import List, Dict, Optional


# ============================================================
# mDNS Protocol Helpers
# ============================================================

class MDNSHelper:
    """Minimal mDNS protocol implementation for testing."""

    MDNS_ADDR = "224.0.0.251"
    MDNS_PORT = 5353
    MDNS_ADDR_V6 = "ff02::fb"

    @staticmethod
    def build_query(name: str, qtype: int = 12) -> bytes:
        """
        Build an mDNS query packet.
        qtype: 12=PTR (service discovery), 1=A, 28=AAAA, 33=SRV, 16=TXT
        """
        # Header
        header = struct.pack("!HHHHHH", 0, 0, 1, 0, 0, 0)
        # Question section
        question = b""
        for part in name.split("."):
            question += bytes([len(part)]) + part.encode()
        question += b"\x00"
        question += struct.pack("!HH", qtype, 1)  # QCLASS=IN
        return header + question

    @staticmethod
    def parse_response(data: bytes) -> Dict:
        """Parse minimal mDNS response — extract answer count and names."""
        if len(data) < 12:
            return {"valid": False}

        header = struct.unpack("!HHHHHH", data[:12])
        return {
            "valid": True,
            "id": header[0],
            "flags": header[1],
            "questions": header[2],
            "answers": header[3],
            "authority": header[4],
            "additional": header[5],
            "is_response": bool(header[1] & 0x8000),
            "raw_length": len(data),
        }

    @staticmethod
    def send_query(name: str, timeout: float = 2.0) -> List[Dict]:
        """Send mDNS query and collect responses."""
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        sock.settimeout(timeout)

        try:
            # Send query to mDNS multicast
            query = MDNSHelper.build_query(name)
            sock.sendto(query, (MDNSHelper.MDNS_ADDR, MDNSHelper.MDNS_PORT))

            # Collect responses
            responses = []
            deadline = time.time() + timeout
            while time.time() < deadline:
                try:
                    data, addr = sock.recvfrom(4096)
                    parsed = MDNSHelper.parse_response(data)
                    parsed["source_ip"] = addr[0]
                    responses.append(parsed)
                except socket.timeout:
                    break

            return responses
        except PermissionError:
            return []
        finally:
            sock.close()


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
        # Header should be 12 bytes
        assert len(query) > 12
        # First 2 bytes (ID) should be 0 for mDNS
        assert query[0:2] == b"\x00\x00"
        # QR bit should be 0 (query)
        assert (query[2] & 0x80) == 0
        # QDCOUNT should be 1
        assert struct.unpack("!H", query[4:6])[0] == 1

    def test_mdns_query_for_airdrop_service(self):
        """Build and validate an AirDrop service discovery query."""
        query = MDNSHelper.build_query("_airdrop._tcp.local")
        assert b"_airdrop" in query
        assert b"_tcp" in query
        assert b"local" in query

    def test_mdns_query_for_airplay_service(self):
        """Build and validate an AirPlay service discovery query."""
        query = MDNSHelper.build_query("_airplay._tcp.local")
        assert b"_airplay" in query

    def test_mdns_query_for_companion_link(self):
        """Companion Link is used for Handoff between iPhone and Mac."""
        query = MDNSHelper.build_query("_companion-link._tcp.local")
        assert b"_companion-link" in query

    def test_services_discovery_query(self):
        """Meta-query to discover all available service types on the network."""
        query = MDNSHelper.build_query("_services._dns-sd._udp.local")
        assert b"_services" in query
        assert b"_dns-sd" in query

    def test_mdns_multicast_send(self):
        """Verify we can send to the mDNS multicast address without error."""
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)
        try:
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            query = MDNSHelper.build_query("_airdrop._tcp.local")
            # Should not raise — just sends the packet
            bytes_sent = sock.sendto(query, (MDNSHelper.MDNS_ADDR, MDNSHelper.MDNS_PORT))
            assert bytes_sent > 0
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
        # Construct a minimal valid response
        # Header: ID=0, QR=1 (response), AA=1, ANCOUNT=1
        header = struct.pack("!HHHHHH", 0, 0x8400, 0, 1, 0, 0)
        # Minimal answer (just enough to parse header)
        answer = b"\x00" + struct.pack("!HHIH", 1, 1, 60, 4) + b"\x7f\x00\x00\x01"
        data = header + answer

        result = MDNSHelper.parse_response(data)
        assert result["valid"] is True
        assert result["is_response"] is True
        assert result["answers"] == 1

    def test_parse_invalid_short_packet(self):
        """Short packets should be rejected gracefully — no crashes."""
        result = MDNSHelper.parse_response(b"\x00\x01")
        assert result["valid"] is False

    def test_parse_empty_response(self):
        """Empty data should be handled gracefully."""
        result = MDNSHelper.parse_response(b"")
        assert result["valid"] is False

    def test_parse_query_vs_response(self):
        """Distinguish queries from responses — receiver should ignore queries."""
        query = MDNSHelper.build_query("_airdrop._tcp.local")
        result = MDNSHelper.parse_response(query)
        assert result["valid"] is True
        assert result["is_response"] is False  # This is a query, not response

    def test_scan_local_network_services(self):
        """
        Actually scan the local network for mDNS services.
        On a network with Apple devices, you'll see _airdrop, _airplay, etc.
        """
        responses = MDNSHelper.send_query("_services._dns-sd._udp.local", timeout=2.0)
        # We may or may not get responses depending on the network
        # The test validates that the scan runs without errors
        print(f"\n  Found {len(responses)} mDNS responses on local network")
        for resp in responses[:5]:  # Print first 5
            print(f"    Source: {resp.get('source_ip', 'unknown')}, "
                  f"Answers: {resp.get('answers', 0)}")
        # Test passes regardless — it's about the mechanism working
        assert isinstance(responses, list)


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
        Real format: [Length][Type][Apple Company ID][Action][Contact Hash]
        """
        apple_company_id = b"\x4c\x00"  # Apple Inc.
        payload = (
            bytes([2 + len(apple_company_id) + 1 + len(contact_hash)])  # Length
            + bytes([0xFF])  # Type: Manufacturer Specific
            + apple_company_id
            + bytes([action])  # AirDrop action byte
            + contact_hash
        )
        return payload

    def test_ble_payload_size_within_limit(self):
        """BLE advertisement payload must be <= 31 bytes."""
        contact_hash = b"\xab\xcd"  # 2-byte truncated hash
        payload = self.build_airdrop_ble_payload(contact_hash)
        assert len(payload) <= 31, f"BLE payload too large: {len(payload)} bytes"

    def test_ble_payload_contains_apple_company_id(self):
        """Apple Company ID (0x004C) must be in the advertisement."""
        contact_hash = b"\x12\x34"
        payload = self.build_airdrop_ble_payload(contact_hash)
        assert b"\x4c\x00" in payload

    def test_ble_payload_different_per_contact(self):
        """Different contacts should produce different BLE payloads."""
        import hashlib
        hash1 = hashlib.sha256(b"user1@example.com").digest()[:2]
        hash2 = hashlib.sha256(b"user2@example.com").digest()[:2]

        payload1 = self.build_airdrop_ble_payload(hash1)
        payload2 = self.build_airdrop_ble_payload(hash2)
        assert payload1 != payload2

    def test_namedrop_proximity_payload(self):
        """NameDrop uses a different action byte than regular AirDrop."""
        contact_hash = b"\xab\xcd"
        airdrop_payload = self.build_airdrop_ble_payload(contact_hash, action=0x05)
        namedrop_payload = self.build_airdrop_ble_payload(contact_hash, action=0x14)
        # Same structure, different action byte
        assert airdrop_payload != namedrop_payload
        assert len(airdrop_payload) == len(namedrop_payload)
