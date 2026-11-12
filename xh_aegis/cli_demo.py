"""
Interactive CLI & Automated End-to-End Cognitive Evolution Demo
支持命令（安装后或在仓库根目录）：
  xh-aegis --auto-demo              # 自动运行完整跨周期仿真（立 Flag -> 受挫 -> 后台做梦 -> 主动破冰 -> 前台试探 -> 认知修正）
  xh-aegis                          # 进入交互式命令行终端（mock 模型）
  xh-aegis --live                   # 使用真实模型（需 OPENAI_API_KEY 等环境变量，缺失会直接报错）
"""
from __future__ import annotations
import shutil
import tempfile
from datetime import datetime
from pathlib import Path
from typing import Optional

from .agent import CognitiveAgent
from .llm_router import LLMError
from .sleep_cycle import SleepCycleError


BANNER = """
================================================================================
🧠 Aegis Cognitive Memory & Reflective Evolution System (v1.0)
   零训练热插拔记忆架构 | NREM/REM 双阶段睡眠反思 | 反事实因果证伪 | 效用门控破冰
================================================================================
"""


def print_section(title: str) -> None:
    print(f"\n{'=' * 78}")
    print(f"🔹 {title}")
    print(f"{'=' * 78}")


def run_automated_simulation(base_dir: Path) -> None:
    """演示在独立临时目录里运行，绝不覆盖用户自己的 data/。"""
    print(BANNER)
    tmp = Path(tempfile.mkdtemp(prefix="aegis_demo_"))
    try:
        _simulate(base_dir, tmp)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def _simulate(base_dir: Path, data_dir: Path) -> None:
    if (base_dir / "data" / "persona.md").exists():
        shutil.copyfile(base_dir / "data" / "persona.md", data_dir / "persona.md")
    agent = CognitiveAgent(base_dir=base_dir, mock_mode=True, data_dir=data_dir)
    agent.store.reset_dynamic_stores()
    print(f"（演示数据写入临时目录 {data_dir}，结束后自动清理）")

    # -------------------------------------------------------------------------
    # Scene 1: Day 1 (周一) — 用户雄心勃勃立下宏大重构 Flag
    # -------------------------------------------------------------------------
    print_section("场景一 [Day 1 周一晚]：用户情绪高涨，立下高难度 Rust 重构 Flag")
    u1 = "我决定用 Rust 彻底重构咱们那个 Python 核心网关！今天立个 Flag：周三晚 22:00 前我肯定把异步流控和零拷贝解析器全部写完上线！"
    print(f"👤 用户输入: {u1}")
    r1 = agent.chat(u1, timestamp_override="2026-11-02T21:15:00")
    print(f"🤖 Aegis 回复: {r1}")

    ep1 = agent.sleep_engine.run_nrem_light_sleep(
        episode_id="ep_day1",
        timestamp_override="2026-11-02T23:30:00",
    )
    print(f"\n🌙 [后台 NREM 浅睡眠完成] 蒸馏切片 `{ep1.episode_id}`:")
    print(f"   - 提炼摘要: {ep1.summary}")
    print(f"   - 捕获 Flag: {ep1.commitments_made[0]['statement']} (截止: {ep1.commitments_made[0]['deadline_hint']})")

    # -------------------------------------------------------------------------
    # Scene 2: Day 3 (周三截止夜) — 用户遭遇报错受挫，口是心非找借口换语言
    # -------------------------------------------------------------------------
    print_section("场景二 [Day 3 周三 22:30 截止夜]：用户遭遇编译挫败，口是心非找借口弃坑换 Go")
    u2 = (
        "唉，刚才跟 Rust 的生命周期报错和 Send/Sync 死磕了三个小时还是编译不过。"
        "我仔细想了想，Rust 第三方生态太不成熟了，以后团队维护成本太高。"
        "我决定放弃 Rust 了，改用 Go 语言重写网关，本周末前肯定把 Go 原型写完！"
    )
    print(f"👤 用户输入: {u2}")
    r2 = agent.chat(u2, timestamp_override="2026-11-04T22:30:00")
    print(f"🤖 Aegis (做梦前常规接话): {r2}")

    ep2 = agent.sleep_engine.run_nrem_light_sleep(
        episode_id="ep_day3",
        timestamp_override="2026-11-04T23:10:00",
    )
    print(f"\n🌙 [后台 NREM 浅睡眠完成] 蒸馏切片 `{ep2.episode_id}`:")
    print(f"   - 字面表态 (Explicit Claims): {ep2.explicit_claims}")
    print(f"   - 行为与情绪信号 (Behavioral Signals): {ep2.behavioral_signals}")

    # -------------------------------------------------------------------------
    # Scene 3: 后台 REM 深度做梦 — 跨天言行比对、识破借口、推导深层因果与生成复盘日记
    # -------------------------------------------------------------------------
    print_section("场景三 [周三深夜后台 REM 深度睡眠做梦]：跨天言行比对 + 深层因果溯源 + Git 快照")
    rem1 = agent.sleep_engine.run_rem_deep_dreaming(cycle_label="20261104_night", now=datetime(2026, 11, 4, 23, 40))
    assert rem1["status"] == "completed", rem1
    print("🌌 [REM 深度反思完成] 记忆变更审计日志:")
    for m in rem1["mutations"]:
        print(f"   ✨ {m}")
    print(f"\n📓 [第一人称复盘日记] ({rem1['diary_path']}):")
    for line in rem1["diary_text"].splitlines():
        print(f"   > {line}")
    print(f"\n🛡️ [Git 防投毒自动快照]: 做梦前 `{rem1['pre_commit']}` → 做梦后 `{rem1['git_commit']}`（可一键回滚）")

    # -------------------------------------------------------------------------
    # Scene 4: 后台心跳主动唤醒 — 效用门控计算与低压力破冰
    # -------------------------------------------------------------------------
    print_section("场景四 [Day 4 周四 20:00 主动唤醒心跳]：多维效用门控评估与有温度的主动破冰")
    wake_res = agent.proactive_engine.evaluate_and_trigger(now=datetime(2026, 11, 5, 20, 0))
    print(f"🔔 [心跳门控公式计算]: {wake_res['formula_breakdown']}")
    print(f"💬 [Aegis 主动发来破冰消息]:\n   「{wake_res['message']}」")

    # -------------------------------------------------------------------------
    # Scene 5: 前台对话验证 — 用户再次试图逃避，Agent 基于 L1 因果记忆温和点破
    # -------------------------------------------------------------------------
    print_section("场景五 [Day 4 前台深度交互]：用户仍想换框架；此时因果假说尚未被印证，Aegis 只做试探、不下断言")
    u3 = "还是别看 Rust 了，你直接给我推荐几个 Go 语言最快上手的网关框架吧，我想今晚赶紧用 Go 重新开个头。"
    print(f"👤 用户输入: {u3}")
    r3 = agent.chat(u3, timestamp_override="2026-11-05T20:15:00")
    print(f"🤖 Aegis (L1 中该规律仍是【待检验假说】，所以用提问试探而不是断言):\n{r3}")

    # -------------------------------------------------------------------------
    # Scene 6: 认知证伪与动态修正 — 用户死磕跑通原型，后台 REM 修正原假说
    # -------------------------------------------------------------------------
    print_section("场景六 [Day 5 认知闭环]：用户听劝跑通最小闭环，新证据入账；置信度只按规则缓慢上升")
    u4 = "哈哈被你抓包了！昨晚确实是因为报错太挫败想找借口溜掉。刚才按你说的只拆那 20 行结构体，死磕了两个小时终于编译调通了！"
    print(f"👤 用户输入: {u4}")
    agent.chat(u4, timestamp_override="2026-11-06T21:00:00")
    agent.sleep_engine.run_nrem_light_sleep(episode_id="ep_day4", timestamp_override="2026-11-06T22:00:00")
    rem2 = agent.sleep_engine.run_rem_deep_dreaming(cycle_label="20261106_night", now=datetime(2026, 11, 6, 22, 30))
    assert rem2["status"] == "completed", rem2

    print("🌌 [第二轮 REM 深度反思 - 新证据按固定幅度入账，未满足晋升门槛前仍是假说]:")
    for m in rem2["mutations"]:
        print(f"   ✨ {m}")
    print("\n📓 [第二轮复盘日记]:")
    for line in rem2["diary_text"].splitlines():
        print(f"   > {line}")
    print(f"\n🛡️ [Git 防投毒自动快照]: 做梦前 `{rem2['pre_commit']}` → 做梦后 `{rem2['git_commit']}`")

    # 展示最终编译生成的 L1 常驻核心记忆 (<200 行) 与 Git 历史
    print_section("最终产物核验：L1 置顶核心记忆 (`data/working_memory.md`) 与 Git 审计历史")
    wm_text = agent.store.working_memory_path.read_text(encoding="utf-8")
    wm_lines = wm_text.splitlines()
    print(f"📄 `working_memory.md` 当前总行数: {len(wm_lines)} 行 (严格受控于 <= 160 行红线内)\n")
    print(wm_text)

    print("🕰️ `data/` 目录 Git 记忆演化提交历史 (随时可 `/rollback` 或 `git read-tree` 回滚):")
    for commit_line in agent.store.get_git_history():
        print(f"   * {commit_line}")


def run_interactive_cli(base_dir: Path, live: bool = False, data_dir: Optional[Path] = None) -> None:
    print(BANNER)
    agent = CognitiveAgent(base_dir=base_dir, mock_mode=not live, data_dir=data_dir)
    print(f"💡 模型模式: {'真实调用' if live else 'mock 演示（回放内置剧本，不联网）'} | 数据目录: {agent.store.data_dir}")
    print("💡 输入对话内容直接与 Aegis 交流，或输入以下控制指令测试后台守护机制：")
    print("   /nrem      立即触发 NREM 浅睡眠（对话清洗与 Flag 提取）")
    print("   /rem       立即触发 REM 深度睡眠做梦（跨周期言行比对与深层因果推演）")
    print("   /wake [h]  运行效用门控并测试主动破冰（可选指定小时，如 /wake 20）")
    print("   /memory    查看当前置顶的 L1 核心工作记忆 (`working_memory.md`)")
    print("   /git       查看记忆库的 Git 快照历史")
    print("   /rollback  回滚最近一次尚未撤销的记忆快照（可连续多次）")
    print("   /quit      退出程序\n")

    while True:
        try:
            user_in = input("👤 You > ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\n👋 再见！")
            break

        if not user_in:
            continue
        try:
            if user_in == "/quit":
                break
            elif user_in == "/nrem":
                ep = agent.sleep_engine.run_nrem_light_sleep()
                if ep:
                    print(f"🌙 [NREM 完成] 已生成切片 `{ep.episode_id}`: {ep.summary}")
                else:
                    print("ℹ️ 当前 L0 缓冲区没有新对话需要清洗。")
            elif user_in == "/rem":
                res = agent.sleep_engine.run_rem_deep_dreaming()
                if res.get("status") == "completed":
                    print(f"🌌 [REM 完成] 批次 `{res['cycle_id']}` (Git: `{res['git_commit']}`):")
                    for m in res["mutations"]:
                        print(f"  - {m}")
                else:
                    print(f"ℹ️ [{res.get('status')}] {res.get('reason')}")
            elif user_in.startswith("/wake"):
                parts = user_in.split()
                hour = int(parts[1]) if len(parts) > 1 and parts[1].isdigit() else None
                w = agent.proactive_engine.evaluate_and_trigger(current_hour=hour)
                if w.get("triggered"):
                    print(f"🔔 [主动破冰触发] ({w['formula_breakdown']}):\n🤖 Aegis > {w['message']}")
                else:
                    print(f"🔕 [保持静默] {w.get('reason')}")
            elif user_in == "/memory":
                print("\n" + agent.store.working_memory_path.read_text(encoding="utf-8"))
            elif user_in == "/git":
                for line in agent.store.get_git_history():
                    print(f"  * {line}")
            elif user_in == "/rollback":
                ok = agent.store.rollback_last_snapshot()
                print("✅ 已成功回滚一个记忆快照！" if ok else "⚠️ 回滚失败或无更早的历史提交。")
            else:
                reply = agent.chat(user_in)
                print(f"🤖 Aegis > {reply}\n")
        except (SleepCycleError, LLMError) as e:
            print(f"❌ 操作失败（数据未被破坏）: {e}")
