"""
pcap_parser.py — Packet Capture Analyzer (tshark wrapper)
==========================================================
Wraps tshark commands to analyze .pcap / .logdump files.

Extracts protocol-level insights relevant to Apple's Sharing features:
  - TLS handshakes (version, cipher, cert chain)
  - DNS queries and responses
  - mDNS / Bonjour service discovery
  - BLE advertisements (btsnoop logs)
  - TCP retransmissions
  - HTTP/2 streams
  - Traffic statistics

Usage:
    from pcap_parser import PcapParser
    parser = PcapParser("capture.pcap")
    report = parser.full_analysis()

    # Or individual analyses
    tls = parser.analyze_tls()
    dns = parser.analyze_dns()
"""

import subprocess
import shutil
import json
import re
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Optional


# ============================================================
# Data Models
# ============================================================

@dataclass
class PcapFinding:
    """A single finding from packet analysis."""

    category: str  # TLS, DNS, mDNS, BLE, TCP, HTTP2
    description: str
    details: dict = field(default_factory=dict)


@dataclass
class PcapIssue:
    """A flagged issue from packet analysis."""

    pattern: str
    severity: str  # P0, P1, P2
    category: str
    description: str
    impact: str


@dataclass
class PcapReport:
    """Complete packet analysis report."""

    capture_file: str
    tshark_available: bool = False
    analyses: dict = field(default_factory=dict)
    findings: list = field(default_factory=list)
    issues: list = field(default_factory=list)

    def to_dict(self) -> dict:
        d = asdict(self)
        return d

    def to_json(self, indent: int = 2) -> str:
        return json.dumps(self.to_dict(), indent=indent)


# ============================================================
# tshark Command Definitions
# ============================================================

TSHARK_COMMANDS = {
    "tls": {
        "description": "TLS Handshake Analysis",
        "filter": "tls.handshake",
        "fields": [
            "frame.time",
            "ip.src",
            "ip.dst",
            "tls.handshake.type",
            "tls.handshake.version",
            "tls.handshake.ciphersuite",
        ],
    },
    "dns": {
        "description": "DNS Query/Response Analysis",
        "filter": "dns",
        "fields": [
            "frame.time",
            "ip.src",
            "ip.dst",
            "dns.qry.name",
            "dns.resp.addr",
            "dns.time",
            "dns.flags.rcode",
        ],
    },
    "mdns": {
        "description": "mDNS / Bonjour Service Discovery",
        "filter": "mdns",
        "fields": [
            "frame.time",
            "ip.src",
            "dns.qry.name",
            "dns.resp.name",
            "dns.srv.name",
        ],
    },
    "ble": {
        "description": "BLE Advertisement Analysis",
        "filter": "btle.advertising_header",
        "fields": [
            "frame.time",
            "btle.advertising_header.pdu_type",
            "btcommon.eir_ad.entry.company_id",
            "btle.length",
        ],
    },
    "retransmissions": {
        "description": "TCP Retransmission Analysis",
        "filter": "tcp.analysis.retransmission",
        "fields": [
            "frame.time",
            "ip.src",
            "ip.dst",
            "tcp.srcport",
            "tcp.dstport",
        ],
    },
    "http2": {
        "description": "HTTP/2 Stream Analysis",
        "filter": "http2",
        "fields": [
            "frame.time",
            "http2.streamid",
            "http2.header.name",
            "http2.header.value",
            "http2.type",
        ],
    },
}

# Statistics commands (use -z flag, no field extraction)
TSHARK_STATS = {
    "io_stat": {
        "description": "Traffic I/O Statistics",
        "args": ["-q", "-z", "io,stat,1"],
    },
    "conversations": {
        "description": "TCP Conversations",
        "args": ["-q", "-z", "conv,tcp"],
    },
    "endpoints": {
        "description": "IP Endpoints",
        "args": ["-q", "-z", "endpoints,ip"],
    },
}


# ============================================================
# Known Issue Patterns
# ============================================================

PCAP_ISSUE_PATTERNS = [
    {
        "name": "TLS version < 1.2",
        "category": "TLS",
        "check": lambda findings: any(
            "0x0301" in str(f.details.get("version", "")) or  # TLS 1.0
            "0x0300" in str(f.details.get("version", ""))      # SSL 3.0
            for f in findings if f.category == "TLS"
        ),
        "severity": "P0",
        "impact": "ATS violation — insecure protocol version negotiated",
    },
    {
        "name": "DNS NXDOMAIN",
        "category": "DNS",
        "check": lambda findings: any(
            f.details.get("rcode") == "3"
            for f in findings if f.category == "DNS"
        ),
        "severity": "P1",
        "impact": "Domain not found — Apple service unreachable",
    },
    {
        "name": "Slow DNS (>500ms)",
        "category": "DNS",
        "check": lambda findings: any(
            float(f.details.get("response_time", 0)) > 0.5
            for f in findings if f.category == "DNS"
        ),
        "severity": "P2",
        "impact": "Slow DNS resolution — AirDrop/Handoff discovery delayed",
    },
    {
        "name": "No Apple mDNS services",
        "category": "mDNS",
        "check": lambda findings: (
            any(f.category == "mDNS" for f in findings) and
            not any(
                "_airdrop" in str(f.details) or "_airplay" in str(f.details)
                for f in findings if f.category == "mDNS"
            )
        ),
        "severity": "P1",
        "impact": "No Apple sharing services discovered on network",
    },
    {
        "name": "High retransmission rate",
        "category": "TCP",
        "check": lambda findings: (
            sum(1 for f in findings if f.category == "TCP_RETRANS") > 5
        ),
        "severity": "P1",
        "impact": "Network instability — AirDrop/SharePlay transfers unreliable",
    },
]


# ============================================================
# Pcap Parser
# ============================================================

class PcapParser:
    """
    Wraps tshark to analyze packet captures.

    Args:
        capture_file: Path to .pcap, .pcapng, or .logdump file.
    """

    def __init__(self, capture_file: str):
        self.capture_file = str(capture_file)
        self.report = PcapReport(capture_file=self.capture_file)
        self.report.tshark_available = self._check_tshark()
        self.findings: list[PcapFinding] = []

    @staticmethod
    def _check_tshark() -> bool:
        """Check if tshark is installed."""
        return shutil.which("tshark") is not None

    def _run_tshark(self, display_filter: str, fields: list[str]) -> list[dict]:
        """
        Run a tshark command and return parsed field output.

        Args:
            display_filter: Wireshark display filter string.
            fields: List of field names to extract.

        Returns:
            List of dicts mapping field names to values.
        """
        if not self.report.tshark_available:
            return []

        cmd = [
            "tshark", "-r", self.capture_file,
            "-Y", display_filter,
            "-T", "fields",
        ]
        for f in fields:
            cmd.extend(["-e", f])
        cmd.append("-E")
        cmd.append("separator=|")

        try:
            result = subprocess.run(
                cmd, capture_output=True, text=True, timeout=30
            )
            if result.returncode != 0:
                return []

            rows = []
            for line in result.stdout.strip().splitlines():
                if not line.strip():
                    continue
                values = line.split("|")
                row = {}
                for i, field_name in enumerate(fields):
                    # Use full field path as key to avoid collisions
                    row[field_name] = values[i] if i < len(values) else ""
                rows.append(row)
            return rows

        except (subprocess.TimeoutExpired, FileNotFoundError):
            return []

    def _run_tshark_stats(self, stat_args: list[str]) -> str:
        """Run a tshark statistics command and return raw output."""
        if not self.report.tshark_available:
            return ""

        cmd = ["tshark", "-r", self.capture_file] + stat_args
        try:
            result = subprocess.run(
                cmd, capture_output=True, text=True, timeout=30
            )
            return result.stdout if result.returncode == 0 else ""
        except (subprocess.TimeoutExpired, FileNotFoundError):
            return ""

    # ---- Individual Analyses ----

    def analyze_tls(self) -> dict:
        """Extract and analyze TLS handshakes."""
        spec = TSHARK_COMMANDS["tls"]
        rows = self._run_tshark(spec["filter"], spec["fields"])

        handshakes = []
        for row in rows:
            finding = PcapFinding(
                category="TLS",
                description=f"TLS handshake: {row.get('ip.src', '?')} -> {row.get('ip.dst', '?')}",
                details={
                    "type": row.get("tls.handshake.type", ""),
                    "version": row.get("tls.handshake.version", ""),
                    "cipher": row.get("tls.handshake.ciphersuite", ""),
                },
            )
            self.findings.append(finding)
            handshakes.append(row)

        analysis = {
            "description": spec["description"],
            "count": len(handshakes),
            "handshakes": handshakes,
            "command": f"tshark -r {self.capture_file} -Y \"{spec['filter']}\" -T fields "
                       + " ".join(f"-e {f}" for f in spec["fields"]),
        }
        self.report.analyses["tls"] = analysis
        return analysis

    def analyze_dns(self) -> dict:
        """Extract and analyze DNS queries/responses."""
        spec = TSHARK_COMMANDS["dns"]
        rows = self._run_tshark(spec["filter"], spec["fields"])

        queries = []
        for row in rows:
            finding = PcapFinding(
                category="DNS",
                description=f"DNS query: {row.get('dns.qry.name', '?')}",
                details={
                    "domain": row.get("dns.qry.name", ""),
                    "resolved_ip": row.get("dns.resp.addr", ""),
                    "response_time": row.get("dns.time", "0"),
                    "rcode": row.get("dns.flags.rcode", ""),
                },
            )
            self.findings.append(finding)
            queries.append(row)

        analysis = {
            "description": spec["description"],
            "count": len(queries),
            "queries": queries,
            "command": f"tshark -r {self.capture_file} -Y \"{spec['filter']}\" -T fields "
                       + " ".join(f"-e {f}" for f in spec["fields"]),
        }
        self.report.analyses["dns"] = analysis
        return analysis

    def analyze_mdns(self) -> dict:
        """Extract and analyze mDNS/Bonjour service discovery."""
        spec = TSHARK_COMMANDS["mdns"]
        rows = self._run_tshark(spec["filter"], spec["fields"])

        services = []
        apple_services_found = set()
        for row in rows:
            # Check ALL field values for Apple sharing service names
            all_values = " ".join(str(v) for v in row.values())
            for svc in ["_airdrop", "_airplay", "_companion-link", "_homekit"]:
                if svc in all_values:
                    apple_services_found.add(svc)

            finding = PcapFinding(
                category="mDNS",
                description=f"mDNS: {all_values[:60]}",
                details=row,
            )
            self.findings.append(finding)
            services.append(row)

        analysis = {
            "description": spec["description"],
            "count": len(services),
            "apple_services": list(apple_services_found),
            "services": services,
            "command": f"tshark -r {self.capture_file} -Y \"{spec['filter']}\" -T fields "
                       + " ".join(f"-e {f}" for f in spec["fields"]),
        }
        self.report.analyses["mdns"] = analysis
        return analysis

    def analyze_ble(self) -> dict:
        """Extract and analyze BLE advertisements (btsnoop/HCI logs)."""
        spec = TSHARK_COMMANDS["ble"]
        rows = self._run_tshark(spec["filter"], spec["fields"])

        advertisements = []
        apple_devices = 0
        for row in rows:
            company_id = row.get("btcommon.eir_ad.entry.company_id", "")
            is_apple = "0x004c" in company_id.lower() if company_id else False
            if is_apple:
                apple_devices += 1

            finding = PcapFinding(
                category="BLE",
                description=f"BLE advertisement: company={company_id}",
                details={
                    "pdu_type": row.get("btle.advertising_header.pdu_type", ""),
                    "company_id": company_id,
                    "length": row.get("btle.length", ""),
                    "is_apple": is_apple,
                },
            )
            self.findings.append(finding)
            advertisements.append(row)

        analysis = {
            "description": spec["description"],
            "count": len(advertisements),
            "apple_devices": apple_devices,
            "advertisements": advertisements,
            "command": f"tshark -r {self.capture_file} -Y \"{spec['filter']}\" -T fields "
                       + " ".join(f"-e {f}" for f in spec["fields"]),
        }
        self.report.analyses["ble"] = analysis
        return analysis

    def analyze_retransmissions(self) -> dict:
        """Detect TCP retransmissions and calculate rate."""
        spec = TSHARK_COMMANDS["retransmissions"]
        rows = self._run_tshark(spec["filter"], spec["fields"])

        for row in rows:
            finding = PcapFinding(
                category="TCP_RETRANS",
                description=f"Retransmission: {row.get('ip.src', '?')}:{row.get('tcp.srcport', '?')} -> "
                            f"{row.get('ip.dst', '?')}:{row.get('tcp.dstport', '?')}",
                details=row,
            )
            self.findings.append(finding)

        # Get total TCP packet count for rate calculation
        total_tcp = len(self._run_tshark("tcp", ["frame.number"]))
        rate = (len(rows) / total_tcp * 100) if total_tcp > 0 else 0

        analysis = {
            "description": spec["description"],
            "retransmissions": len(rows),
            "total_tcp_packets": total_tcp,
            "retransmission_rate": f"{rate:.1f}%",
            "command": f"tshark -r {self.capture_file} -Y \"{spec['filter']}\" -T fields "
                       + " ".join(f"-e {f}" for f in spec["fields"]),
        }
        self.report.analyses["retransmissions"] = analysis
        return analysis

    def analyze_http2(self) -> dict:
        """Analyze HTTP/2 streams and multiplexing."""
        spec = TSHARK_COMMANDS["http2"]
        rows = self._run_tshark(spec["filter"], spec["fields"])

        streams = set()
        for row in rows:
            stream_id = row.get("http2.streamid", "")
            if stream_id:
                streams.add(stream_id)

        analysis = {
            "description": spec["description"],
            "frame_count": len(rows),
            "unique_streams": len(streams),
            "multiplexing": len(streams) > 1,
            "command": f"tshark -r {self.capture_file} -Y \"{spec['filter']}\" -T fields "
                       + " ".join(f"-e {f}" for f in spec["fields"]),
        }
        self.report.analyses["http2"] = analysis
        return analysis

    def analyze_traffic_stats(self) -> dict:
        """Get traffic statistics."""
        stats = {}
        for name, spec in TSHARK_STATS.items():
            output = self._run_tshark_stats(spec["args"])
            stats[name] = {
                "description": spec["description"],
                "raw_output": output[:500] if output else "No data",
                "command": f"tshark -r {self.capture_file} " + " ".join(spec["args"]),
            }

        self.report.analyses["traffic_stats"] = stats
        return stats

    # ---- Issue Detection ----

    def flag_issues(self) -> list[PcapIssue]:
        """Detect known issue patterns from packet analysis."""
        issues = []
        for pattern_def in PCAP_ISSUE_PATTERNS:
            try:
                if pattern_def["check"](self.findings):
                    issues.append(PcapIssue(
                        pattern=pattern_def["name"],
                        severity=pattern_def["severity"],
                        category=pattern_def["category"],
                        description=pattern_def["name"],
                        impact=pattern_def["impact"],
                    ))
            except Exception:
                pass  # Skip pattern if check fails

        self.report.issues = [asdict(i) for i in issues]
        return issues

    # ---- Full Analysis ----

    def full_analysis(self) -> PcapReport:
        """Run all analyses and return combined report."""
        if not self.report.tshark_available:
            print("  ⚠️  tshark not found — install Wireshark for packet analysis")
            print("     brew install wireshark  (macOS)")
            print("     sudo apt install tshark (Linux)")
            return self.report

        self.analyze_tls()
        self.analyze_dns()
        self.analyze_mdns()
        self.analyze_ble()
        self.analyze_retransmissions()
        self.analyze_http2()
        self.analyze_traffic_stats()
        self.flag_issues()
        return self.report

    def get_commands(self) -> dict:
        """Return all tshark commands this tool uses (for reference/docs)."""
        commands = {}
        for name, spec in TSHARK_COMMANDS.items():
            cmd = (
                f"tshark -r <capture.pcap> -Y \"{spec['filter']}\" "
                f"-T fields " + " ".join(f"-e {f}" for f in spec["fields"])
            )
            commands[name] = {"description": spec["description"], "command": cmd}

        for name, spec in TSHARK_STATS.items():
            cmd = f"tshark -r <capture.pcap> " + " ".join(spec["args"])
            commands[name] = {"description": spec["description"], "command": cmd}

        return commands


# ============================================================
# CLI
# ============================================================

def print_commands():
    """Print all tshark commands this tool wraps."""
    parser = PcapParser("/dev/null")
    commands = parser.get_commands()

    print(f"\n{'='*60}")
    print(f"  NetQual — tshark Commands Reference")
    print(f"{'='*60}\n")

    for name, info in commands.items():
        print(f"  {name}: {info['description']}")
        print(f"    $ {info['command']}")
        print()


if __name__ == "__main__":
    import sys

    if len(sys.argv) < 2 or sys.argv[1] == "--help":
        print("Usage:")
        print("  python pcap_parser.py <capture.pcap>     # Full analysis")
        print("  python pcap_parser.py --commands          # Show tshark commands")
        sys.exit(0)

    if sys.argv[1] == "--commands":
        print_commands()
        sys.exit(0)

    capture_file = sys.argv[1]
    parser = PcapParser(capture_file)
    report = parser.full_analysis()

    print(f"\n{'='*60}")
    print(f"  NetQual Packet Analysis — {capture_file}")
    print(f"{'='*60}\n")

    print(f"  tshark available: {report.tshark_available}")
    for name, analysis in report.analyses.items():
        if isinstance(analysis, dict) and "count" in analysis:
            print(f"  {name}: {analysis.get('count', 'N/A')} entries found")

    if report.issues:
        print(f"\n  Flagged Issues ({len(report.issues)}):")
        for issue in report.issues:
            icon = {"P0": "🔴", "P1": "🟠", "P2": "🟡"}.get(issue["severity"], "⚪")
            print(f"    {icon} [{issue['severity']}] {issue['pattern']}")
            print(f"         Impact: {issue['impact']}")
    else:
        print("\n  ✅ No issues flagged.")
