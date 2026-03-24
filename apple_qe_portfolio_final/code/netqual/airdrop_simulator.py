"""
airdrop_simulator.py — AirDrop Protocol Simulator
===================================================
Simulates the AirDrop discovery and transfer protocol using the shared
protocol_base classes (BLEHelper, MDNSHelper, SessionLog, ProtocolSimulator).

Protocol steps simulated:
  1. BLE Advertisement (sender broadcasts truncated contact hash)
  2. mDNS Discovery (query _airdrop._tcp.local)
  3. Contact Resolution (match hash against contacts list)
  4. AWDL Channel Setup (P2P Wi-Fi)
  5. TLS 1.3 Mutual Authentication
  6. File Transfer
  7. Session Cleanup

Usage:
    from airdrop_simulator import AirDropSimulator
    sim = AirDropSimulator()
    log = sim.simulate_discovery(sender_email="alice@icloud.com")
    log = sim.simulate_session(
        sender_email="alice@icloud.com",
        receiver_email="bob@icloud.com",
        file_name="vacation.heic",
        file_size_mb=8.5,
    )
"""

from dataclasses import dataclass
from typing import Optional

from protocol_base import (
    BLEHelper,
    MDNSHelper,
    ProtocolSimulator,
    SessionLog,
    register_protocol,
)


# ============================================================
# AirDrop-specific Data Models
# ============================================================

@dataclass
class ContactMatch:
    """Result of AirDrop identity resolution."""

    matched: bool
    contact_name: str = ""
    matched_on: str = ""   # "email" or "phone"
    hash_prefix: bytes = b""


# ============================================================
# AirDrop Simulator
# ============================================================

@register_protocol("airdrop")
class AirDropSimulator(ProtocolSimulator):
    """
    Simulates AirDrop protocol for testing and demonstration.

    Inherits shared BLE/mDNS helpers and SessionLog from ProtocolSimulator.
    Registered in PROTOCOL_REGISTRY under "airdrop" via @register_protocol.

    Args:
        protocol_name: Registry key — defaults to "airdrop".
        contacts: Optional dict of {email: {name, phone}} for contact matching.
                  Defaults to three built-in test contacts.
    """

    # BLE action bytes per Apple spec
    ACTION_AIRDROP = 0x05
    ACTION_NAMEDROP = 0x14

    def __init__(
        self,
        protocol_name: str = "airdrop",
        contacts: Optional[dict] = None,
    ):
        super().__init__(protocol_name)
        self.ble = BLEHelper()
        self.mdns = MDNSHelper()
        self.contacts = contacts or {
            "alice@icloud.com": {"name": "Alice", "phone": "+14155551001"},
            "bob@icloud.com":   {"name": "Bob",   "phone": "+14155551002"},
            "carol@example.com":{"name": "Carol", "phone": "+14155551003"},
        }

    # ---- Required abstract method implementations ----

    def get_components(self) -> list[str]:
        """Return network components used by AirDrop."""
        return self.config.get(
            "components", ["BLE", "AirDrop", "mDNS", "AWDL", "TLS"]
        )

    def simulate_discovery(self, **kwargs) -> SessionLog:
        """
        Simulate AirDrop discovery phase.

        Kwargs:
            sender_email (str): Sender's iCloud email.
            action (str): "airdrop" (default) or "namedrop".

        Returns:
            SessionLog compatible with log_parser.
        """
        sender_email = kwargs.get("sender_email", "alice@icloud.com")
        action = kwargs.get("action", "airdrop")
        feature = "AirDrop" if action == "airdrop" else "NameDrop"
        action_byte = self.ACTION_AIRDROP if action == "airdrop" else self.ACTION_NAMEDROP

        log = SessionLog()

        # Step 1: BLE Advertisement
        hash_prefix = self.ble.compute_contact_hash(sender_email)
        payload = self.ble.build_advertisement(hash_prefix, action_byte)

        log.log("INFO", "BLE",
                f"Starting advertisement: action=0x{action_byte:02X}, "
                f"hash_prefix=0x{hash_prefix.hex().upper()}")
        log.log("INFO", "BLE",
                f"Advertisement payload: {len(payload)} bytes, Apple Company ID 0x004C")

        validation = self.ble.validate_payload(payload)
        if not validation["size_ok"]:
            log.log("ERROR", "BLE",
                    f"Advertisement payload invalid: {len(payload)} bytes (max 31)")
            return log

        # Step 2: mDNS Discovery
        mdns_service = self.get_mdns_service() or "_airdrop._tcp.local"
        query_packet = self.mdns.build_query(mdns_service)
        log.log("INFO", "mDNS", f"Query sent: {mdns_service} (PTR)")

        if not self.mdns.validate_query(query_packet):
            log.log("ERROR", "mDNS", "Query packet malformed")
            return log

        peers_found = len(self.contacts)
        log.log("INFO", "mDNS",
                f"Response received: {peers_found} peers found on local network")

        # Step 3: Contact Resolution
        log.log("INFO", feature,
                f"Identity resolution: checking {peers_found} peers against "
                f"{len(self.contacts)} contacts")

        match = self.resolve_contact(hash_prefix)
        if match.matched:
            log.log("INFO", feature,
                    f"Contact matched: {match.contact_name} "
                    f"(matched on {match.matched_on})")
        else:
            log.log("INFO", feature,
                    f"No contact match — sender appears as '{feature}' "
                    f"(hash: 0x{hash_prefix.hex().upper()})")

        log.log("INFO", feature, "Discovery phase complete")
        return log

    def simulate_session(self, **kwargs) -> SessionLog:
        """
        Simulate a complete AirDrop transfer session.

        Kwargs: same as simulate_full_transfer (sender_email, receiver_email,
                file_name, file_size_mb, success).
        """
        return self.simulate_full_transfer(**kwargs)

    # ---- AirDrop-specific helpers ----

    def resolve_contact(self, hash_prefix: bytes) -> ContactMatch:
        """Match a BLE hash prefix against the contacts list."""
        for email, info in self.contacts.items():
            if self.ble.compute_contact_hash(email) == hash_prefix:
                return ContactMatch(
                    matched=True,
                    contact_name=info["name"],
                    matched_on="email",
                    hash_prefix=hash_prefix,
                )
            if self.ble.compute_contact_hash(info["phone"]) == hash_prefix:
                return ContactMatch(
                    matched=True,
                    contact_name=info["name"],
                    matched_on="phone",
                    hash_prefix=hash_prefix,
                )
        return ContactMatch(matched=False, hash_prefix=hash_prefix)

    # ---- Simulation Scenarios ----

    def simulate_full_transfer(
        self,
        sender_email: str = "alice@icloud.com",
        receiver_email: str = "bob@icloud.com",
        file_name: str = "photo.heic",
        file_size_mb: float = 4.2,
        success: bool = True,
        **kwargs,
    ) -> SessionLog:
        """
        Simulate a complete AirDrop file transfer.

        Returns:
            SessionLog compatible with log_parser.
        """
        log = SessionLog()
        log.log("INFO", "AirDrop",
                f"User initiated share: {file_name} ({file_size_mb}MB)")

        # Discovery phase
        discovery_log = self.simulate_discovery(sender_email=sender_email)
        log.merge(discovery_log)

        # AWDL Connection
        log.log("INFO", "AWDL", "Initiating P2P Wi-Fi channel with receiver")
        if success:
            log.log("INFO", "AWDL", "Channel established: 5GHz, bandwidth=80MHz")
        else:
            log.log("ERROR", "AWDL",
                    "Peer connection failed: timeout waiting for channel negotiation")
            return log

        # TLS Handshake
        log.log("INFO", "TLS", "Mutual authentication started")
        log.log("INFO", "TLS",
                "Handshake complete: TLSv1.3, TLS_CHACHA20_POLY1305_SHA256")

        # File Transfer
        log.log("INFO", "AirDrop", f"Sending offer: {file_name} ({file_size_mb}MB)")
        log.log("INFO", "AirDrop", "Offer accepted by receiver")
        log.log("INFO", "AirDrop", f"Transfer started: {file_name}")

        for pct in [25, 50, 75, 100]:
            transferred = file_size_mb * pct / 100
            log.log("INFO", "AirDrop",
                    f"Transfer progress: {pct}% ({transferred:.2f}MB)")

        transfer_time_ms = int(file_size_mb * 476)  # ~2.1 Mbps simulated
        throughput = file_size_mb * 8 / (transfer_time_ms / 1000)
        log.log("INFO", "AirDrop",
                f"Transfer complete: {file_size_mb}MB in {transfer_time_ms}ms "
                f"({throughput:.1f} Mbps)")

        # Cleanup
        log.log("INFO", "AWDL", "P2P channel closed")
        log.log("INFO", "BLE", "Advertisement stopped")

        return log

    def simulate_namedrop(self, sender_email: str) -> SessionLog:
        """Simulate a NameDrop contact share session."""
        return self.simulate_discovery(sender_email=sender_email, action="namedrop")


# ============================================================
# CLI
# ============================================================

if __name__ == "__main__":
    sim = AirDropSimulator()

    print(f"\n{'='*60}")
    print(f"  NetQual — AirDrop Protocol Simulator")
    print(f"{'='*60}\n")

    print("  --- AirDrop Discovery (alice@icloud.com) ---\n")
    log = sim.simulate_discovery(sender_email="alice@icloud.com")
    print(log.to_text())

    print(f"\n  --- Full AirDrop Transfer ---\n")
    log = sim.simulate_full_transfer(
        sender_email="alice@icloud.com",
        receiver_email="bob@icloud.com",
        file_name="vacation.heic",
        file_size_mb=8.5,
    )
    print(log.to_text())

    print(f"\n  --- NameDrop Session ---\n")
    log = sim.simulate_namedrop("alice@icloud.com")
    print(log.to_text())

    print(f"\n  --- Failed Transfer (AWDL timeout) ---\n")
    log = sim.simulate_full_transfer(
        sender_email="alice@icloud.com",
        receiver_email="bob@icloud.com",
        success=False,
    )
    print(log.to_text())
