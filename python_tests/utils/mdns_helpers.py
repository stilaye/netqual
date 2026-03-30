"""
utils/mdns_helpers.py
=====================
Minimal mDNS (Multicast DNS / Bonjour) protocol helpers for testing.

mDNS is the protocol Apple devices use to advertise and discover services
on a local network — it powers AirDrop (_airdrop._tcp.local), AirPlay
(_airplay._tcp.local), Handoff (_companion-link._tcp.local), and more.

RFC references:
  RFC 6762 — Multicast DNS
  RFC 6763 — DNS-SD (Service Discovery over DNS)

Usage:
    from utils.mdns_helpers import MDNSHelper

    query  = MDNSHelper.build_query("_airdrop._tcp.local")
    result = MDNSHelper.parse_response(raw_bytes)
    responses = MDNSHelper.send_query("_airdrop._tcp.local", timeout=2.0)
"""

import logging
import socket
import struct
import time
from typing import Dict, List

logger = logging.getLogger(__name__)

# ============================================================
# Protocol constants
# ============================================================

MDNS_ADDR      = "224.0.0.251"   # IPv4 mDNS multicast group (RFC 6762 §3)
MDNS_PORT      = 5353            # Well-known mDNS port
MDNS_ADDR_V6   = "ff02::fb"      # IPv6 mDNS multicast group

# DNS record types used in service discovery
QTYPE_PTR  = 12    # Pointer — maps service type to instance name
QTYPE_A    = 1     # IPv4 address
QTYPE_AAAA = 28    # IPv6 address
QTYPE_SRV  = 33    # Service location (host + port)
QTYPE_TXT  = 16    # Arbitrary text records

# Header byte offsets
_HDR_FLAGS_OFFSET    = 2
_HDR_QDCOUNT_OFFSET  = 4
_HDR_ANCOUNT_OFFSET  = 6
_HDR_NSCOUNT_OFFSET  = 8
_HDR_ARCOUNT_OFFSET  = 10
_HDR_SIZE            = 12


class MDNSHelper:
    """
    Minimal mDNS protocol implementation for testing Apple service discovery.

    All methods are static — no state is held between calls.
    """

    # ------------------------------------------------------------------
    # Packet building
    # ------------------------------------------------------------------

    @staticmethod
    def build_query(name: str, qtype: int = QTYPE_PTR) -> bytes:
        """
        Build a standard mDNS query packet (RFC 6762 §6).

        Packet layout:
          [0:2]   Transaction ID — always 0x0000 for mDNS queries
          [2:4]   Flags         — 0x0000 = standard query (QR=0, Opcode=0)
          [4:6]   QDCOUNT       — number of questions (1)
          [6:8]   ANCOUNT       — answer count (0 in a query)
          [8:10]  NSCOUNT       — authority records (0)
          [10:12] ARCOUNT       — additional records (0)
          [12:]   Question      — DNS label-encoded name + qtype + qclass

        Args:
            name:  Service name, e.g. "_airdrop._tcp.local"
            qtype: DNS record type (default: 12=PTR for service discovery)

        Returns:
            Raw bytes ready to sendto() the mDNS multicast address.
        """
        # Header: ID=0, Flags=0 (query), 1 question, 0 answers
        header = struct.pack("!HHHHHH", 0, 0, 1, 0, 0, 0)

        # Question: DNS label format — each label prefixed by its length
        question = b""
        for label in name.split("."):
            if label:  # skip empty labels from trailing dots
                question += bytes([len(label)]) + label.encode()
        question += b"\x00"                         # root label terminator
        question += struct.pack("!HH", qtype, 1)    # QTYPE, QCLASS=IN

        return header + question

    # ------------------------------------------------------------------
    # Packet parsing
    # ------------------------------------------------------------------

    @staticmethod
    def parse_response(data: bytes) -> Dict:
        """
        Parse the 12-byte mDNS header from a raw response packet.

        Always returns a dict with a ``valid`` key. When ``valid`` is False
        all other keys are absent. When ``valid`` is True the following keys
        are always present (never None):

          valid        bool   — True if packet is at least 12 bytes
          id           int    — Transaction ID (always 0 for mDNS)
          flags        int    — Raw 16-bit flags field
          questions    int    — Question count (QDCOUNT)
          answers      int    — Answer count (ANCOUNT)
          authority    int    — Authority record count (NSCOUNT)
          additional   int    — Additional record count (ARCOUNT)
          is_response  bool   — True when QR bit (0x8000) is set
          raw_length   int    — Total packet length in bytes

        Args:
            data: Raw bytes received from a socket.

        Returns:
            Parsed header dict. Never raises.
        """
        if len(data) < _HDR_SIZE:
            logger.debug(
                "parse_response: packet too short (%d bytes, need %d)",
                len(data), _HDR_SIZE
            )
            return {"valid": False}

        id_, flags, qdcount, ancount, nscount, arcount = struct.unpack(
            "!HHHHHH", data[:_HDR_SIZE]
        )
        return {
            "valid":       True,
            "id":          id_,
            "flags":       flags,
            "questions":   qdcount,
            "answers":     ancount,
            "authority":   nscount,
            "additional":  arcount,
            "is_response": bool(flags & 0x8000),
            "raw_length":  len(data),
        }

    # ------------------------------------------------------------------
    # Network send
    # ------------------------------------------------------------------

    @staticmethod
    def send_query(name: str, timeout: float = 2.0) -> List[Dict]:
        """
        Send an mDNS PTR query and collect responses until timeout.

        Sends to 224.0.0.251:5353 (IPv4 mDNS multicast). Each response is
        parsed with parse_response() and augmented with a ``source_ip`` key.

        Args:
            name:    Service name to query, e.g. "_airdrop._tcp.local"
            timeout: Seconds to wait for responses before returning.

        Returns:
            List of parsed response dicts (may be empty if no devices respond
            or if multicast is unavailable on this network).
        """
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        sock.settimeout(timeout)

        try:
            query = MDNSHelper.build_query(name)
            sock.sendto(query, (MDNS_ADDR, MDNS_PORT))
            logger.debug("mDNS query sent for '%s' (timeout=%.1fs)", name, timeout)

            responses: List[Dict] = []
            deadline = time.monotonic() + timeout

            while time.monotonic() < deadline:
                try:
                    data, addr = sock.recvfrom(4096)
                    parsed = MDNSHelper.parse_response(data)
                    parsed["source_ip"] = addr[0]
                    responses.append(parsed)
                except socket.timeout:
                    break

            logger.debug(
                "mDNS query for '%s' collected %d response(s)", name, len(responses)
            )
            return responses

        except PermissionError as exc:
            logger.warning(
                "PermissionError sending mDNS query for '%s': %s — "
                "multicast requires elevated privileges or run with --offline",
                name, exc
            )
            return []
        finally:
            sock.close()
