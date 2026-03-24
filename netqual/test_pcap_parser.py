"""
test_pcap_parser.py — Tests for the Packet Capture Parser
==========================================================
Uses mocked tshark output so tests run without actual pcap files.

Run: pytest test_pcap_parser.py -v
"""

import pytest
from unittest.mock import patch, MagicMock
from pcap_parser import PcapParser, PcapFinding, PcapIssue, PCAP_ISSUE_PATTERNS

try:
    import allure
    HAS_ALLURE = True
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
    HAS_ALLURE = False


# ============================================================
# Mock tshark output fixtures
# ============================================================

MOCK_TLS_OUTPUT = """Mar 20, 2026 10:00:01|192.168.1.5|17.253.144.10|1|0x0304|0x1301
Mar 20, 2026 10:00:01|17.253.144.10|192.168.1.5|2|0x0304|0x1301"""

MOCK_TLS_DOWNGRADE_OUTPUT = """Mar 20, 2026 10:00:01|192.168.1.5|192.168.1.50|1|0x0301|0x002f
Mar 20, 2026 10:00:01|192.168.1.50|192.168.1.5|2|0x0301|0x002f"""

MOCK_DNS_OUTPUT = """Mar 20, 2026 10:00:01|192.168.1.5|8.8.8.8|apple.com|17.253.144.10|0.030|0
Mar 20, 2026 10:00:01|192.168.1.5|8.8.8.8|icloud.com|17.248.128.1|0.045|0"""

MOCK_DNS_NXDOMAIN_OUTPUT = """Mar 20, 2026 10:00:01|192.168.1.5|8.8.8.8|nonexistent.apple.com||0.100|3"""

MOCK_DNS_SLOW_OUTPUT = """Mar 20, 2026 10:00:01|192.168.1.5|8.8.8.8|apple.com|17.253.144.10|0.750|0"""

MOCK_MDNS_OUTPUT = """Mar 20, 2026 10:00:02|192.168.1.5|_airdrop._tcp.local|_airdrop._tcp.local|
Mar 20, 2026 10:00:02|192.168.1.10||iPhone-Alice._airdrop._tcp.local|iPhone-Alice._airdrop._tcp.local
Mar 20, 2026 10:00:02|192.168.1.5|_airplay._tcp.local|_airplay._tcp.local|"""

MOCK_MDNS_NO_APPLE = """Mar 20, 2026 10:00:02|192.168.1.5|_http._tcp.local||
Mar 20, 2026 10:00:02|192.168.1.5|_printer._tcp.local||"""

MOCK_RETRANS_OUTPUT = """Mar 20, 2026 10:00:03|192.168.1.5|17.253.144.10|49152|443
Mar 20, 2026 10:00:03|192.168.1.5|17.253.144.10|49152|443
Mar 20, 2026 10:00:04|192.168.1.5|17.253.144.10|49152|443"""

MOCK_TCP_TOTAL = "\n".join([f"{i}" for i in range(50)])  # 50 TCP packets

MOCK_TRAFFIC_STATS = """IO Statistics
Interval: 1.000 secs
| Interval | Frames | Bytes |
| 0.0-1.0  |    120 | 15360 |
| 1.0-2.0  |     95 | 12160 |"""


# ============================================================
# Helper: Create parser with mocked tshark
# ============================================================

def make_parser_with_mock(mock_outputs: dict):
    """Create a PcapParser with mocked _run_tshark responses."""
    parser = PcapParser.__new__(PcapParser)
    parser.capture_file = "test_capture.pcap"
    parser.report = __import__("pcap_parser").PcapReport(capture_file="test_capture.pcap")
    parser.report.tshark_available = True
    parser.findings = []

    original_run = PcapParser._run_tshark

    def mock_run_tshark(self_inner, display_filter, fields):
        """Return mock output based on the display filter."""
        mock_output = mock_outputs.get(display_filter, "")
        if not mock_output:
            return []

        rows = []
        for line in mock_output.strip().splitlines():
            if not line.strip():
                continue
            values = line.split("|")
            row = {}
            for i, field_name in enumerate(fields):
                row[field_name] = values[i].strip() if i < len(values) else ""
            rows.append(row)
        return rows

    parser._run_tshark = lambda df, f: mock_run_tshark(parser, df, f)
    parser._run_tshark_stats = lambda args: MOCK_TRAFFIC_STATS
    return parser


# ============================================================
# Tests
# ============================================================

@allure.feature("Packet Analysis")
@allure.story("tshark Availability")
class TestTsharkSetup:

    @allure.severity(allure.severity_level.CRITICAL)
    def test_tshark_available_check(self):
        """Check if tshark binary detection works."""
        # This tests the static method — result depends on environment
        result = PcapParser._check_tshark()
        assert isinstance(result, bool)

    @allure.severity(allure.severity_level.NORMAL)
    def test_graceful_when_no_tshark(self):
        """Parser handles missing tshark gracefully."""
        parser = PcapParser.__new__(PcapParser)
        parser.capture_file = "test.pcap"
        parser.report = __import__("pcap_parser").PcapReport(capture_file="test.pcap")
        parser.report.tshark_available = False
        parser.findings = []
        # Should not crash
        result = parser._run_tshark("tcp", ["frame.number"])
        assert result == []


@allure.feature("Packet Analysis")
@allure.story("TLS Handshake")
class TestTLSAnalysis:

    @allure.severity(allure.severity_level.BLOCKER)
    def test_parse_tls_handshake(self):
        """TLS version and cipher extracted from packets."""
        parser = make_parser_with_mock({"tls.handshake": MOCK_TLS_OUTPUT})
        analysis = parser.analyze_tls()
        assert analysis["count"] == 2
        assert len(parser.findings) == 2
        assert parser.findings[0].category == "TLS"

    @allure.severity(allure.severity_level.BLOCKER)
    def test_flag_tls_downgrade(self):
        """TLS < 1.2 flagged as P0."""
        parser = make_parser_with_mock({"tls.handshake": MOCK_TLS_DOWNGRADE_OUTPUT})
        parser.analyze_tls()
        issues = parser.flag_issues()
        tls_issues = [i for i in issues if i.pattern == "TLS version < 1.2"]
        assert len(tls_issues) == 1
        assert tls_issues[0].severity == "P0"


@allure.feature("Packet Analysis")
@allure.story("DNS Analysis")
class TestDNSAnalysis:

    @allure.severity(allure.severity_level.CRITICAL)
    def test_parse_dns_queries(self):
        """DNS queries and responses extracted."""
        parser = make_parser_with_mock({"dns": MOCK_DNS_OUTPUT})
        analysis = parser.analyze_dns()
        assert analysis["count"] == 2

    @allure.severity(allure.severity_level.CRITICAL)
    def test_flag_dns_nxdomain(self):
        """NXDOMAIN flagged as P1."""
        parser = make_parser_with_mock({"dns": MOCK_DNS_NXDOMAIN_OUTPUT})
        parser.analyze_dns()
        issues = parser.flag_issues()
        dns_issues = [i for i in issues if i.pattern == "DNS NXDOMAIN"]
        assert len(dns_issues) == 1
        assert dns_issues[0].severity == "P1"

    @allure.severity(allure.severity_level.NORMAL)
    def test_flag_dns_slow(self):
        """Slow DNS (>500ms) flagged as P2."""
        parser = make_parser_with_mock({"dns": MOCK_DNS_SLOW_OUTPUT})
        parser.analyze_dns()
        issues = parser.flag_issues()
        slow_issues = [i for i in issues if i.pattern == "Slow DNS (>500ms)"]
        assert len(slow_issues) == 1


@allure.feature("Packet Analysis")
@allure.story("mDNS / Bonjour")
class TestMDNSAnalysis:

    @allure.severity(allure.severity_level.CRITICAL)
    def test_parse_mdns_services(self):
        """Apple sharing services detected in mDNS traffic."""
        parser = make_parser_with_mock({"mdns": MOCK_MDNS_OUTPUT})
        analysis = parser.analyze_mdns()
        assert analysis["count"] == 3
        assert "_airdrop" in analysis["apple_services"]
        assert "_airplay" in analysis["apple_services"]

    @allure.severity(allure.severity_level.CRITICAL)
    def test_flag_no_apple_services(self):
        """Missing Apple services flagged as P1."""
        parser = make_parser_with_mock({"mdns": MOCK_MDNS_NO_APPLE})
        parser.analyze_mdns()
        issues = parser.flag_issues()
        missing = [i for i in issues if i.pattern == "No Apple mDNS services"]
        assert len(missing) == 1


@allure.feature("Packet Analysis")
@allure.story("TCP Retransmissions")
class TestRetransmissionAnalysis:

    @allure.severity(allure.severity_level.CRITICAL)
    def test_parse_retransmissions(self):
        """Retransmission count extracted."""
        mock = {
            "tcp.analysis.retransmission": MOCK_RETRANS_OUTPUT,
            "tcp": MOCK_TCP_TOTAL,
        }
        parser = make_parser_with_mock(mock)
        analysis = parser.analyze_retransmissions()
        assert analysis["retransmissions"] == 3

    @allure.severity(allure.severity_level.CRITICAL)
    def test_flag_high_retransmission(self):
        """High retransmission rate (>5%) flagged as P1."""
        # 6 retransmissions to trigger the threshold
        many_retrans = "\n".join([
            f"Mar 20, 2026 10:00:0{i}|192.168.1.5|17.253.144.10|49152|443"
            for i in range(6)
        ])
        mock = {
            "tcp.analysis.retransmission": many_retrans,
            "tcp": MOCK_TCP_TOTAL,
        }
        parser = make_parser_with_mock(mock)
        parser.analyze_retransmissions()
        issues = parser.flag_issues()
        retrans_issues = [i for i in issues if i.pattern == "High retransmission rate"]
        assert len(retrans_issues) == 1
        assert retrans_issues[0].severity == "P1"


@allure.feature("Packet Analysis")
@allure.story("Commands Reference")
class TestCommandsReference:

    @allure.severity(allure.severity_level.MINOR)
    def test_get_commands(self):
        """All tshark commands documented and accessible."""
        parser = PcapParser.__new__(PcapParser)
        parser.capture_file = "test.pcap"
        commands = parser.get_commands()
        assert "tls" in commands
        assert "dns" in commands
        assert "mdns" in commands
        assert "ble" in commands
        assert "retransmissions" in commands
        assert all("command" in v for v in commands.values())
