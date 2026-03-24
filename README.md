# Apple Applied Networking — QE Test Portfolio

**Author: Swapnil Tilaye**
**Role: Software Quality Engineer — Applied Networking**

An enterprise-grade test portfolio covering the protocols behind Apple's Continuity
and Sharing features — AirDrop, Handoff, SharePlay, Universal Clipboard, NameDrop.

---

## Repository Structure

```
apple_qe_portfolio/
│
├── apple_qe_portfolio_final/          # Primary submission package
│   ├── code/
│   │   ├── netqual/                   # NetQual CLI + simulators + 60 tests
│   │   ├── postman/                   # Postman collection (15 API tests)
│   │   └── swift_tests/               # XCTest suite (~20 Swift tests)
│   └── docs/coding_prep/              # Interview prep materials
│
└── python_tests/                      # Enterprise pytest framework
    ├── conftest.py                    # Shared fixtures and hooks
    ├── pytest.ini                     # Markers and configuration
    ├── requirements.txt
    ├── tests/
    │   ├── test_network_protocols.py  # TLS, DNS, HTTP/2, identity hashing (40 tests)
    │   ├── test_bonjour_discovery.py  # mDNS, BLE payloads, NameDrop (15 tests)
    │   ├── test_network_protocols_fixed.py
    │   ├── example_enterprise_test.py # Framework reference patterns (19 tests)
    │   └── verify_test_dependencies.py
    └── utils/
        ├── network_helpers.py         # ConnectionHelper, SSLValidator, performance monitor
        └── test_data_factory.py       # Contact and endpoint data generation
```

---

## Quick Start

### NetQual CLI (primary framework)

```bash
cd apple_qe_portfolio_final/code/netqual
pip install -r requirements.txt

# Run all 60 tests (no hardware required)
pytest -v

# AirDrop simulation
python netqual.py simulate --scenario transfer

# Log analysis
python netqual.py log sample_logs/network_diag.log

# Packet capture analysis
python netqual.py pcap capture.pcap

# Real AirDrop (requires macOS + pip install opendrop)
python netqual.py opendrop preflight
python netqual.py opendrop discover
python netqual.py opendrop send --file photo.heic --target "iPhone"
```

### Enterprise pytest framework

```bash
cd python_tests
source apple_qe_env/bin/activate
pip install -r requirements.txt

# Run all tests
pytest -v

# Offline only (no network required)
pytest -v -m "not network"

# By category
pytest -m security
pytest -m protocol
pytest -m performance
```

---

## Test Summary

| Suite | Tests | Coverage | Runs Offline? |
|-------|-------|----------|---------------|
| `netqual/test_log_parser.py` | 17 | Log parsing, pattern detection, filtering | Yes |
| `netqual/test_pcap_parser.py` | 12 | TLS, DNS, mDNS, retransmissions (mocked tshark) | Yes |
| `netqual/test_opendrop.py` | 31 | Preflight, data models, mocked I/O, real hardware | Tier 1 yes |
| `python_tests/test_network_protocols.py` | 40 | TLS 1.3, ATS, DNS, TCP/UDP, HTTP/2, identity hashing | 28 yes / 12 need network |
| `python_tests/test_bonjour_discovery.py` | 15 | mDNS packets, AirDrop/AirPlay discovery, BLE, NameDrop | Yes |
| `python_tests/example_enterprise_test.py` | 19 | Framework patterns and integration | Partial |
| `postman/` | 15 | Apple service health, TLS validation, HTTP/2 | Needs network |
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

See `python_tests/requirements.txt` for the full list.

---

## Documentation

- [`apple_qe_portfolio_final/README.md`](apple_qe_portfolio_final/README.md) — Final package overview and CLI reference
- [`apple_qe_portfolio_final/code/netqual/README.md`](apple_qe_portfolio_final/code/netqual/README.md) — NetQual module documentation
- [`python_tests/QUICK_START.md`](python_tests/QUICK_START.md) — pytest framework quick reference
- [`python_tests/docs/ENTERPRISE_FRAMEWORK_GUIDE.md`](python_tests/docs/ENTERPRISE_FRAMEWORK_GUIDE.md) — Complete framework guide

---

**Note:** All tests use publicly documented Apple protocols and APIs.
No proprietary or confidential information is included.
