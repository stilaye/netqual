#!/usr/bin/env python3
"""
Verify that all test dependencies are properly installed.
Run this before running the test suite.
"""

import sys


def check_dependencies():
    """Check if all required packages are available."""
    issues = []

    # Check SSL/TLS support
    try:
        import ssl

        context = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
        context.load_default_certs()
        print("✓ SSL/TLS support: OK")
    except Exception as e:
        issues.append(f"✗ SSL/TLS: {e}")

    # Check certifi
    try:
        import certifi

        print(f"✓ certifi: OK (certificates at {certifi.where()})")
    except ImportError:
        issues.append("✗ certifi: Missing (run: pip install certifi)")

    # Check httpx
    try:
        import httpx

        print("✓ httpx: OK")
    except ImportError:
        issues.append("✗ httpx: Missing (run: pip install httpx)")

    # Check HTTP/2 support (h2)
    try:
        import h2

        print("✓ HTTP/2 (h2): OK")
    except ImportError:
        issues.append("✗ HTTP/2 (h2): Missing (run: pip install 'httpx[http2]')")

    # Check socket options
    try:
        import socket

        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_KEEPALIVE, 1)
        value = sock.getsockopt(socket.SOL_SOCKET, socket.SO_KEEPALIVE)
        sock.close()
        print(f"✓ Socket options: OK (SO_KEEPALIVE returns {value})")
    except Exception as e:
        issues.append(f"✗ Socket options: {e}")

    # Check pytest
    try:
        import pytest

        print(f"✓ pytest: OK (version {pytest.__version__})")
    except ImportError:
        issues.append("✗ pytest: Missing (run: pip install pytest)")

    print("\n" + "=" * 60)
    if issues:
        print("ISSUES FOUND:")
        for issue in issues:
            print(f"  {issue}")
        return False
    else:
        print("All dependencies are properly installed! ✓")
        return True


if __name__ == "__main__":
    success = check_dependencies()
    sys.exit(0 if success else 1)
