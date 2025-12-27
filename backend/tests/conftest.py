"""
Shared pytest fixtures and configuration for all tests.
"""
import sys
from pathlib import Path

# Add backend to Python path for all tests
backend_path = Path(__file__).parent.parent
sys.path.insert(0, str(backend_path))

# This file makes pytest recognize the tests directory
# and allows fixtures to be shared across all test modules
