"""
sysdiagnose_parser.py
=====================
Parse key files from an iPhone/Mac sysdiagnose bundle to validate
AirDrop protocol behaviour under real device conditions.

Supported files:
  WiFi/awdl_status.txt      — AWDL mode, channels, election, peer count, Data state
  WiFi/bluetooth_status.txt — BLE power, MAC, scan state, device inventory

Usage:
    from utils.sysdiagnose_parser import SysdiagnoseParser

    parser = SysdiagnoseParser("/path/to/sysdiagnose_root/")
    awdl = parser.awdl()
    ble  = parser.bluetooth()

    assert awdl.data_duration_ms > 0          # transfer happened
    assert awdl.discoverable_mode == "Contacts Only"
    assert ble.power == "On"
"""

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

# ============================================================
# AWDL Status
# ============================================================


@dataclass
class AWDLStatus:
    """Parsed state from WiFi/awdl_status.txt.

    Attributes:
        enabled: True if AWDL daemon reported "awdl is enabled".
        mode: Scheduling mode, e.g. "AUTO".
        master_channel: Primary channel (typically 6 = 2.4 GHz).
        secondary_channel: Secondary channel (typically 149 = 5 GHz DFS).
        election_state: "master" or "slave".
        peers_discovered: Number of peers found during the session.
        data_duration_ms: Total milliseconds spent in Data state (> 0 = transfer occurred).
        discoverable_mode: "Contacts Only", "Everyone", or "No One".
        encryption_enabled: False by design — AWDL transport is unencrypted; TLS sits above.
        rx_bytes: Bytes received over AWDL.
        tx_bytes: Bytes transmitted over AWDL.
        ipv6_address: Link-local IPv6 of awdl0 interface.
    """

    enabled: bool = False
    mode: str = ""
    master_channel: Optional[int] = None
    secondary_channel: Optional[int] = None
    election_state: str = ""
    peers_discovered: int = 0
    data_duration_ms: int = 0
    discoverable_mode: str = ""
    encryption_enabled: bool = False
    rx_bytes: int = 0
    tx_bytes: int = 0
    ipv6_address: str = ""


@dataclass
class BluetoothDevice:
    """A single paired/connected BT device entry.

    Attributes:
        name: Device display name.
        address: Bluetooth MAC address.
        paired: Whether the device is paired.
        connected: Whether the device is currently connected.
        is_apple: Whether iOS/macOS flagged this as an Apple device.
    """

    name: str = ""
    address: str = ""
    paired: bool = False
    connected: bool = False
    is_apple: bool = False


@dataclass
class BluetoothStatus:
    """Parsed state from WiFi/bluetooth_status.txt.

    Attributes:
        power: "On" or "Off".
        mac_address: This device's BT MAC address.
        discoverable: Whether BT is in discoverable mode.
        scanning: Whether BT is actively scanning at capture time.
        total_devices: Count of all known devices.
        connected_devices: Devices with Connected: Yes.
    """

    power: str = ""
    mac_address: str = ""
    discoverable: bool = False
    scanning: bool = False
    total_devices: int = 0
    connected_devices: list = field(default_factory=list)


# ============================================================
# Parsers
# ============================================================


class AWDLStatusParser:
    """Parse WiFi/awdl_status.txt from a sysdiagnose bundle.

    Args:
        path: Path to awdl_status.txt.

    Example:
        parser = AWDLStatusParser("/sysdiagnose/WiFi/awdl_status.txt")
        status = parser.parse()
        assert status.data_duration_ms > 0
    """

    def __init__(self, path: Path) -> None:
        self._path = Path(path)

    def parse(self) -> AWDLStatus:
        """Parse the file and return an AWDLStatus dataclass.

        Returns:
            AWDLStatus with all fields populated from the file.

        Raises:
            FileNotFoundError: If awdl_status.txt does not exist.
        """
        text = self._path.read_text(errors="replace")
        status = AWDLStatus()

        # --- Basic state ---
        status.enabled = bool(re.search(r"awdl is enabled", text))
        status.encryption_enabled = bool(re.search(r"awdl encryption is ENABLED", text, re.I))

        m = re.search(r"awdl mode\s*=\s*(\S+)", text)
        if m:
            status.mode = m.group(1)

        m = re.search(r"IPv6:\s*(\S+)", text)
        if m:
            status.ipv6_address = m.group(1)

        # --- Channels ---
        m = re.search(r"awdl master channel\s*=\s*(\d+)", text)
        if m:
            status.master_channel = int(m.group(1))

        m = re.search(r"awdl secondary master channel\s*=\s*(\d+)", text)
        if m:
            status.secondary_channel = int(m.group(1))

        # --- Election ---
        m = re.search(r"awdl state:\s*(\w+)", text)
        if m:
            status.election_state = m.group(1).lower()

        # --- Discoverable mode ---
        m = re.search(r"AirDrop Discoverable Mode:\s*(.+)", text)
        if m:
            status.discoverable_mode = m.group(1).strip()

        # --- Peer count ---
        m = re.search(r"# of Peers Discovered\s*=\s*(\d+)", text)
        if m:
            status.peers_discovered = int(m.group(1))

        # --- Traffic ---
        m = re.search(r"Rx Bytes\s*=\s*(\d+)", text)
        if m:
            status.rx_bytes = int(m.group(1))

        m = re.search(r"Tx Bytes\s*=\s*(\d+)", text)
        if m:
            status.tx_bytes = int(m.group(1))

        # --- Data state duration ---
        # Table row: "  Data   <count>   <duration_ms>"
        m = re.search(r"^\s*Data\s+\d+\s+(\d+)", text, re.MULTILINE)
        if m:
            status.data_duration_ms = int(m.group(1))

        return status


class BluetoothStatusParser:
    """Parse WiFi/bluetooth_status.txt from a sysdiagnose bundle.

    Args:
        path: Path to bluetooth_status.txt.

    Example:
        parser = BluetoothStatusParser("/sysdiagnose/WiFi/bluetooth_status.txt")
        status = parser.parse()
        assert status.power == "On"
    """

    def __init__(self, path: Path) -> None:
        self._path = Path(path)

    def parse(self) -> BluetoothStatus:
        """Parse the file and return a BluetoothStatus dataclass.

        Returns:
            BluetoothStatus with all fields populated from the file.

        Raises:
            FileNotFoundError: If bluetooth_status.txt does not exist.
        """
        text = self._path.read_text(errors="replace")
        status = BluetoothStatus()

        m = re.search(r"Power\s*:\s*(\S+)", text)
        if m:
            status.power = m.group(1)

        m = re.search(r"MAC Address\s*:\s*([0-9a-fA-F:]{17})", text)
        if m:
            status.mac_address = m.group(1)

        m = re.search(r"Discoverable\s*:\s*(\S+)", text)
        if m:
            status.discoverable = m.group(1).lower() == "yes"

        m = re.search(r"Scanning\s*:\s*(\S+)", text)
        if m:
            status.scanning = m.group(1).lower() == "yes"

        m = re.search(r"Devices\s*:\s*(\d+)", text)
        if m:
            status.total_devices = int(m.group(1))

        # Parse individual device blocks
        # Each block starts with a device name on its own line, followed by indented fields
        blocks = re.split(r"\n(?=\S)", text)
        current_name = ""
        for block in blocks:
            lines = block.strip().splitlines()
            if not lines:
                continue
            # Device name is a non-indented line not starting with '#' or known field patterns
            first = lines[0].strip()
            if first and not first.startswith("#") and ":" not in first:
                current_name = first
            elif current_name:
                device = BluetoothDevice(name=current_name)
                for line in lines:
                    if re.search(r"Address\s*:\s*([0-9a-fA-F:]{17})", line):
                        device.address = re.search(r"Address\s*:\s*([0-9a-fA-F:]{17})", line).group(
                            1
                        )
                    if re.search(r"Connected\s*:\s*Yes", line):
                        device.connected = True
                    if re.search(r"Paired\s*:\s*Yes", line):
                        device.paired = True
                    if re.search(r"Apple\s*:\s*Yes", line):
                        device.is_apple = True
                if device.connected:
                    status.connected_devices.append(device)
                current_name = ""

        return status


# ============================================================
# Top-level facade
# ============================================================


class SysdiagnoseParser:
    """Facade for parsing an entire sysdiagnose bundle.

    Resolves file paths relative to the bundle root and delegates
    to individual sub-parsers.

    Args:
        root: Path to the sysdiagnose root directory
              (the folder containing system_logs.logarchive, WiFi/, logs/, etc.).

    Example:
        parser = SysdiagnoseParser("/path/to/sysdiagnose_root/")
        awdl = parser.awdl()
        ble  = parser.bluetooth()

        # Was there an actual AirDrop data transfer?
        assert awdl.data_duration_ms > 0, "No Data state in AWDL — transfer may not have occurred"
    """

    # Relative paths within any sysdiagnose bundle (iOS + macOS)
    _AWDL_PATH = Path("WiFi") / "awdl_status.txt"
    _BT_PATH = Path("WiFi") / "bluetooth_status.txt"

    def __init__(self, root: str | Path) -> None:
        self._root = Path(root)
        if not self._root.is_dir():
            raise FileNotFoundError(f"Sysdiagnose root not found: {self._root}")

    def awdl(self) -> AWDLStatus:
        """Parse and return AWDL status.

        Returns:
            AWDLStatus dataclass.

        Raises:
            FileNotFoundError: If WiFi/awdl_status.txt is absent.
        """
        path = self._root / self._AWDL_PATH
        if not path.is_file():
            raise FileNotFoundError(f"awdl_status.txt not found at {path}")
        return AWDLStatusParser(path).parse()

    def bluetooth(self) -> BluetoothStatus:
        """Parse and return Bluetooth/BLE status.

        Returns:
            BluetoothStatus dataclass.

        Raises:
            FileNotFoundError: If WiFi/bluetooth_status.txt is absent.
        """
        path = self._root / self._BT_PATH
        if not path.is_file():
            raise FileNotFoundError(f"bluetooth_status.txt not found at {path}")
        return BluetoothStatusParser(path).parse()

    def has_awdl(self) -> bool:
        """Return True if WiFi/awdl_status.txt exists in this bundle."""
        return (self._root / self._AWDL_PATH).is_file()

    def has_bluetooth(self) -> bool:
        """Return True if WiFi/bluetooth_status.txt exists in this bundle."""
        return (self._root / self._BT_PATH).is_file()
