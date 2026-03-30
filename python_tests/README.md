# Apple Applied Networking — QE Test Portfolio

**Prepared by: Swapnil**  
**Role: Software Quality Engineer — Applied Networking**

## 🎯 What This Demonstrates

An enterprise-level test suite covering the protocols behind Apple's Continuity and Sharing features (AirDrop, AirPlay, OpenDrop, Handoff, NameDrop, Universal Clipboard) — including the open-source OpenDrop AirDrop implementation.

## 🚀 Quick Start

```bash
# Install dependencies
pip install -r requirements.txt

# Run all tests
pytest -v

# Run offline tests only (no network required)
pytest -v -m "not network"

# Run security-focused tests
pytest -v -m security

# Run with coverage
pytest --cov=. --cov-report=html
```

## 📊 Test Summary

**Total: 102 tests across 6 test suites**

| Test Suite | Tests | Sudo Required | Coverage |
|------------|-------|---------------|----------|
| `test_network_protocols.py` | 40 | No | TLS 1.3, ATS, DNS, TCP/UDP, HTTP/2, identity hashing, performance |
| `test_bonjour_discovery.py` | 15 | No | mDNS packets, AirDrop/AirPlay discovery, BLE payloads, NameDrop |
| `test_opendrop.py` | 11 | No | OpenDrop /Discover handshake, mDNS service record, BLE advertisement |
| `test_network_conditioning.py` | 17 | Partial | Network profile validation (offline) + live 3G/4G/5G conditioning |
| `example_enterprise_test.py` | 19 | No | Framework usage examples and integration tests |
| Postman Collection | 15 | No | Apple service health, TLS validation, HTTP/2 endpoints |

### Test Results
- ✅ **92 tests passing** (offline mode)
- ⏭️ **9 tests skipped** (4 network + 4 requires_sudo + 1 flaky)
- ⚠️ **1 flaky test** (hash collision simulation - expected behavior)

## 📁 Project Structure

```
python_tests/
├── conftest.py                 # Pytest fixtures & configuration
├── pytest.ini                  # Pytest settings
├── requirements.txt            # All dependencies
├── QUICK_START.md             # Quick reference guide
│
├── tests/                      # All test files
│   ├── test_network_protocols.py
│   ├── test_bonjour_discovery.py
│   ├── test_opendrop.py            # OpenDrop protocol tests
│   ├── test_network_conditioning.py # comcast + NLC network simulation
│   ├── test_network_protocols_fixed.py
│   ├── example_enterprise_test.py
│   └── verify_test_dependencies.py
│
├── utils/                      # Test utilities
│   ├── __init__.py
│   ├── network_helpers.py      # Connection, SSL, performance helpers
│   ├── network_conditioner.py  # ComcastConditioner + NLCConditioner
│   └── test_data_factory.py   # Test data generation
│
├── docs/                       # Documentation
│   ├── ENTERPRISE_FRAMEWORK_GUIDE.md
│   ├── FILE_INDEX.md
│   ├── CHANGES_APPLIED.md
│   └── FIX_GUIDE.md
│
└── reports/                    # Generated test reports
    ├── html/
    ├── junit/
    └── coverage/
```

## 🧪 Test Coverage by Feature

| Test Area | AirDrop | OpenDrop | AirPlay | Handoff | NameDrop |
|-----------|---------|----------|---------|---------|----------|
| TLS 1.3 validation | ✅ | ✅ | ✅ | ✅ | ✅ |
| mDNS/Bonjour | ✅ | ✅ | ✅ | ✅ | |
| BLE advertisements | ✅ | ✅ | | ✅ | ✅ |
| /Discover handshake | | ✅ | | | |
| HTTP/2 | | | ✅ | ✅ | |
| Identity hashing | ✅ | ✅ | | | ✅ |
| Socket behavior | ✅ | ✅ | | | ✅ |
| DNS resolution | ✅ | ✅ | ✅ | ✅ | ✅ |
## 📡 Supported Protocol Features

### Features with Dedicated Test Code

| Feature | Protocol/Stack | Test File(s) |
|---------|---------------|--------------|
| **AirDrop** | TLS 1.3, mDNS (_airdrop._tcp.local), BLE payloads, identity hashing | test_network_protocols.py, test_bonjour_discovery.py |
| **OpenDrop** | /Discover plist handshake, mDNS, BLE advertisement (port 8770) | test_opendrop.py |
| **AirPlay** | mDNS (_airplay._tcp.local) service discovery | test_bonjour_discovery.py |
| **Bonjour/mDNS** | DNS-SD, multicast UDP (224.0.0.251:5353), packet build/parse | test_bonjour_discovery.py, test_network_protocols.py |
| **NameDrop** | BLE proximity payload (action byte 0x14), contact hash truncation | test_bonjour_discovery.py, test_network_protocols.py |
| **Handoff** | Companion Link mDNS discovery (_companion-link._tcp.local) | test_bonjour_discovery.py |
| **BLE Advertisements** | Payload structure, Apple Company ID (0x004C), 31-byte size limit | test_bonjour_discovery.py |
| **Identity & Privacy** | SHA-256 contact hashing, PII protection, collision rate, BLE truncation | test_network_protocols.py, test_bonjour_discovery.py |
| **TLS/SSL** | TLS 1.3 validation, TLS 1.1 downgrade rejection, cipher strength (≥128-bit), cert chains | test_network_protocols.py, test_network_protocols_fixed.py |
| **HTTP/2** | Protocol negotiation, HSTS header enforcement, HTTPS redirect | test_network_protocols.py, test_network_protocols_fixed.py |
| **DNS** | Resolution correctness, latency benchmarks (<500ms) | test_network_protocols.py |
| **TCP/UDP Sockets** | Keep-alive, timeout, bind, SO_REUSEADDR, refused-connection handling | test_network_protocols.py, test_network_protocols_fixed.py |
| **Performance** | TLS handshake (<1s), DNS (<500ms), full connection latency (<2s) | test_network_protocols.py, example_enterprise_test.py |
| **Network Conditioning (comcast)** | 3G/4G/5G profiles, TCP latency degradation, teardown/restore | test_network_conditioning.py |
| **Network Conditioning (NLC)** | Profile plist structure, key validation, write/read roundtrip | test_network_conditioning.py |

### Protocols Validated Indirectly

| Feature | What Is Tested | Not Tested |
|---------|---------------|------------|
| **ATS (App Transport Security)** | TLS 1.2+ enforcement, TLS 1.1 rejection (the requirements ATS mandates) | ATS policy enforcement directly (not testable in Python) |
| **Universal Clipboard** | Underlying DNS, TLS, HTTP/2 layers | Clipboard-specific APIs |
| **SharePlay** | Underlying TCP, TLS, HTTP/2 layers | SharePlay session/framing APIs |

> **OpenDrop** (`github.com/seemoo-lab/opendrop`) is the open-source Python implementation of AirDrop. `test_opendrop.py` directly tests its three-stage protocol: BLE advertisement format, mDNS service discovery, and the `/Discover` HTTPS plist handshake.

## 🎨 Enterprise Framework Features

This test suite includes an enterprise-level pytest framework with:

### ✅ Core Features
- **17+ reusable fixtures** (SSL contexts, sockets, HTTP clients, network conditioners)
- **Custom pytest hooks** (auto-marking, result tracking)
- **Environment-specific configuration** (test/staging/production)
- **Network utilities** (retry logic, SSL validation, performance monitoring)
- **Network conditioning** (3G/4G/5G simulation via comcast + NLC profile generation)
- **Test data factories** (contacts, endpoints, hashes)
- **Performance tracking** (timing, benchmarking)
- **Comprehensive documentation** (1000+ lines)

### 🔧 Fixtures Available
- `ssl_context` - Configured SSL/TLS context
- `tcp_socket` / `udp_socket` - Sockets with auto-cleanup
- `http_client` - HTTP client with auto-cleanup
- `logger` - Configured logger
- `test_config` - Environment-specific settings
- `measure_time` - Performance timing
- `comcast_conditioner` - System-wide 3G/4G/5G network simulation *(requires sudo)*
- `nlc_conditioner` - Network Link Conditioner profile builder/validator
- `skip_if_no_network` - Graceful skip when offline
- `mock_network_unavailable` - Simulate no-network conditions

### 🛠️ Utilities Available
- `ConnectionHelper` - Connections with retry logic
- `SSLValidator` - Certificate and cipher validation
- `NetworkPerformanceMonitor` - Performance tracking
- `ComcastConditioner` - Apply/restore network profiles via comcast CLI
- `NLCConditioner` - Build and validate NLC plist profiles
- `ContactFactory` - Generate test contacts
- `NetworkDataFactory` - Generate test endpoints

### ⚙️ CLI Options
| Option | Default | Description |
|--------|---------|-------------|
| `--offline` | false | Skip all `@pytest.mark.network` tests |
| `--no-sudo` | false | Skip all `@pytest.mark.requires_sudo` tests |
| `--env` | test | Target environment: `test`, `staging`, `production` |
| `--generate-report` | false | Generate HTML/JSON test report |

## 📖 Documentation

- **[QUICK_START.md](QUICK_START.md)** - Quick reference for common commands
- **[docs/ENTERPRISE_FRAMEWORK_GUIDE.md](docs/ENTERPRISE_FRAMEWORK_GUIDE.md)** - Complete framework guide
- **[docs/FILE_INDEX.md](docs/FILE_INDEX.md)** - Detailed file descriptions
- **[docs/CHANGES_APPLIED.md](docs/CHANGES_APPLIED.md)** - Recent changes
- **[docs/FIX_GUIDE.md](docs/FIX_GUIDE.md)** - Troubleshooting guide

## 🏃 Running Tests

### Basic Commands
```bash
# All tests
pytest

# Verbose output
pytest -v

# Specific test file
pytest tests/test_network_protocols.py

# Specific test class
pytest tests/test_network_protocols.py::TestTLSValidation

# Run by marker
pytest -m network          # Network tests only
pytest -m security         # Security tests only
pytest -m "not slow"       # Exclude slow tests
```

### Network Conditioning Commands
```bash
# Offline validation only (no sudo needed)
pytest tests/test_network_conditioning.py -m "not requires_sudo and not network"

# Full live conditioning (requires: brew install comcast + sudo)
pytest tests/test_network_conditioning.py -v

# Skip sudo tests globally
pytest -m "not requires_sudo"
```

### Advanced Commands
```bash
# Parallel execution (faster)
pytest -n auto

# With coverage report
pytest --cov=. --cov-report=html --cov-report=term

# Generate HTML report
pytest --html=reports/report.html --self-contained-html

# Offline mode (skip network tests)
pytest --offline

# Different environment
pytest --env=staging
pytest --env=production
```

## 🔍 Test Categories

Tests are organized using pytest markers:

- `@pytest.mark.network` - Requires network connectivity
- `@pytest.mark.security` - Security-focused tests
- `@pytest.mark.protocol` - Protocol-level tests
- `@pytest.mark.performance` - Performance benchmarks
- `@pytest.mark.slow` - Slow-running tests
- `@pytest.mark.integration` - Integration tests
- `@pytest.mark.requires_sudo` - Requires sudo (comcast/pfctl network conditioning)

## 📦 Dependencies

Core dependencies:
```
pytest>=7.4.0
pytest-cov>=4.1.0
httpx[http2]>=0.24.0
cryptography>=41.0.0
faker>=19.0.0
```

See `requirements.txt` for full list.

## 🎯 Key Test Scenarios

### Network Protocol Tests
- ✅ TLS 1.3 connection validation
- ✅ Certificate chain verification
- ✅ Cipher strength validation (≥128 bits)
- ✅ HTTP/2 protocol support
- ✅ HSTS header enforcement
- ✅ DNS resolution performance
- ✅ TCP keep-alive configuration

### Discovery & Advertisement Tests
- ✅ mDNS packet format validation
- ✅ AirDrop service discovery (_airdrop._tcp.local)
- ✅ AirPlay service discovery (_airplay._tcp.local)
- ✅ OpenDrop mDNS service record (_airdrop._tcp.local, port 8770)
- ✅ BLE advertisement payload structure
- ✅ NameDrop contact sharing format

### OpenDrop Protocol Tests
- ✅ /Discover plist request format (SenderRecordData)
- ✅ /Discover plist response fields (ReceiverComputerName, ReceiverModelName)
- ✅ BLE advertisement Apple Company ID (0x004C)
- ✅ BLE AirDrop action byte (0x05)
- ✅ Contact hash truncation to 2 bytes for BLE privacy

### Network Conditioning Tests
- ✅ 3G / 4G / 5G profile constants validated (bandwidth, latency, packet loss)
- ✅ Uplink asymmetry validated (uplink = downlink / 2)
- ✅ NLC profile plist structure validates all required keys
- ✅ Profile write/read roundtrip (binary plist, disk I/O)
- ✅ 5G < 4G < 3G latency ordering enforced
- ⚡ 3G profile measurably increases TCP latency vs baseline *(requires sudo)*
- ⚡ Network fully restored after context manager exits *(requires sudo)*
- ⚡ High-latency (500ms) profile verified against live connection *(requires sudo)*

### Security & Privacy Tests
- ✅ Contact hash determinism
- ✅ Hash collision rate analysis
- ✅ Truncated hash validation (BLE)
- ✅ PII protection in hashes
- ✅ Identity privacy preservation

### Performance Tests
- ✅ TLS handshake latency (<1s)
- ✅ DNS resolution speed (<500ms)
- ✅ Full connection latency (<2s)

## 🤝 Contributing

This is a demonstration portfolio showcasing QE skills for Apple's Applied Networking team.

## 📝 License

This is a proof-of-concept test portfolio for job application purposes.

---

**Note**: All tests use publicly documented Apple protocols and APIs. No proprietary or confidential information is included.

