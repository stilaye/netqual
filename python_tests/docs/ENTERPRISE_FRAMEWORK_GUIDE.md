# Enterprise-Level Pytest Framework Guide

## 📋 Table of Contents
1. [Framework Structure](#framework-structure)
2. [Core Components](#core-components)
3. [Usage Examples](#usage-examples)
4. [Best Practices](#best-practices)
5. [Advanced Features](#advanced-features)

---

## Framework Structure

```
test_framework/
│
├── conftest.py                 # Global fixtures & pytest configuration
├── pytest.ini                  # Pytest settings
├── requirements.txt            # Test dependencies
│
├── tests/                      # All test files
│   ├── unit/                   # Unit tests
│   ├── integration/            # Integration tests
│   ├── e2e/                    # End-to-end tests
│   └── performance/            # Performance tests
│
├── utils/                      # Test utilities
│   ├── __init__.py
│   ├── network_helpers.py      # Network testing utilities
│   ├── test_data_factory.py   # Test data generation
│   ├── assertions.py           # Custom assertions
│   └── reporters.py            # Custom reporting
│
├── fixtures/                   # Shared fixtures
│   ├── __init__.py
│   ├── network_fixtures.py     # Network-related fixtures
│   └── data_fixtures.py        # Data-related fixtures
│
├── config/                     # Configuration files
│   ├── test_config.yaml        # Test configuration
│   ├── staging_config.yaml     # Staging environment
│   └── prod_config.yaml        # Production environment
│
└── reports/                    # Test reports & artifacts
    ├── html/                   # HTML reports
    ├── junit/                  # JUnit XML reports
    └── coverage/               # Coverage reports
```

---

## Core Components

### 1. conftest.py
Central fixture and configuration hub. Already created with:
- ✅ Session/function/module scoped fixtures
- ✅ Custom pytest hooks
- ✅ Command-line options (--offline, --env, etc.)
- ✅ Automatic test result tracking
- ✅ Network availability checks

### 2. pytest.ini
Configuration file for pytest settings:

```ini
[pytest]
# Test discovery patterns
python_files = test_*.py *_test.py
python_classes = Test*
python_functions = test_*

# Markers
markers =
    network: tests requiring network connectivity
    security: security-focused tests
    protocol: protocol-level tests
    performance: performance benchmarks
    slow: slow-running tests (> 1s)
    integration: integration tests

# Output options
addopts = 
    -v
    --strict-markers
    --tb=short
    --color=yes
    --junit-xml=reports/junit/results.xml
    --html=reports/html/report.html
    --self-contained-html

# Test paths
testpaths = tests

# Coverage options (if using pytest-cov)
[coverage:run]
source = .
omit = 
    */tests/*
    */venv/*
    */__pycache__/*

[coverage:report]
precision = 2
show_missing = True
```

### 3. requirements.txt
Test dependencies:

```txt
# Core testing
pytest>=7.4.0
pytest-cov>=4.1.0
pytest-html>=3.2.0
pytest-xdist>=3.3.0  # Parallel test execution
pytest-timeout>=2.1.0
pytest-mock>=3.11.0

# Network testing
httpx>=0.24.0
httpx[http2]>=0.24.0
requests>=2.31.0

# SSL/TLS
certifi>=2023.7.0
cryptography>=41.0.0

# Data generation
faker>=19.0.0  # For generating realistic test data

# Reporting
allure-pytest>=2.13.0  # Advanced reporting
pytest-json-report>=1.5.0

# Code quality
pytest-pylint>=0.19.0
pytest-flake8>=1.1.0
```

---

## Usage Examples

### Example 1: Using Network Fixtures

```python
def test_ssl_connection(ssl_context, logger):
    """Test using shared SSL context fixture."""
    logger.info("Testing SSL connection")
    
    with socket.create_connection(("apple.com", 443)) as sock:
        with ssl_context.wrap_socket(sock, server_hostname="apple.com") as ssock:
            assert ssock.version() in ["TLSv1.3", "TLSv1.2"]
            logger.info(f"Connected with {ssock.version()}")
```

### Example 2: Using Test Data Factory

```python
from utils.test_data_factory import ContactFactory, NetworkDataFactory

def test_contact_hashing():
    """Test contact hash generation with factory data."""
    contacts = ContactFactory.create_contacts(100)
    
    hashes = {contact.get_email_hash() for contact in contacts}
    assert len(hashes) == 100, "Hash collision detected"
    
    for contact in contacts:
        assert len(contact.get_truncated_hash()) == 2
```

### Example 3: Using Network Helpers

```python
from utils.network_helpers import ConnectionHelper, SSLValidator

def test_connection_retry_logic():
    """Test connection with automatic retry."""
    helper = ConnectionHelper(retry_count=3, retry_delay=0.5)
    
    success, sock, error = helper.connect_with_retry("apple.com", 443)
    assert success, f"Connection failed: {error}"
    sock.close()

def test_cipher_strength():
    """Test cipher strength validation."""
    passes, info = SSLValidator.verify_cipher_strength("apple.com", min_bits=128)
    assert passes, f"Weak cipher: {info['bits']} bits"
```

### Example 4: Performance Monitoring

```python
from utils.network_helpers import NetworkPerformanceMonitor

def test_network_performance():
    """Monitor network operation performance."""
    monitor = NetworkPerformanceMonitor()
    
    # Measure DNS lookup
    result = monitor.measure_operation(
        "DNS Lookup",
        socket.gethostbyname,
        "apple.com"
    )
    assert result['duration_ms'] < 500
    
    # Get statistics
    stats = monitor.get_statistics()
    assert stats['avg_duration_ms'] < 1000
```

### Example 5: Environment-Specific Testing

```python
def test_api_endpoint(test_config, test_environment):
    """Test API with environment-specific configuration."""
    api_url = test_config['api_base_url']
    timeout = test_config['timeout']
    
    if test_environment == "production":
        # Use production-specific assertions
        assert timeout >= 30
    
    # Make request with configured settings
    response = make_request(api_url, timeout=timeout)
    assert response.status_code == 200
```

---

## Best Practices

### 1. Test Organization

**✅ DO:**
```python
class TestSSLValidation:
    """Group related tests in classes."""
    
    def test_tls_1_3_support(self, ssl_context):
        """Use descriptive names and docstrings."""
        pass
    
    def test_cipher_strength(self, ssl_context):
        pass
```

**❌ DON'T:**
```python
def test1():  # Poor naming
    pass

def test2():  # No grouping
    pass
```

### 2. Fixture Scoping

```python
@pytest.fixture(scope="session")  # Setup once per session
def expensive_resource():
    """Use session scope for expensive resources."""
    resource = create_expensive_resource()
    yield resource
    cleanup_resource(resource)

@pytest.fixture(scope="function")  # Setup for each test
def test_data():
    """Use function scope for test isolation."""
    return generate_test_data()
```

### 3. Parametrized Testing

```python
@pytest.mark.parametrize("host,port,expected", [
    ("apple.com", 443, True),
    ("icloud.com", 443, True),
    ("invalid.test", 443, False),
])
def test_host_reachability(host, port, expected):
    """Test multiple scenarios efficiently."""
    reachable = check_host_reachable(host, port)
    assert reachable == expected
```

### 4. Error Handling

```python
def test_connection_error_handling():
    """Always test error cases."""
    with pytest.raises(ConnectionError) as exc_info:
        connect_to_invalid_host()
    
    assert "Connection refused" in str(exc_info.value)
```

### 5. Test Independence

```python
# ✅ Good: Each test is independent
def test_create_user(clean_database):
    user = create_user("test@example.com")
    assert user.email == "test@example.com"

def test_delete_user(clean_database):
    user = create_user("test@example.com")
    delete_user(user.id)
    assert get_user(user.id) is None

# ❌ Bad: Tests depend on execution order
def test_create_user():
    global user  # Bad practice!
    user = create_user("test@example.com")

def test_delete_user():
    delete_user(user.id)  # Breaks if test_create_user didn't run
```

---

## Advanced Features

### 1. Parallel Test Execution

```bash
# Run tests in parallel using pytest-xdist
pytest -n auto  # Use all available CPU cores
pytest -n 4     # Use 4 workers
```

### 2. Test Filtering

```bash
# Run specific markers
pytest -m network          # Only network tests
pytest -m "not slow"       # Exclude slow tests
pytest -m "security and not network"  # Combine markers

# Run specific test patterns
pytest -k "ssl"            # Tests with "ssl" in name
pytest -k "test_tls or test_dns"  # Multiple patterns
```

### 3. Custom Assertions

```python
# utils/assertions.py
def assert_valid_ip(ip_string):
    """Custom assertion for IP validation."""
    parts = ip_string.split('.')
    assert len(parts) == 4, f"Invalid IP format: {ip_string}"
    for part in parts:
        num = int(part)
        assert 0 <= num <= 255, f"Invalid octet: {part}"

def assert_response_time(duration_ms, max_ms):
    """Assert response time is within threshold."""
    assert duration_ms <= max_ms, \
        f"Response too slow: {duration_ms}ms (max: {max_ms}ms)"
```

### 4. Test Retry on Failure

```python
@pytest.mark.flaky(reruns=3, reruns_delay=2)  # Requires pytest-rerunfailures
def test_flaky_network_operation():
    """Retry flaky tests automatically."""
    result = make_network_request()
    assert result.status_code == 200
```

### 5. Test Timeouts

```python
@pytest.mark.timeout(10)  # Requires pytest-timeout
def test_with_timeout():
    """Fail test if it takes longer than 10 seconds."""
    perform_long_operation()
```

### 6. Custom Markers for Test Suites

```python
# Define custom test suites
@pytest.mark.smoke
def test_critical_feature():
    """Part of smoke test suite."""
    pass

@pytest.mark.regression
def test_bug_fix():
    """Part of regression suite."""
    pass

# Run with: pytest -m smoke
```

### 7. Test Data Fixtures with Cleanup

```python
@pytest.fixture
def test_file(tmp_path):
    """Create test file with automatic cleanup."""
    file_path = tmp_path / "test_data.txt"
    file_path.write_text("test content")
    
    yield file_path
    
    # Cleanup happens automatically after test
    # tmp_path is cleaned up by pytest
```

---

## Running Tests

### Basic Commands

```bash
# Run all tests
pytest

# Run with verbose output
pytest -v

# Run specific test file
pytest tests/test_network_protocols.py

# Run specific test
pytest tests/test_network_protocols.py::TestTLSValidation::test_tls_1_3_supported

# Run in offline mode (custom flag from conftest.py)
pytest --offline

# Run with specific environment
pytest --env=staging
```

### Generate Reports

```bash
# HTML report
pytest --html=reports/report.html --self-contained-html

# Coverage report
pytest --cov=. --cov-report=html --cov-report=term

# JUnit XML (for CI/CD)
pytest --junit-xml=reports/junit.xml

# JSON report
pytest --json-report --json-report-file=reports/report.json
```

### CI/CD Integration

```yaml
# GitHub Actions example
name: Test Suite
on: [push, pull_request]

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - name: Set up Python
        uses: actions/setup-python@v4
        with:
          python-version: '3.11'
      - name: Install dependencies
        run: |
          pip install -r requirements.txt
      - name: Run tests
        run: |
          pytest -v --junit-xml=reports/junit.xml --cov=. --cov-report=xml
      - name: Upload coverage
        uses: codecov/codecov-action@v3
```

---

## Scaling & Maintainability Tips

### 1. Modular Design
- Keep tests focused and single-purpose
- Group related tests in classes
- Use fixtures for shared setup/teardown
- Extract common logic into utils

### 2. Scalability
- Use parallel execution for large test suites
- Implement test tagging for selective runs
- Create test suites (smoke, regression, full)
- Consider distributed testing for very large suites

### 3. Maintainability
- Write clear, descriptive test names
- Add docstrings explaining what's being tested
- Use factories instead of hardcoded test data
- Keep fixtures simple and reusable
- Document custom markers and fixtures

### 4. Code Quality
- Follow naming conventions
- Maintain DRY (Don't Repeat Yourself) principle
- Use type hints for better IDE support
- Run linters (pylint, flake8) on test code

---

## Next Steps

1. ✅ **Install dependencies**: `pip install -r requirements.txt`
2. ✅ **Create pytest.ini**: Configure pytest settings
3. ✅ **Run tests**: `pytest -v`
4. ✅ **Generate reports**: `pytest --html=reports/report.html`
5. ✅ **Integrate with CI/CD**: Add to your pipeline

Your enterprise-level pytest framework is now ready! 🚀
