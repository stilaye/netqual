"""
log_parser.py — Network Diagnostic Log Parser
===============================================
Parses sysdiagnose-style network logs and surfaces issues.

Levels of analysis:
  1. Parse & Structure — regex parse into structured entries
  2. Categorize & Count — error/warning counts per component
  3. Pattern Detection — flag known issue signatures with severity
  4. Summary Report — JSON output for reporting

Usage:
    from log_parser import LogParser
    parser = LogParser("sample_logs/network_diag.log")
    report = parser.analyze()
    print(report.to_json())
"""

import re
import json
from dataclasses import dataclass, field, asdict
from typing import Optional
from datetime import datetime
from collections import Counter, defaultdict
from pathlib import Path


# ============================================================
# Data Models
# ============================================================

@dataclass
class LogEntry:
    """A single parsed log line."""

    timestamp: str
    level: str
    component: str
    message: str
    line_number: int = 0

    @property
    def is_error(self) -> bool:
        return self.level == "ERROR"

    @property
    def is_warning(self) -> bool:
        return self.level == "WARN"


@dataclass
class FlaggedPattern:
    """A detected issue pattern with severity and impact."""

    pattern: str
    severity: str  # P0, P1, P2
    line_number: int
    component: str
    message: str
    impact: str


@dataclass
class LogReport:
    """Complete analysis report."""

    log_file: str
    total_entries: int = 0
    parse_errors: int = 0
    errors: int = 0
    warnings: int = 0
    duration: str = ""
    by_component: dict = field(default_factory=dict)
    by_level: dict = field(default_factory=dict)
    flagged_patterns: list = field(default_factory=list)
    entries: list = field(default_factory=list)

    def to_dict(self) -> dict:
        """Convert report to dictionary."""
        d = asdict(self)
        d["flagged_patterns"] = [asdict(p) for p in self.flagged_patterns]
        d.pop("entries")  # Don't include raw entries in JSON
        return d

    def to_json(self, indent: int = 2) -> str:
        """Convert report to JSON string."""
        return json.dumps(self.to_dict(), indent=indent)


# ============================================================
# Pattern Definitions
# ============================================================

KNOWN_PATTERNS = [
    {
        "name": "DNS timeout",
        "regex": r"Resolution failed.*timeout",
        "severity": "P1",
        "impact": "All sharing features blocked — devices cannot resolve Apple services",
    },
    {
        "name": "TLS certificate failure",
        "regex": r"Certificate validation failed",
        "severity": "P0",
        "impact": "MITM vulnerability — all encrypted connections fail, AirDrop/Handoff blocked",
    },
    {
        "name": "TLS downgrade",
        "regex": r"Downgrade detected.*TLSv1\.[01]",
        "severity": "P0",
        "impact": "ATS violation — connection uses insecure protocol version",
    },
    {
        "name": "BLE interval out of range",
        "regex": r"[Ii]nterval out of range",
        "severity": "P2",
        "impact": "AirDrop/NameDrop discovery unreliable — devices may not find each other",
    },
    {
        "name": "AWDL peer timeout",
        "regex": r"Peer connection failed.*timeout",
        "severity": "P1",
        "impact": "AirDrop file transfer blocked — P2P Wi-Fi channel cannot be established",
    },
    {
        "name": "SharePlay sync drift",
        "regex": r"Sync drift detected.*\d+ms",
        "severity": "P2",
        "impact": "SharePlay participants out of sync — degraded shared viewing experience",
    },
    {
        "name": "Slow HTTP response",
        "regex": r"Response slow.*\d{4,}ms",
        "severity": "P2",
        "impact": "Handoff/iCloud sync delayed — user experiences lag in cross-device features",
    },
    {
        "name": "Handshake aborted",
        "regex": r"Handshake aborted",
        "severity": "P0",
        "impact": "TLS connection cannot be established — secure communication blocked",
    },
]


# ============================================================
# Log Parser
# ============================================================

# Regex for standard log line format:
# TIMESTAMP LEVEL [COMPONENT] MESSAGE
LOG_PATTERN = re.compile(
    r"^(\S+)\s+"           # timestamp
    r"(INFO|WARN|ERROR|DEBUG)\s+"  # level
    r"\[(\w+)\]\s+"        # component in brackets
    r"(.+)$"               # message (rest of line)
)


class LogParser:
    """
    Parses sysdiagnose-style network diagnostic logs.

    Args:
        log_source: Path to log file, or list of log lines.
    """

    def __init__(self, log_source):
        if isinstance(log_source, (str, Path)):
            self.log_file = str(log_source)
            self.raw_lines = Path(log_source).read_text().strip().splitlines()
        elif isinstance(log_source, list):
            self.log_file = "<in-memory>"
            self.raw_lines = log_source
        else:
            raise ValueError("log_source must be a file path or list of strings")

        self.entries: list[LogEntry] = []
        self.report = LogReport(log_file=self.log_file)

    # ---- Level 1: Parse & Structure ----

    def parse(self) -> list[LogEntry]:
        """Parse all log lines into structured entries."""
        self.entries = []
        self.report.parse_errors = 0

        for i, line in enumerate(self.raw_lines, start=1):
            line = line.strip()
            if not line:
                continue

            match = LOG_PATTERN.match(line)
            if match:
                entry = LogEntry(
                    timestamp=match.group(1),
                    level=match.group(2),
                    component=match.group(3),
                    message=match.group(4).strip(),
                    line_number=i,
                )
                self.entries.append(entry)
            else:
                self.report.parse_errors += 1

        self.report.total_entries = len(self.entries)
        self.report.entries = self.entries
        return self.entries

    # ---- Level 2: Categorize & Count ----

    def categorize(self) -> dict:
        """Count entries by component and level."""
        by_component = defaultdict(lambda: defaultdict(int))
        by_level = Counter()

        for entry in self.entries:
            by_component[entry.component][entry.level.lower()] += 1
            by_level[entry.level] += 1

        self.report.by_component = {k: dict(v) for k, v in by_component.items()}
        self.report.by_level = dict(by_level)
        self.report.errors = by_level.get("ERROR", 0)
        self.report.warnings = by_level.get("WARN", 0)

        # Calculate duration from first to last entry
        if len(self.entries) >= 2:
            first = self.entries[0].timestamp
            last = self.entries[-1].timestamp
            self.report.duration = f"{first} to {last}"

        return self.report.by_component

    # ---- Level 3: Pattern Detection ----

    def detect_patterns(self) -> list[FlaggedPattern]:
        """Scan entries for known issue patterns."""
        flagged = []

        for entry in self.entries:
            if entry.level not in ("ERROR", "WARN"):
                continue

            for pattern_def in KNOWN_PATTERNS:
                if re.search(pattern_def["regex"], entry.message):
                    flagged.append(FlaggedPattern(
                        pattern=pattern_def["name"],
                        severity=pattern_def["severity"],
                        line_number=entry.line_number,
                        component=entry.component,
                        message=entry.message,
                        impact=pattern_def["impact"],
                    ))

        self.report.flagged_patterns = flagged
        return flagged

    # ---- Level 4: Full Analysis ----

    def analyze(self) -> LogReport:
        """Run all analysis levels and return complete report."""
        self.parse()
        self.categorize()
        self.detect_patterns()
        return self.report

    # ---- Filtering ----

    def filter_by_level(self, level: str) -> list[LogEntry]:
        """Return entries matching the given level."""
        return [e for e in self.entries if e.level == level.upper()]

    def filter_by_component(self, *components: str) -> list[LogEntry]:
        """Return entries matching any of the given components."""
        comp_set = {c.upper() for c in components}
        return [e for e in self.entries if e.component.upper() in comp_set]

    def filter_by_time_range(self, start: str, end: str) -> list[LogEntry]:
        """Return entries within the time range (string comparison)."""
        return [e for e in self.entries if start <= e.timestamp <= end]


# ============================================================
# CLI
# ============================================================

def print_report(report: LogReport, verbose: bool = False):
    """Pretty-print the analysis report to terminal."""
    print(f"\n{'='*60}")
    print(f"  NetQual Log Analysis — {report.log_file}")
    print(f"{'='*60}\n")

    print(f"  Total entries: {report.total_entries}")
    print(f"  Errors: {report.errors}")
    print(f"  Warnings: {report.warnings}")
    if report.parse_errors:
        print(f"  Parse errors: {report.parse_errors}")
    print(f"  Duration: {report.duration}")
    print()

    # By component
    print("  Entries by Component:")
    for comp, counts in sorted(report.by_component.items()):
        parts = ", ".join(f"{k}={v}" for k, v in sorted(counts.items()))
        err_marker = " ⚠" if "error" in counts else ""
        print(f"    {comp:20s} {parts}{err_marker}")
    print()

    # Flagged patterns
    if report.flagged_patterns:
        print(f"  Flagged Issues ({len(report.flagged_patterns)}):")
        for p in report.flagged_patterns:
            icon = {"P0": "🔴", "P1": "🟠", "P2": "🟡"}.get(p.severity, "⚪")
            print(f"    {icon} [{p.severity}] {p.pattern} (line {p.line_number})")
            print(f"         Component: {p.component}")
            print(f"         Impact: {p.impact}")
            print()
    else:
        print("  ✅ No issues flagged — log looks clean.\n")


if __name__ == "__main__":
    import sys

    if len(sys.argv) < 2:
        print("Usage: python log_parser.py <logfile> [--level ERROR] [--component DNS TLS]")
        sys.exit(1)

    log_file = sys.argv[1]

    # Parse optional flags
    level_filter = None
    component_filter = []
    args = sys.argv[2:]
    i = 0
    while i < len(args):
        if args[i] == "--level" and i + 1 < len(args):
            level_filter = args[i + 1]
            i += 2
        elif args[i] == "--component":
            i += 1
            while i < len(args) and not args[i].startswith("--"):
                component_filter.append(args[i])
                i += 1
        else:
            i += 1

    parser = LogParser(log_file)
    report = parser.analyze()

    # Apply filters for display
    if level_filter:
        filtered = parser.filter_by_level(level_filter)
        print(f"\n  Filtered by level={level_filter}: {len(filtered)} entries")
        for e in filtered:
            print(f"    [{e.line_number:3d}] {e.timestamp} {e.level:5s} [{e.component}] {e.message}")
        print()

    if component_filter:
        filtered = parser.filter_by_component(*component_filter)
        print(f"\n  Filtered by component={','.join(component_filter)}: {len(filtered)} entries")
        for e in filtered:
            print(f"    [{e.line_number:3d}] {e.timestamp} {e.level:5s} [{e.component}] {e.message}")
        print()

    if not level_filter and not component_filter:
        print_report(report)

    # Also output JSON
    print(f"  JSON report written to stdout (pipe to file with > report.json)")
