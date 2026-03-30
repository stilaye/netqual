"""
utils/network_conditioner.py
============================
Network conditioning utilities for simulating real-world network environments.

Two backends are supported:

  ComcastConditioner  — wraps the `comcast` CLI (brew install comcast).
                        Calls pfctl+dnctl under the hood. Needs sudo.
                        Full automation: apply, measure, restore in one context.

  NLCConditioner      — builds Network Link Conditioner profile plists.
                        NLC has no public CLI to toggle on/off, so this class
                        handles profile creation/validation only. Toggling
                        still requires the NLC preference pane UI.

Network profiles (3G / 4G / 5G / lossy / high_latency) are shared between
both backends via the NetworkProfile dataclass.

Usage (comcast):
    conditioner = ComcastConditioner()
    with conditioner.profile("3g"):
        response = requests.get("https://apple.com")   # runs under 3G conditions

Usage (NLC):
    nlc = NLCConditioner()
    path = nlc.write_profile(PROFILES["3g"], Path("/tmp/3g.plist"))
    # Import the plist in Network Link Conditioner preference pane
"""

import logging
import plistlib
import shutil
import socket
import subprocess
import time
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path

logger = logging.getLogger(__name__)


# ============================================================
# Network Profile Definitions
# ============================================================


@dataclass
class NetworkProfile:
    """Represents a network conditioning profile."""

    name: str
    bandwidth_kbps: int  # downstream; 0 = unlimited
    latency_ms: int  # one-way added delay in milliseconds
    packet_loss_pct: float  # 0.0 – 100.0
    device: str = "en0"

    @property
    def uplink_kbps(self) -> int:
        """Uplink is half of downlink (typical asymmetric mobile link)."""
        return self.bandwidth_kbps // 2 if self.bandwidth_kbps > 0 else 0


PROFILES: dict[str, NetworkProfile] = {
    "3g": NetworkProfile("3G", 1_000, 200, 2.0),
    "4g": NetworkProfile("4G LTE", 20_000, 40, 0.1),
    "5g": NetworkProfile("5G", 300_000, 5, 0.0),
    "lossy": NetworkProfile("Lossy", 0, 0, 10.0),
    "high_latency": NetworkProfile("High Latency", 0, 500, 0.0),
}


# ============================================================
# Comcast Conditioner
# ============================================================


class ComcastConditioner:
    """
    System-wide network conditioner using the `comcast` CLI tool.

    `comcast` is a thin wrapper around pfctl + dnctl (dummynet) and provides
    a cleaner interface than writing raw pf rules manually.

    Requirements:
        brew install comcast
        sudo privileges at test runtime

    Warning:
        Conditions apply to the entire machine on the specified interface.
        The context manager guarantees teardown even if the test raises.
    """

    def __init__(self, device: str = "en0"):
        self.device = device
        self._active = False

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    @staticmethod
    def is_available() -> bool:
        """Return True if the comcast binary is on PATH."""
        return shutil.which("comcast") is not None

    def apply(self, profile: NetworkProfile) -> None:
        """Apply a network profile system-wide. Requires sudo."""
        if not self.is_available():
            raise RuntimeError("comcast not found — install with: brew install comcast")
        cmd = ["sudo", "comcast", f"--device={profile.device or self.device}"]
        if profile.latency_ms > 0:
            cmd.append(f"--latency={profile.latency_ms}")
        if profile.bandwidth_kbps > 0:
            cmd.append(f"--target-bw={profile.bandwidth_kbps}")
        if profile.packet_loss_pct > 0:
            cmd.append(f"--packet-loss={profile.packet_loss_pct}%")

        logger.info("Applying network profile: %s → %s", profile.name, cmd)
        try:
            subprocess.run(cmd, check=True, capture_output=True)
        except subprocess.CalledProcessError as exc:
            logger.error(
                "comcast failed applying '%s' (exit %d): %s",
                profile.name,
                exc.returncode,
                exc.stderr.decode(errors="replace") if exc.stderr else "(no stderr)",
            )
            raise
        self._active = True

    def restore(self) -> None:
        """Remove all conditioning rules and restore normal network."""
        if self._active:
            try:
                subprocess.run(
                    ["sudo", "comcast", "--stop"],
                    check=True,
                    capture_output=True,
                )
            except subprocess.CalledProcessError as exc:
                logger.error(
                    "comcast --stop failed (exit %d): %s",
                    exc.returncode,
                    exc.stderr.decode(errors="replace") if exc.stderr else "(no stderr)",
                )
                raise
            self._active = False
            logger.info("Network conditioning removed — restored to normal")

    @contextmanager
    def profile(self, name: str):
        """
        Context manager that applies a named profile and always restores.

        Usage:
            with conditioner.profile("3g"):
                latency = measure_tcp_latency("apple.com", 443)
        """
        if name not in PROFILES:
            raise ValueError(f"Unknown profile '{name}'. Choose from: {list(PROFILES)}")
        p = PROFILES[name]
        try:
            self.apply(p)
            yield p
        finally:
            self.restore()

    # ------------------------------------------------------------------
    # Measurement helper
    # ------------------------------------------------------------------

    @staticmethod
    def measure_tcp_latency(host: str, port: int, timeout: int = 10) -> float:
        """Return TCP connection latency in seconds."""
        start = time.monotonic()
        with socket.create_connection((host, port), timeout=timeout):
            pass
        return time.monotonic() - start


# ============================================================
# NLC Conditioner
# ============================================================


class NLCConditioner:
    """
    Network Link Conditioner profile builder.

    Network Link Conditioner (installed via Xcode Additional Tools) uses
    dummynet at the kernel level — the same engine comcast wraps. It has
    no public CLI to enable/disable programmatically.

    This class handles:
      - Building correctly-structured NLC profile plists
      - Writing profiles to disk for manual import
      - Validating profile structure in tests (offline, no sudo)

    To apply a profile manually:
      1. Write the plist:  nlc.write_profile(PROFILES["3g"], Path("3g.plist"))
      2. Open Network Link Conditioner preference pane
      3. Import the plist and enable it
    """

    # Keys required by the NLC preference pane
    REQUIRED_KEYS = frozenset(
        {
            "name",
            "downlink-bandwidth-kbps",
            "uplink-bandwidth-kbps",
            "delay",
            "packet-loss-percent",
        }
    )

    # ------------------------------------------------------------------
    # Profile building
    # ------------------------------------------------------------------

    def build_profile(self, profile: NetworkProfile) -> dict:
        """Return a dict matching the NLC plist profile schema."""
        return {
            "profile": {
                "name": profile.name,
                "downlink-bandwidth-kbps": profile.bandwidth_kbps,
                "uplink-bandwidth-kbps": profile.uplink_kbps,
                "delay": profile.latency_ms,
                "packet-loss-percent": profile.packet_loss_pct,
            }
        }

    def write_profile(self, profile: NetworkProfile, path: Path) -> Path:
        """Serialise a profile to a binary plist file and return the path."""
        data = self.build_profile(profile)
        path.write_bytes(plistlib.dumps(data, fmt=plistlib.FMT_BINARY))
        logger.info("NLC profile written: %s → %s", profile.name, path)
        return path

    def load_profile(self, path: Path) -> dict:
        """Read and deserialise an NLC plist from disk."""
        return plistlib.loads(path.read_bytes())

    def validate_profile(self, profile_dict: dict) -> bool:
        """Return True if the profile dict contains all required NLC keys."""
        inner = profile_dict.get("profile", {})
        return self.REQUIRED_KEYS.issubset(inner.keys())
