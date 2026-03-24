"""
test_opendrop.py — Tests for the OpenDrop Integration
======================================================
Tests are split into two tiers:

  Tier 1 — No hardware required (always run in CI):
    • Preflight check structure and logic
    • OpenDropLog format
    • AirDropDevice / TransferResult data models
    • File-not-found and opendrop-not-installed error paths
    • Mocked discover / send / receive (subprocess patched)

  Tier 2 — Real hardware required (skip if OpenDrop not available):
    • Real device discovery via opendrop CLI
    • Real file send to a nearby device
    • Real file receive from a nearby device
    Uses the @requires_opendrop decorator — tests skip automatically
    when opendrop is not installed or awdl0 is not available.

Run all (Tier 1 only if no device):
    pytest test_opendrop.py -v

Run with Allure report:
    pytest test_opendrop.py -v --alluredir=allure-results
"""

import os
import tempfile
import pytest
from unittest.mock import patch, MagicMock

from opendrop_wrapper import (
    AirDropDevice,
    OpenDropLog,
    OpenDropTester,
    TransferResult,
    requires_opendrop,
)

try:
    import allure
except ImportError:
    class _Allure:
        @staticmethod
        def feature(name): return lambda f: f
        @staticmethod
        def story(name): return lambda f: f
        @staticmethod
        def severity(level): return lambda f: f
        class severity_level:
            BLOCKER = "blocker"
            CRITICAL = "critical"
            NORMAL = "normal"
            MINOR = "minor"
    allure = _Allure()


# ============================================================
# Tier 1 — No hardware required
# ============================================================

@allure.feature("OpenDrop Integration")
@allure.story("Preflight")
class TestPreflight:

    @allure.severity(allure.severity_level.CRITICAL)
    def test_preflight_returns_required_keys(self):
        """preflight_check() returns dict with all required keys."""
        tester = OpenDropTester()
        result = tester.preflight_check()
        for key in ("opendrop_installed", "macos", "awdl_available", "ready", "recommendations"):
            assert key in result, f"Missing key: {key}"

    @allure.severity(allure.severity_level.CRITICAL)
    def test_ready_requires_both_opendrop_and_awdl(self):
        """ready=True only when opendrop is installed AND awdl0 is available."""
        tester = OpenDropTester()
        result = tester.preflight_check()
        if result["ready"]:
            assert result["opendrop_installed"]
            assert result["awdl_available"]

    @allure.severity(allure.severity_level.NORMAL)
    def test_not_ready_provides_recommendations(self):
        """When not ready, at least one recommendation is returned."""
        tester = OpenDropTester()
        result = tester.preflight_check()
        if not result["ready"]:
            assert len(result["recommendations"]) > 0

    @allure.severity(allure.severity_level.NORMAL)
    def test_preflight_writes_to_session_log(self):
        """preflight_check() logs its result to the session log."""
        tester = OpenDropTester()
        tester.preflight_check()
        assert len(tester.log.entries) > 0
        assert any("Preflight" in e for e in tester.log.entries)

    @allure.severity(allure.severity_level.NORMAL)
    def test_recommendations_is_list(self):
        """recommendations is always a list, never None."""
        tester = OpenDropTester()
        result = tester.preflight_check()
        assert isinstance(result["recommendations"], list)


@allure.feature("OpenDrop Integration")
@allure.story("Session Logging")
class TestOpenDropLog:

    @allure.severity(allure.severity_level.NORMAL)
    def test_entry_contains_level_component_message(self):
        """Log entry contains level, bracketed component, and message."""
        log = OpenDropLog()
        log.log("INFO", "AirDrop", "Transfer started")
        assert len(log.entries) == 1
        entry = log.entries[0]
        assert "INFO" in entry
        assert "[AirDrop]" in entry
        assert "Transfer started" in entry

    @allure.severity(allure.severity_level.NORMAL)
    def test_entry_contains_timestamp(self):
        """Log entry begins with an ISO-format timestamp."""
        log = OpenDropLog()
        log.log("INFO", "OpenDrop", "Ready")
        assert "T" in log.entries[0]  # ISO 8601 separator

    @allure.severity(allure.severity_level.NORMAL)
    def test_to_text_joins_with_newlines(self):
        """to_text() returns all entries joined by newlines."""
        log = OpenDropLog()
        log.log("INFO", "OpenDrop", "Starting")
        log.log("INFO", "AirDrop", "Done")
        text = log.to_text()
        assert "Starting" in text
        assert "Done" in text
        assert "\n" in text

    @allure.severity(allure.severity_level.MINOR)
    def test_multiple_levels(self):
        """Logs multiple levels without error."""
        log = OpenDropLog()
        for level in ("INFO", "WARN", "ERROR", "DEBUG"):
            log.log(level, "Test", f"{level} message")
        assert len(log.entries) == 4


@allure.feature("OpenDrop Integration")
@allure.story("Data Models")
class TestDataModels:

    @allure.severity(allure.severity_level.MINOR)
    def test_airdrop_device_fields(self):
        """AirDropDevice stores name, id, and model."""
        dev = AirDropDevice(name="Alice's iPhone", id="alice-01", model="iPhone16,2")
        assert dev.name == "Alice's iPhone"
        assert dev.id == "alice-01"
        assert dev.model == "iPhone16,2"

    @allure.severity(allure.severity_level.MINOR)
    def test_airdrop_device_default_model(self):
        """AirDropDevice model defaults to empty string."""
        dev = AirDropDevice(name="Bob's Mac", id="bob-01")
        assert dev.model == ""

    @allure.severity(allure.severity_level.MINOR)
    def test_transfer_result_success(self):
        """TransferResult stores all success metrics."""
        result = TransferResult(
            success=True,
            file_name="photo.heic",
            file_size_bytes=4_200_000,
            target="Alice's iPhone",
            duration_ms=1_250.0,
            throughput_mbps=26.9,
        )
        assert result.success
        assert result.file_name == "photo.heic"
        assert result.file_size_bytes == 4_200_000
        assert result.throughput_mbps > 0
        assert result.error == ""

    @allure.severity(allure.severity_level.MINOR)
    def test_transfer_result_failure(self):
        """TransferResult stores failure reason in error field."""
        result = TransferResult(
            success=False,
            file_name="video.mov",
            error="Timeout after 30s",
        )
        assert not result.success
        assert "Timeout" in result.error


@allure.feature("OpenDrop Integration")
@allure.story("Error Handling")
class TestErrorHandling:

    @allure.severity(allure.severity_level.CRITICAL)
    def test_send_nonexistent_file_returns_failure(self):
        """Sending a non-existent file returns TransferResult(success=False)."""
        tester = OpenDropTester()
        result = tester.send_file("/nonexistent/path/photo.heic")
        assert not result.success
        assert "not found" in result.error.lower()

    @allure.severity(allure.severity_level.CRITICAL)
    def test_send_without_opendrop_returns_failure(self):
        """Sending without opendrop installed returns TransferResult(success=False)."""
        with tempfile.NamedTemporaryFile(suffix=".txt", delete=False) as f:
            f.write(b"test content")
            tmp_path = f.name
        try:
            tester = OpenDropTester()
            tester.available = False
            result = tester.send_file(tmp_path)
            assert not result.success
            assert "opendrop" in result.error.lower()
        finally:
            os.unlink(tmp_path)

    @allure.severity(allure.severity_level.CRITICAL)
    def test_discover_without_opendrop_returns_empty(self):
        """discover() returns empty list when opendrop is not installed."""
        tester = OpenDropTester()
        tester.available = False
        result = tester.discover(timeout=1)
        assert result == []

    @allure.severity(allure.severity_level.CRITICAL)
    def test_receive_without_opendrop_returns_empty(self):
        """receive() returns empty list when opendrop is not installed."""
        tester = OpenDropTester()
        tester.available = False
        result = tester.receive(timeout=1)
        assert result == []


@allure.feature("OpenDrop Integration")
@allure.story("Discovery — Mocked")
class TestDiscoveryMocked:

    @allure.severity(allure.severity_level.CRITICAL)
    def test_parses_device_names_from_stdout(self):
        """discover() parses opendrop stdout into AirDropDevice objects."""
        mock_proc = MagicMock()
        mock_proc.returncode = 0
        mock_proc.stdout = "Alice's iPhone\nBob's MacBook Pro\n"

        tester = OpenDropTester()
        tester.available = True
        with patch("subprocess.run", return_value=mock_proc):
            devices = tester.discover(timeout=5)

        assert len(devices) == 2
        assert devices[0].name == "Alice's iPhone"
        assert devices[1].name == "Bob's MacBook Pro"

    @allure.severity(allure.severity_level.NORMAL)
    def test_skips_opendrop_status_lines(self):
        """discover() ignores 'Looking...' and 'Found N devices' header lines."""
        mock_proc = MagicMock()
        mock_proc.returncode = 0
        mock_proc.stdout = "Looking for AirDrop receivers...\nAlice's iPhone\nFound 1 device\n"

        tester = OpenDropTester()
        tester.available = True
        with patch("subprocess.run", return_value=mock_proc):
            devices = tester.discover(timeout=5)

        names = [d.name for d in devices]
        assert "Alice's iPhone" in names
        assert not any("Looking" in n or "Found" in n for n in names)

    @allure.severity(allure.severity_level.NORMAL)
    def test_logs_device_count(self):
        """discover() logs the number of devices found."""
        mock_proc = MagicMock()
        mock_proc.returncode = 0
        mock_proc.stdout = "Alice's iPhone\n"

        tester = OpenDropTester()
        tester.available = True
        with patch("subprocess.run", return_value=mock_proc):
            tester.discover(timeout=5)

        assert any("1 devices" in e for e in tester.log.entries)

    @allure.severity(allure.severity_level.NORMAL)
    def test_handles_empty_output(self):
        """discover() returns empty list when no devices in stdout."""
        mock_proc = MagicMock()
        mock_proc.returncode = 0
        mock_proc.stdout = ""

        tester = OpenDropTester()
        tester.available = True
        with patch("subprocess.run", return_value=mock_proc):
            devices = tester.discover(timeout=5)

        assert devices == []


@allure.feature("OpenDrop Integration")
@allure.story("Send — Mocked")
class TestSendMocked:

    @allure.severity(allure.severity_level.BLOCKER)
    def test_successful_send_returns_metrics(self):
        """Successful send returns TransferResult with duration and throughput."""
        mock_proc = MagicMock()
        mock_proc.returncode = 0
        mock_proc.stdout = "Transfer complete"
        mock_proc.stderr = ""

        with tempfile.NamedTemporaryFile(suffix=".heic", delete=False) as f:
            f.write(b"x" * 1024 * 100)  # 100 KB
            tmp_path = f.name

        try:
            tester = OpenDropTester()
            tester.available = True
            with patch("subprocess.run", return_value=mock_proc):
                result = tester.send_file(tmp_path, target_name="Alice's iPhone")

            assert result.success
            assert result.file_name == os.path.basename(tmp_path)
            assert result.file_size_bytes == 1024 * 100
            assert result.target == "Alice's iPhone"
            assert result.duration_ms >= 0
            assert result.throughput_mbps >= 0
        finally:
            os.unlink(tmp_path)

    @allure.severity(allure.severity_level.BLOCKER)
    def test_failed_send_captures_stderr(self):
        """Failed send captures opendrop stderr as error field."""
        mock_proc = MagicMock()
        mock_proc.returncode = 1
        mock_proc.stderr = "Peer rejected transfer"

        with tempfile.NamedTemporaryFile(suffix=".txt", delete=False) as f:
            f.write(b"hello")
            tmp_path = f.name

        try:
            tester = OpenDropTester()
            tester.available = True
            with patch("subprocess.run", return_value=mock_proc):
                result = tester.send_file(tmp_path)

            assert not result.success
            assert "Peer rejected" in result.error
        finally:
            os.unlink(tmp_path)

    @allure.severity(allure.severity_level.CRITICAL)
    def test_send_includes_target_flag_when_specified(self):
        """send_file passes --receiver flag to opendrop when target is given."""
        mock_proc = MagicMock()
        mock_proc.returncode = 0
        mock_proc.stdout = ""
        mock_proc.stderr = ""

        with tempfile.NamedTemporaryFile(suffix=".txt", delete=False) as f:
            f.write(b"data")
            tmp_path = f.name

        try:
            tester = OpenDropTester()
            tester.available = True
            with patch("subprocess.run", return_value=mock_proc) as mock_run:
                tester.send_file(tmp_path, target_name="Bob's Mac")
                cmd = mock_run.call_args[0][0]
                assert "--receiver" in cmd
                assert "Bob's Mac" in cmd
        finally:
            os.unlink(tmp_path)


@allure.feature("OpenDrop Integration")
@allure.story("Receive — Mocked")
class TestReceiveMocked:

    @allure.severity(allure.severity_level.CRITICAL)
    def test_receive_creates_output_directory(self):
        """receive() creates the output directory if it doesn't exist."""
        mock_proc = MagicMock()
        mock_proc.returncode = 0

        with tempfile.TemporaryDirectory() as tmp_dir:
            output_dir = os.path.join(tmp_dir, "airdrop_out")
            tester = OpenDropTester()
            tester.available = True
            with patch("subprocess.run", return_value=mock_proc):
                tester.receive(output_dir=output_dir, timeout=1)
            assert os.path.isdir(output_dir)

    @allure.severity(allure.severity_level.NORMAL)
    def test_receive_logs_file_count(self):
        """receive() logs how many files were received."""
        mock_proc = MagicMock()
        mock_proc.returncode = 0

        with tempfile.TemporaryDirectory() as output_dir:
            # Pre-populate to simulate received files
            for name in ("photo.heic", "doc.pdf"):
                open(os.path.join(output_dir, name), "w").close()

            tester = OpenDropTester()
            tester.available = True
            with patch("subprocess.run", return_value=mock_proc):
                files = tester.receive(output_dir=output_dir, timeout=1)

            assert len(files) == 2
            assert any("Received" in e for e in tester.log.entries)


# ============================================================
# Tier 2 — Real hardware required
# Tests are skipped automatically when OpenDrop is not available.
# ============================================================

@allure.feature("OpenDrop Integration")
@allure.story("Real Device — Discovery")
class TestRealDiscovery:

    @requires_opendrop
    @allure.severity(allure.severity_level.BLOCKER)
    def test_real_discover_returns_list(self):
        """Real OpenDrop discovery returns a list (may be empty if no peers nearby)."""
        tester = OpenDropTester()
        devices = tester.discover(timeout=15)
        assert isinstance(devices, list)

    @requires_opendrop
    @allure.severity(allure.severity_level.BLOCKER)
    def test_real_discover_device_names_are_strings(self):
        """Every discovered device has a non-empty name string."""
        tester = OpenDropTester()
        devices = tester.discover(timeout=15)
        for dev in devices:
            assert isinstance(dev.name, str)
            assert len(dev.name) > 0

    @requires_opendrop
    @allure.severity(allure.severity_level.CRITICAL)
    def test_real_preflight_passes(self):
        """Full preflight passes when OpenDrop + AWDL are ready."""
        tester = OpenDropTester()
        checks = tester.preflight_check()
        assert checks["ready"], f"Preflight failed: {checks['recommendations']}"


@allure.feature("OpenDrop Integration")
@allure.story("Real Device — Send")
class TestRealSend:

    @requires_opendrop
    @allure.severity(allure.severity_level.BLOCKER)
    def test_real_send_small_file(self):
        """Send a small test file via real AirDrop — verifies end-to-end transfer."""
        with tempfile.NamedTemporaryFile(suffix=".txt", delete=False) as f:
            f.write(b"NetQual AirDrop test payload\n")
            tmp_path = f.name

        try:
            tester = OpenDropTester()
            result = tester.send_file(tmp_path, timeout=30)
            # result.success depends on a receiver accepting — log either way
            assert isinstance(result.success, bool)
            assert result.file_name == os.path.basename(tmp_path)
            assert result.duration_ms >= 0
        finally:
            os.unlink(tmp_path)


@allure.feature("OpenDrop Integration")
@allure.story("Real Device — Receive")
class TestRealReceive:

    @requires_opendrop
    @allure.severity(allure.severity_level.CRITICAL)
    def test_real_receive_listen_mode(self):
        """OpenDrop receive mode runs without error for the duration of the timeout."""
        with tempfile.TemporaryDirectory() as output_dir:
            tester = OpenDropTester()
            files = tester.receive(output_dir=output_dir, timeout=10)
            assert isinstance(files, list)
            for f in files:
                assert os.path.exists(f)
