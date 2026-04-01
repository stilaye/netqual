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
├── netqual/                              # NetQual CLI framework (60 tests)
│   ├── netqual.py                        # CLI entry point (6 subcommands)
│   ├── protocol_base.py                  # Plugin architecture: ABC, registry, helpers
│   ├── log_parser.py                     # 4-level sysdiagnose log analysis
│   ├── pcap_parser.py                    # tshark packet capture analyzer
│   ├── airdrop_simulator.py              # AirDrop + NameDrop protocol simulator
│   ├── handoff_simulator.py              # Handoff (NSUserActivity) simulator
│   ├── opendrop_wrapper.py               # AirDrop protocol wrapper (OpenDrop reference)
│   ├── netqual_config.yaml               # Central config (thresholds, devices, patterns)
│   ├── test_log_parser.py                # 17 tests
│   ├── test_pcap_parser.py               # 12 tests
│   ├── test_opendrop.py                  # 31 tests (CLI wrapper + data models)
│   ├── CLI_CHEAT_SHEET.md                # Quick reference for all CLI commands
│   ├── sample_logs/                      # Simulated sysdiagnose-style logs
│   ├── sample_captures/                  # Pcap generation instructions
│   └── sample_files/                     # Test files for AirDrop send tests
│
├── postman/                              # Postman collection (15 API tests)
│   └── Apple_Applied_Networking_QE.postman_collection.json
│
├── swift_tests/                          # XCTest suite (~20 Swift tests)
│   └── SharingFeatureTests.swift
│
├── logs/                                 # Real device sysdiagnose captures
│   └── sysdiagnose_2026.03.31_*/         # Live AirDrop session (iPhone)
│
└── python_tests/                         # Enterprise pytest framework (118 tests)
    ├── conftest.py                       # 20 shared fixtures and hooks
    ├── pytest.ini                        # Markers, strict mode, log config
    ├── requirements.txt                  # Runtime dependencies
    ├── device_config.yaml                # DUT, reference & auxiliary device inventory
    ├── ruff.toml                         # Linter configuration
    ├── .pre-commit-config.yaml           # black + ruff + pre-commit hooks
    ├── tests/
    │   ├── test_network_protocols.py     # TLS, DNS, HTTP/2, identity hashing (29 tests)
    │   ├── test_bonjour_discovery.py     # mDNS, BLE payloads, NameDrop (16 tests)
    │   ├── test_opendrop.py              # OpenDrop protocol format (11 tests)
    │   ├── test_network_conditioning.py  # comcast + NLC profiles (17 tests)
    │   ├── test_sysdiagnose_analysis.py  # Real AirDrop sysdiagnose validation (17 tests)
    │   ├── example_enterprise_test.py    # Framework reference patterns (19 tests)
    │   └── verify_test_dependencies.py  # Dependency health check
    ├── utils/
    │   ├── network_helpers.py            # ConnectionHelper, SSLValidator, retry logic
    │   ├── test_data_factory.py          # Contact and endpoint data generation
    │   ├── mdns_helpers.py               # mDNS packet builder and constants
    │   ├── opendrop_helpers.py           # OpenDrop plist, BLE, hash helpers
    │   ├── network_conditioner.py        # ComcastConditioner + NLCConditioner
    │   └── sysdiagnose_parser.py         # AWDL + BLE status parser
    └── docs/
        ├── ENTERPRISE_FRAMEWORK_GUIDE.md
        ├── SYSDIAGNOSE_ANALYSIS_GUIDE.md
        ├── OPENDROP_TECHNOLOGY_ASSESSMENT.md
        ├── TECH_DEBT.md
        ├── FILE_INDEX.md
        └── FIX_GUIDE.md
```

---

## Quick Start

### NetQual CLI

```bash
cd netqual
pip install -r requirements.txt

python netqual.py log sample_logs/network_diag.log   # Analyse a log
python netqual.py simulate --scenario transfer        # AirDrop simulation
python netqual.py pcap capture.pcap                   # Analyse packet capture
python netqual.py test                                # Run all 60 tests
python netqual.py all                                 # Run everything
```

See [`netqual/CLI_CHEAT_SHEET.md`](netqual/CLI_CHEAT_SHEET.md) for the full reference.

### Enterprise pytest framework

```bash
cd python_tests
source apple_qe_env/bin/activate
pip install -r requirements.txt

pytest -v                                              # All 118 tests
pytest -m "not network and not requires_sudo" -v       # 86 offline tests
pytest tests/test_sysdiagnose_analysis.py -v           # Real device validation
pytest -m security                                     # Security-focused tests
pytest --offline                                       # Skip all network tests
pytest --no-sudo                                       # Skip all sudo tests
```

---

## Test Summary

| Suite | Tests | Runs Offline? | Coverage |
|-------|-------|---------------|----------|
| `netqual/test_log_parser.py` | 17 | ✅ Yes | Log parsing, pattern detection |
| `netqual/test_pcap_parser.py` | 12 | ✅ Yes | TLS, DNS, mDNS, retransmissions |
| `netqual/test_opendrop.py` | 31 | Tier 1 ✅ | CLI wrapper, data models, mocked I/O |
| `test_network_protocols.py` | 29 | Partial ✅ | TLS 1.3, ATS, DNS, TCP/UDP, HTTP/2 |
| `test_bonjour_discovery.py` | 16 | ✅ Yes | mDNS packets, BLE payloads, NameDrop |
| `test_opendrop.py` | 11 | ✅ Yes | /Discover plist, BLE advertisement |
| `test_network_conditioning.py` | 17 | Partial ✅ | 3G/4G/5G profiles, NLC plist |
| `test_sysdiagnose_analysis.py` | 17 | ✅ Yes | Real AirDrop device capture |
| `example_enterprise_test.py` | 19 | Partial | Framework usage patterns |
| `postman/` | 15 | 🌐 Network | Apple service health, TLS, HTTP/2 |
| `swift_tests/` | ~20 | Needs Xcode | Handoff, SharePlay, URLSession |
| **Total** | **~204** | | |

---

## Test Coverage by Feature

| Test Area | AirDrop | Handoff | SharePlay | Clipboard | NameDrop |
|-----------|:-------:|:-------:|:---------:|:---------:|:--------:|
| TLS 1.3 validation | ✅ | ✅ | ✅ | ✅ | ✅ |
| mDNS / Bonjour | ✅ | ✅ | | | |
| BLE advertisements | ✅ | ✅ | | | ✅ |
| HTTP/2 | | ✅ | ✅ | ✅ | |
| Identity hashing | ✅ | | | | ✅ |
| Socket behaviour | ✅ | | ✅ | ✅ | ✅ |
| DNS resolution | ✅ | ✅ | ✅ | ✅ | ✅ |
| Protocol simulation | ✅ | ✅ | | | ✅ |
| Real sysdiagnose | ✅ | | | | |
| Network conditioning | ✅ | ✅ | | | |
| Packet capture | ✅ | ✅ | ✅ | | |
| NSUserActivity (Swift) | | ✅ | ✅ | ✅ | |

---

## pytest Markers

```bash
pytest -m network          # Requires live network
pytest -m security         # SSL/TLS and privacy tests
pytest -m protocol         # Low-level socket and mDNS tests
pytest -m performance      # Timing and benchmark tests
pytest -m requires_sudo    # Needs sudo (comcast/pfctl conditioning)
pytest -m "not network"    # Everything offline
pytest -m "not network and not requires_sudo"  # Safe for CI
```

---

## Key Dependencies

```
pytest >= 7.4          httpx[http2]       cryptography
pytest-cov             requests           pyOpenSSL
pytest-xdist           faker              pyyaml
pytest-asyncio         hypothesis         certifi
black >= 24.0          ruff >= 0.4        pre-commit
```

---

## Documentation

| Document | Location | Purpose |
|----------|----------|---------|
| Framework Guide | [`python_tests/docs/ENTERPRISE_FRAMEWORK_GUIDE.md`](python_tests/docs/ENTERPRISE_FRAMEWORK_GUIDE.md) | Full framework reference |
| Quick Start | [`python_tests/QUICK_START.md`](python_tests/QUICK_START.md) | Commands and usage |
| Sysdiagnose Guide | [`python_tests/docs/SYSDIAGNOSE_ANALYSIS_GUIDE.md`](python_tests/docs/SYSDIAGNOSE_ANALYSIS_GUIDE.md) | AirDrop log analysis from real capture |
| OpenDrop Assessment | [`python_tests/docs/OPENDROP_TECHNOLOGY_ASSESSMENT.md`](python_tests/docs/OPENDROP_TECHNOLOGY_ASSESSMENT.md) | Technology decision + modern alternatives |
| Tech Debt | [`python_tests/docs/TECH_DEBT.md`](python_tests/docs/TECH_DEBT.md) | All 12 items resolved |
| CLI Cheat Sheet | [`netqual/CLI_CHEAT_SHEET.md`](netqual/CLI_CHEAT_SHEET.md) | NetQual CLI commands |

---

**Note:** All tests use publicly documented Apple protocols and APIs.
No proprietary or confidential information is included.
