# NetQual — Applied Networking Quality Validator

A Python CLI tool for testing and validating Apple's Applied Networking protocols.
Parses network diagnostic logs, analyzes packet captures with tshark, simulates
AirDrop and Handoff protocol sessions, and runs real over-the-air AirDrop tests
via the open-source OpenDrop CLI.

**Author:** Swapnil Tilaye
**Purpose:** Apple Applied Networking QE — Interview Portfolio

---

## Quick Start

```bash
# Install dependencies
pip install -r requirements.txt

# Parse a network log
python netqual.py log sample_logs/network_diag.log

# Run AirDrop simulation
python netqual.py simulate --scenario transfer

# Run real AirDrop (requires opendrop + macOS)
python netqual.py opendrop preflight
python netqual.py opendrop discover

# Run all tests (60 total)
python netqual.py test

# Run everything: log parse + simulation + tests
python netqual.py all
```

---

## Architecture

See `architecture_diagram.pdf` and `architecture.mermaid` for the full visual diagram.

```
netqual/
├── netqual.py                # CLI entry point (6 subcommands)
├── protocol_base.py          # Plugin architecture: ABC, registry, BLEHelper, MDNSHelper
├── log_parser.py             # Text log parser (4-level analysis, 10 patterns)
├── pcap_parser.py            # tshark packet capture analyzer (7 analyses)
├── airdrop_simulator.py      # AirDrop + NameDrop protocol simulator
├── handoff_simulator.py      # Handoff (NSUserActivity) protocol simulator
├── opendrop_wrapper.py       # Real AirDrop via OpenDrop CLI
├── netqual_config.yaml       # Central config: devices, thresholds, patterns, suites
├── test_log_parser.py        # 17 tests for log parser
├── test_pcap_parser.py       # 12 tests for pcap parser (mocked tshark)
├── test_opendrop.py          # 31 tests for OpenDrop integration
├── sample_logs/              # Simulated sysdiagnose-style logs
├── sample_captures/          # Instructions for generating pcap files
├── architecture.mermaid      # Mermaid source for architecture diagram
├── architecture_diagram.pdf  # Visual architecture diagram
└── requirements.txt
```

---

## Modules

### 1. Protocol Base (`protocol_base.py`)

Plugin architecture shared across all simulators. Add new Apple protocols
without touching existing code.

```python
from protocol_base import ProtocolSimulator, register_protocol, BLEHelper, MDNSHelper

@register_protocol("airplay")
class AirPlaySimulator(ProtocolSimulator):
    def simulate_discovery(self, **kwargs): ...
    def simulate_session(self, **kwargs): ...
    def get_components(self) -> list[str]: ...
```

**Shared helpers available to all simulators:**
- `BLEHelper` — SHA-256 contact hashing, BLE payload builder, payload validation
- `MDNSHelper` — mDNS query builder, packet validation
- `SessionLog` — structured log output compatible with `log_parser`
- `PROTOCOL_REGISTRY` — auto-discovery of all registered simulators

---

### 2. Log Parser (`log_parser.py`)

Parses sysdiagnose-style network diagnostic logs with 4 levels of analysis:

- **Level 1 — Parse:** Regex-based structured parsing (timestamp, level, component, message)
- **Level 2 — Categorize:** Error/warning counts per component (DNS, TLS, BLE, AWDL, mDNS)
- **Level 3 — Detect:** 10 known issue patterns with severity and user-facing impact
- **Level 4 — Report:** JSON summary output

```bash
python netqual.py log sample_logs/network_diag.log
python netqual.py log sample_logs/network_diag.log --level ERROR
python netqual.py log sample_logs/network_diag.log --component DNS TLS
python netqual.py log sample_logs/network_diag.log --json > report.json
```

**Detected Patterns:**

| Pattern | Severity | Apple Feature Impact |
|---------|----------|----------------------|
| DNS timeout | P1 | All sharing features blocked |
| TLS certificate failure | P0 | MITM vulnerability |
| TLS downgrade | P0 | ATS violation |
| BLE interval out of range | P2 | AirDrop/NameDrop discovery unreliable |
| AWDL peer timeout | P1 | AirDrop transfer blocked |
| SharePlay sync drift | P2 | Participants out of sync |
| Slow HTTP response | P2 | Handoff/iCloud sync delayed |
| Handshake aborted | P0 | TLS connection blocked |
| mDNS no response | P1 | Device discovery broken |
| NFC communication error | P1 | NameDrop exchange failed |

---

### 3. Packet Capture Parser (`pcap_parser.py`)

Wraps tshark to analyze `.pcap` and `.logdump` files:

```bash
python netqual.py pcap capture.pcap
python netqual.py pcap --commands    # Print all tshark commands used
```

**7 Protocol Analyses:**

| Analysis | tshark Filter | Apple Feature |
|----------|--------------|---------------|
| TLS Handshakes | `tls.handshake` | AirDrop encryption |
| DNS Queries | `dns` | All features |
| mDNS/Bonjour | `mdns` | Device discovery |
| BLE Advertisements | `btle.advertising_header` | AirDrop/NameDrop |
| TCP Retransmissions | `tcp.analysis.retransmission` | Transfer reliability |
| HTTP/2 Streams | `http2` | URLSession behavior |
| Traffic Statistics | `-z io,stat` | Performance baseline |

---

### 4. AirDrop Simulator (`airdrop_simulator.py`)

Simulates the full AirDrop protocol offline — runs anywhere, no devices needed.
Inherits from `ProtocolSimulator`, registered as `"airdrop"` in `PROTOCOL_REGISTRY`.

```bash
python netqual.py simulate --scenario discovery
python netqual.py simulate --scenario transfer
python netqual.py simulate --scenario namedrop
python netqual.py simulate --scenario failure
python netqual.py simulate --scenario transfer --parse   # Feed output into log parser
```

**Protocol Steps Simulated:**
1. BLE Advertisement (truncated SHA-256 contact hash via `BLEHelper`)
2. mDNS Discovery (`_airdrop._tcp.local` via `MDNSHelper`)
3. Contact Resolution (hash prefix matching against contacts list)
4. AWDL Channel Setup (P2P Wi-Fi, 5GHz/80MHz)
5. TLS 1.3 Mutual Authentication (`TLS_CHACHA20_POLY1305_SHA256`)
6. File Transfer with progress (simulated throughput)
7. Session Cleanup

---

### 5. Handoff Simulator (`handoff_simulator.py`)

Simulates the Handoff (NSUserActivity) protocol offline.
Inherits from `ProtocolSimulator`, registered as `"handoff"` in `PROTOCOL_REGISTRY`.

```bash
python handoff_simulator.py   # Run directly for demo output
```

**Two transfer paths simulated:**

| Payload Size | Path | Protocol |
|---|---|---|
| < 4 KB | BLE advertisement | Direct BLE |
| ≥ 4 KB | Continuation Stream | AWDL + TLS 1.3 |

---

### 6. OpenDrop Integration (`opendrop_wrapper.py`)

Wraps the open-source [OpenDrop](https://github.com/seemoo-lab/opendrop) CLI for
**real over-the-air AirDrop testing** using actual Apple devices.

```bash
# Via netqual CLI (recommended)
python netqual.py opendrop preflight
python netqual.py opendrop discover --timeout 15
python netqual.py opendrop send --file photo.heic --target "iPhone"
python netqual.py opendrop receive --output /tmp/drops --timeout 60
python netqual.py opendrop discover --parse   # also runs session log through log_parser

# Or directly
python opendrop_wrapper.py
```

**Two AirDrop testing layers — test pyramid coverage:**

| Layer | Tool | CI/CD | Real Devices | What It Validates |
|-------|------|-------|--------------|-------------------|
| Protocol logic | `airdrop_simulator.py` | Yes | No | BLE format, contact hashing, mDNS packets, session flow |
| Real over-the-air | `opendrop_wrapper.py` | No | Yes (AWDL) | BLE advertising, AWDL negotiation, TLS with Apple certs |

**Prerequisites:**
- macOS with Wi-Fi enabled (AWDL on `awdl0`)
- `pip install opendrop`
- Target device AirDrop set to **"Everyone"**
- Run `python netqual.py opendrop preflight` to verify readiness

---

## Tests

```bash
# Run all 60 tests
pytest -v

# Run without real hardware (mocked tests only)
pytest -v -k "not Real"

# With Allure reporting
pytest --alluredir=allure-results
allure serve allure-results
```

**Test Coverage:**

| File | Tests | What It Validates | Needs Hardware? |
|------|-------|--------------------|-----------------|
| `test_log_parser.py` | 17 | Parsing, filtering, categorization, 6 pattern detections | No |
| `test_pcap_parser.py` | 12 | TLS, DNS, mDNS, retransmission analysis (mocked tshark) | No |
| `test_opendrop.py` | 31 | Preflight, log format, data models, mocked discover/send/receive, real hardware tests | Tier 2 only |
| **Total** | **60** | | |

`test_opendrop.py` is split into two tiers:
- **Tier 1 (31 tests, always run):** Preflight structure, `OpenDropLog` format, data models, error handling, subprocess-mocked discover/send/receive
- **Tier 2 (5 tests, hardware-gated):** Use `@requires_opendrop` — auto-skip when OpenDrop is not installed or `awdl0` is unavailable

---

## Configuration (`netqual_config.yaml`)

Single YAML file drives everything — edit thresholds, patterns, and device inventory
without touching code:

```yaml
opendrop:
  discovery:
    timeout_sec: 15
    min_expected_devices: 1
  send:
    timeout_sec: 30
    min_throughput_mbps: 5
  receive:
    output_dir: /tmp/airdrop_received

protocols:
  airdrop:
    enabled: true
    mdns_service: "_airdrop._tcp.local"

test_suites:
  ci:
    tests: [test_log_parser.py, test_pcap_parser.py, test_opendrop.py]
  nightly:
    mode: device
    capture_packets: true
```

---

## How This Maps to the Role

| Job Requirement | NetQual Feature |
|----------------|-----------------|
| "Build tools and test frameworks" | CLI + plugin architecture + 60 tests |
| "Manual/automation testing" | Log parser (manual triage automated) + pcap analysis |
| "Test boundaries and edge cases" | 10 log patterns + 5 pcap patterns detected automatically |
| "Python, Swift, or similar" | 100% Python, stdlib + tshark + OpenDrop |
| "UI and lower level testing" | Text logs (app level) + pcap (packet level) + real AirDrop |
| "Invent new ways to test" | Protocol simulation + OpenDrop integration + log-parser pipeline |

---

## Prerequisites

- Python 3.10+
- tshark *(optional, for pcap analysis)*: `brew install wireshark`
- OpenDrop *(optional, for real AirDrop)*: `pip install opendrop`
- Allure *(optional, for reports)*: `brew install allure`
