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

import plistlib
import struct

import pytest

from utils.opendrop_helpers import (
    AIRDROP_ACTION_BYTE,
    APPLE_COMPANY_ID,
    OPENDROP_HASH_LEN,
    OPENDROP_HTTPS_PORT,
    OPENDROP_SERVICE_TYPE,
    build_ble_advertisement,
    build_discover_request,
    contact_hash,
    parse_discover_response,
)

# ============================================================
# Tests
# ============================================================


class TestOpenDropDiscoverPayload:
    """Validate the /Discover HTTPS handshake payload (offline)."""

    def test_discover_request_is_valid_plist(self):
        """
        OpenDrop POSTs a binary plist to /Discover.
        Verify the payload serialises and round-trips without data loss.
        """
        sender_record = b"\xde\xad\xbe\xef" * 4  # 16 bytes of mock record data
        raw = build_discover_request(sender_record)
        parsed = plistlib.loads(raw)

        assert (
            "SenderRecordData" in parsed
        ), "Discover request plist must contain 'SenderRecordData' key"
        assert parsed["SenderRecordData"] == sender_record, (
            f"SenderRecordData corrupted during plist serialisation: "
            f"expected {sender_record!r}, got {parsed['SenderRecordData']!r}"
        )

    def test_discover_response_contains_required_fields(self):
        """
        A valid /Discover response must include ReceiverComputerName and
        ReceiverModelName so the sender can display a device name in the UI.
        """
        mock_response = plistlib.dumps(
            {
                "ReceiverComputerName": "Avyaan's MacBook Pro",
                "ReceiverModelName": "MacBookPro18,1",
            },
            fmt=plistlib.FMT_BINARY,
        )

        parsed = parse_discover_response(mock_response)

        assert "ReceiverComputerName" in parsed, (
            "Discover response missing 'ReceiverComputerName' — "
            "sender cannot display the receiver's device name"
        )
        assert "ReceiverModelName" in parsed, (
            "Discover response missing 'ReceiverModelName' — "
            "sender cannot display the receiver's model"
        )
        assert len(parsed["ReceiverComputerName"]) > 0, "ReceiverComputerName must not be empty"

    def test_sender_record_preserved_exactly(self):
        """SenderRecordData must survive plist serialisation without corruption."""
        original = bytes(range(32))
        raw = build_discover_request(original)
        result = plistlib.loads(raw)["SenderRecordData"]
        assert result == original, (
            f"SenderRecordData changed during serialisation: "
            f"expected {len(original)} bytes, got {len(result)} bytes"
        )


class TestOpenDropMDNS:
    """Validate the mDNS service record that OpenDrop advertises."""

    def test_service_type_format(self):
        """
        OpenDrop advertises _airdrop._tcp.local. — the constant must match
        the DNS-SD naming convention (underscore prefix, .local. suffix).
        """
        parts = OPENDROP_SERVICE_TYPE.split(".")
        assert parts[0].startswith(
            "_"
        ), f"Service name '{parts[0]}' must start with '_' (DNS-SD convention)"
        assert parts[1].startswith(
            "_"
        ), f"Protocol '{parts[1]}' must start with '_' (DNS-SD convention)"
        assert OPENDROP_SERVICE_TYPE.endswith(
            ".local."
        ), f"Service type must end with '.local.' — got '{OPENDROP_SERVICE_TYPE}'"

    def test_opendrop_port_is_valid(self):
        """Port 8770 must be in the valid unprivileged range (1024–65535)."""
        assert 1024 <= OPENDROP_HTTPS_PORT <= 65535, (
            f"OpenDrop port {OPENDROP_HTTPS_PORT} is outside the valid "
            "unprivileged range (1024–65535)"
        )

    def test_mdns_query_packet_for_opendrop(self):
        """
        Build a minimal mDNS PTR query for _airdrop._tcp.local and verify
        the packet header flags indicate a standard query (QR=0, Opcode=0).

        Packet header layout (RFC 6762 §6):
          [0:2]  ID    — 0x0000 for mDNS
          [2:4]  Flags — 0x0000 = standard query (QR=0, Opcode=0000)
          [4:6]  QDCOUNT = 1
          [6:8]  ANCOUNT = 0
          [8:10] NSCOUNT = 0
          [10:12] ARCOUNT = 0
        """
        name = "_airdrop._tcp.local"
        header = struct.pack("!HHHHHH", 0, 0, 1, 0, 0, 0)
        question = b""
        for label in name.split("."):
            question += bytes([len(label)]) + label.encode()
        question += b"\x00"
        question += struct.pack("!HH", 12, 1)  # PTR, IN
        packet = header + question

        flags = struct.unpack("!H", packet[2:4])[0]
        assert flags == 0, (
            f"Flags must be 0x0000 for a standard mDNS query (QR=0, Opcode=0), "
            f"got 0x{flags:04x}"
        )
        assert len(packet) > 12, f"Packet is only {len(packet)} bytes — question section is missing"


class TestOpenDropBLEAdvertisement:
    """Validate the BLE advertisement OpenDrop broadcasts for peer detection."""

    def test_advertisement_contains_apple_company_id(self):
        """
        First two bytes must be Apple's Company ID 0x004C (little-endian).

        BLE MSD byte map:
          [0:2]  Apple Company ID  (0x4C 0x00 — little-endian 0x004C)
          [2]    Action byte       (0x05 = AirDrop)
          [3]    Sub-payload len   (0x04)
          [4:6]  Version/flags     (0x00 0x00)
          [6:8]  Truncated hash    (SHA-256(contact)[0:2])
        """
        adv = build_ble_advertisement("user@example.com")
        cid = struct.unpack("<H", adv[:2])[0]
        assert cid == APPLE_COMPANY_ID, (
            f"Expected Apple Company ID 0x{APPLE_COMPANY_ID:04X} "
            f"at bytes [0:2], got 0x{cid:04X}"
        )

    def test_advertisement_fits_ble_payload_limit(self):
        """BLE Manufacturer Specific Data must fit in 31 bytes (BLE spec)."""
        adv = build_ble_advertisement("user@example.com")
        assert len(adv) <= 31, (
            f"BLE advertisement is {len(adv)} bytes — exceeds 31-byte limit. "
            "AirDrop discovery will fail on real hardware."
        )

    def test_action_byte_identifies_airdrop(self):
        """Byte index 2 must be 0x05 — the AirDrop action identifier."""
        adv = build_ble_advertisement("user@example.com")
        assert adv[2] == AIRDROP_ACTION_BYTE, (
            f"Expected action byte 0x{AIRDROP_ACTION_BYTE:02X} at index 2, " f"got 0x{adv[2]:02X}"
        )

    def test_contact_hash_truncated_to_two_bytes(self):
        """
        OpenDrop truncates SHA-256(contact) to 2 bytes for BLE privacy.
        The truncated hash must appear at the end of the advertisement payload.
        """
        contact = "test@apple.com"
        adv = build_ble_advertisement(contact)
        full_hash = contact_hash(contact)

        hash_in_adv = adv[-OPENDROP_HASH_LEN:]
        assert hash_in_adv == full_hash[:OPENDROP_HASH_LEN], (
            f"Truncated hash mismatch: "
            f"expected {full_hash[:OPENDROP_HASH_LEN].hex()}, "
            f"got {hash_in_adv.hex()}"
        )

    def test_different_contacts_produce_different_advertisements(self):
        """Two distinct contacts must produce different BLE payloads."""
        adv1 = build_ble_advertisement("alice@example.com")
        adv2 = build_ble_advertisement("bob@example.com")
        assert adv1 != adv2, (
            "Different contacts produced identical BLE advertisements — "
            "contact matching will be broken"
        )
