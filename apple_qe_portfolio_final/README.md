# Apple Applied Networking — QE Test Portfolio

A comprehensive test automation portfolio for Apple's Applied Networking stack,
covering AirDrop, Handoff, SharePlay, Universal Clipboard, and NameDrop.

**Author:** Swapnil Tilaye
**Role:** Software Quality Engineer — Applied Networking

---

## Repository Structure

```
apple-qe-portfolio/
├── code/
│   ├── netqual/                       # NetQual — Quality Validator Framework
│   │   ├── netqual.py                 # CLI entry point (6 subcommands)
│   │   ├── protocol_base.py           # Plugin architecture: ABC, registry, shared helpers
│   │   ├── log_parser.py              # sysdiagnose log parser (10 patterns, 4-level analysis)
│   │   ├── pcap_parser.py             # tshark packet capture analyzer (7 analyses)
│   │   ├── airdrop_simulator.py       # AirDrop + NameDrop protocol simulator
│   │   ├── handoff_simulator.py       # Handoff (NSUserActivity) protocol simulator
│   │   ├── opendrop_wrapper.py        # Real AirDrop via OpenDrop CLI
│   │   ├── netqual_config.yaml        # Central config (devices, thresholds, patterns, suites)
│   │   ├── test_log_parser.py         # 17 tests for log parser
│   │   ├── test_pcap_parser.py        # 12 tests for pcap parser (mocked tshark)
│   │   ├── test_opendrop.py           # 31 tests for OpenDrop integration
│   │   ├── sample_logs/               # Simulated sysdiagnose logs
│   │   ├── sample_captures/           # pcap generation instructions
│   │   ├── architecture.mermaid       # Mermaid source diagram
│   │   └── architecture_diagram.pdf   # Visual architecture
│   │
│   ├── postman/                       # API-Level Tests
│   │   └── Apple_Applied_Networking_QE.postman_collection.json  # 15 requests
│   │
│   └── swift_tests/                   # XCTest (Swift)
│       └── SharingFeatureTests.swift  # Handoff, SharePlay, URLSession (~20 tests)
│
└── docs/
    └── coding_prep/                   # Interview prep materials
```

---

## Quick Start

```bash
# Install Python dependencies
pip install -r code/netqual/requirements.txt

# Run all 60 NetQual tests (no hardware required)
cd code/netqual
pytest -v

# Run AirDrop simulation
python netqual.py simulate --scenario transfer

# Parse a network diagnostic log
python netqual.py log sample_logs/network_diag.log

# Analyze a packet capture
python netqual.py pcap sample_captures/capture.pcap

# Real AirDrop testing via OpenDrop (requires macOS + opendrop installed)
python netqual.py opendrop preflight
python netqual.py opendrop discover --timeout 15
python netqual.py opendrop send --file photo.heic --target "iPhone"

# Run everything
python netqual.py all
```

---

## Test Summary

| Suite | Tests | What It Covers | Runs Offline? |
|-------|-------|----------------|--------------|
| `netqual/test_log_parser.py` | 17 | Log parsing, filtering, pattern detection | Yes |
| `netqual/test_pcap_parser.py` | 12 | TLS, DNS, mDNS, retransmission analysis | Yes (mocked) |
| `netqual/test_opendrop.py` | 31 | Preflight, data models, mocked I/O, real hardware | Tier 1 yes / Tier 2 needs hardware |
| `postman/` | 15 | Apple service health, TLS, HTTP/2 endpoints | Needs network |
| `swift_tests/` | ~20 | Handoff NSUserActivity, SharePlay sync, URLSession | Needs Xcode |
| **Total** | **~95** | | |

---

## Framework Architecture

```
                      ┌───────────────────────────────────────┐
                      │   netqual.py (CLI)                     │
                      │   log │ pcap │ simulate │ opendrop │ test│
                      └──────────────┬────────────────────────┘
                                     │
              ┌──────────────────────┼──────────────────────┐
              │                      │                      │
    ┌─────────▼──────┐   ┌───────────▼──────┐   ┌──────────▼───────────┐
    │  log_parser     │   │   pcap_parser    │   │  simulators          │
    │  10 patterns    │   │   7 tshark       │   │  airdrop_simulator   │
    │  P0 / P1 / P2   │   │   analyses       │   │  handoff_simulator   │
    │  sysdiagnose    │   │   TLS/DNS/BLE    │   │  opendrop_wrapper    │
    └─────────────────┘   └──────────────────┘   └──────────────────────┘
                                     │
              ┌──────────────────────┼──────────────────────┐
              │                      │                      │
    ┌─────────▼──────┐   ┌───────────▼──────┐   ┌──────────▼───────────┐
    │  protocol_      │   │   YAML config    │   │  Allure reporting    │
    │  base.py        │   │   devices        │   │  60 tests            │
    │  plugin arch    │   │   thresholds     │   │  P0→Minor severity   │
    │  BLE/mDNS       │   │   test suites    │   │                      │
    └─────────────────┘   └──────────────────┘   └──────────────────────┘
```

---

## CLI Reference

```bash
# Log analysis
python netqual.py log <logfile>
python netqual.py log <logfile> --level ERROR
python netqual.py log <logfile> --component DNS TLS
python netqual.py log <logfile> --json

# Packet capture analysis
python netqual.py pcap <capture.pcap>
python netqual.py pcap --commands          # Print all tshark commands

# Protocol simulation
python netqual.py simulate --scenario discovery
python netqual.py simulate --scenario transfer
python netqual.py simulate --scenario namedrop
python netqual.py simulate --scenario failure
python netqual.py simulate --scenario transfer --parse

# Real AirDrop (requires opendrop + macOS + awdl0)
python netqual.py opendrop preflight
python netqual.py opendrop discover [--timeout 15]
python netqual.py opendrop send --file <path> [--target "Device Name"] [--timeout 30]
python netqual.py opendrop receive [--output /tmp/drops] [--timeout 60]
python netqual.py opendrop discover --parse   # also runs log_parser on session

# Run test suite
python netqual.py test [--allure]

# Run everything
python netqual.py all [--logfile sample_logs/network_diag.log]
```

---

## Key Design Decisions

**Plugin architecture:** Add new Apple protocols by inheriting `ProtocolSimulator`
and registering with `@register_protocol("name")`. No changes to core code needed.
`AirDropSimulator` and `HandoffSimulator` both use this pattern.

**Shared helpers:** `BLEHelper` and `MDNSHelper` in `protocol_base.py` are shared
across all BLE-based protocols. No duplicated BLE hashing or mDNS packet logic.

**Single config file:** `netqual_config.yaml` drives everything — device inventory,
test thresholds, log patterns, test suites (CI/nightly/release). Tune per-release
without touching Python code.

**Two-layer AirDrop testing:** Protocol logic tested offline via `airdrop_simulator.py`
(runs in CI, no hardware). Real over-the-air behavior tested via `opendrop_wrapper.py`
when macOS + AWDL is available. Same YAML config drives both.

**Graceful degradation:** `@requires_opendrop` auto-skips hardware tests when OpenDrop
is not installed or AWDL is unavailable. All 31 `test_opendrop.py` Tier 1 tests always
run in CI without any hardware dependency.

---

## How This Maps to the Role

| Job Requirement | Portfolio Feature |
|----------------|-------------------|
| "Build tools and test frameworks" | NetQual CLI + plugin architecture + 60 tests |
| "Manual/automation testing" | Log parser (automates manual triage) + pcap (protocol analysis) |
| "Test boundaries and edge cases" | 15 known issue patterns detected automatically |
| "Python, Swift, or similar" | Python (NetQual + pytest) + Swift (XCTest) |
| "UI and lower level testing" | Text logs (app level) + pcap (packet level) + real AirDrop |
| "Invent new ways to test" | Protocol simulation + OpenDrop integration + log-parser pipeline |
