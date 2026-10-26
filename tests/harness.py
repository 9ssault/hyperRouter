"""Shared loader for the single-file CLI.

`hyperrouter` has no .py suffix, so importlib needs an explicit SourceFileLoader.
HOME and the XDG dirs are redirected to a throwaway directory *before* the module
is executed, so no test touches the real config, database or skill library.
"""

import importlib.util
import os
import tempfile
from importlib.machinery import SourceFileLoader
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

_HOME = tempfile.mkdtemp(prefix="hyperrouter-tests-home-")
os.environ["HOME"] = _HOME
os.environ["XDG_CONFIG_HOME"] = str(Path(_HOME) / ".config")
os.environ["XDG_DATA_HOME"] = str(Path(_HOME) / ".local" / "share")
os.environ["XDG_CACHE_HOME"] = str(Path(_HOME) / ".cache")
# Never let a test spawn MCP servers or hit the network through them.
os.environ["HYPERROUTER_NO_MCP"] = "1"

loader = SourceFileLoader("hyperrouter_cli", str(ROOT / "hyperrouter"))
spec = importlib.util.spec_from_loader("hyperrouter_cli", loader)
hr = importlib.util.module_from_spec(spec)
loader.exec_module(hr)


def require(testcase, name):
    """Skip a test only when the running script predates the feature."""
    value = getattr(hr, name, None)
    if value is None:
        testcase.skipTest(f"{name} is not available in this build")
    return value
