#!/usr/bin/env python3
"""兼容入口：等价于 `python -m xh_aegis.cli`。保留以便旧命令 `python3 cli_demo.py --auto-demo` 继续可用。"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from xh_aegis.cli import main  # noqa: E402

if __name__ == "__main__":
    raise SystemExit(main())
