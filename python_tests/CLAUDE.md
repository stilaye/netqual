# CLAUDE.md — Apple QE Portfolio: Python Tests

## Project Overview

Enterprise-grade network protocol test suite targeting Apple's networking stack (TLS/SSL, Bonjour, ATS, AirDrop protocols). Written in Python using pytest.

## Environment Setup

```bash
# Activate the virtual environment
source apple_qe_env/bin/activate

# Install dependencies
pip install -r requirements.txt
```

Virtual environment lives at `apple_qe_env/` — never commit it.

## Running Tests

```bash
# Run all tests
pytest

# Run with verbose output
pytest -v

# Run only offline-safe tests (no network required)
pytest -m "not network"

# Skip network tests explicitly
pytest --offline

# Run a specific marker group
pytest -m smoke
pytest -m security
pytest -m integration

# Target a specific test file
pytest tests/test_network_protocols.py -v

# Run against a specific environment
pytest --env staging
pytest --env production
```

## Custom CLI Options

| Option | Default | Description |
|---|---|---|
| `--offline` | false | Skip all `@pytest.mark.network` tests |
| `--env` | test | Target environment: `test`, `staging`, `production` |
| `--generate-report` | false | Generate detailed HTML/JSON test report |

## Project Structure

```
python_tests/
├── conftest.py                        # Shared fixtures and pytest hooks
├── pytest.ini                         # Pytest configuration and markers
├── requirements.txt                   # Python dependencies
├── tests/
│   ├── test_network_protocols.py      # TLS/SSL, HTTP/2, protocol tests
│   ├── test_network_protocols_fixed.py
│   ├── test_bonjour_discovery.py      # mDNS/Bonjour discovery tests
│   ├── example_enterprise_test.py     # Reference test patterns
│   └── verify_test_dependencies.py   # Dependency validation
├── utils/
│   ├── network_helpers.py             # ConnectionHelper, SSL utils, retry logic
│   └── test_data_factory.py          # Test data generation
├── reports/
│   └── pytest.log                    # Test execution logs
└── docs/                             # Framework guides and changelogs
```

## Custom Markers

Defined in `pytest.ini` and registered in `conftest.py`:

| Marker | Purpose |
|---|---|
| `network` | Requires live network connectivity |
| `skip_if_no_network` | Skip gracefully if network unavailable |
| `security` | SSL/TLS and security-focused tests |
| `protocol` | Low-level protocol tests |
| `performance` | Benchmark and timing tests |
| `slow` | Tests that take > 1 second |
| `integration` | Multi-component integration tests |
| `smoke` | Critical path / smoke tests |
| `regression` | Bug regression tests |

Always use `--strict-markers` (already set in `pytest.ini`) — unregistered markers cause failures.

## Key Fixtures (conftest.py)

| Fixture | Scope | Description |
|---|---|---|
| `ssl_context` | session | Secure SSLContext (TLS 1.2+, cert verification) |
| `tcp_socket` | function | TCP socket with auto-cleanup |
| `udp_socket` | function | UDP socket with auto-cleanup |
| `http_client` | function | `httpx.Client` with timeout and redirects |
| `test_config` | session | Env-specific config dict (urls, timeouts, retries) |
| `test_environment` | session | Returns `--env` value |
| `logger` | session | Configured `logging.Logger` |
| `measure_time` | function | Context manager for timing code blocks |
| `skip_if_no_network` | function | Skips test if DNS/network is unavailable |
| `mock_network_unavailable` | function | Monkeypatches socket to simulate no network |
| `apple_test_domains` | function | List of Apple domains for network tests |
| `sample_email_addresses` | function | Sample emails for hashing/contact tests |
| `temp_test_directory` | function | Temporary directory (auto-cleaned) |

## Reports

- Logs: `reports/pytest.log` (DEBUG level)
- HTML/JUnit/coverage reports are commented out in `pytest.ini` — uncomment to enable.

## Dependencies (Key)

- `pytest >= 7.4`, `pytest-cov`, `pytest-html`, `pytest-xdist`, `pytest-asyncio`
- `httpx` (with HTTP/2 support), `requests`
- `cryptography`, `pyOpenSSL`, `certifi`
- `faker`, `factory-boy`, `hypothesis`
- Python >= 3.8 required
