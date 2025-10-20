"""
Email Services Package

Bu package tüm email service implementasyonlarını içerir.
"""

from .base import EmailServiceBase
from .mock_service import MockEmailService

__all__ = [
    'EmailServiceBase',
    'MockEmailService',
]