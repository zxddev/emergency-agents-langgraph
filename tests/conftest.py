from __future__ import annotations

import asyncio
import inspect
import os
import sys
from pathlib import Path
from typing import Optional

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, os.fspath(ROOT / "src"))


@pytest.hookimpl(tryfirst=True)
def pytest_pyfunc_call(pyfuncitem: pytest.Function) -> Optional[bool]:
    """异步测试兼容层：仅传递函数签名接受的 fixture，避免参数不匹配."""

    function = pyfuncitem.obj
    if not asyncio.iscoroutinefunction(function):
        return None

    signature = inspect.signature(function)
    accepted = {
        name: value
        for name, value in pyfuncitem.funcargs.items()
        if name in signature.parameters
    }

    loop = asyncio.new_event_loop()
    try:
        loop.run_until_complete(function(**accepted))
    finally:
        loop.close()
    return True
