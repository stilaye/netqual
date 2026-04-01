# Apple Applied Networking — Enterprise pytest Framework

**Author: Swapnil Tilaye**
**Role: Software Quality Engineer — Applied Networking**

---

## What This Demonstrates

An enterprise-level pytest framework validating the protocols behind Apple's
Continuity and Sharing features (AirDrop, AirPlay, Bonjour, NameDrop, Handoff)
— including real sysdiagnose analysis from a live AirDrop session on an iPhone.

---

## Quick Start

```bash
# Setup
source apple_qe_env/bin/activate
pip install -r requirements.txt

# Run offline tests (CI-safe — no network or sudo needed)
pytest -m "not network and not requires_sudo" -v

# Run the real sysdiagnose analysis (validates a live AirDrop capture)
pytest tests/test_sysdiagnose_analysis.py -v

# Run all tests
pytest -v

# Lint and format
ruff check .
black --check --line-length=100 .
```

---

## Test Summary

**118 tests across 6 test files**

| Test File | Tests | Sudo | Coverage |
|-----------|-------|------|----------|
| `test_network_protocols.py` | 29 | No | TLS 1.3, ATS, DNS, TCP/UDP, HTTP/2, identity hashing, performance |
| `test_bonjour_discovery.py` | 16 | No | mDNS packets, AirDrop/AirPlay/NameDrop/Handoff service discovery |
| `test_opendrop.py` | 11 | No | OpenDrop `/Discover` plist, mDNS service record, BLE advertisement |
| `test_network_conditioning.py` | 17 | Partial | 3G/4G/5G comcast profiles + NLC plist validation |
| `test_sysdiagnose_analysis.py` | 17 | No | Real iPhone AirDrop capture — AWDL, BLE, session evidence |
| `example_enterprise_test.py` | 19 | No | Framework usage patterns and integration examples |
| Postman Collection | 15 | No | Apple service health, TLS, HTTP/2 endpoints |

**Results (offline mode):**
- ✅ **86 tests passing** with `pytest -m "not network and not requires_sudo"`
- ✅ **17/17** sysdiagnose tests pass against real iPhone capture
- ⏭️ Network and sudo tests deselected in offline mode

---

## Project Structure

```
python_tests/
├── conftest.py                       # 20 shared fixtures and hooks
├── pytest.ini                        # Markers, strict mode, log config
├── requirements.txt                  # All dependencies
├── device_config.yaml                # DUT, reference & auxiliary device inventory
├── ruff.toml                         # Linter rules (E/W/F/I/UP/B/C4/SIM/PT)
├── .pre-commit-config.yaml           # black + ruff + whitespace/yaml checks
│
├── tests/
│   ├── test_network_protocols.py     # TLS, DNS, HTTP/2, sockets, identity hashing
│   ├── test_bonjour_discovery.py     # mDNS/Bonjour, BLE, NameDrop, Handoff
│   ├── test_opendrop.py              # OpenDrop protocol format tests
│   ├── test_network_conditioning.py  # comcast + NLC network conditioning
│   ├── test_sysdiagnose_analysis.py  # Real AirDrop sysdiagnose validation
│   ├── example_enterprise_test.py    # Framework reference patterns
│   └── verify_test_dependencies.py  # Dependency health check
│
├── utils/
│   ├── network_helpers.py            # ConnectionHelper, SSLValidator, retry logic
│   ├── test_data_factory.py          # ContactFactory, NetworkDataFactory, HashDataFactory
│   ├── mdns_helpers.py               # MDNSHelper, packet builder, RFC 6762 constants
│   ├── opendrop_helpers.py           # OpenDrop plist, BLE advertisement, contact hash
│   ├── network_conditioner.py        # ComcastConditioner, NLCConditioner, PROFILES
│   └── sysdiagnose_parser.py         # AWDLStatusParser, BluetoothStatusParser
│
├── docs/
│   ├── ENTERPRISE_FRAMEWORK_GUIDE.md
│   ├── SYSDIAGNOSE_ANALYSIS_GUIDE.md     # ← AirDrop real capture learnings
│   ├── OPENDROP_TECHNOLOGY_ASSESSMENT.md # ← OpenDrop status + modern alternatives
│   ├── TECH_DEBT.md                      # 12 items, all resolved
│   ├── FILE_INDEX.md
│   └── FIX_GUIDE.md
│
└── reports/
    └── pytest.log
```

---

## Supported Protocol Features

| Feature | Protocol / Stack | Test File(s) |
|---------|-----------------|--------------|
| **AirDrop** | TLS 1.3, mDNS `_airdrop._tcp.local`, BLE SHA-256 hash, AWDL | `test_network_protocols.py`, `test_bonjour_discovery.py`, `test_sysdiagnose_analysis.py` |
| **OpenDrop** | `/Discover` plist handshake, mDNS, BLE advertisement (port 8770) | `test_opendrop.py` |
| **AirPlay** | mDNS `_airplay._tcp.local` service discovery | `test_bonjour_discovery.py` |
| **Bonjour/mDNS** | DNS-SD, multicast UDP (224.0.0.251:5353), packet build/parse | `test_bonjour_discovery.py`, `test_network_protocols.py` |
| **NameDrop** | BLE proximity payload (action byte 0x14), contact hash truncation | `test_bonjour_discovery.py`, `test_network_protocols.py` |
| **Handoff** | Companion Link mDNS `_companion-link._tcp.local` | `test_bonjour_discovery.py` |
| **BLE Advertisements** | Payload structure, Apple Company ID (0x004C), 31-byte limit | `test_bonjour_discovery.py`, `test_opendrop.py` |
| **Identity & Privacy** | SHA-256 contact hashing, PII protection, collision rate, BLE truncation | `test_network_protocols.py` |
| **TLS/SSL** | TLS 1.3, downgrade rejection, cipher strength (≥128-bit), cert chains | `test_network_protocols.py` |
| **HTTP/2** | Protocol negotiation, HSTS enforcement, HTTPS redirect, connection pooling | `test_network_protocols.py` |
| **TCP/UDP Sockets** | Keep-alive, timeout, bind, SO_REUSEADDR, non-blocking | `test_network_protocols.py` |
| **DNS** | Resolution correctness, latency benchmarks (<500ms) | `test_network_protocols.py` |
| **Network Conditioning** | 3G/4G/5G comcast profiles, NLC plist structure | `test_network_conditioning.py` |
| **Sysdiagnose** | AWDL state, BLE state, real AirDrop session evidence | `test_sysdiagnose_analysis.py` |
| **Performance** | TLS handshake (<1s), DNS (<500ms), connection latency (<2s) | `test_network_protocols.py` |

---

## Framework Features

### Fixtures (conftest.py — 20 total)

| Fixture | Scope | Description |
|---------|-------|-------------|
| `ssl_context` | function | Secure SSLContext (TLS 1.2+, cert verification) |
| `tcp_socket` | function | TCP socket with auto-cleanup |
| `udp_socket` | function | UDP socket with auto-cleanup |
| `http_client` | function | `httpx.Client` with timeout and redirects |
| `logger` | session | Configured `logging.Logger` |
| `test_config` | session | Env-specific config dict (urls, timeouts, retries) |
| `test_environment` | session | Returns `--env` value (`test`/`staging`/`production`) |
| `device_config` | session | DUT, reference, auxiliary device inventory from `device_config.yaml` |
| `sysdiagnose_path` | session | Path to sysdiagnose bundle (`SYSDIAGNOSE_PATH` env var) |
| `measure_time` | function | Context manager for timing code blocks |
| `comcast_conditioner` | function | Apply/restore 3G/4G/5G network profiles *(requires sudo)* |
| `nlc_conditioner` | function | NLC profile builder and plist validator |
| `skip_if_no_network` | function | Skips test if DNS/network is unavailable |
| `mock_network_unavailable` | function | Monkeypatches socket to simulate no network |
| `apple_test_domains` | function | List of Apple domains for network tests |
| `sample_email_addresses` | function | Sample emails for hashing/contact tests |
| `temp_test_directory` | function | Temporary directory (auto-cleaned) |
| `require_ssl_support` | function | Skips test if SSL/TLS support is insufficient |
| `test_result_tracker` | function | Automatic pass/fail tracking |
| `session_cleanup` | session | Final cleanup hook |

### Utilities (utils/)

| Module | Key Classes | Purpose |
|--------|------------|---------|
| `network_helpers.py` | `ConnectionHelper`, `SSLValidator`, `NetworkPerformanceMonitor` | Retry logic, cert validation, perf tracking |
| `test_data_factory.py` | `ContactFactory`, `NetworkDataFactory`, `HashDataFactory` | Realistic test data generation |
| `mdns_helpers.py` | `MDNSHelper` | RFC 6762 mDNS packet construction |
| `opendrop_helpers.py` | `build_discover_request`, `build_ble_advertisement` | OpenDrop protocol helpers |
| `network_conditioner.py` | `ComcastConditioner`, `NLCConditioner`, `PROFILES` | Network conditioning for 3G/4G/5G |
| `sysdiagnose_parser.py` | `SysdiagnoseParser`, `AWDLStatusParser`, `BluetoothStatusParser` | Real device log analysis |

### CLI Options

| Option | Default | Env Var | Description |
|--------|---------|---------|-------------|
| `--offline` | false | `TEST_OFFLINE` | Skip all `@pytest.mark.network` tests |
| `--no-sudo` | false | `TEST_NO_SUDO` | Skip all `@pytest.mark.requires_sudo` tests |
| `--env` | test | `TEST_ENV` | Target environment: `test`, `staging`, `production` |
| `--test-log-level` | INFO | `TEST_LOG_LEVEL` | Log verbosity for test output |
| `--generate-report` | false | — | Generate HTML/JSON report |

### Custom Markers

| Marker | Purpose |
|--------|---------|
| `network` | Requires live network connectivity |
| `security` | SSL/TLS and security-focused tests |
| `protocol` | Low-level protocol tests (mDNS, BLE, sockets) |
| `performance` | Benchmark and timing tests |
| `slow` | Tests that take > 1 second |
| `integration` | Multi-component integration tests |
| `smoke` | Critical path / smoke tests |
| `regression` | Bug regression tests |
| `requires_sudo` | Needs sudo (comcast/pfctl network conditioning) |

---

## Running Tests

```bash
# CI-safe (no network, no sudo)
pytest -m "not network and not requires_sudo" -v

# Real sysdiagnose validation
pytest tests/test_sysdiagnose_analysis.py -v

# Point at a different sysdiagnose bundle
SYSDIAGNOSE_PATH=/path/to/bundle pytest tests/test_sysdiagnose_analysis.py -v

# Protocol tests only
pytest tests/test_bonjour_discovery.py tests/test_opendrop.py -v

# Network conditioning (offline profile validation)
pytest tests/test_network_conditioning.py -m "not requires_sudo" -v

# Live network conditioning (requires brew install comcast + sudo)
pytest tests/test_network_conditioning.py -v

# Parallel execution
pytest -n auto

# With coverage
pytest --cov=. --cov-report=html --cov-report=term

# Full run against staging
pytest --env=staging -v
```

---

## Linting & Formatting

```bash
# Format
black --line-length=100 .

# Lint
ruff check .
ruff check . --fix        # auto-fix safe issues

# Pre-commit (runs automatically on git commit after setup)
pre-commit install        # one-time setup
pre-commit run --all-files
```

---

## Device Configuration

Edit `device_config.yaml` to define your test rack:

```yaml
dut:
  - id: "dut-iphone-01"
    name: "iPhone 16 Pro (DUT)"
    os_version: "18.4"
    ip_address: "192.168.1.100"
    enabled: true

reference:
  - id: "ref-mac-01"
    name: "MacBook Pro M3 (Reference)"
    ip_address: "192.168.1.200"
    enabled: true
```

Access in tests via the `device_config` fixture:

```python
def test_airdrop_pair(device_config):
    dut = device_config["dut"][0]
    ref = device_config["reference"][0]
    # dut["name"] → "iPhone 16 Pro (DUT)"
```

Override path: `DEVICE_CONFIG_FILE=/path/to/lab.yaml pytest ...`

---

## Sysdiagnose Analysis

Validates real device behaviour from an iPhone AirDrop sysdiagnose:

```bash
# Uses bundled capture automatically
pytest tests/test_sysdiagnose_analysis.py -v

# Use your own capture
SYSDIAGNOSE_PATH=/path/to/sysdiagnose_root pytest tests/test_sysdiagnose_analysis.py -v
```

```python
from utils.sysdiagnose_parser import SysdiagnoseParser

parser = SysdiagnoseParser("path/to/sysdiagnose/")
awdl = parser.awdl()
print(awdl.data_duration_ms)    # 5194 — real transfer occurred
print(awdl.discoverable_mode)   # "Contacts Only"

ble = parser.bluetooth()
print(ble.power)                # "On"
```

See [`docs/SYSDIAGNOSE_ANALYSIS_GUIDE.md`](docs/SYSDIAGNOSE_ANALYSIS_GUIDE.md) for full guide.

---

## Documentation

| Document | Purpose |
|----------|---------|
| [`docs/ENTERPRISE_FRAMEWORK_GUIDE.md`](docs/ENTERPRISE_FRAMEWORK_GUIDE.md) | Full framework architecture guide |
| [`docs/SYSDIAGNOSE_ANALYSIS_GUIDE.md`](docs/SYSDIAGNOSE_ANALYSIS_GUIDE.md) | AirDrop sysdiagnose learnings from real capture |
| [`docs/OPENDROP_TECHNOLOGY_ASSESSMENT.md`](docs/OPENDROP_TECHNOLOGY_ASSESSMENT.md) | OpenDrop status + pymobiledevice3/XCTest roadmap |
| [`docs/TECH_DEBT.md`](docs/TECH_DEBT.md) | Technical debt register (all 12 items resolved) |
| [`docs/FILE_INDEX.md`](docs/FILE_INDEX.md) | Complete file descriptions and stats |
| [`QUICK_START.md`](QUICK_START.md) | Commands quick reference |

---

## Dependencies

```
pytest>=7.4.0           httpx[http2]>=0.24.0    cryptography>=41.0.0
pytest-cov>=4.1.0       requests>=2.31.0         pyOpenSSL>=23.2.0
pytest-xdist>=3.3.0     pyyaml>=6.0              certifi>=2023.7.0
pytest-asyncio>=0.21.0  faker>=19.0.0            hypothesis>=6.82.0
black>=24.0.0           ruff>=0.4.0              pre-commit>=3.7.0
```

---

**Note:** All tests use publicly documented Apple protocols and APIs.
No proprietary or confidential information is included.
