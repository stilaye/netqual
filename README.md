# Apple Applied Networking — QE Test Portfolio

**Author: Swapnil Tilaye**
**Role: Software Quality Engineer — Applied Networking**

An enterprise-grade test portfolio covering the protocols behind Apple's Continuity
and Sharing features — AirDrop, Handoff, SharePlay, Universal Clipboard, NameDrop.

---

## Repository Structure

```
netqual/  (repo root)
│
├── netqual/                           # NetQual CLI framework (60 tests)
│   ├── netqual.py                     # CLI entry point (6 subcommands)
│   ├── protocol_base.py               # Plugin architecture: ABC, registry, helpers
│   ├── log_parser.py                  # 4-level sysdiagnose log analysis
│   ├── pcap_parser.py                 # tshark packet capture analyzer
│   ├── airdrop_simulator.py           # AirDrop + NameDrop protocol simulator
│   ├── handoff_simulator.py           # Handoff (NSUserActivity) simulator
│   ├── opendrop_wrapper.py            # Real AirDrop via OpenDrop CLI
│   ├── netqual_config.yaml            # Central config (thresholds, devices, patterns)
│   ├── test_log_parser.py             # 17 tests
│   ├── test_pcap_parser.py            # 12 tests
│   ├── test_opendrop.py               # 31 tests (Tier 1 mocked + Tier 2 hardware)
│   ├── CLI_CHEAT_SHEET.md             # Quick reference for all CLI commands
│   ├── sample_logs/                   # Simulated sysdiagnose-style logs
│   ├── sample_captures/               # pcap generation instructions
│   └── sample_files/                  # Test files for AirDrop send tests
│
├── postman/                           # Postman collection (15 API tests)
│   └── Apple_Applied_Networking_QE.postman_collection.json
│
├── swift_tests/                       # XCTest suite (~20 Swift tests)
│   └── SharingFeatureTests.swift
│
└── python_tests/                      # Enterprise pytest framework
    ├── conftest.py                    # Shared fixtures and hooks
    ├── pytest.ini                     # Markers and configuration
    ├── requirements.txt               # Runtime dependencies
    ├── requirements-dev.txt           # Dev/CI dependencies
    ├── tests/
    │   ├── test_network_protocols.py  # TLS, DNS, HTTP/2, identity hashing (40 tests)
    │   ├── test_bonjour_discovery.py  # mDNS, BLE payloads, NameDrop (15 tests)
    │   ├── example_enterprise_test.py # Framework reference patterns (19 tests)
    │   └── verify_test_dependencies.py
    └── utils/
        ├── network_helpers.py         # ConnectionHelper, SSLValidator, retry logic
        └── test_data_factory.py       # Contact and endpoint data generation
```

---

## Quick Start

### NetQual CLI (primary framework)

```bash
cd netqual
pip install -r requirements.txt

# Parse a network diagnostic log
python netqual.py log sample_logs/network_diag.log

# Run AirDrop simulation
python netqual.py simulate --scenario transfer

# Analyze a packet capture
python netqual.py pcap capture.pcap

# Real AirDrop (requires macOS + pip install opendrop)
python netqual.py opendrop preflight
python netqual.py opendrop discover
python netqual.py opendrop send --file photo.heic --target "iPhone"

# Run all 60 tests
python netqual.py test

# Run everything in one shot
python netqual.py all
```

See [`netqual/CLI_CHEAT_SHEET.md`](netqual/CLI_CHEAT_SHEET.md) for the full command reference.

### Enterprise pytest framework

```bash
cd python_tests
source apple_qe_env/bin/activate
pip install -r requirements.txt

pytest -v                    # Run all tests
pytest -v -m "not network"  # Offline only
pytest -m security
pytest -m protocol
pytest -m performance
```

---

## Test Summary

| Suite | Tests | Coverage | Runs Offline? |
|-------|-------|----------|---------------|
| `netqual/test_log_parser.py` | 17 | Log parsing, pattern detection, filtering | ✅ Yes |
| `netqual/test_pcap_parser.py` | 12 | TLS, DNS, mDNS, retransmissions (mocked tshark) | ✅ Yes |
| `netqual/test_opendrop.py` | 31 | Preflight, data models, mocked I/O, real hardware | Tier 1 ✅ |
| `python_tests/test_network_protocols.py` | 40 | TLS 1.3, ATS, DNS, TCP/UDP, HTTP/2, identity hashing | 28 ✅ / 12 🌐 |
| `python_tests/test_bonjour_discovery.py` | 15 | mDNS packets, AirDrop/AirPlay discovery, BLE, NameDrop | ✅ Yes |
| `python_tests/example_enterprise_test.py` | 19 | Framework patterns and integration | Partial |
| `postman/` | 15 | Apple service health, TLS validation, HTTP/2 | 🌐 Needs network |
| `swift_tests/` | ~20 | Handoff NSUserActivity, SharePlay, URLSession | Needs Xcode |
| **Total** | **~169** | | |

---

## Test Coverage by Feature

| Test Area | AirDrop | Handoff | SharePlay | Clipboard | NameDrop |
|-----------|:-------:|:-------:|:---------:|:---------:|:--------:|
| TLS 1.3 validation | ✅ | ✅ | ✅ | ✅ | ✅ |
| mDNS / Bonjour | ✅ | ✅ | | | |
| BLE advertisements | ✅ | ✅ | | | ✅ |
| HTTP/2 | | ✅ | ✅ | ✅ | |
| Identity hashing | ✅ | | | | ✅ |
| Socket behavior | ✅ | | ✅ | ✅ | ✅ |
| DNS resolution | ✅ | ✅ | ✅ | ✅ | ✅ |
| Protocol simulation | ✅ | ✅ | | | ✅ |
| Real over-the-air | ✅ | | | | |
| Packet capture | ✅ | ✅ | ✅ | | |
| NSUserActivity (Swift) | | ✅ | ✅ | ✅ | |

---

## Markers (pytest framework)

```bash
pytest -m network      # Requires live network connectivity
pytest -m security     # SSL/TLS and privacy tests
pytest -m protocol     # Low-level socket and mDNS tests
pytest -m performance  # Timing and benchmark tests
pytest -m integration  # Multi-component tests
pytest -m smoke        # Critical path smoke tests
pytest -m "not network"  # Run everything offline
```

---

## Key Dependencies

```
pytest >= 7.4         httpx[http2]      cryptography
pytest-cov            requests          pyOpenSSL
pytest-html           faker             certifi
pytest-asyncio        hypothesis        pyyaml
```

---

## Documentation

- [`netqual/README.md`](netqual/README.md) — NetQual module documentation and architecture
- [`netqual/CLI_CHEAT_SHEET.md`](netqual/CLI_CHEAT_SHEET.md) — All CLI commands at a glance
- [`python_tests/QUICK_START.md`](python_tests/QUICK_START.md) — pytest framework quick reference
- [`python_tests/docs/ENTERPRISE_FRAMEWORK_GUIDE.md`](python_tests/docs/ENTERPRISE_FRAMEWORK_GUIDE.md) — Complete framework guide

---

**Note:** All tests use publicly documented Apple protocols and APIs.
No proprietary or confidential information is included.
