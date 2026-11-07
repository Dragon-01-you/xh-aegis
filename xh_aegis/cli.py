"""CLI entrypoint for `xh-aegis` and `xh` commands."""
from __future__ import annotations
import argparse
from pathlib import Path
from xh_aegis import __version__
from cli_demo import run_automated_simulation, run_interactive_cli


def main() -> int:
    parser = argparse.ArgumentParser(
        prog="xh-aegis",
        description="🔥 芯火·灵镜 XH-Aegis: 零训练热插拔 Agent 记忆与后台反思进化系统",
    )
    parser.add_argument("--version", action="version", version=f"xh-aegis {__version__}")
    parser.add_argument("--auto-demo", action="store_true", help="运行 5 天跨周期言行比对与反事实因果进化演示")
    args = parser.parse_args()

    root = Path(__file__).resolve().parent.parent
    if args.auto_demo:
        run_automated_simulation(root)
    else:
        run_interactive_cli(root)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
