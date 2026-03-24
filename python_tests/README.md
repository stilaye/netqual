# Apple Applied Networking — QE Test Portfolio

**Prepared by: Swapnil**  
**Role: Software Quality Engineer — Applied Networking**

## 🎯 What This Demonstrates

An enterprise-level test suite covering the protocols behind Apple's Continuity and Sharing features (AirDrop, SharePlay, Handoff, Universal Clipboard, NameDrop).

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

**Total: 74 tests across 4 test suites**

| Test Suite | Tests | Coverage |
|------------|-------|----------|
| `test_network_protocols.py` | 40 | TLS 1.3, ATS, DNS, TCP/UDP, HTTP/2, identity hashing, performance |
| `test_bonjour_discovery.py` | 15 | mDNS packets, AirDrop/AirPlay discovery, BLE payloads, NameDrop |
| `example_enterprise_test.py` | 19 | Framework usage examples and integration tests |
| Postman Collection | 15 | Apple service health, TLS validation, HTTP/2 endpoints |

### Test Results
- ✅ **68 tests passing**
- ⏭️ **5 tests skipped** (network tests in offline mode)
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
│   ├── test_network_protocols_fixed.py
│   ├── example_enterprise_test.py
│   └── verify_test_dependencies.py
│
├── utils/                      # Test utilities
│   ├── __init__.py
│   ├── network_helpers.py      # Connection, SSL, performance helpers
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

| Test Area | AirDrop | SharePlay | Handoff | Clipboard | NameDrop |
|-----------|---------|-----------|---------|-----------|----------|
| TLS 1.3 validation | ✅ | ✅ | ✅ | ✅ | ✅ |
| mDNS/Bonjour | ✅ | | ✅ | | |
| BLE advertisements | ✅ | | ✅ | | ✅ |
| HTTP/2 | | ✅ | ✅ | ✅ | |
| Identity hashing | ✅ | | | | ✅ |
| Socket behavior | ✅ | ✅ | | ✅ | ✅ |
| DNS resolution | ✅ | ✅ | ✅ | ✅ | ✅ |
## 🎨 Enterprise Framework Features

This test suite includes an enterprise-level pytest framework with:

### ✅ Core Features
- **15+ reusable fixtures** (SSL contexts, sockets, HTTP clients)
- **Custom pytest hooks** (auto-marking, result tracking)
- **Environment-specific configuration** (test/staging/production)
- **Network utilities** (retry logic, SSL validation, performance monitoring)
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
- And more...

### 🛠️ Utilities Available
- `ConnectionHelper` - Connections with retry logic
- `SSLValidator` - Certificate and cipher validation
- `NetworkPerformanceMonitor` - Performance tracking
- `ContactFactory` - Generate test contacts
- `NetworkDataFactory` - Generate test endpoints
- And more...

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
- ✅ BLE advertisement payload structure
- ✅ NameDrop contact sharing format

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

