"""
test_opendrop.py
================
Tests for the OpenDrop protocol layer — the open-source implementation of
Apple's AirDrop (github.com/seemoo-lab/opendrop).

OpenDrop works in three stages:
  1. BLE advertisement — sender broadcasts truncated contact hash
  2. mDNS discovery   — peers advertise via _airdrop._tcp.local (port 8770)
  3. HTTPS handshake  — /Discover → /Ask → /Upload over self-signed TLS

These tests validate the protocol structures OpenDrop relies on using only
Python standard-library modules (no opendrop package required to install).

Run: pytest tests/test_opendrop.py -v
"""

import hashlib
import plistlib
import socket
import struct
import pytest


# ============================================================
# OpenDrop Protocol Constants
# ============================================================

OPENDROP_SERVICE_TYPE = "_airdrop._tcp.local."
OPENDROP_HTTPS_PORT   = 8770
APPLE_COMPANY_ID      = 0x004C   # Little-endian in BLE: b'\x4c\x00'
AIRDROP_ACTION_BYTE   = 0x05     # OpenDrop BLE action type
OPENDROP_HASH_LEN     = 2        # Bytes of SHA-256 used in BLE payload


# ============================================================
# Helpers
# ============================================================

def _contact_hash(value: str) -> bytes:
    """SHA-256 of a phone/email, as used by OpenDrop contact matching."""
    return hashlib.sha256(value.encode()).digest()


def _build_discover_request(sender_record: bytes) -> bytes:
    """
    Build an OpenDrop /Discover plist payload.

    OpenDrop sends a POST to https://<peer>:8770/Discover with a plist body:
        { "SenderRecordData": <bytes> }
    The receiver replies with ComputerName / ModelName if it accepts.
    """
    payload = {"SenderRecordData": sender_record}
    return plistlib.dumps(payload, fmt=plistlib.FMT_BINARY)


def _parse_discover_response(data: bytes) -> dict:
    """Parse an OpenDrop /Discover plist response."""
    return plistlib.loads(data)


def _build_ble_advertisement(contact: str) -> bytes:
    """
    Build the BLE advertisement payload OpenDrop uses for proximity detection.

    Layout (Manufacturer Specific Data, type 0xFF):
      [0x4c, 0x00]  Apple Company ID (little-endian)
      [0x05]        AirDrop action byte
      [len]         Payload length
      [0x00, 0x00]  Version / flags
      [h0, h1]      First 2 bytes of SHA-256(contact)
    """
    truncated = _contact_hash(contact)[:OPENDROP_HASH_LEN]
    payload = bytes([AIRDROP_ACTION_BYTE, 4, 0x00, 0x00]) + truncated
    company  = struct.pack("<H", APPLE_COMPANY_ID)
    return company + payload


# ============================================================
# Tests
# ============================================================

class TestOpenDropDiscoverPayload:
    """Validate the /Discover HTTPS handshake payload (offline)."""

    def test_discover_request_is_valid_plist(self):
        """
        OpenDrop POSTs a binary plist to /Discover.
        Verify the payload round-trips correctly.
        """
        sender_record = b"\xde\xad\xbe\xef" * 4   # 16 bytes of mock record data
        raw = _build_discover_request(sender_record)

        parsed = plistlib.loads(raw)
        assert "SenderRecordData" in parsed
        assert parsed["SenderRecordData"] == sender_record

    def test_discover_response_contains_required_fields(self):
        """
        A valid OpenDrop /Discover response must include ReceiverComputerName
        and ReceiverModelName so the sender can show a device name in the UI.
        """
        mock_response = plistlib.dumps({
            "ReceiverComputerName": "Avyaan's MacBook Pro",
            "ReceiverModelName":    "MacBookPro18,1",
        }, fmt=plistlib.FMT_BINARY)

        parsed = _parse_discover_response(mock_response)
        assert "ReceiverComputerName" in parsed
        assert "ReceiverModelName"    in parsed
        assert len(parsed["ReceiverComputerName"]) > 0

    def test_sender_record_preserved_exactly(self):
        """SenderRecordData must survive plist serialisation without corruption."""
        original = bytes(range(32))   # 32 arbitrary bytes
        raw      = _build_discover_request(original)
        assert plistlib.loads(raw)["SenderRecordData"] == original


class TestOpenDropMDNS:
    """Validate the mDNS service record that OpenDrop advertises."""

    def test_service_type_format(self):
        """
        OpenDrop advertises _airdrop._tcp.local. — verify the constant matches
        the DNS-SD naming convention (underscore prefix, .local. suffix).
        """
        parts = OPENDROP_SERVICE_TYPE.split(".")
        assert parts[0].startswith("_"), "service name must start with _"
        assert parts[1].startswith("_"), "protocol must start with _"
        assert OPENDROP_SERVICE_TYPE.endswith(".local.")

    def test_opendrop_port_is_valid(self):
        """Port 8770 must be in the valid unprivileged range (1024–65535)."""
        assert 1024 <= OPENDROP_HTTPS_PORT <= 65535

    def test_mdns_query_packet_for_opendrop(self):
        """
        Build a minimal mDNS PTR query for _airdrop._tcp.local and verify the
        packet header flags indicate a standard query (QR=0, Opcode=0).
        """
        name = "_airdrop._tcp.local"
        header = struct.pack("!HHHHHH", 0, 0, 1, 0, 0, 0)
        question = b""
        for label in name.split("."):
            question += bytes([len(label)]) + label.encode()
        question += b"\x00"
        question += struct.pack("!HH", 12, 1)   # PTR, IN
        packet = header + question

        flags = struct.unpack("!H", packet[2:4])[0]
        assert flags == 0, "standard query must have QR=0 and Opcode=0"
        assert len(packet) > 12, "packet must have question section"


class TestOpenDropBLEAdvertisement:
    """Validate the BLE advertisement OpenDrop broadcasts for peer detection."""

    def test_advertisement_contains_apple_company_id(self):
        """First two bytes must be Apple's Company ID 0x004C (little-endian)."""
        adv    = _build_ble_advertisement("user@example.com")
        cid    = struct.unpack("<H", adv[:2])[0]
        assert cid == APPLE_COMPANY_ID

    def test_advertisement_fits_ble_payload_limit(self):
        """BLE Manufacturer Specific Data must fit in 31 bytes."""
        adv = _build_ble_advertisement("user@example.com")
        assert len(adv) <= 31

    def test_action_byte_identifies_airdrop(self):
        """Byte index 2 must be 0x05 — the AirDrop action identifier."""
        adv = _build_ble_advertisement("user@example.com")
        assert adv[2] == AIRDROP_ACTION_BYTE

    def test_contact_hash_truncated_to_two_bytes(self):
        """OpenDrop truncates SHA-256(contact) to 2 bytes for BLE privacy."""
        contact   = "test@apple.com"
        adv       = _build_ble_advertisement(contact)
        full_hash = _contact_hash(contact)

        hash_in_adv = adv[-OPENDROP_HASH_LEN:]
        assert hash_in_adv == full_hash[:OPENDROP_HASH_LEN]

    def test_different_contacts_produce_different_advertisements(self):
        """Two distinct contacts must produce different BLE payloads."""
        adv1 = _build_ble_advertisement("alice@example.com")
        adv2 = _build_ble_advertisement("bob@example.com")
        assert adv1 != adv2
