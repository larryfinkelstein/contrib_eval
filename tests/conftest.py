import sys
import os

# Add project root to sys.path so tests can import top-level modules like 'storage', 'scoring', 'normalize', etc.
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

