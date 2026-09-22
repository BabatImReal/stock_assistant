"""The one check Phase 2 needs: the skeleton is actually wired together.

It fails if the package cannot be imported (wrong layout or wrong pythonpath),
if a module lost its docstring, or if the rules config went missing. That is
all there is to verify while the modules are still empty.
"""

from importlib import import_module
from pathlib import Path

import vnstock_research

REPO_ROOT = Path(__file__).resolve().parent.parent

# The pipeline stages from the knowledge document, in the order data flows.
SUBMODULES = ["data", "features", "patterns", "backtest", "report"]


def test_package_imports():
    assert vnstock_research.__doc__


def test_every_stage_exists_and_explains_itself():
    # Every module must say what it is for and which doc section it maps to -
    # the skeleton is documentation right now, so an undocumented module is an
    # empty module in the bad sense.
    for name in SUBMODULES:
        module = import_module(f"vnstock_research.{name}")
        assert module.__doc__, f"{name} has no docstring"
        assert "doc §" in module.__doc__.lower(), f"{name} cites no doc section"


def test_pattern_parameters_live_in_config_not_code():
    # doc §3.5: thresholds are choices and must be visible in one reviewable
    # file, never inlined in a detection function.
    assert (REPO_ROOT / "config" / "rules" / "patterns.yaml").is_file()


def test_secrets_are_not_committable():
    gitignore = (REPO_ROOT / ".gitignore").read_text()
    assert ".env" in gitignore
    assert "data/" in gitignore
