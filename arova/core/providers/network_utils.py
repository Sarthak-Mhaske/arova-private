import ssl
import logging
from typing import Optional

logger = logging.getLogger(__name__)

def get_ssl_context() -> ssl.SSLContext:
    """
    Returns a robust SSL context that works seamlessly across Windows, macOS, and Linux,
    even in PyInstaller frozen binaries and enterprise environments.
    """
    # 1. Try certifi bundled Mozilla CA bundle
    try:
        import certifi
        ca_path = certifi.where()
        return ssl.create_default_context(cafile=ca_path)
    except Exception:
        pass

    # 2. Try default system context
    try:
        return ssl.create_default_context()
    except Exception:
        pass

    # 3. Fallback unverified context
    return ssl._create_unverified_context()

def get_aiohttp_connector():
    """
    Creates an aiohttp TCPConnector with SSL verification and auto-fallback.
    """
    try:
        import aiohttp
        ctx = get_ssl_context()
        return aiohttp.TCPConnector(ssl=ctx)
    except Exception:
        try:
            import aiohttp
            return aiohttp.TCPConnector(ssl=False)
        except Exception:
            return None
