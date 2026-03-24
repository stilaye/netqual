"""
test_log_parser.py — Tests for the Network Log Parser
======================================================
17 tests covering parse, filter, categorize, and pattern detection.

Run: pytest test_log_parser.py -v
"""

import pytest
from log_parser import LogParser, LogEntry, FlaggedPattern, LogReport

try:
    import allure
    HAS_ALLURE = True
except ImportError:
    # Stub allure decorators if not installed
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
    HAS_ALLURE = False


# ============================================================
# Fixtures
# ============================================================

SAMPLE_LINES = [
    '2026-03-20T10:00:01.123 INFO  [NetworkProcess] URLSession started: GET https://apple.com',
    '2026-03-20T10:00:01.280 INFO  [DNS]            Resolved apple.com -> 17.253.144.10 (30ms)',
    '2026-03-20T10:00:02.001 ERROR [DNS]            Resolution failed: timeout after 5000ms for api.push.apple.com',
    '2026-03-20T10:00:02.500 WARN  [BLE]            Advertisement interval out of range: 120ms (expected 20-100ms)',
    '2026-03-20T10:00:03.000 ERROR [AWDL]           Peer connection failed: timeout waiting for channel negotiation',
    '2026-03-20T10:00:04.000 ERROR [TLS]            Certificate validation failed: self-signed cert in chain',
    '2026-03-20T10:00:04.200 WARN  [HTTP]           Response slow: 3200ms for GET https://icloud.com/api/sync',
    '2026-03-20T10:00:05.000 ERROR [SharePlay]      Sync drift detected: 650ms between participants (threshold: 500ms)',
    '2026-03-20T10:00:05.500 DEBUG [TLS]            Offered versions: TLSv1.3, TLSv1.2',
]

CLEAN_LINES = [
    '2026-03-20T10:00:01.100 INFO  [DNS]            Resolved apple.com -> 17.253.144.10 (15ms)',
    '2026-03-20T10:00:01.300 INFO  [TLS]            Handshake complete: TLSv1.3 (120ms)',
    '2026-03-20T10:00:01.500 INFO  [AirDrop]        Transfer complete: 4.2MB in 2000ms',
]


@pytest.fixture
def parser():
    return LogParser(SAMPLE_LINES)


@pytest.fixture
def clean_parser():
    return LogParser(CLEAN_LINES)


# ============================================================
# Level 1: Parse & Structure
# ============================================================

@allure.feature("Log Analysis")
@allure.story("Text Log Parsing")
class TestParsing:

    @allure.severity(allure.severity_level.CRITICAL)
    def test_parse_valid_line(self, parser):
        """Single well-formed log line parsed correctly."""
        entries = parser.parse()
        assert len(entries) > 0
        first = entries[0]
        assert first.timestamp == "2026-03-20T10:00:01.123"
        assert first.level == "INFO"
        assert first.component == "NetworkProcess"
        assert "URLSession started" in first.message

    @allure.severity(allure.severity_level.CRITICAL)
    def test_parse_all_levels(self, parser):
        """INFO, WARN, ERROR, DEBUG all parsed."""
        entries = parser.parse()
        levels = {e.level for e in entries}
        assert levels == {"INFO", "WARN", "ERROR", "DEBUG"}

    @allure.severity(allure.severity_level.CRITICAL)
    def test_parse_all_components(self, parser):
        """All component types parsed correctly."""
        entries = parser.parse()
        components = {e.component for e in entries}
        expected = {"NetworkProcess", "DNS", "BLE", "AWDL", "TLS", "HTTP", "SharePlay"}
        assert expected.issubset(components)

    @allure.severity(allure.severity_level.NORMAL)
    def test_parse_malformed_line(self):
        """Malformed lines skipped gracefully, not crash."""
        lines = [
            '2026-03-20T10:00:01.123 INFO  [DNS] Good line',
            'THIS IS NOT A VALID LOG LINE',
            '',
            '2026-03-20T10:00:02.000 ERROR [TLS] Another good line',
        ]
        parser = LogParser(lines)
        entries = parser.parse()
        assert len(entries) == 2
        assert parser.report.parse_errors == 1

    @allure.severity(allure.severity_level.NORMAL)
    def test_parse_empty_file(self):
        """Empty input returns empty results."""
        parser = LogParser([])
        entries = parser.parse()
        assert len(entries) == 0
        assert parser.report.total_entries == 0

    @allure.severity(allure.severity_level.NORMAL)
    def test_line_numbers_assigned(self, parser):
        """Each entry has correct line number."""
        entries = parser.parse()
        assert entries[0].line_number == 1
        assert entries[-1].line_number == len(SAMPLE_LINES)


# ============================================================
# Level 2: Filtering
# ============================================================

@allure.feature("Log Analysis")
@allure.story("Log Filtering")
class TestFiltering:

    @allure.severity(allure.severity_level.NORMAL)
    def test_filter_by_level(self, parser):
        """Filter only ERROR entries."""
        parser.parse()
        errors = parser.filter_by_level("ERROR")
        assert len(errors) == 4
        assert all(e.level == "ERROR" for e in errors)

    @allure.severity(allure.severity_level.NORMAL)
    def test_filter_by_component(self, parser):
        """Filter only DNS entries."""
        parser.parse()
        dns = parser.filter_by_component("DNS")
        assert len(dns) == 2
        assert all(e.component == "DNS" for e in dns)

    @allure.severity(allure.severity_level.NORMAL)
    def test_filter_by_multiple_components(self, parser):
        """Filter by DNS and TLS together."""
        parser.parse()
        filtered = parser.filter_by_component("DNS", "TLS")
        components = {e.component for e in filtered}
        assert components == {"DNS", "TLS"}

    @allure.severity(allure.severity_level.MINOR)
    def test_filter_by_time_range(self, parser):
        """Only entries within time window returned."""
        parser.parse()
        filtered = parser.filter_by_time_range(
            "2026-03-20T10:00:02.000",
            "2026-03-20T10:00:04.999"
        )
        assert len(filtered) > 0
        for e in filtered:
            assert e.timestamp >= "2026-03-20T10:00:02.000"
            assert e.timestamp <= "2026-03-20T10:00:04.999"


# ============================================================
# Level 2: Categorize & Count
# ============================================================

@allure.feature("Log Analysis")
@allure.story("Categorization")
class TestCategorize:

    @allure.severity(allure.severity_level.CRITICAL)
    def test_count_by_component(self, parser):
        """Error/warning counts per component are correct."""
        parser.parse()
        parser.categorize()
        report = parser.report

        assert report.errors == 4
        assert report.warnings == 2
        assert report.by_component["DNS"]["error"] == 1
        assert report.by_component["TLS"]["error"] == 1
        assert report.by_component["BLE"]["warn"] == 1


# ============================================================
# Level 3: Pattern Detection
# ============================================================

@allure.feature("Log Analysis")
@allure.story("Pattern Detection")
class TestPatternDetection:

    @allure.severity(allure.severity_level.BLOCKER)
    def test_detect_dns_timeout(self, parser):
        """DNS timeout pattern flagged as P1."""
        parser.parse()
        patterns = parser.detect_patterns()
        dns_patterns = [p for p in patterns if p.pattern == "DNS timeout"]
        assert len(dns_patterns) == 1
        assert dns_patterns[0].severity == "P1"

    @allure.severity(allure.severity_level.BLOCKER)
    def test_detect_tls_cert_failure(self, parser):
        """TLS cert failure pattern flagged as P0."""
        parser.parse()
        patterns = parser.detect_patterns()
        tls_patterns = [p for p in patterns if p.pattern == "TLS certificate failure"]
        assert len(tls_patterns) == 1
        assert tls_patterns[0].severity == "P0"

    @allure.severity(allure.severity_level.CRITICAL)
    def test_detect_ble_interval(self, parser):
        """BLE interval drift pattern flagged as P2."""
        parser.parse()
        patterns = parser.detect_patterns()
        ble_patterns = [p for p in patterns if p.pattern == "BLE interval out of range"]
        assert len(ble_patterns) == 1
        assert ble_patterns[0].severity == "P2"

    @allure.severity(allure.severity_level.CRITICAL)
    def test_detect_awdl_timeout(self, parser):
        """AWDL peer timeout pattern flagged as P1."""
        parser.parse()
        patterns = parser.detect_patterns()
        awdl_patterns = [p for p in patterns if p.pattern == "AWDL peer timeout"]
        assert len(awdl_patterns) == 1
        assert awdl_patterns[0].severity == "P1"

    @allure.severity(allure.severity_level.NORMAL)
    def test_detect_shareplay_drift(self, parser):
        """SharePlay sync drift pattern flagged as P2."""
        parser.parse()
        patterns = parser.detect_patterns()
        sp_patterns = [p for p in patterns if p.pattern == "SharePlay sync drift"]
        assert len(sp_patterns) == 1

    @allure.severity(allure.severity_level.NORMAL)
    def test_detect_slow_http(self, parser):
        """Slow HTTP response pattern flagged as P2."""
        parser.parse()
        patterns = parser.detect_patterns()
        http_patterns = [p for p in patterns if p.pattern == "Slow HTTP response"]
        assert len(http_patterns) == 1


# ============================================================
# Level 4: Full Analysis
# ============================================================

@allure.feature("Log Analysis")
@allure.story("Full Analysis")
class TestFullAnalysis:

    @allure.severity(allure.severity_level.CRITICAL)
    def test_full_log_analysis(self, parser):
        """End-to-end: parse → categorize → detect → report."""
        report = parser.analyze()
        assert report.total_entries == 9
        assert report.errors == 4
        assert report.warnings == 2
        assert len(report.flagged_patterns) == 6
        # Verify JSON output works
        json_str = report.to_json()
        assert "DNS timeout" in json_str
        assert "TLS certificate failure" in json_str

    @allure.severity(allure.severity_level.NORMAL)
    def test_no_issues_in_clean_log(self, clean_parser):
        """Clean log with no errors → no patterns flagged."""
        report = clean_parser.analyze()
        assert report.errors == 0
        assert report.warnings == 0
        assert len(report.flagged_patterns) == 0

    @allure.severity(allure.severity_level.NORMAL)
    def test_sample_log_file(self):
        """Full analysis of the sample log file."""
        parser = LogParser("sample_logs/network_diag.log")
        report = parser.analyze()
        assert report.total_entries == 23
        assert report.errors == 4
        assert len(report.flagged_patterns) >= 5  # At least 5 known patterns
