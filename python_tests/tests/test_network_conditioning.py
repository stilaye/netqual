"""
test_network_conditioning.py
============================
Tests for simulated network conditions using two macOS backends:

  ComcastConditioner  — comcast CLI (wraps pfctl+dnctl). Needs sudo + network.
  NLCConditioner      — Network Link Conditioner profile plists. Fully offline.

Markers used:
  @pytest.mark.requires_sudo  — skipped unless comcast is installed + sudo available
  @pytest.mark.network        — skipped in --offline mode
  (no marker)                 — fully offline, always runs

Run offline tests only:
    pytest tests/test_network_conditioning.py -m "not requires_sudo and not network"

Run all (requires sudo + comcast):
    pytest tests/test_network_conditioning.py -v
"""

import plistlib
import shutil
import pytest

from utils.network_conditioner import PROFILES

# Skip entire comcast block if binary not present
comcast_available = pytest.mark.skipif(
    not shutil.which("comcast"),
    reason="comcast not installed — run: brew install comcast",
)


# ============================================================
# Comcast — offline validation (no sudo, no network)
# ============================================================

class TestComcastProfiles:
    """Validate profile constants — no network or sudo needed."""

    def test_all_profiles_defined(self):
        """3G, 4G, 5G, lossy and high_latency profiles must all exist."""
        for name in ("3g", "4g", "5g", "lossy", "high_latency"):
            assert name in PROFILES

    def test_3g_profile_values(self):
        p = PROFILES["3g"]
        assert p.bandwidth_kbps == 1_000
        assert p.latency_ms     == 200
        assert p.packet_loss_pct == 2.0

    def test_4g_faster_than_3g(self):
        assert PROFILES["4g"].bandwidth_kbps > PROFILES["3g"].bandwidth_kbps
        assert PROFILES["4g"].latency_ms     < PROFILES["3g"].latency_ms

    def test_5g_faster_than_4g(self):
        assert PROFILES["5g"].bandwidth_kbps > PROFILES["4g"].bandwidth_kbps
        assert PROFILES["5g"].latency_ms     < PROFILES["4g"].latency_ms

    def test_uplink_is_half_of_downlink(self):
        """Mobile links are asymmetric — uplink should be half of downlink."""
        for name in ("3g", "4g", "5g"):
            p = PROFILES[name]
            assert p.uplink_kbps == p.bandwidth_kbps // 2

    def test_unknown_profile_raises(self, comcast_conditioner):
        with pytest.raises(ValueError, match="Unknown profile"):
            with comcast_conditioner.profile("nonexistent"):
                pass


# ============================================================
# Comcast — live conditioning (requires sudo + network)
# ============================================================

class TestComcastConditioning:
    """Live network conditioning tests — require comcast installed and sudo."""

    @comcast_available
    @pytest.mark.requires_sudo
    def test_comcast_binary_found(self, comcast_conditioner):
        """Sanity check: comcast must be on PATH before live tests run."""
        assert comcast_conditioner.is_available()

    @comcast_available
    @pytest.mark.requires_sudo
    @pytest.mark.network
    def test_3g_increases_tcp_latency(self, comcast_conditioner):
        """
        Applying the 3G profile (200ms delay) must measurably increase
        TCP connection latency compared to the baseline.
        """
        baseline = comcast_conditioner.measure_tcp_latency("apple.com", 443)

        with comcast_conditioner.profile("3g"):
            degraded = comcast_conditioner.measure_tcp_latency("apple.com", 443)

        assert degraded > baseline, (
            f"3G profile did not increase latency — "
            f"baseline={baseline:.3f}s degraded={degraded:.3f}s"
        )

    @comcast_available
    @pytest.mark.requires_sudo
    @pytest.mark.network
    def test_network_restored_after_3g(self, comcast_conditioner):
        """
        After the 3G context exits, TCP latency must return close to the
        pre-test baseline (within 2 s — well above any 3G residual effect).
        """
        with comcast_conditioner.profile("3g"):
            pass  # apply and immediately exit

        restored = comcast_conditioner.measure_tcp_latency("apple.com", 443)
        assert restored < 2.0, (
            f"Network not restored after teardown — latency={restored:.3f}s"
        )

    @comcast_available
    @pytest.mark.requires_sudo
    @pytest.mark.network
    def test_high_latency_profile(self, comcast_conditioner):
        """500 ms delay profile must produce noticeably slower connections."""
        baseline = comcast_conditioner.measure_tcp_latency("apple.com", 443)

        with comcast_conditioner.profile("high_latency"):
            degraded = comcast_conditioner.measure_tcp_latency("apple.com", 443)

        assert degraded > baseline + 0.4, (
            f"High-latency profile had no effect — "
            f"baseline={baseline:.3f}s degraded={degraded:.3f}s"
        )


# ============================================================
# NLC — plist validation (fully offline, no sudo)
# ============================================================

class TestNLCProfilePlist:
    """Validate NLC profile plist structure — no sudo or network needed."""

    def test_3g_profile_is_valid_plist(self, nlc_conditioner):
        """Build a 3G profile and verify it round-trips as a valid binary plist."""
        data   = nlc_conditioner.build_profile(PROFILES["3g"])
        raw    = plistlib.dumps(data, fmt=plistlib.FMT_BINARY)
        parsed = plistlib.loads(raw)
        assert "profile" in parsed

    def test_profile_contains_all_required_nlc_keys(self, nlc_conditioner):
        """Every key expected by NLC preference pane must be present."""
        for name in ("3g", "4g", "5g"):
            data = nlc_conditioner.build_profile(PROFILES[name])
            assert nlc_conditioner.validate_profile(data), (
                f"{name} profile missing required NLC keys"
            )

    def test_profile_name_matches_tier(self, nlc_conditioner):
        """Profile name field must reflect the network tier."""
        assert nlc_conditioner.build_profile(PROFILES["3g"])["profile"]["name"] == "3G"
        assert nlc_conditioner.build_profile(PROFILES["4g"])["profile"]["name"] == "4G LTE"
        assert nlc_conditioner.build_profile(PROFILES["5g"])["profile"]["name"] == "5G"

    def test_write_and_read_roundtrip(self, nlc_conditioner, tmp_path):
        """
        A profile written to disk must deserialise back with identical
        bandwidth, latency and packet-loss values.
        """
        profile = PROFILES["4g"]
        out     = tmp_path / "4g.plist"
        nlc_conditioner.write_profile(profile, out)

        loaded = nlc_conditioner.load_profile(out)["profile"]
        assert loaded["downlink-bandwidth-kbps"] == profile.bandwidth_kbps
        assert loaded["delay"]                   == profile.latency_ms
        assert loaded["packet-loss-percent"]     == profile.packet_loss_pct

    def test_all_tiers_write_without_error(self, nlc_conditioner, tmp_path):
        """3G, 4G and 5G profiles must all serialise to disk cleanly."""
        for name in ("3g", "4g", "5g"):
            out = tmp_path / f"{name}.plist"
            nlc_conditioner.write_profile(PROFILES[name], out)
            assert out.exists()
            assert out.stat().st_size > 0

    def test_5g_has_lowest_latency(self, nlc_conditioner):
        """5G profile must have the lowest delay of all three mobile tiers."""
        delays = {
            name: nlc_conditioner.build_profile(PROFILES[name])["profile"]["delay"]
            for name in ("3g", "4g", "5g")
        }
        assert delays["5g"] < delays["4g"] < delays["3g"]

    def test_lossy_profile_has_high_packet_loss(self, nlc_conditioner):
        """Lossy profile must configure packet loss above 5%."""
        data = nlc_conditioner.build_profile(PROFILES["lossy"])
        assert data["profile"]["packet-loss-percent"] > 5.0
