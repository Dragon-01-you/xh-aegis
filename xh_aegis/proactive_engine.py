"""Utility-Gated Proactive Heartbeat Engine with Anti-Annoyance Circuit Breaker."""
from __future__ import annotations
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, Any, Callable, Optional
import yaml

from .memory_store import CognitiveMemoryStore
from .llm_router import DualTierLLMRouter
from .models import ProactiveHook, EpistemicState
from .util import in_quiet_hours


class ProactiveOutreachEngine:
    """
    有温度且克制的主动唤醒引擎：
    - 多维效用门控：U_wake = V_relevance * U_timing * C_confidence - Cost_intrusion
    - 免打扰时段（支持跨午夜）、两次主动之间的冷却期、连续未回复熔断
    - 熔断计数 / 上次发送时间落盘（proactive_state.json），重启进程不会清零
    - 钩子带过期时间；发出的消息写入发件箱 outbox.jsonl 并进入 L0 对话历史
    - 发给用户的话术模型只会看到用户自己说过的事实，看不到后台对其动机的推断
    """

    def __init__(
        self,
        store: CognitiveMemoryStore,
        router: DualTierLLMRouter,
        prompts_dir: Path,
        config: Dict[str, Any],
        clock: Callable[[], datetime] = datetime.now,
    ):
        self.store = store
        self.router = router
        self.prompts_dir = Path(prompts_dir)
        self.config = config
        self.clock = clock

    # -------- persisted state --------
    @property
    def unanswered_strikes(self) -> int:
        return int(self.store.load_state().get("unanswered_strikes", 0))

    @unanswered_strikes.setter
    def unanswered_strikes(self, value: int) -> None:
        st = self.store.load_state()
        st["unanswered_strikes"] = int(value)
        self.store.save_state(st)

    def record_user_activity(self, now: Optional[datetime] = None) -> None:
        """用户说话了：清零熔断计数。"""
        now = now or self.clock()
        st = self.store.load_state()
        st["unanswered_strikes"] = 0
        st["last_user_message_at"] = now.isoformat(timespec="seconds")
        self.store.save_state(st)

    # -------- helpers --------
    @staticmethod
    def _parse(ts: Optional[str]) -> Optional[datetime]:
        try:
            return datetime.fromisoformat(ts) if ts else None
        except ValueError:
            return None

    def _expire_hooks(self, hooks: list, now: datetime) -> bool:
        changed = False
        for h in hooks:
            exp = self._parse(h.expires_at)
            if h.status == "PENDING" and exp is not None and exp <= now:
                h.status = "EXPIRED"
                changed = True
        return changed

    def _known_facts(self, hook: ProactiveHook) -> str:
        """只给话术模型用户自己说过的承诺原文；已印证(VERIFIED)的信念才允许作为背景，其余推断一律不给。"""
        parts = []
        if hook.related_commitment_id:
            for c in self.store.load_commitments():
                if c.commitment_id == hook.related_commitment_id:
                    parts.append(f"用户说过：{c.statement}（期限：{c.deadline_hint}）")
        if hook.related_belief_id:
            for b in self.store.load_beliefs():
                if b.belief_id == hook.related_belief_id and b.state == EpistemicState.VERIFIED_PATTERN:
                    parts.append(f"已印证的协作规律：{b.predicted_next_behavior}")
        return "；".join(parts) or "(无)"

    # -------- main entry --------
    def evaluate_and_trigger(
        self,
        current_hour: Optional[int] = None,
        now: Optional[datetime] = None,
    ) -> Dict[str, Any]:
        """评估所有待触发钩子，挑选净效用最高且跨过阈值的钩子生成破冰消息。current_hour 仅用于演示时强制指定小时。"""
        rules = self.config["proactive_engine"]
        threshold = float(rules["utility_threshold"])
        max_strikes = int(rules["max_unanswered_strikes"])
        q_start = int(rules["quiet_hours_start"])
        q_end = int(rules["quiet_hours_end"])
        cooldown = float(rules.get("cooldown_hours", 0))

        now = now or self.clock()
        hour = now.hour if current_hour is None else int(current_hour)

        # 1. 免打扰时段
        if in_quiet_hours(hour, q_start, q_end):
            return {
                "triggered": False,
                "reason": f"当前时间 ({hour}:00) 处于免打扰静默窗口 ({q_start}:00 - {q_end:02d}:00)",
            }

        # 2. 连续未回复熔断
        state = self.store.load_state()
        strikes = int(state.get("unanswered_strikes", 0))
        if strikes >= max_strikes:
            return {
                "triggered": False,
                "reason": f"已连续 {strikes} 次主动破冰未获回应，触发防骚扰退避熔断",
            }

        # 3. 冷却期
        last_sent = self._parse(state.get("last_sent_at"))
        if last_sent is not None and now - last_sent < timedelta(hours=cooldown):
            left = timedelta(hours=cooldown) - (now - last_sent)
            return {"triggered": False, "reason": f"距上次主动联系不足 {cooldown:g} 小时，冷却中（还需约 {left.total_seconds() / 3600:.1f} 小时）"}

        hooks = self.store.load_hooks()
        if self._expire_hooks(hooks, now):
            self.store.save_hooks(hooks)
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

        # 4. 生成话术（只喂用户自己说过的事实）
        sys_template = yaml.safe_load(
            (self.prompts_dir / "proactive_outreach.yaml").read_text(encoding="utf-8")
        )["system_prompt"]
        sys_prompt = sys_template.format(
            agent_name=self.config["system"]["agent_name"],
            trigger_reason=best_hook.trigger_reason,
            known_facts=self._known_facts(best_hook),
            icebreaker_draft=best_hook.icebreaker_draft,
        )
        message = (self.router.chat_completion(
            tier="fast_tier",
            system_prompt=sys_prompt,
            user_prompt="请生成此刻发送给用户的破冰消息。",
            response_format="text",
            mock_context_hint="proactive",
        ) or "").strip()
        if not message:
            return {"triggered": False, "reason": "话术模型返回为空，本次不打扰用户"}

        # 5. 发出：状态落盘 + 发件箱 + 进入对话历史
        best_hook.status = "TRIGGERED"
        self.store.save_hooks(hooks)
        state["unanswered_strikes"] = strikes + 1
        state["last_sent_at"] = now.isoformat(timespec="seconds")
        self.store.save_state(state)
        stamp = now.isoformat(timespec="seconds")
        self.store.append_outbox({
            "sent_at": stamp,
            "hook_id": best_hook.hook_id,
            "net_utility": best_hook.net_utility,
            "message": message,
        })
        self.store.append_turn("assistant", message, timestamp=stamp, proactive=True)

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
