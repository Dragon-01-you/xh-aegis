"""Main Foreground & Background Coordinator for the Cognitive Memory Agent."""
from __future__ import annotations
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, Optional
import yaml

from .memory_store import CognitiveMemoryStore
from .llm_router import DualTierLLMRouter
from .sleep_cycle import SleepConsolidationEngine
from .proactive_engine import ProactiveOutreachEngine


class CognitiveAgent:
    """
    集成了前台低延迟共创对话、后台 NREM/REM 双阶段睡眠反思、以及效用门控主动破冰的完整 Agent 核心。
    """

    def __init__(self, base_dir: Path, mock_mode: bool = True, data_dir: Optional[Path] = None):
        self.base_dir = Path(base_dir)
        cfg_path = self.base_dir / "config" / "settings.yaml"
        self.config: Dict[str, Any] = yaml.safe_load(cfg_path.read_text(encoding="utf-8"))

        data_dir = Path(data_dir) if data_dir else self.base_dir / self.config["system"]["data_dir"]
        prompts_dir = self.base_dir / "config" / "prompts"

        self.store = CognitiveMemoryStore(data_dir=data_dir, config=self.config)
        self.router = DualTierLLMRouter(config=self.config, mock_mode=mock_mode)
        self.sleep_engine = SleepConsolidationEngine(
            store=self.store,
            router=self.router,
            prompts_dir=prompts_dir,
            config=self.config,
        )
        self.proactive_engine = ProactiveOutreachEngine(
            store=self.store,
            router=self.router,
            prompts_dir=prompts_dir,
            config=self.config,
        )
        self.prompts_dir = prompts_dir

    def chat(self, user_input: str, timestamp_override: Optional[str] = None) -> str:
        """
        前台主对话链路：
        1. 用户开口即重置主动破冰未回复计数（落盘）
        2. 挂载 Persona + L1 常驻核心记忆 (<200行) + 按需检索的 L2 主题胶囊
        3. 带上最近 l0_recent_turns_window 轮真实对话历史调用模型（否则前台模型每轮都是“失忆”的）
        4. 原始对话写入落盘的 L0 缓冲区，等待 NREM 蒸馏
        """
        window = int(self.config["memory_budget"].get("l0_recent_turns_window", 8))
        history = self.store.recent_turns(window * 2)  # N 轮 = 2N 条消息；必须在追加本轮用户消息之前取

        now = datetime.fromisoformat(timestamp_override) if timestamp_override else None
        self.proactive_engine.record_user_activity(now)
        self.store.append_turn("user", user_input, timestamp=timestamp_override)

        persona_md = self.store.persona_path.read_text(encoding="utf-8")
        working_mem_md = self.store.working_memory_path.read_text(encoding="utf-8")
        retrieved_l2 = self.store.retrieve_relevant_l2_context(user_input)

        front_tpl = yaml.safe_load(
            (self.prompts_dir / "front_chat.yaml").read_text(encoding="utf-8")
        )["system_prompt"]

        sys_prompt = front_tpl.format(
            agent_name=self.config["system"]["agent_name"],
            persona_markdown=persona_md,
            working_memory_markdown=working_mem_md,
            retrieved_topic_context=retrieved_l2,
        )

        reply = self.router.chat_completion(
            tier="fast_tier",
            system_prompt=sys_prompt,
            user_prompt=user_input,
            response_format="text",
            history=history,
        )
        self.store.append_turn("assistant", reply, timestamp=timestamp_override)
        return reply
