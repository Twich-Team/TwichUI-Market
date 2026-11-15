"""One authoritative frozen contract validator, shared with offline fixtures."""
from functools import lru_cache
import importlib.util
from pathlib import Path


@lru_cache(maxsize=1)
def contract():
    root=Path(__file__).resolve().parents[2]/'contracts/bridge/v1'
    spec=importlib.util.spec_from_file_location('market_frozen_bridge_contract',root/'validate.py')
    module=importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module
