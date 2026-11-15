"""One authoritative frozen validator from the explicit deployment contract bundle."""
from functools import lru_cache
import importlib.util
import os
from pathlib import Path
from fastapi import HTTPException


@lru_cache(maxsize=1)
def contract():
    explicit=os.environ.get('BRIDGE_CONTRACT_ROOT')
    if explicit and not Path(explicit).is_absolute():
        raise HTTPException(503,'Bridge contract bundle must use an explicit absolute path')
    # Docker already copies the authoritative contracts to /contracts. Source
    # checkouts can use their own repository bundle; installed packages need the
    # deployment bundle, never code discovered from an arbitrary working folder.
    candidates=[Path(explicit)] if explicit else [Path('/contracts/bridge/v1'),Path(__file__).resolve().parents[2]/'contracts/bridge/v1']
    root=next((p for p in candidates if (p/'validate.py').is_file()),None)
    if root is None:raise HTTPException(503,'Bridge contract bundle unavailable')
    spec=importlib.util.spec_from_file_location('market_frozen_bridge_contract',root/'validate.py')
    module=importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module
