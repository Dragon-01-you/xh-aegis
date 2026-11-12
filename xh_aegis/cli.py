"""CLI entrypoint for `xh-aegis` and `xh` commands."""
from __future__ import annotations
import argparse
import os
import sys
from pathlib import Path
from typing import Optional

from xh_aegis import __version__
from xh_aegis.cli_demo import run_automated_simulation, run_interactive_cli
from xh_aegis.llm_router import LLMConfigError


def resolve_home(explicit: Optional[str]) -> Path:
    """项目根目录（含 config/settings.yaml）：--home > $XH_AEGIS_HOME > 当前目录 > 源码仓库根目录。
    安装成 wheel 后 __file__ 在 site-packages 里，不能再用它推算根目录。"""
    if explicit:  # 显式指定的目录无效就直接报错，不悄悄换成别的目录
        if (Path(explicit) / "config" / "settings.yaml").exists():
            return Path(explicit).resolve()
        raise SystemExit(f"--home 指定的目录里没有 config/settings.yaml: {explicit}")
    candidates = [os.environ.get("XH_AEGIS_HOME"), str(Path.cwd()), str(Path(__file__).resolve().parent.parent)]
    for c in candidates:
        if c and (Path(c) / "config" / "settings.yaml").exists():
            return Path(c).resolve()
    raise SystemExit("找不到 config/settings.yaml：请在项目根目录运行，或用 --home / XH_AEGIS_HOME 指定。")


def main(argv: Optional[list] = None) -> int:
    parser = argparse.ArgumentParser(
        prog="xh-aegis",
        description="🔥 芯火·灵镜 XH-Aegis: 零训练热插拔 Agent 记忆与后台反思进化系统",
    )
    parser.add_argument("--version", action="version", version=f"xh-aegis {__version__}")
    parser.add_argument("--auto-demo", action="store_true", help="运行 5 天跨周期言行比对与反事实因果进化演示（临时目录，不污染 data/）")
    parser.add_argument("--live", action="store_true", help="使用真实模型（需环境变量 API Key；缺失将直接报错而不是悄悄回退 mock）")
    parser.add_argument("--home", help="项目根目录（含 config/settings.yaml）")
    args = parser.parse_args(argv)

    root = resolve_home(args.home)
    if args.auto_demo:
        run_automated_simulation(root)
    else:
        try:
            run_interactive_cli(root, live=args.live)
        except LLMConfigError as e:
            print(f"❌ {e}", file=sys.stderr)
            return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
