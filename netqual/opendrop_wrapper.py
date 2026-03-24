"""
opendrop_wrapper.py — OpenDrop Integration for Real AirDrop Testing
====================================================================
Wraps the OpenDrop CLI (https://github.com/seemoo-lab/opendrop) to
perform real AirDrop operations and capture protocol-level data.

OpenDrop is an open-source Python implementation of the AirDrop protocol
using reverse-engineered Apple stack (AWDL + BLE + TLS).

Requirements:
  - macOS with AWDL support
  - pip install opendrop
  - AirDrop set to "Everyone" on receiver device
  - OWL (Open Wireless Link) for AWDL on Linux: https://github.com/seemoo-lab/owl

Usage:
    from opendrop_wrapper import OpenDropTester
    tester = OpenDropTester()

    # Discover nearby AirDrop devices
    devices = tester.discover()

    # Send a file to a discovered device
    result = tester.send_file("photo.jpg", target_name="iPhone")

    # Receive files (listen mode)
    tester.receive(output_dir="/tmp/airdrop_received")

Limitations:
  - Only works when AirDrop is set to "Everyone" (no Contacts Only)
  - Requires AWDL support (macOS native, Linux via OWL)
  - Experimental — not 100% feature complete
  - Cannot test NameDrop or Handoff (AirDrop protocol only)

Author: Swapnil Tilaye
"""

import subprocess
import shutil
import json
import time
import platform
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional
from datetime import datetime


# ============================================================
# Data Models
# ============================================================

@dataclass
class AirDropDevice:
    """A discovered AirDrop device."""

    name: str
    id: str
    model: str = ""


@dataclass
class TransferResult:
    """Result of an AirDrop file transfer."""

    success: bool
    file_name: str
    file_size_bytes: int = 0
    target: str = ""
    duration_ms: float = 0
    throughput_mbps: float = 0
    error: str = ""


@dataclass
class OpenDropLog:
    """Collects structured log from OpenDrop operations."""

    entries: list = field(default_factory=list)

    def log(self, level: str, component: str, message: str):
        ts = datetime.now().strftime("%Y-%m-%dT%H:%M:%S.") + \
             f"{datetime.now().microsecond // 1000:03d}"
        self.entries.append(
            f"{ts} {level:5s} [{component}] {message}"
        )

    def to_text(self) -> str:
        return "\n".join(self.entries)


# ============================================================
# OpenDrop Tester
# ============================================================

class OpenDropTester:
    """
    Wraps OpenDrop CLI for real AirDrop protocol testing.

    OpenDrop must be installed: pip install opendrop
    See: https://github.com/seemoo-lab/opendrop
    """

    def __init__(self):
        self.available = self._check_opendrop()
        self.is_macos = platform.system() == "Darwin"
        self.log = OpenDropLog()

    @staticmethod
    def _check_opendrop() -> bool:
        """Check if opendrop CLI is installed."""
        return shutil.which("opendrop") is not None

    @staticmethod
    def _check_awdl() -> bool:
        """Check if AWDL interface is available (macOS only)."""
        if platform.system() != "Darwin":
            return False
        try:
            result = subprocess.run(
                ["ifconfig", "awdl0"],
                capture_output=True, text=True, timeout=5
            )
            return result.returncode == 0
        except Exception:
            return False

    def preflight_check(self) -> dict:
        """
        Verify all prerequisites for real AirDrop testing.

        Returns:
            Dict with check results and recommendations.
        """
        checks = {
            "opendrop_installed": self.available,
            "macos": self.is_macos,
            "awdl_available": self._check_awdl() if self.is_macos else False,
            "python_version": platform.python_version(),
            "platform": platform.platform(),
        }

        recommendations = []
        if not checks["opendrop_installed"]:
            recommendations.append(
                "Install OpenDrop: pip install opendrop"
            )
        if not checks["macos"]:
            recommendations.append(
                "OpenDrop requires macOS for native AWDL support. "
                "For Linux, install OWL: https://github.com/seemoo-lab/owl"
            )
        if checks["macos"] and not checks["awdl_available"]:
            recommendations.append(
                "AWDL interface (awdl0) not found. "
                "Ensure Wi-Fi is enabled and AirDrop is not disabled."
            )

        checks["ready"] = all([
            checks["opendrop_installed"],
            checks["awdl_available"] if checks["macos"] else False,
        ])
        checks["recommendations"] = recommendations

        self.log.log("INFO", "OpenDrop",
                     f"Preflight: ready={checks['ready']}, "
                     f"opendrop={checks['opendrop_installed']}, "
                     f"awdl={checks.get('awdl_available', False)}")

        return checks

    # ---- Discovery ----

    def discover(self, timeout: int = 10) -> list[AirDropDevice]:
        """
        Discover nearby AirDrop devices using OpenDrop.

        Args:
            timeout: Discovery timeout in seconds.

        Returns:
            List of discovered AirDropDevice objects.
        """
        self.log.log("INFO", "OpenDrop", f"Starting device discovery (timeout={timeout}s)")

        if not self.available:
            self.log.log("ERROR", "OpenDrop", "opendrop not installed")
            return []

        try:
            result = subprocess.run(
                ["opendrop", "find", "--timeout", str(timeout)],
                capture_output=True, text=True, timeout=timeout + 5,
            )

            devices = []
            for line in result.stdout.strip().splitlines():
                # OpenDrop outputs discovered devices line by line
                line = line.strip()
                if line and not line.startswith(("Looking", "Found")):
                    devices.append(AirDropDevice(
                        name=line,
                        id=line,
                    ))

            self.log.log("INFO", "OpenDrop",
                         f"Discovery complete: {len(devices)} devices found")
            for dev in devices:
                self.log.log("INFO", "AirDrop",
                             f"Device found: {dev.name}")

            return devices

        except subprocess.TimeoutExpired:
            self.log.log("WARN", "OpenDrop",
                         f"Discovery timed out after {timeout}s")
            return []
        except FileNotFoundError:
            self.log.log("ERROR", "OpenDrop",
                         "opendrop binary not found in PATH")
            return []

    # ---- Send File ----

    def send_file(
        self,
        file_path: str,
        target_name: Optional[str] = None,
        timeout: int = 30,
    ) -> TransferResult:
        """
        Send a file via AirDrop using OpenDrop.

        Args:
            file_path: Path to the file to send.
            target_name: Name of target device (None = first discovered).
            timeout: Transfer timeout in seconds.

        Returns:
            TransferResult with success/failure and metrics.
        """
        path = Path(file_path)
        if not path.exists():
            return TransferResult(
                success=False,
                file_name=str(path),
                error=f"File not found: {file_path}",
            )

        file_size = path.stat().st_size
        self.log.log("INFO", "AirDrop",
                     f"Sending: {path.name} ({file_size / 1024 / 1024:.1f}MB)")

        if not self.available:
            self.log.log("ERROR", "OpenDrop", "opendrop not installed")
            return TransferResult(
                success=False,
                file_name=path.name,
                file_size_bytes=file_size,
                error="opendrop not installed",
            )

        cmd = ["opendrop", "send", str(path)]
        if target_name:
            cmd.extend(["--receiver", target_name])

        try:
            start = time.time()
            result = subprocess.run(
                cmd, capture_output=True, text=True, timeout=timeout,
            )
            duration_ms = (time.time() - start) * 1000
            throughput = (file_size * 8 / 1_000_000) / (duration_ms / 1000) if duration_ms > 0 else 0

            success = result.returncode == 0

            self.log.log(
                "INFO" if success else "ERROR",
                "AirDrop",
                f"Transfer {'complete' if success else 'failed'}: "
                f"{path.name} ({duration_ms:.0f}ms, {throughput:.1f} Mbps)"
            )

            return TransferResult(
                success=success,
                file_name=path.name,
                file_size_bytes=file_size,
                target=target_name or "auto",
                duration_ms=duration_ms,
                throughput_mbps=throughput,
                error=result.stderr.strip() if not success else "",
            )

        except subprocess.TimeoutExpired:
            self.log.log("ERROR", "AirDrop",
                         f"Transfer timed out after {timeout}s")
            return TransferResult(
                success=False,
                file_name=path.name,
                file_size_bytes=file_size,
                error=f"Timeout after {timeout}s",
            )

    # ---- Receive Files ----

    def receive(
        self,
        output_dir: str = "/tmp/airdrop_received",
        timeout: int = 60,
    ) -> list[str]:
        """
        Listen for incoming AirDrop files using OpenDrop.

        Args:
            output_dir: Directory to save received files.
            timeout: Listen timeout in seconds.

        Returns:
            List of received file paths.
        """
        out_path = Path(output_dir)
        out_path.mkdir(parents=True, exist_ok=True)

        self.log.log("INFO", "OpenDrop",
                     f"Listening for AirDrop files (timeout={timeout}s, "
                     f"output={output_dir})")

        if not self.available:
            self.log.log("ERROR", "OpenDrop", "opendrop not installed")
            return []

        try:
            result = subprocess.run(
                ["opendrop", "receive", "--output", str(out_path)],
                capture_output=True, text=True, timeout=timeout,
            )

            received = list(out_path.glob("*"))
            self.log.log("INFO", "AirDrop",
                         f"Received {len(received)} files")
            return [str(f) for f in received]

        except subprocess.TimeoutExpired:
            received = list(out_path.glob("*"))
            self.log.log("INFO", "OpenDrop",
                         f"Listen timeout. Received {len(received)} files.")
            return [str(f) for f in received]


# ============================================================
# Pytest Integration
# ============================================================

def requires_opendrop(func):
    """Decorator to skip tests when OpenDrop is not available."""
    import functools
    import pytest

    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        tester = OpenDropTester()
        checks = tester.preflight_check()
        if not checks["ready"]:
            reasons = "; ".join(checks["recommendations"])
            pytest.skip(f"OpenDrop not available: {reasons}")
        return func(*args, **kwargs)
    return wrapper


# ============================================================
# CLI
# ============================================================

if __name__ == "__main__":
    import sys

    tester = OpenDropTester()

    print(f"\n{'='*60}")
    print(f"  NetQual — OpenDrop Real AirDrop Tester")
    print(f"{'='*60}\n")

    # Preflight
    checks = tester.preflight_check()
    print("  Preflight Checks:")
    for key, val in checks.items():
        if key != "recommendations":
            icon = "✅" if val else "❌" if isinstance(val, bool) else "ℹ️"
            print(f"    {icon} {key}: {val}")

    if checks["recommendations"]:
        print("\n  Recommendations:")
        for rec in checks["recommendations"]:
            print(f"    → {rec}")

    if not checks["ready"]:
        print("\n  ⚠️  OpenDrop not ready. Use airdrop_simulator.py for offline testing.")
        print("     Install: pip install opendrop")
        print("     Docs: https://github.com/seemoo-lab/opendrop")
        sys.exit(0)

    # If ready, run discovery
    if len(sys.argv) > 1 and sys.argv[1] == "discover":
        print("\n  Scanning for AirDrop devices...")
        devices = tester.discover(timeout=15)
        for dev in devices:
            print(f"    📱 {dev.name}")

    elif len(sys.argv) > 1 and sys.argv[1] == "send":
        if len(sys.argv) < 3:
            print("  Usage: python opendrop_wrapper.py send <file_path>")
            sys.exit(1)
        result = tester.send_file(sys.argv[2])
        print(f"    {'✅' if result.success else '❌'} {result.file_name}: "
              f"{result.duration_ms:.0f}ms, {result.throughput_mbps:.1f} Mbps")

    elif len(sys.argv) > 1 and sys.argv[1] == "receive":
        print("\n  Listening for AirDrop files...")
        files = tester.receive(timeout=30)
        for f in files:
            print(f"    📥 {f}")

    else:
        print("\n  Commands:")
        print("    python opendrop_wrapper.py discover")
        print("    python opendrop_wrapper.py send <file>")
        print("    python opendrop_wrapper.py receive")
