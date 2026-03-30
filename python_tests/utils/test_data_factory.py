"""
utils/test_data_factory.py
===========================
Test data generation utilities for enterprise test framework.

Provides factories for generating test data including:
- Email addresses and contact information
- Network addresses and hostnames
- Random data for stress testing
- Mock API responses
"""

import hashlib
import random
import string
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Dict, List, Optional

# ============================================================
# Data Classes
# ============================================================


@dataclass
class TestContact:
    """Represents a test contact for AirDrop/identity testing."""

    email: str
    phone: Optional[str] = None
    name: Optional[str] = None

    def get_email_hash(self) -> str:
        """Get SHA-256 hash of email address."""
        return hashlib.sha256(self.email.encode()).hexdigest()

    def get_truncated_hash(self, bytes_count: int = 2) -> bytes:
        """Get truncated hash for BLE advertisement simulation."""
        return hashlib.sha256(self.email.encode()).digest()[:bytes_count]


@dataclass
class TestNetworkEndpoint:
    """Represents a test network endpoint."""

    host: str
    port: int
    protocol: str  # tcp, udp, http, https
    expected_reachable: bool = True

    def __str__(self):
        return f"{self.protocol}://{self.host}:{self.port}"


# ============================================================
# Contact Data Factory
# ============================================================


class ContactFactory:
    """Factory for generating test contact data."""

    FIRST_NAMES = [
        "Alice",
        "Bob",
        "Charlie",
        "Diana",
        "Eve",
        "Frank",
        "Grace",
        "Henry",
        "Iris",
        "Jack",
    ]

    LAST_NAMES = [
        "Smith",
        "Johnson",
        "Williams",
        "Brown",
        "Jones",
        "Garcia",
        "Miller",
        "Davis",
        "Rodriguez",
        "Martinez",
    ]

    DOMAINS = ["example.com", "test.com", "demo.com", "mail.com", "email.com"]

    @classmethod
    def create_contact(
        cls, email: Optional[str] = None, name: Optional[str] = None, phone: Optional[str] = None
    ) -> TestContact:
        """
        Create a single test contact.

        Args:
            email: Optional specific email address
            name: Optional specific name
            phone: Optional phone number

        Returns:
            TestContact instance

        Example:
            >>> contact = ContactFactory.create_contact()
            >>> print(contact.email)
        """
        if email is None:
            first = random.choice(cls.FIRST_NAMES).lower()
            last = random.choice(cls.LAST_NAMES).lower()
            domain = random.choice(cls.DOMAINS)
            email = f"{first}.{last}@{domain}"

        if name is None:
            name = f"{random.choice(cls.FIRST_NAMES)} {random.choice(cls.LAST_NAMES)}"

        if phone is None and random.random() > 0.5:
            phone = cls._generate_phone_number()

        return TestContact(email=email, name=name, phone=phone)

    @classmethod
    def create_contacts(cls, count: int) -> List[TestContact]:
        """
        Create multiple test contacts.

        Args:
            count: Number of contacts to create

        Returns:
            List of TestContact instances

        Example:
            >>> contacts = ContactFactory.create_contacts(100)
            >>> assert len(contacts) == 100
        """
        return [cls.create_contact() for _ in range(count)]

    @classmethod
    def create_contact_list_with_duplicates(
        cls, unique_count: int, duplicate_count: int
    ) -> List[TestContact]:
        """
        Create contact list with intentional duplicates for testing.

        Args:
            unique_count: Number of unique contacts
            duplicate_count: Number of duplicate entries to add

        Returns:
            List with duplicates
        """
        unique_contacts = cls.create_contacts(unique_count)
        duplicates = random.choices(unique_contacts, k=duplicate_count)
        return unique_contacts + duplicates

    @staticmethod
    def _generate_phone_number() -> str:
        """Generate random phone number in format +1-XXX-XXX-XXXX."""
        area = random.randint(200, 999)
        prefix = random.randint(200, 999)
        line = random.randint(1000, 9999)
        return f"+1-{area}-{prefix}-{line}"


# ============================================================
# Network Data Factory
# ============================================================


class NetworkDataFactory:
    """Factory for generating network-related test data."""

    @staticmethod
    def create_endpoint(
        host: Optional[str] = None, port: Optional[int] = None, protocol: str = "https"
    ) -> TestNetworkEndpoint:
        """
        Create a test network endpoint.

        Example:
            >>> endpoint = NetworkDataFactory.create_endpoint()
            >>> print(endpoint)  # https://test-server.example.com:443
        """
        if host is None:
            prefix = random.choice(["api", "test", "staging", "dev"])
            suffix = random.choice(["example.com", "test.com", "demo.com"])
            host = f"{prefix}.{suffix}"

        if port is None:
            port = {
                "http": 80,
                "https": 443,
                "tcp": random.randint(8000, 9000),
                "udp": random.randint(5000, 6000),
            }.get(protocol, 443)

        return TestNetworkEndpoint(host=host, port=port, protocol=protocol)

    @staticmethod
    def create_apple_test_endpoints() -> List[TestNetworkEndpoint]:
        """
        Create endpoints for Apple services testing.

        Returns:
            List of Apple-related test endpoints
        """
        return [
            TestNetworkEndpoint("apple.com", 443, "https"),
            TestNetworkEndpoint("icloud.com", 443, "https"),
            TestNetworkEndpoint("me.com", 443, "https"),
            TestNetworkEndpoint("apple-cloudkit.com", 443, "https"),
        ]

    @staticmethod
    def create_unreachable_endpoints() -> List[TestNetworkEndpoint]:
        """
        Create endpoints that should be unreachable (for negative testing).

        Returns:
            List of unreachable test endpoints
        """
        return [
            TestNetworkEndpoint("192.0.2.1", 80, "http", expected_reachable=False),  # TEST-NET-1
            TestNetworkEndpoint("198.51.100.1", 80, "http", expected_reachable=False),  # TEST-NET-2
            TestNetworkEndpoint("203.0.113.1", 80, "http", expected_reachable=False),  # TEST-NET-3
        ]

    @staticmethod
    def generate_random_ip(version: int = 4) -> str:
        """
        Generate random IP address.

        Args:
            version: IP version (4 or 6)

        Returns:
            Random IP address string

        Example:
            >>> ip = NetworkDataFactory.generate_random_ip()
            >>> assert len(ip.split('.')) == 4
        """
        if version == 4:
            return ".".join(str(random.randint(1, 255)) for _ in range(4))
        else:
            return ":".join(f"{random.randint(0, 65535):x}" for _ in range(8))

    @staticmethod
    def generate_mac_address() -> str:
        """
        Generate random MAC address.

        Returns:
            MAC address in format XX:XX:XX:XX:XX:XX
        """
        return ":".join(f"{random.randint(0, 255):02x}" for _ in range(6))


# ============================================================
# Hash Test Data Factory
# ============================================================


class HashDataFactory:
    """Factory for generating hash-related test data."""

    @staticmethod
    def create_hash_collision_test_set(size: int = 1000) -> Dict[bytes, List[str]]:
        """
        Create test set for hash collision detection.

        Args:
            size: Number of test inputs to generate

        Returns:
            Dictionary mapping truncated hashes to list of inputs

        Example:
            >>> collisions = HashDataFactory.create_hash_collision_test_set(1000)
            >>> for hash_val, inputs in collisions.items():
            >>>     if len(inputs) > 1:
            >>>         print(f"Collision: {len(inputs)} inputs produce {hash_val.hex()}")
        """
        hash_map: Dict[bytes, List[str]] = {}

        for _ in range(size):
            # Generate random email
            email = f"user{random.randint(1, 999999)}@test.com"
            # Get 2-byte truncated hash
            truncated = hashlib.sha256(email.encode()).digest()[:2]

            if truncated not in hash_map:
                hash_map[truncated] = []
            hash_map[truncated].append(email)

        return hash_map

    @staticmethod
    def calculate_collision_rate(hash_map: Dict[bytes, List[str]]) -> float:
        """
        Calculate collision rate from hash map.

        Args:
            hash_map: Dictionary from create_hash_collision_test_set()

        Returns:
            Collision rate as float (0.0 to 1.0)
        """
        total_inputs = sum(len(inputs) for inputs in hash_map.values())
        unique_hashes = len(hash_map)

        if total_inputs == 0:
            return 0.0

        return 1.0 - (unique_hashes / total_inputs)


# ============================================================
# Mock API Response Factory
# ============================================================


class APIResponseFactory:
    """Factory for generating mock API responses."""

    @staticmethod
    def create_success_response(data: Any = None) -> Dict[str, Any]:
        """
        Create mock successful API response.

        Args:
            data: Optional response data

        Returns:
            Dictionary representing API response
        """
        return {
            "status": "success",
            "code": 200,
            "data": data or {"message": "Operation successful"},
            "timestamp": datetime.now().isoformat(),
        }

    @staticmethod
    def create_error_response(
        error_code: int = 500, message: str = "Internal server error"
    ) -> Dict[str, Any]:
        """
        Create mock error API response.

        Args:
            error_code: HTTP error code
            message: Error message

        Returns:
            Dictionary representing error response
        """
        return {
            "status": "error",
            "code": error_code,
            "error": {"message": message, "code": f"ERR_{error_code}"},
            "timestamp": datetime.now().isoformat(),
        }

    @staticmethod
    def create_paginated_response(
        items: List[Any], page: int = 1, page_size: int = 10
    ) -> Dict[str, Any]:
        """
        Create mock paginated API response.

        Args:
            items: List of all items
            page: Current page number (1-indexed)
            page_size: Items per page

        Returns:
            Dictionary representing paginated response
        """
        start_idx = (page - 1) * page_size
        end_idx = start_idx + page_size
        page_items = items[start_idx:end_idx]

        total_pages = (len(items) + page_size - 1) // page_size

        return {
            "status": "success",
            "data": page_items,
            "pagination": {
                "page": page,
                "page_size": page_size,
                "total_items": len(items),
                "total_pages": total_pages,
                "has_next": page < total_pages,
                "has_prev": page > 1,
            },
            "timestamp": datetime.now().isoformat(),
        }


# ============================================================
# Random Data Generators
# ============================================================


def generate_random_string(length: int = 10, charset: str = string.ascii_letters) -> str:
    """
    Generate random string of specified length.

    Args:
        length: Length of string to generate
        charset: Character set to use

    Returns:
        Random string

    Example:
        >>> s = generate_random_string(20)
        >>> assert len(s) == 20
    """
    return "".join(random.choices(charset, k=length))


def generate_random_bytes(length: int = 16) -> bytes:
    """
    Generate random bytes.

    Args:
        length: Number of bytes to generate

    Returns:
        Random bytes

    Example:
        >>> data = generate_random_bytes(32)
        >>> assert len(data) == 32
    """
    return bytes(random.getrandbits(8) for _ in range(length))


def generate_test_payload(size_kb: int = 1) -> bytes:
    """
    Generate test payload of specified size.

    Args:
        size_kb: Size in kilobytes

    Returns:
        Test payload bytes

    Example:
        >>> payload = generate_test_payload(100)  # 100KB
        >>> # Use for network transfer testing
    """
    return generate_random_bytes(size_kb * 1024)
