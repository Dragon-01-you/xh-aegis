"""Main Foreground & Background Coordinator for the Cognitive Memory Agent."""
from __future__ import annotations
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

    def __init__(self, base_dir: Path, mock_mode: bool = True):
        self.base_dir = Path(base_dir)
        cfg_path = self.base_dir / "config" / "settings.yaml"
        self.config: Dict[str, Any] = yaml.safe_load(cfg_path.read_text(encoding="utf-8"))

        data_dir = self.base_dir / self.config["system"]["data_dir"]
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
        前台非阻塞主对话链路：
        1. 收到用户消息后重置主动破冰未回复计数
        2. 挂载 Persona + L1 常驻核心记忆 (<200行) + 按需检索的 L2 主题胶囊
        3. 调用模型生成有洞察的回应，并将原始对话追加至 L0 缓冲区
        """
        self.proactive_engine.unanswered_strikes = 0
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
        )
        self.store.append_turn("assistant", reply, timestamp=timestamp_override)
        return reply
