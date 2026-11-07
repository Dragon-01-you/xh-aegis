"""Utility-Gated Proactive Heartbeat Engine with Anti-Annoyance Circuit Breaker."""
from __future__ import annotations
from pathlib import Path
from typing import Dict, Any, Optional
import yaml

from .memory_store import CognitiveMemoryStore
from .llm_router import DualTierLLMRouter
from .models import ProactiveHook


class ProactiveOutreachEngine:
    """
    有温度且克制的主动唤醒引擎：
    - 摒弃简单的定时 Cron 硬发消息，采用多维效用门控：
      U_wake = V_relevance * U_timing * C_confidence - Cost_intrusion
    - 内置免打扰时段（Quiet Hours）与连续未回复熔断机制（Circuit Breaker）
    """

    def __init__(
        self,
        store: CognitiveMemoryStore,
        router: DualTierLLMRouter,
        prompts_dir: Path,
        config: Dict[str, Any],
    ):
        self.store = store
        self.router = router
        self.prompts_dir = Path(prompts_dir)
        self.config = config
        self.unanswered_strikes = 0

    def evaluate_and_trigger(self, current_hour: int = 20) -> Optional[Dict[str, Any]]:
        """评估所有待触发钩子，挑选净效用最高且跨过阈值的钩子生成破冰消息"""
        rules = self.config["proactive_engine"]
        threshold = float(rules["utility_threshold"])
        max_strikes = int(rules["max_unanswered_strikes"])
        q_start = int(rules["quiet_hours_start"])
        q_end = int(rules["quiet_hours_end"])

        # 1. 免打扰时段检查
        if current_hour >= q_start or current_hour < q_end:
            return {
                "triggered": False,
                "reason": f"当前时间 ({current_hour}:00) 处于免打扰静默窗口 ({q_start}:00 - {q_end:02d}:00)",
            }

        # 2. 连续未回复熔断检查
        if self.unanswered_strikes >= max_strikes:
            return {
                "triggered": False,
                "reason": f"已连续 {self.unanswered_strikes} 次主动破冰未获回应，触发防骚扰退避熔断",
            }

        hooks = self.store.load_hooks()
        pending = [h for h in hooks if h.status == "PENDING"]
        if not pending:
            return {"triggered": False, "reason": "当前无待触发的主动关怀钩子"}

        pending.sort(key=lambda x: x.net_utility, reverse=True)
        best_hook: ProactiveHook = pending[0]

        if best_hook.net_utility < threshold:
            return {
                "triggered": False,
                "reason": (
                    f"最高候选钩子 `{best_hook.hook_id}` 净效用 ({best_hook.net_utility:.2f}) "
                    f"低于唤醒门槛 ({threshold:.2f})，保持安静"
                ),
            }

        # 3. 满足唤醒门槛，调用轻量模型结合最新工作记忆润色破冰话术
        prompt_path = self.prompts_dir / "proactive_outreach.yaml"
        sys_template = yaml.safe_load(prompt_path.read_text(encoding="utf-8"))["system_prompt"]
        working_mem = self.store.working_memory_path.read_text(encoding="utf-8")

        sys_prompt = sys_template.format(
            agent_name=self.config["system"]["agent_name"],
            trigger_reason=best_hook.trigger_reason,
            latent_context=working_mem,
            icebreaker_draft=best_hook.icebreaker_draft,
        )

        message = self.router.chat_completion(
            tier="fast_tier",
            system_prompt=sys_prompt,
            user_prompt="请生成此刻发送给用户的破冰消息。",
            response_format="text",
            mock_context_hint="proactive",
        )

        best_hook.status = "TRIGGERED"
        self.store.save_hooks(hooks)
        self.unanswered_strikes += 1

        return {
            "triggered": True,
            "hook_id": best_hook.hook_id,
            "net_utility": best_hook.net_utility,
            "formula_breakdown": (
                f"V({best_hook.relevance_score:.2f}) * T({best_hook.timing_urgency:.2f}) * "
                f"C({best_hook.confidence_score:.2f}) - Cost({best_hook.intrusion_cost:.2f}) = {best_hook.net_utility:.2f} >= {threshold:.2f}"
            ),
            "trigger_reason": best_hook.trigger_reason,
            "message": message,
        }
