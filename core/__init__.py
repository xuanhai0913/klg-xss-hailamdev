"""
KLG-XSS HAILAMDEV Core Modules
"""

from .keylogger import KeyloggerCore, create_keylogger
from .xss_framework import (
    XSSPayloadGenerator,
    XSSScanner,
    XSSExploitFramework,
    XSSTarget,
    XSSPayload,
    XSSContext,
    XSSVectorType
)

__all__ = [
    'KeyloggerCore',
    'create_keylogger',
    'XSSPayloadGenerator',
    'XSSScanner',
    'XSSExploitFramework',
    'XSSTarget',
    'XSSPayload',
    'XSSContext',
    'XSSVectorType'
]