"""
utils/opendrop_helpers.py
=========================
Protocol helpers for testing the OpenDrop AirDrop implementation.

OpenDrop (github.com/seemoo-lab/opendrop) is an open-source Python
implementation of Apple's AirDrop protocol. It operates in three stages:

  Stage 1 — BLE advertisement
    Sender broadcasts a Manufacturer Specific Data (MSD) BLE advertisement
    containing a truncated SHA-256 hash of the sender's contacts.

  Stage 2 — mDNS discovery
    Peers advertise themselves as _airdrop._tcp.local on port 8770.

  Stage 3 — HTTPS handshake
    /Discover  — sender POSTs SenderRecordData plist; receiver replies with
                 its ComputerName and ModelName if it accepts.
    /Ask       — sender requests transfer approval.
    /Upload    — file transfer over self-signed TLS.

No third-party OpenDrop package is required — all helpers use Python stdlib.

Usage:
    from utils.opendrop_helpers import (
        contact_hash,
        build_discover_request,
        parse_discover_response,
        build_ble_advertisement,
        OPENDROP_SERVICE_TYPE,
        OPENDROP_HTTPS_PORT,
        APPLE_COMPANY_ID,
        AIRDROP_ACTION_BYTE,
        OPENDROP_HASH_LEN,
    )
"""

import hashlib
import plistlib
import struct

# ============================================================
# Protocol constants
# ============================================================

OPENDROP_SERVICE_TYPE = "_airdrop._tcp.local."  # DNS-SD service type
OPENDROP_HTTPS_PORT = 8770  # Self-signed TLS port
APPLE_COMPANY_ID = 0x004C  # BLE: little-endian b'\x4c\x00'
AIRDROP_ACTION_BYTE = 0x05  # BLE action identifier for AirDrop
NAMEDROP_ACTION_BYTE = 0x14  # BLE action identifier for NameDrop
OPENDROP_HASH_LEN = 2  # Bytes of SHA-256 used in BLE payload


# ============================================================
# Hashing
# ============================================================


def contact_hash(value: str) -> bytes:
    """
    Compute SHA-256 of a contact identifier (email or phone number).

    This is the exact hash function OpenDrop uses for contact matching.
    The full 32-byte digest is truncated to 2 bytes before being placed
    in the BLE advertisement to preserve privacy while still enabling
    proximity-based contact matching.

    Args:
        value: Email address or phone number as a plain string.

    Returns:
        32-byte SHA-256 digest.
    """
    return hashlib.sha256(value.encode()).digest()


# ============================================================
# /Discover handshake
# ============================================================


def build_discover_request(sender_record: bytes) -> bytes:
    """
    Build the binary plist body for an OpenDrop POST /Discover request.

    OpenDrop sends:
        POST https://<peer>:8770/Discover
        Content-Type: application/x-apple-binary-plist

        { "SenderRecordData": <bytes> }

    SenderRecordData is an ObjC-serialised record containing the sender's
    identity (public key + contact hashes). In tests a synthetic byte
    sequence is used in place of a real record.

    Args:
        sender_record: Raw bytes representing the sender identity record.

    Returns:
        Binary plist bytes ready to use as an HTTP request body.
    """
    return plistlib.dumps(
        {"SenderRecordData": sender_record},
        fmt=plistlib.FMT_BINARY,
    )


def parse_discover_response(data: bytes) -> dict:
    """
    Parse a binary plist from an OpenDrop /Discover response.

    A successful response contains at minimum:
      ReceiverComputerName  — human-readable device name shown in the UI
      ReceiverModelName     — model identifier, e.g. "MacBookPro18,1"

    Args:
        data: Raw binary plist bytes from the HTTP response body.

    Returns:
        Deserialised dict.
    """
    return plistlib.loads(data)


# ============================================================
# BLE advertisement
# ============================================================


def build_ble_advertisement(contact: str, action: int = AIRDROP_ACTION_BYTE) -> bytes:
    """
    Build the BLE Manufacturer Specific Data (MSD) payload used by OpenDrop.

    BLE MSD byte layout (total 8 bytes, fits within 31-byte BLE limit):

        Offset  Size  Value                        Description
        ------  ----  ---------------------------  -------------------------
        0       2     0x4C 0x00                    Apple Company ID (little-endian)
        2       1     0x05 (AirDrop) / 0x14 (NameDrop)  Action byte
        3       1     0x04                         Sub-payload length (4 bytes follow)
        4       1     0x00                         Version / flags (high byte)
        5       1     0x00                         Version / flags (low byte)
        6       2     SHA-256(contact)[0:2]        Truncated contact hash

    The receiver collects these 2-byte hash fragments and compares them
    against truncated hashes of its own contacts. A match triggers the
    AirDrop invitation UI.

    Args:
        contact: Email address or phone number of the sending user.
        action:  BLE action byte. Use AIRDROP_ACTION_BYTE (0x05) for AirDrop
                 or NAMEDROP_ACTION_BYTE (0x14) for NameDrop.

    Returns:
        8-byte BLE advertisement payload.
    """
    truncated = contact_hash(contact)[:OPENDROP_HASH_LEN]
    sub_payload = bytes([action, 4, 0x00, 0x00]) + truncated
    company_id = struct.pack("<H", APPLE_COMPANY_ID)
    return company_id + sub_payload
