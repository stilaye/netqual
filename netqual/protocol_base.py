"""
protocol_base.py — Base Classes for Protocol Testing
=====================================================
Plugin architecture: add new Apple protocols by creating a new class
that inherits from ProtocolSimulator. No changes to core code needed.

To add a new protocol (e.g., AirPlay):
  1. Create airplay_simulator.py
  2. Inherit from ProtocolSimulator
  3. Implement required methods
  4. Add config entry in netqual_config.yaml
  5. Register in PROTOCOL_REGISTRY

Author: Swapnil Tilaye
"""

import yaml
import hashlib
import struct
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Optional


# ============================================================
# Configuration Loader
# ============================================================

_CONFIG_CACHE = None

def load_config(config_path: str = "netqual_config.yaml") -> dict:
    """Load and cache the YAML configuration."""
    global _CONFIG_CACHE
    if _CONFIG_CACHE is None:
        path = Path(config_path)
        if path.exists():
            with open(path) as f:
                _CONFIG_CACHE = yaml.safe_load(f)
        else:
            _CONFIG_CACHE = {}
    return _CONFIG_CACHE


def get_protocol_config(protocol_name: str) -> dict:
    """Get configuration for a specific protocol."""
    config = load_config()
    return config.get("protocols", {}).get(protocol_name, {})


def get_patterns() -> list:
    """Get all log parser patterns from config."""
    config = load_config()
    return config.get("log_parser", {}).get("patterns", [])


def get_thresholds() -> dict:
    """Get pcap parser thresholds from config."""
    config = load_config()
    return config.get("pcap_parser", {}).get("thresholds", {})


# ============================================================
# Session Log (shared across all simulators)
# ============================================================

@dataclass
class SessionLog:
    """Collects log entries from a simulation session."""

    entries: list = field(default_factory=list)

    def log(self, level: str, component: str, message: str):
        """Add a log entry in sysdiagnose-compatible format."""
        ts = datetime.now().strftime("%Y-%m-%dT%H:%M:%S.") + \
             f"{datetime.now().microsecond // 1000:03d}"
        self.entries.append(
            f"{ts} {level:5s} [{component}] {message}"
        )

    def to_text(self) -> str:
        """Return all entries as text (compatible with log_parser)."""
        return "\n".join(self.entries)

    def merge(self, other: "SessionLog"):
        """Merge another session's entries into this one."""
        self.entries.extend(other.entries)


# ============================================================
# BLE Helper (shared across AirDrop, NameDrop, Handoff)
# ============================================================

class BLEHelper:
    """Shared BLE operations for all protocols using BLE discovery."""

    def __init__(self, config: Optional[dict] = None):
        sim_config = load_config().get("simulator", {}).get("ble", {})
        self.hash_prefix_bytes = sim_config.get("hash_prefix_bytes", 2)
        self.max_payload_bytes = sim_config.get("max_payload_bytes", 31)
        self.apple_company_id = b"\x4c\x00"

    def compute_contact_hash(self, identifier: str) -> bytes:
        """Compute SHA-256 hash and truncate for BLE advertisement."""
        return hashlib.sha256(identifier.encode()).digest()[:self.hash_prefix_bytes]

    def build_advertisement(self, hash_prefix: bytes, action_byte: int) -> bytes:
        """Build BLE advertisement payload."""
        payload = (
            bytes([2 + len(self.apple_company_id) + 1 + len(hash_prefix)])
            + bytes([0xFF])
            + self.apple_company_id
            + bytes([action_byte])
            + hash_prefix
        )
        return payload

    def validate_payload(self, payload: bytes) -> dict:
        """Validate a BLE payload against spec."""
        return {
            "size_ok": len(payload) <= self.max_payload_bytes,
            "has_apple_id": self.apple_company_id in payload,
            "size": len(payload),
        }


# ============================================================
# mDNS Helper (shared across AirDrop, Handoff, AirPlay)
# ============================================================

class MDNSHelper:
    """Shared mDNS operations for all protocols using Bonjour discovery."""

    @staticmethod
    def build_query(service: str, qtype: int = 12) -> bytes:
        """Build mDNS query packet for a service."""
        header = struct.pack("!HHHHHH", 0, 0, 1, 0, 0, 0)
        name = b""
        for part in service.split("."):
            name += bytes([len(part)]) + part.encode()
        name += b"\x00"
        question = name + struct.pack("!HH", qtype, 1)
        return header + question

    @staticmethod
    def validate_query(packet: bytes) -> bool:
        """Validate mDNS query packet format."""
        return (
            len(packet) > 12
            and packet[0:2] == b"\x00\x00"
            and (packet[2] & 0x80) == 0
        )


# ============================================================
# Abstract Protocol Simulator
# ============================================================

class ProtocolSimulator(ABC):
    """
    Base class for all Apple protocol simulators.

    To add a new protocol:
      1. Inherit from this class
      2. Implement all abstract methods
      3. Register in PROTOCOL_REGISTRY
    """

    def __init__(self, protocol_name: str):
        self.protocol_name = protocol_name
        self.config = get_protocol_config(protocol_name)
        self.display_name = self.config.get("display_name", protocol_name)
        self.enabled = self.config.get("enabled", True)
        self.log = SessionLog()

    @abstractmethod
    def simulate_discovery(self, **kwargs) -> SessionLog:
        """Simulate the discovery phase of this protocol."""
        pass

    @abstractmethod
    def simulate_session(self, **kwargs) -> SessionLog:
        """Simulate a complete protocol session."""
        pass

    @abstractmethod
    def get_components(self) -> list[str]:
        """Return list of network components this protocol uses."""
        pass

    def get_mdns_service(self) -> Optional[str]:
        """Return mDNS service name if applicable."""
        return self.config.get("mdns_service")


# ============================================================
# Protocol Registry
# ============================================================

# Simulators register themselves here.
# The CLI and test runner discover protocols from this registry.
PROTOCOL_REGISTRY: dict[str, type] = {}


def register_protocol(name: str):
    """Decorator to register a protocol simulator class."""
    def decorator(cls):
        PROTOCOL_REGISTRY[name] = cls
        return cls
    return decorator


def get_available_protocols() -> dict:
    """Return all registered protocols and their enabled status."""
    config = load_config()
    protocols = config.get("protocols", {})
    result = {}
    for name, pconfig in protocols.items():
        result[name] = {
            "display_name": pconfig.get("display_name", name),
            "enabled": pconfig.get("enabled", True),
            "has_simulator": name in PROTOCOL_REGISTRY,
            "description": pconfig.get("description", ""),
        }
    return result


def get_simulator(protocol_name: str) -> Optional[ProtocolSimulator]:
    """Get a simulator instance for the given protocol."""
    if protocol_name in PROTOCOL_REGISTRY:
        return PROTOCOL_REGISTRY[protocol_name](protocol_name)
    return None
