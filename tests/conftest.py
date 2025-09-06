import os
import sys

# Ensure the app package is importable in tests
ROOT = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT = os.path.dirname(ROOT)
APP_ROOT = os.path.join(REPO_ROOT, "legal-document-analysis")

# Add application root (so `nodes` etc. are importable)
if os.path.isdir(APP_ROOT) and APP_ROOT not in sys.path:
    sys.path.insert(0, APP_ROOT)

# Also add repository root as a fallback
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)
