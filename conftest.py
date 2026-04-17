"""Root conftest — ensure vendored packages in src/ don't shadow system packages."""
import sys
import os

# Default ACCESS_CONTROL_ENABLED to false for tests so existing tests
# continue to work without providing user identity in events.
os.environ.setdefault("ACCESS_CONTROL_ENABLED", "false")

# Remove src/ from sys.path so vendored pydantic/pydantic_core don't shadow
# the system-installed versions. The bare imports in src/models/__init__.py
# (e.g. `from models.case_file import ...`) need src/ on the path, but the
# vendored pydantic_core is missing its compiled extension. We fix this by:
# 1. Removing src/ from sys.path
# 2. Letting tests import via `from src.models.case_file import ...` (works
#    because the project root is on the path)

_src_dir = os.path.join(os.path.dirname(__file__), "src")
sys.path = [p for p in sys.path if os.path.normpath(p) != os.path.normpath(_src_dir)]

# Now add src/ back but AFTER site-packages so system pydantic wins
sys.path.append(_src_dir)
