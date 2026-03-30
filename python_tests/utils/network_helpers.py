"""
utils/network_helpers.py
=========================
Network utility functions for enterprise test framework.

Provides reusable network testing utilities including:
- Connection helpers with retry logic
- SSL/TLS validation utilities
- Network availability checks
- Protocol-specific helpers
"""

import socket
import ssl
import time
from typing import Optional, Tuple, List, Dict, Any
from contextlib import contextmanager
import logging

logger = logging.getLogger(__name__)


# ============================================================
# Connection Utilities
# ============================================================

class ConnectionHelper:
    """Helper class for managing network connections with retry logic."""
    
    def __init__(self, timeout: int = 10, retry_count: int = 3, retry_delay: float = 1.0):
        """
        Initialize connection helper.
        
        Args:
            timeout: Socket timeout in seconds
            retry_count: Number of retry attempts
            retry_delay: Delay between retries in seconds
        """
        self.timeout = timeout
        self.retry_count = retry_count
        self.retry_delay = retry_delay
    
    def connect_with_retry(
        self, 
        host: str, 
        port: int, 
        use_ssl: bool = True,
        ssl_context: Optional[ssl.SSLContext] = None
    ) -> Tuple[bool, Optional[socket.socket], Optional[str]]:
        """
        Attempt connection with automatic retry on failure.
        
        Args:
            host: Target hostname
            port: Target port
            use_ssl: Whether to wrap socket with SSL
            ssl_context: Optional custom SSL context
        
        Returns:
            Tuple of (success, socket, error_message)
        
        Example:
            >>> helper = ConnectionHelper()
            >>> success, sock, error = helper.connect_with_retry("apple.com", 443)
            >>> if success:
            >>>     # Use socket
            >>>     sock.close()
        """
        last_error = None
        
        for attempt in range(self.retry_count):
            try:
                logger.debug(f"Connection attempt {attempt + 1}/{self.retry_count} to {host}:{port}")
                
                sock = socket.create_connection((host, port), timeout=self.timeout)
                
                if use_ssl:
                    if ssl_context is None:
                        ssl_context = ssl.create_default_context()
                    sock = ssl_context.wrap_socket(sock, server_hostname=host)
                
                logger.info(f"Successfully connected to {host}:{port}")
                return True, sock, None
                
            except Exception as e:
                last_error = str(e)
                logger.debug(
                    "Connection attempt %d/%d to %s:%d failed: %s",
                    attempt + 1, self.retry_count, host, port, e
                )
                
                if attempt < self.retry_count - 1:
                    time.sleep(self.retry_delay)
        
        return False, None, last_error
    
    @contextmanager
    def managed_connection(self, host: str, port: int, use_ssl: bool = True):
        """
        Context manager for automatic connection cleanup.
        
        Example:
            >>> helper = ConnectionHelper()
            >>> with helper.managed_connection("apple.com", 443) as sock:
            >>>     # Use socket
            >>>     data = sock.recv(1024)
            >>> # Socket automatically closed
        """
        success, sock, error = self.connect_with_retry(host, port, use_ssl)
        
        if not success:
            raise ConnectionError(f"Failed to connect: {error}")
        
        try:
            yield sock
        finally:
            if sock:
                sock.close()


# ============================================================
# Network Availability
# ============================================================

def is_network_available(test_host: str = "8.8.8.8", test_port: int = 53, timeout: int = 3) -> bool:
    """
    Check if network connectivity is available.
    
    Args:
        test_host: Host to test connectivity (default: Google DNS)
        test_port: Port to test (default: DNS port 53)
        timeout: Timeout in seconds
    
    Returns:
        True if network is available, False otherwise
    
    Example:
        >>> if is_network_available():
        >>>     run_network_tests()
        >>> else:
        >>>     skip_network_tests()
    """
    try:
        sock = socket.create_connection((test_host, test_port), timeout=timeout)
        sock.close()
        return True
    except OSError:
        return False


def check_host_reachable(host: str, port: int = 443, timeout: int = 5) -> Dict[str, Any]:
    """
    Check if a specific host is reachable and measure latency.
    
    Args:
        host: Target hostname
        port: Target port
        timeout: Timeout in seconds
    
    Returns:
        Dictionary with reachability status and metrics
    
    Example:
        >>> result = check_host_reachable("apple.com")
        >>> if result['reachable']:
        >>>     print(f"Latency: {result['latency_ms']}ms")
    """
    result = {
        'reachable': False,
        'latency_ms': None,
        'error': None,
        'resolved_ip': None
    }
    
    start_time = time.time()
    
    try:
        # Resolve hostname
        ip = socket.gethostbyname(host)
        result['resolved_ip'] = ip
        
        # Attempt connection
        sock = socket.create_connection((host, port), timeout=timeout)
        sock.close()
        
        latency = (time.time() - start_time) * 1000
        result['reachable'] = True
        result['latency_ms'] = latency
        
    except Exception as e:
        result['error'] = str(e)
    
    return result


# ============================================================
# SSL/TLS Utilities
# ============================================================

class SSLValidator:
    """Utility class for SSL/TLS certificate validation and inspection."""
    
    @staticmethod
    def get_certificate_info(host: str, port: int = 443) -> Optional[Dict[str, Any]]:
        """
        Retrieve and parse SSL certificate information.
        
        Args:
            host: Target hostname
            port: Target port (default: 443)
        
        Returns:
            Dictionary containing certificate details or None on error
        
        Example:
            >>> info = SSLValidator.get_certificate_info("apple.com")
            >>> print(f"Issuer: {info['issuer']}")
            >>> print(f"Expires: {info['expires']}")
        """
        try:
            context = ssl.create_default_context()
            
            with socket.create_connection((host, port), timeout=10) as sock:
                with context.wrap_socket(sock, server_hostname=host) as ssock:
                    cert = ssock.getpeercert()
                    
                    return {
                        'subject': dict(x[0] for x in cert.get('subject', [])),
                        'issuer': dict(x[0] for x in cert.get('issuer', [])),
                        'version': cert.get('version'),
                        'serial_number': cert.get('serialNumber'),
                        'not_before': cert.get('notBefore'),
                        'not_after': cert.get('notAfter'),
                        'san': cert.get('subjectAltName', []),
                        'tls_version': ssock.version(),
                        'cipher': ssock.cipher()
                    }
        except Exception as e:
            logger.error(f"Failed to retrieve certificate for {host}: {e}")
            return None
    
    @staticmethod
    def verify_cipher_strength(host: str, port: int = 443, min_bits: int = 128) -> Tuple[bool, Dict[str, Any]]:
        """
        Verify SSL cipher strength meets minimum requirements.
        
        Args:
            host: Target hostname
            port: Target port
            min_bits: Minimum acceptable cipher strength in bits
        
        Returns:
            Tuple of (meets_requirement, cipher_info)
        
        Example:
            >>> passes, info = SSLValidator.verify_cipher_strength("apple.com")
            >>> assert passes, f"Weak cipher: {info['bits']} bits"
        """
        try:
            context = ssl.create_default_context()
            
            with socket.create_connection((host, port), timeout=10) as sock:
                with context.wrap_socket(sock, server_hostname=host) as ssock:
                    cipher_name, tls_version, bits = ssock.cipher()
                    
                    cipher_info = {
                        'name': cipher_name,
                        'version': tls_version,
                        'bits': bits,
                        'tls_protocol': ssock.version()
                    }
                    
                    return bits >= min_bits, cipher_info
        except Exception as e:
            logger.error(f"Cipher strength check failed for {host}: {e}")
            return False, {'error': str(e)}
    
    @staticmethod
    def check_tls_version_support(host: str, port: int = 443) -> Dict[str, bool]:
        """
        Check which TLS versions are supported by a host.
        
        Args:
            host: Target hostname
            port: Target port
        
        Returns:
            Dictionary mapping TLS version to support status
        
        Example:
            >>> support = SSLValidator.check_tls_version_support("apple.com")
            >>> assert support['TLS 1.3'], "TLS 1.3 not supported"
        """
        results = {}
        
        versions_to_test = [
            ('TLS 1.3', ssl.TLSVersion.TLSv1_3),
            ('TLS 1.2', ssl.TLSVersion.TLSv1_2),
        ]
        
        for version_name, version_constant in versions_to_test:
            try:
                context = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
                context.load_default_certs()
                context.minimum_version = version_constant
                context.maximum_version = version_constant
                
                with socket.create_connection((host, port), timeout=5) as sock:
                    with context.wrap_socket(sock, server_hostname=host) as ssock:
                        results[version_name] = True
            except:
                results[version_name] = False
        
        return results


# ============================================================
# DNS Utilities
# ============================================================

def resolve_hostname_with_timing(hostname: str) -> Tuple[Optional[str], float]:
    """
    Resolve hostname and measure DNS lookup time.
    
    Args:
        hostname: Hostname to resolve
    
    Returns:
        Tuple of (resolved_ip, lookup_time_ms)
    
    Example:
        >>> ip, duration = resolve_hostname_with_timing("apple.com")
        >>> assert duration < 500, f"DNS lookup too slow: {duration}ms"
    """
    start_time = time.time()
    
    try:
        ip = socket.gethostbyname(hostname)
        duration = (time.time() - start_time) * 1000
        return ip, duration
    except socket.gaierror:
        duration = (time.time() - start_time) * 1000
        return None, duration


def resolve_all_addresses(hostname: str) -> List[str]:
    """
    Resolve all IP addresses for a hostname.
    
    Args:
        hostname: Hostname to resolve
    
    Returns:
        List of IP addresses
    
    Example:
        >>> ips = resolve_all_addresses("apple.com")
        >>> assert len(ips) > 0, "No IPs resolved"
    """
    try:
        addr_info = socket.getaddrinfo(hostname, None)
        # Extract unique IPs
        ips = list(set([addr[4][0] for addr in addr_info]))
        return ips
    except socket.gaierror:
        return []


# ============================================================
# Protocol Helpers
# ============================================================

def send_http_request(host: str, path: str = "/", port: int = 80, timeout: int = 10) -> Optional[str]:
    """
    Send a simple HTTP request and return response.
    
    Args:
        host: Target hostname
        path: Request path
        port: Target port
        timeout: Request timeout
    
    Returns:
        Response text or None on error
    
    Example:
        >>> response = send_http_request("example.com", "/")
        >>> assert "200 OK" in response
    """
    try:
        sock = socket.create_connection((host, port), timeout=timeout)
        
        request = f"GET {path} HTTP/1.1\r\nHost: {host}\r\nConnection: close\r\n\r\n"
        sock.sendall(request.encode())
        
        response = b""
        while True:
            chunk = sock.recv(4096)
            if not chunk:
                break
            response += chunk
        
        sock.close()
        return response.decode('utf-8', errors='ignore')
        
    except Exception as e:
        logger.error(f"HTTP request failed: {e}")
        return None


def check_port_open(host: str, port: int, timeout: int = 3) -> bool:
    """
    Check if a specific port is open on a host.
    
    Args:
        host: Target hostname or IP
        port: Port to check
        timeout: Connection timeout
    
    Returns:
        True if port is open, False otherwise
    
    Example:
        >>> if check_port_open("apple.com", 443):
        >>>     print("HTTPS port is open")
    """
    try:
        sock = socket.create_connection((host, port), timeout=timeout)
        sock.close()
        return True
    except (socket.timeout, ConnectionRefusedError, OSError):
        return False


# ============================================================
# Performance Measurement
# ============================================================

class NetworkPerformanceMonitor:
    """Monitor and measure network operation performance."""
    
    def __init__(self):
        self.measurements = []
    
    def measure_operation(self, operation_name: str, operation_func, *args, **kwargs) -> Dict[str, Any]:
        """
        Measure the performance of a network operation.
        
        Args:
            operation_name: Descriptive name for the operation
            operation_func: Function to measure
            *args, **kwargs: Arguments to pass to the function
        
        Returns:
            Dictionary containing operation results and timing
        
        Example:
            >>> monitor = NetworkPerformanceMonitor()
            >>> result = monitor.measure_operation(
            >>>     "DNS Lookup",
            >>>     socket.gethostbyname,
            >>>     "apple.com"
            >>> )
            >>> print(f"Operation took {result['duration_ms']}ms")
        """
        start_time = time.time()
        error = None
        result = None
        
        try:
            result = operation_func(*args, **kwargs)
        except Exception as e:
            error = str(e)
        
        duration = (time.time() - start_time) * 1000
        
        measurement = {
            'operation': operation_name,
            'duration_ms': duration,
            'success': error is None,
            'error': error,
            'result': result,
            'timestamp': time.time()
        }
        
        self.measurements.append(measurement)
        return measurement
    
    def get_statistics(self) -> Dict[str, Any]:
        """
        Get statistics about all measurements.
        
        Returns:
            Dictionary containing min, max, avg, and median durations
        """
        if not self.measurements:
            return {}
        
        durations = [m['duration_ms'] for m in self.measurements]
        success_count = sum(1 for m in self.measurements if m['success'])
        
        return {
            'total_operations': len(self.measurements),
            'successful_operations': success_count,
            'failed_operations': len(self.measurements) - success_count,
            'min_duration_ms': min(durations),
            'max_duration_ms': max(durations),
            'avg_duration_ms': sum(durations) / len(durations),
            'median_duration_ms': sorted(durations)[len(durations) // 2]
        }
