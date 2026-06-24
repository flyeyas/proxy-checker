"""
Proxy Checker - Vercel Serverless Compatibility Entrypoint
"""

from proxy_checker.serverless import AUTH_PASSWORD, app, unauthorized_response

__all__ = ["AUTH_PASSWORD", "app", "unauthorized_response"]
