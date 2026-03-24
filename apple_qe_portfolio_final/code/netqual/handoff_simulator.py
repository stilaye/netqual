"""
handoff_simulator.py — Handoff Protocol Simulator
===================================================
Simulates NSUserActivity-based Handoff between Apple devices.

Protocol steps:
  1. Source device registers NSUserActivity via BLE advertisement
  2. Destination device detects BLE advertisement
  3. If userInfo < 4KB: delivered via BLE payload
  4. If userInfo > 4KB: continuation stream via AWDL/Wi-Fi
  5. iCloud KV Store syncs activity metadata
  6. Destination device resumes activity in target app

Usage:
    from handoff_simulator import HandoffSimulator
    sim = HandoffSimulator()
    log = sim.simulate_session(
        source_device="iPhone",
        dest_device="Mac",
        activity_type="com.apple.safari.browsing",
        user_info={"url": "https://apple.com", "scroll": 450},
    )
"""

import json
from protocol_base import (
    ProtocolSimulator, register_protocol,
    SessionLog, BLEHelper, MDNSHelper, load_config,
)


@register_protocol("handoff")
class HandoffSimulator(ProtocolSimulator):
    """Simulates Handoff (NSUserActivity) protocol."""

    def __init__(self, protocol_name: str = "handoff"):
        super().__init__(protocol_name)
        self.ble = BLEHelper()
        self.mdns = MDNSHelper()
        # NSUserActivity BLE limit is 4KB (not BLE advertisement 31 bytes)
        self.ble_payload_limit = 4096

    def get_components(self) -> list[str]:
        return self.config.get("components", ["BLE", "Handoff", "iCloud", "NetworkProcess"])

    def simulate_discovery(self, **kwargs) -> SessionLog:
        """Simulate Handoff device discovery via BLE + companion-link."""
        source = kwargs.get("source_device", "iPhone")
        log = SessionLog()

        # BLE advertisement for Handoff
        log.log("INFO", "BLE",
                f"Handoff advertisement started from {source}")

        # mDNS companion-link query
        mdns_service = self.get_mdns_service() or "_companion-link._tcp.local"
        query = self.mdns.build_query(mdns_service)
        log.log("INFO", "mDNS",
                f"Query sent: {mdns_service} (PTR)")

        if self.mdns.validate_query(query):
            log.log("INFO", "mDNS",
                    "Response received: 1 peer found (MacBook-Pro.local)")
        else:
            log.log("ERROR", "mDNS",
                    "Query packet malformed")

        log.log("INFO", "Handoff", "Discovery complete")
        return log

    def simulate_session(self, **kwargs) -> SessionLog:
        """
        Simulate a complete Handoff session.

        Args:
            source_device: Name of source device (e.g., "iPhone")
            dest_device: Name of destination device (e.g., "Mac")
            activity_type: NSUserActivity type (e.g., "com.apple.safari.browsing")
            user_info: Dict of activity data to transfer
        """
        source = kwargs.get("source_device", "iPhone")
        dest = kwargs.get("dest_device", "MacBook-Pro")
        activity_type = kwargs.get("activity_type", "com.apple.safari.browsing")
        user_info = kwargs.get("user_info", {"url": "https://apple.com", "scroll_position": 450})

        log = SessionLog()
        log.log("INFO", "Handoff",
                f"NSUserActivity registered on {source}: {activity_type}")

        # Serialize and check size
        payload = json.dumps(user_info).encode()
        payload_size = len(payload)
        log.log("INFO", "Handoff",
                f"userInfo payload: {payload_size} bytes")

        # Discovery
        discovery_log = self.simulate_discovery(source_device=source)
        log.merge(discovery_log)

        # Transfer path decision
        if payload_size <= self.ble_payload_limit:
            # Small payload — via BLE
            log.log("INFO", "Handoff",
                    f"Payload under {self.ble_payload_limit} bytes — using BLE transfer path")
            log.log("INFO", "BLE",
                    f"Activity data transmitted via BLE advertisement ({payload_size} bytes)")
        else:
            # Large payload — via Continuation Stream (AWDL/Wi-Fi)
            log.log("INFO", "Handoff",
                    f"Payload exceeds {self.ble_payload_limit} bytes — using Continuation Stream")
            log.log("INFO", "AWDL",
                    "Establishing P2P channel for Continuation Stream")
            log.log("INFO", "TLS",
                    "Handshake complete: TLSv1.3 for Continuation Stream")
            log.log("INFO", "Handoff",
                    f"Activity data transmitted via Continuation Stream ({payload_size} bytes)")

        # iCloud sync
        log.log("INFO", "iCloud",
                f"KV Store sync: {activity_type} metadata updated")

        # Destination picks up
        log.log("INFO", "Handoff",
                f"Activity transferred to {dest}: {activity_type}")
        log.log("INFO", "Handoff",
                f"Destination app launched on {dest}")

        return log


# ============================================================
# CLI
# ============================================================

if __name__ == "__main__":
    sim = HandoffSimulator()

    print(f"\n{'='*60}")
    print(f"  NetQual — Handoff Protocol Simulator")
    print(f"{'='*60}")

    # Small payload (BLE path)
    print(f"\n  --- Small Payload (BLE path) ---\n")
    log = sim.simulate_session(
        source_device="iPhone",
        dest_device="MacBook-Pro",
        activity_type="com.apple.safari.browsing",
        user_info={"url": "https://apple.com/iphone", "scroll": 450},
    )
    print(log.to_text())

    # Large payload (Continuation Stream path)
    print(f"\n  --- Large Payload (Continuation Stream) ---\n")
    log = sim.simulate_session(
        source_device="iPhone",
        dest_device="MacBook-Pro",
        activity_type="com.apple.pages.editing",
        user_info={"doc_id": "doc-123", "content": "A" * 5000},
    )
    print(log.to_text())
