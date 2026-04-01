"""
test_sysdiagnose_analysis.py
============================
Validate real AirDrop protocol behaviour using a captured iPhone sysdiagnose bundle.

Unlike simulation tests, these assertions run against actual device state —
what the kernel, AWDL daemon, and Bluetooth stack reported during a live session.

Sysdiagnose path is resolved via:
  1. SYSDIAGNOSE_PATH environment variable
  2. sysdiagnose_path fixture in conftest.py (falls back to bundled sample)

Run all:
    pytest tests/test_sysdiagnose_analysis.py -v

Run offline only (skips log archive commands):
    pytest tests/test_sysdiagnose_analysis.py -m "not network and not requires_sudo" -v
"""

import os
import re
from pathlib import Path

import pytest

from utils.sysdiagnose_parser import SysdiagnoseParser

# ============================================================
# Shared fixture — resolves sysdiagnose bundle path
# ============================================================


@pytest.fixture(scope="module")
def sysd(sysdiagnose_path):
    """Return a SysdiagnoseParser for the configured bundle.

    Args:
        sysdiagnose_path: Path fixture from conftest.py.

    Returns:
        SysdiagnoseParser instance, or None if no bundle is available.
    """
    if sysdiagnose_path is None:
        return None
    return SysdiagnoseParser(sysdiagnose_path)


def skip_if_no_bundle(sysd):
    """Skip the test if no sysdiagnose bundle was configured."""
    if sysd is None:
        pytest.skip("No sysdiagnose bundle configured — set SYSDIAGNOSE_PATH env var")


# ============================================================
# AWDL Analysis
# Validates the Apple Wireless Direct Link layer —
# the P2P Wi-Fi transport that carries AirDrop file data.
# ============================================================


class TestAWDLAnalysis:
    """Assertions against WiFi/awdl_status.txt.

    AWDL (Apple Wireless Direct Link) is the peer-to-peer Wi-Fi
    transport beneath AirDrop. These tests confirm the protocol
    behaved correctly during the captured session.
    """

    def test_awdl_was_enabled(self, sysd):
        """AWDL daemon must be running for AirDrop to function.

        Expected: awdl_status.txt reports 'awdl is enabled'.
        """
        skip_if_no_bundle(sysd)
        status = sysd.awdl()
        assert status.enabled, (
            "AWDL was not enabled at capture time. "
            "AirDrop cannot function without AWDL — check Wi-Fi settings."
        )

    def test_awdl_data_state_occurred(self, sysd):
        """Data state duration > 0 confirms a real file transfer happened.

        AWDL transitions through: Discovery → Idle → Data.
        Non-zero Data duration = bytes were actually exchanged.

        Expected: data_duration_ms > 0 ms.
        """
        skip_if_no_bundle(sysd)
        status = sysd.awdl()
        assert status.data_duration_ms > 0, (
            f"AWDL Data state duration was {status.data_duration_ms} ms. "
            "Expected > 0 — no file transfer appears to have occurred."
        )

    def test_awdl_peer_was_discovered(self, sysd):
        """At least one AWDL peer must be discovered for a transfer.

        Expected: peers_discovered >= 1.
        """
        skip_if_no_bundle(sysd)
        status = sysd.awdl()
        assert status.peers_discovered >= 1, (
            f"AWDL discovered {status.peers_discovered} peers. "
            "AirDrop requires at least one peer to be visible."
        )

    def test_awdl_discoverable_mode_is_contacts_only(self, sysd):
        """'Contacts Only' mode means the BLE hash filter is active.

        In this mode the device only becomes visible to senders whose
        phone/email SHA-256 hash matches the receiver's contact list.

        Expected: discoverable_mode == 'Contacts Only'.
        """
        skip_if_no_bundle(sysd)
        status = sysd.awdl()
        assert status.discoverable_mode == "Contacts Only", (
            f"Discoverable mode was '{status.discoverable_mode}', expected 'Contacts Only'. "
            "Verify AirDrop setting on device."
        )

    def test_awdl_encryption_is_disabled_at_transport_layer(self, sysd):
        """AWDL itself is unencrypted by design — security lives in TLS above it.

        This is expected behaviour: AWDL is a transport layer, not a security
        layer. AirDrop uses mutual TLS 1.3 on top of AWDL for all file data.
        Flagging this as 'enabled' would indicate a misconfiguration.

        Expected: encryption_enabled == False.
        """
        skip_if_no_bundle(sysd)
        status = sysd.awdl()
        assert not status.encryption_enabled, (
            "AWDL encryption was reported as ENABLED — this is unexpected. "
            "AWDL transport should be unencrypted; TLS 1.3 handles security above it."
        )

    def test_awdl_master_channel_is_valid_wifi_channel(self, sysd):
        """AWDL master channel must be a valid 2.4 GHz Wi-Fi channel (1–13).

        Channel 6 is typical. AWDL alternates between 2.4 GHz and 5 GHz
        slots to coexist with infrastructure Wi-Fi.

        Expected: master_channel in 1..13.
        """
        skip_if_no_bundle(sysd)
        status = sysd.awdl()
        assert status.master_channel is not None, "AWDL master channel not found in status file"
        assert (
            1 <= status.master_channel <= 13
        ), f"AWDL master channel {status.master_channel} is outside the valid 2.4 GHz range (1–13)."

    def test_awdl_secondary_channel_is_5ghz(self, sysd):
        """Secondary AWDL channel must be in the 5 GHz band (36–165).

        Channel 149 is a common DFS channel used by AWDL for 5 GHz slots.

        Expected: secondary_channel in 36..165.
        """
        skip_if_no_bundle(sysd)
        status = sysd.awdl()
        assert (
            status.secondary_channel is not None
        ), "AWDL secondary channel not found in status file"
        assert (
            36 <= status.secondary_channel <= 165
        ), f"AWDL secondary channel {status.secondary_channel} is outside the 5 GHz range (36–165)."

    def test_awdl_rx_bytes_nonzero_during_transfer(self, sysd):
        """Receiver must have accumulated Rx bytes if a transfer happened.

        Expected: rx_bytes > 0 (consistent with data_duration_ms > 0).
        """
        skip_if_no_bundle(sysd)
        status = sysd.awdl()
        if status.data_duration_ms > 0:
            assert status.rx_bytes > 0 or status.tx_bytes > 0, (
                "Data state was active but both Rx and Tx bytes are 0. "
                "Expected non-zero traffic when AWDL Data state occurred."
            )

    def test_awdl_ipv6_is_link_local(self, sysd):
        """awdl0 must have a link-local IPv6 address (fe80::/10).

        AirDrop uses IPv6 link-local for addressing over AWDL — a global
        address would be incorrect and indicate a misconfiguration.

        Expected: IPv6 address starts with 'fe80::'.
        """
        skip_if_no_bundle(sysd)
        status = sysd.awdl()
        if status.ipv6_address:
            assert status.ipv6_address.startswith("fe80::"), (
                f"awdl0 IPv6 '{status.ipv6_address}' is not link-local (fe80::/10). "
                "AirDrop requires a link-local address on awdl0."
            )


# ============================================================
# BLE Analysis
# Validates the Bluetooth Low Energy layer —
# the discovery/advertisement layer that precedes AWDL.
# ============================================================


class TestBLEAnalysis:
    """Assertions against WiFi/bluetooth_status.txt.

    BLE is used for the AirDrop discovery phase — before AWDL
    takes over for file transfer. The BLE advertisement carries
    the truncated SHA-256 hash used for "Contacts Only" filtering.
    """

    def test_bluetooth_was_on(self, sysd):
        """Bluetooth must be powered on for AirDrop to advertise or discover.

        Expected: power == 'On'.
        """
        skip_if_no_bundle(sysd)
        status = sysd.bluetooth()
        assert status.power == "On", (
            f"Bluetooth power was '{status.power}'. "
            "AirDrop requires Bluetooth to be On for BLE advertisement."
        )

    def test_bluetooth_mac_is_valid(self, sysd):
        """Device must report a valid 48-bit MAC address.

        Expected: MAC matches XX:XX:XX:XX:XX:XX format.
        """
        skip_if_no_bundle(sysd)
        status = sysd.bluetooth()
        assert re.match(
            r"^([0-9a-fA-F]{2}:){5}[0-9a-fA-F]{2}$", status.mac_address
        ), f"Bluetooth MAC '{status.mac_address}' is not a valid 48-bit MAC address."

    def test_bluetooth_not_discoverable_in_contacts_only_mode(self, sysd):
        """In 'Contacts Only' mode, BT classic should NOT be openly discoverable.

        AirDrop uses BLE advertisements (not classic BT discovery) for the
        contacts hash exchange. Classic BT discoverable = unrelated setting.

        Expected: discoverable == False (correct for a production device).
        """
        skip_if_no_bundle(sysd)
        status = sysd.bluetooth()
        assert not status.discoverable, (
            "Bluetooth was set to Discoverable. "
            "Production iPhones should not be BT-discoverable; "
            "AirDrop uses BLE advertisements, not classic BT inquiry."
        )

    def test_bluetooth_has_paired_devices(self, sysd):
        """A real device should have at least one paired BT device.

        This confirms the Bluetooth stack is functioning correctly
        (not a factory-reset state).

        Expected: total_devices > 0.
        """
        skip_if_no_bundle(sysd)
        status = sysd.bluetooth()
        assert status.total_devices > 0, (
            "No Bluetooth devices in inventory. "
            "Expected at least one paired or known device on a real device."
        )


# ============================================================
# AirDrop Session Evidence
# Cross-file assertions that combine AWDL + BLE data to
# confirm a complete AirDrop session occurred.
# ============================================================


class TestAirDropSessionEvidence:
    """Cross-file assertions confirming a complete AirDrop session.

    AirDrop stages:
      1. BLE advertisement (sender broadcasts truncated contact hash)
      2. AWDL peer discovery (channel election, peer found)
      3. mDNS ._airdrop._tcp.local (service registration)
      4. TLS mutual auth + /Discover handshake (sharingd)
      5. File transfer over AWDL + TCP (Data state)
    """

    def test_full_pipeline_evidence(self, sysd):
        """Confirm BLE was on AND AWDL Data state occurred.

        This is the minimal evidence of a complete AirDrop session:
        - BLE powered = advertisement/discovery phase was possible
        - Data state > 0 = file transfer actually happened

        Expected: bluetooth.power == 'On' AND awdl.data_duration_ms > 0.
        """
        skip_if_no_bundle(sysd)
        ble = sysd.bluetooth()
        awdl = sysd.awdl()
        assert ble.power == "On", "BLE was off — AirDrop discovery phase could not have started"
        assert (
            awdl.data_duration_ms > 0
        ), "BLE was on but no AWDL Data state — transfer did not complete"

    def test_contacts_only_privacy_gate_active(self, sysd):
        """Confirm the privacy gate was active at the time of the transfer.

        'Contacts Only' means the 22-bit truncated SHA-256 filter was in
        effect — the device was not visible to arbitrary senders.

        Expected: discoverable_mode == 'Contacts Only' AND BLE not openly discoverable.
        """
        skip_if_no_bundle(sysd)
        awdl = sysd.awdl()
        ble = sysd.bluetooth()
        assert awdl.discoverable_mode == "Contacts Only", (
            f"AWDL discoverable mode was '{awdl.discoverable_mode}', not 'Contacts Only'. "
            "Privacy gate may not have been active."
        )
        assert (
            not ble.discoverable
        ), "BT was set to Discoverable — unexpected for a device in Contacts Only mode."

    def test_awdl_transport_security_model(self, sysd):
        """Confirm AWDL is unencrypted and TLS carries the security.

        This is a deliberate design choice: AWDL = transport,
        TLS 1.3 mutual auth = security. Both conditions should be
        true simultaneously in a healthy AirDrop session.

        Expected: awdl.encryption_enabled == False (TLS handles it above).
        """
        skip_if_no_bundle(sysd)
        awdl = sysd.awdl()
        # AWDL itself should be unencrypted (TLS sits above it)
        assert not awdl.encryption_enabled, (
            "AWDL encryption was ENABLED — unexpected. "
            "AirDrop security model: AWDL is unencrypted transport, TLS 1.3 is the security layer."
        )

    def test_dual_band_channel_strategy(self, sysd):
        """Confirm AWDL uses both 2.4 GHz and 5 GHz channels.

        Dual-band channel hopping lets AWDL coexist with infrastructure
        Wi-Fi — it alternates slots between 2.4 GHz and 5 GHz DFS channels.

        Expected: master on 2.4 GHz (1–13), secondary on 5 GHz (36–165).
        """
        skip_if_no_bundle(sysd)
        awdl = sysd.awdl()
        assert awdl.master_channel is not None, "AWDL master channel not found in status file"
        assert (
            1 <= awdl.master_channel <= 13
        ), f"Expected 2.4 GHz master channel (1–13), got {awdl.master_channel}"
        assert awdl.secondary_channel is not None, "AWDL secondary channel not found in status file"
        assert (
            36 <= awdl.secondary_channel <= 165
        ), f"Expected 5 GHz secondary channel (36–165), got {awdl.secondary_channel}"
