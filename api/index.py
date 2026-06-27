"""
ProxyForge - Vercel Serverless Compatibility Entrypoint
"""

from proxy_forge.serverless import AUTH_PASSWORD, app, unauthorized_response

__all__ = ["AUTH_PASSWORD", "app", "unauthorized_response"]
