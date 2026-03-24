#!/usr/bin/env python3
"""
NetQual — Applied Networking Quality Validator
================================================
CLI entry point for log parsing, pcap analysis, and AirDrop simulation.

Usage:
    python netqual.py log <logfile> [--level ERROR] [--component DNS TLS]
    python netqual.py pcap <capture.pcap> [--analyze tls dns mdns]
    python netqual.py pcap --commands
    python netqual.py simulate [--scenario discovery|transfer|namedrop|failure]
    python netqual.py test [--allure]
    python netqual.py all --logfile <logfile>

Author: Swapnil Tilaye
"""

import argparse
import subprocess
import sys
from pathlib import Path


def cmd_log(args):
    """Parse a text log file."""
    from log_parser import LogParser, print_report
    parser = LogParser(args.logfile)
    report = parser.analyze()

    if args.level:
        filtered = parser.filter_by_level(args.level)
        print(f"\n  Filtered by level={args.level}: {len(filtered)} entries")
        for e in filtered:
            print(f"    [{e.line_number:3d}] {e.timestamp} {e.level:5s} [{e.component}] {e.message}")
    elif args.component:
        filtered = parser.filter_by_component(*args.component)
        print(f"\n  Filtered by component={','.join(args.component)}: {len(filtered)} entries")
        for e in filtered:
            print(f"    [{e.line_number:3d}] {e.timestamp} {e.level:5s} [{e.component}] {e.message}")
    else:
        print_report(report)

    if args.json:
        print(report.to_json())


def cmd_pcap(args):
    """Analyze a packet capture file."""
    from pcap_parser import PcapParser, print_commands

    if args.commands:
        print_commands()
        return

    parser = PcapParser(args.capture)
    report = parser.full_analysis()

    print(f"\n{'='*60}")
    print(f"  NetQual Packet Analysis — {args.capture}")
    print(f"{'='*60}\n")
    print(f"  tshark available: {report.tshark_available}")

    for name, analysis in report.analyses.items():
        if isinstance(analysis, dict) and "count" in analysis:
            print(f"  {name}: {analysis.get('count', 'N/A')} entries")

    if report.issues:
        print(f"\n  Flagged Issues ({len(report.issues)}):")
        for issue in report.issues:
            icon = {"P0": "🔴", "P1": "🟠", "P2": "🟡"}.get(issue["severity"], "⚪")
            print(f"    {icon} [{issue['severity']}] {issue['pattern']}")
            print(f"         Impact: {issue['impact']}")
    else:
        print("\n  ✅ No issues flagged.")


def cmd_simulate(args):
    """Run AirDrop protocol simulation."""
    from airdrop_simulator import AirDropSimulator

    sim = AirDropSimulator()
    scenario = args.scenario

    print(f"\n{'='*60}")
    print(f"  NetQual — AirDrop Protocol Simulator")
    print(f"  Scenario: {scenario}")
    print(f"{'='*60}\n")

    if scenario == "discovery":
        log = sim.simulate_discovery("alice@icloud.com")
    elif scenario == "transfer":
        log = sim.simulate_full_transfer(
            sender_email="alice@icloud.com",
            receiver_email="bob@icloud.com",
            file_name="vacation.heic",
            file_size_mb=8.5,
        )
    elif scenario == "namedrop":
        log = sim.simulate_namedrop("alice@icloud.com")
    elif scenario == "failure":
        log = sim.simulate_full_transfer(
            sender_email="alice@icloud.com",
            receiver_email="bob@icloud.com",
            success=False,
        )
    else:
        print(f"  Unknown scenario: {scenario}")
        print("  Available: discovery, transfer, namedrop, failure")
        return

    print(log.to_text())

    # Optionally feed into log parser
    if args.parse:
        from log_parser import LogParser, print_report
        parser = LogParser(log.entries)
        report = parser.analyze()
        print(f"\n{'='*60}")
        print(f"  Log Parser Analysis of Simulated Session")
        print(f"{'='*60}")
        print_report(report)


def cmd_test(args):
    """Run all tests."""
    cmd = ["python3", "-m", "pytest", "-v"]
    if args.allure:
        cmd.extend(["--alluredir=allure-results"])
    print(f"  Running: {' '.join(cmd)}\n")
    result = subprocess.run(cmd)

    if args.allure and result.returncode == 0:
        print("\n  Allure results saved to allure-results/")
        print("  To view: allure serve allure-results")


def cmd_opendrop(args):
    """Run real AirDrop operations via the OpenDrop CLI."""
    from opendrop_wrapper import OpenDropTester

    tester = OpenDropTester()

    print(f"\n{'='*60}")
    print(f"  NetQual — OpenDrop Real AirDrop Tester")
    print(f"  Action: {args.action}")
    print(f"{'='*60}\n")

    if args.action == "preflight":
        checks = tester.preflight_check()
        icons = {True: "✅", False: "❌"}
        for key, val in checks.items():
            if key == "recommendations":
                continue
            icon = icons.get(val, "ℹ️") if isinstance(val, bool) else "ℹ️"
            print(f"  {icon}  {key}: {val}")
        if checks["recommendations"]:
            print("\n  Recommendations:")
            for rec in checks["recommendations"]:
                print(f"    → {rec}")
        if not checks["ready"]:
            print("\n  ⚠️  Run airdrop_simulator.py for offline testing.")

    elif args.action == "discover":
        print(f"  Scanning for AirDrop devices (timeout={args.timeout}s)...\n")
        devices = tester.discover(timeout=args.timeout)
        if devices:
            for dev in devices:
                print(f"    📱  {dev.name}")
        else:
            print("  No devices found.")
        if args.parse:
            _parse_opendrop_log(tester)

    elif args.action == "send":
        if not args.file:
            print("  ❌  --file is required for the send action.")
            return
        target_label = f" → {args.target}" if args.target else " → first available"
        print(f"  Sending: {args.file}{target_label}\n")
        result = tester.send_file(args.file, target_name=args.target, timeout=args.timeout)
        icon = "✅" if result.success else "❌"
        print(f"  {icon}  {result.file_name}")
        if result.success:
            print(f"       Duration:   {result.duration_ms:.0f}ms")
            print(f"       Throughput: {result.throughput_mbps:.1f} Mbps")
            print(f"       Size:       {result.file_size_bytes / 1024:.1f} KB")
        else:
            print(f"       Error: {result.error}")
        if args.parse:
            _parse_opendrop_log(tester)

    elif args.action == "receive":
        print(f"  Listening for AirDrop files (timeout={args.timeout}s)...")
        print(f"  Output: {args.output}\n")
        files = tester.receive(output_dir=args.output, timeout=args.timeout)
        if files:
            for f in files:
                print(f"    📥  {f}")
        else:
            print("  No files received.")
        if args.parse:
            _parse_opendrop_log(tester)


def _parse_opendrop_log(tester):
    """Feed an OpenDropTester session log into the log parser and print report."""
    from log_parser import LogParser, print_report
    if tester.log.entries:
        print(f"\n{'='*60}")
        print(f"  Log Parser Analysis of OpenDrop Session")
        print(f"{'='*60}")
        parser = LogParser(tester.log.entries)
        report = parser.analyze()
        print_report(report)


def cmd_all(args):
    """Run everything: log parse + simulate + tests."""
    print(f"\n{'='*60}")
    print(f"  NetQual — Full Suite")
    print(f"{'='*60}")

    # Log parsing
    if args.logfile:
        print(f"\n  [1/3] Parsing log: {args.logfile}")
        from log_parser import LogParser, print_report
        parser = LogParser(args.logfile)
        report = parser.analyze()
        print_report(report)

    # Simulation
    print(f"\n  [2/3] Running AirDrop simulation...")
    from airdrop_simulator import AirDropSimulator
    sim = AirDropSimulator()
    log = sim.simulate_full_transfer(
        sender_email="alice@icloud.com",
        receiver_email="bob@icloud.com",
    )
    print(log.to_text())

    # Tests
    print(f"\n  [3/3] Running tests...")
    subprocess.run(["python3", "-m", "pytest", "-v", "--tb=short"])


def main():
    parser = argparse.ArgumentParser(
        description="NetQual — Applied Networking Quality Validator",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    sub = parser.add_subparsers(dest="command", help="Available commands")

    # log
    p_log = sub.add_parser("log", help="Parse a network diagnostic log file")
    p_log.add_argument("logfile", help="Path to .log file")
    p_log.add_argument("--level", help="Filter by level (INFO, WARN, ERROR, DEBUG)")
    p_log.add_argument("--component", nargs="+", help="Filter by component(s)")
    p_log.add_argument("--json", action="store_true", help="Output JSON report")

    # pcap
    p_pcap = sub.add_parser("pcap", help="Analyze a packet capture file")
    p_pcap.add_argument("capture", nargs="?", help="Path to .pcap file")
    p_pcap.add_argument("--commands", action="store_true", help="Show tshark commands")
    p_pcap.add_argument("--analyze", nargs="+", help="Specific analyses to run")

    # simulate
    p_sim = sub.add_parser("simulate", help="Run AirDrop protocol simulation")
    p_sim.add_argument("--scenario", default="transfer",
                       choices=["discovery", "transfer", "namedrop", "failure"],
                       help="Simulation scenario")
    p_sim.add_argument("--parse", action="store_true",
                       help="Feed simulation output into log parser")

    # opendrop
    p_od = sub.add_parser("opendrop", help="Real AirDrop testing via OpenDrop CLI")
    p_od.add_argument(
        "action",
        choices=["preflight", "discover", "send", "receive"],
        help="preflight: check prerequisites | discover: find nearby devices | "
             "send: send a file | receive: listen for incoming files",
    )
    p_od.add_argument("--file", help="Path to file to send (required for 'send')")
    p_od.add_argument("--target", help="Target device name for 'send' (default: first found)")
    p_od.add_argument("--timeout", type=int, default=15, help="Timeout in seconds (default: 15)")
    p_od.add_argument("--output", default="/tmp/airdrop_received",
                      help="Output directory for 'receive' (default: /tmp/airdrop_received)")
    p_od.add_argument("--parse", action="store_true",
                      help="Feed session log into log_parser after action completes")

    # test
    p_test = sub.add_parser("test", help="Run all tests")
    p_test.add_argument("--allure", action="store_true", help="Generate Allure report")

    # all
    p_all = sub.add_parser("all", help="Run everything")
    p_all.add_argument("--logfile", default="sample_logs/network_diag.log",
                       help="Log file to parse")

    args = parser.parse_args()

    commands = {
        "log": cmd_log,
        "pcap": cmd_pcap,
        "simulate": cmd_simulate,
        "opendrop": cmd_opendrop,
        "test": cmd_test,
        "all": cmd_all,
    }

    if args.command in commands:
        commands[args.command](args)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
