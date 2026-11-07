"""Two-Stage Bio-Inspired Sleep Consolidation & Causal Reflection Engine (NREM + REM)."""
from __future__ import annotations
import json
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, List, Optional
import yaml

from .models import (
    EpisodeDigest,
    UserCommitment,
    CommitmentStatus,
    ProactiveHook,
)
from .memory_store import CognitiveMemoryStore
from .llm_router import DualTierLLMRouter


class SleepConsolidationEngine:
    """
    双阶段仿生睡眠反思引擎：
    - Phase 1 (NREM 浅睡眠 - 轻量模型 Fast Tier):
      将 L0 原始对话清洗为客观【情节切片 EpisodeDigest】，提取字面主张、立下的 Flag 与情绪行为信号。
    - Phase 2 (REM 深度做梦 - 强推理模型 Deep Tier):
      跨天读取多个 EpisodeDigest 与现有长期记忆，执行【言行一致性比对】、【反事实因果溯源】与【证伪检验】，
      更新因果状态机、重编译 L1 工作记忆、生成第一人称审计日记，并自动触发 Git 快照。
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

    def _load_prompt(self, name: str) -> str:
        path = self.prompts_dir / f"{name}.yaml"
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
        return data["system_prompt"]

    def run_nrem_light_sleep(
        self,
        episode_id: Optional[str] = None,
        timestamp_override: Optional[str] = None,
    ) -> Optional[EpisodeDigest]:
        """阶段一：NREM 浅睡眠清洗（使用轻量模型降噪并提取结构化锚点）"""
        raw_turns = self.store.pop_session_buffer()
        if not raw_turns:
            return None

        now_str = timestamp_override or datetime.now().isoformat(timespec="seconds")
        ep_id = episode_id or f"ep_{datetime.now().strftime('%Y%m%d_%H%M%S')}"

        dialogue_text = "\n".join(
            f"[{t['timestamp']}] {t['role'].upper()}: {t['content']}" for t in raw_turns
        )
        sys_prompt = self._load_prompt("nrem_distiller")
        resp_json = self.router.chat_completion(
            tier="fast_tier",
            system_prompt=sys_prompt,
            user_prompt=f"请清洗以下原始对话切片：\n\n{dialogue_text}",
            response_format="json",
            mock_context_hint="nrem",
        )
        parsed = json.loads(resp_json)

        episode = EpisodeDigest(
            episode_id=ep_id,
            timestamp=now_str,
            summary=parsed.get("summary", ""),
            topic_tags=parsed.get("topic_tags", []),
            emotional_valence=parsed.get("emotional_valence", "neutral"),
            explicit_claims=parsed.get("explicit_claims", []),
            behavioral_signals=parsed.get("behavioral_signals", []),
            commitments_made=parsed.get("commitments_made", []),
            raw_messages=raw_turns,
            processed_by_rem=False,
        )
        self.store.save_episode(episode)

        commitments = self.store.load_commitments()
        for idx, c_item in enumerate(episode.commitments_made, start=1):
            c_id = f"cmt_{len(commitments) + idx:03d}"
            commitments.append(
                UserCommitment(
                    commitment_id=c_id,
                    statement=c_item["statement"],
                    created_at=now_str,
                    deadline_hint=c_item.get("deadline_hint", "unspecified"),
                    status=CommitmentStatus.ACTIVE,
                    source_episode_id=ep_id,
                    updated_at=now_str,
                )
            )
        self.store.save_commitments(commitments)
        self.store.compile_working_memory()
        return episode

    def run_rem_deep_dreaming(self, cycle_label: Optional[str] = None) -> Dict[str, Any]:
        """
        阶段二：REM 深度睡眠做梦（使用强推理模型跨周期比对言行、推导深层因果并更新状态机）
        """
        unprocessed = self.store.load_unprocessed_episodes()
        if not unprocessed:
            return {"status": "skipped", "reason": "No unprocessed episodes for REM cycle."}

        cycle_id = cycle_label or datetime.now().strftime("%Y%m%d_%H%M%S")
        existing_beliefs = [b.to_dict() for b in self.store.load_beliefs()]
        existing_commitments = [c.to_dict() for c in self.store.load_commitments()]
        episodes_payload = [ep.to_dict() for ep in unprocessed]

        rem_input = json.dumps(
            {
                "unprocessed_episodes": episodes_payload,
                "existing_causal_beliefs": existing_beliefs,
                "existing_commitments": existing_commitments,
            },
            ensure_ascii=False,
            indent=2,
        )

        sys_prompt = self._load_prompt("rem_reflector")
        resp_json = self.router.chat_completion(
            tier="deep_tier",
            system_prompt=sys_prompt,
            user_prompt=f"请对以下跨周期情节切片与现有信念库进行深度因果反思与言行一致性审计：\n\n{rem_input}",
            response_format="json",
            mock_context_hint="rem",
        )
        rem_result = json.loads(resp_json)
        mutations_log: List[str] = []

        # 1. 更新 Flag / 承诺兑现或借口弃坑状态
        commitments_map = {c.commitment_id: c for c in self.store.load_commitments()}
        for c_upd in rem_result.get("commitment_updates", []):
            cid = c_upd["commitment_id"]
            if cid in commitments_map:
                old_st = commitments_map[cid].status.value
                new_st = CommitmentStatus(c_upd["new_status"].upper())
                commitments_map[cid].status = new_st
                commitments_map[cid].audit_note = c_upd.get("audit_note", "")
                commitments_map[cid].updated_at = datetime.now().isoformat(timespec="seconds")
                mutations_log.append(
                    f"[言行审计] Flag `{cid}` 状态由 `{old_st}` 更新为 `{new_st.value}` | 结论：{c_upd.get('audit_note', '')}"
                )
        self.store.save_commitments(list(commitments_map.values()))

        # 2. 演进长期因果信念状态机（含证伪与双时间线记录）
        for b_mut in rem_result.get("belief_mutations", []):
            log_line = self.store.apply_belief_mutation(b_mut)
            mutations_log.append(log_line)

        # 3. 写入主动破冰关怀钩子
        hooks = self.store.load_hooks()
        now_iso = datetime.now().isoformat(timespec="seconds")
        for h_raw in rem_result.get("proactive_hooks", []):
            hook = ProactiveHook(
                hook_id=h_raw["hook_id"],
                created_at=now_iso,
                trigger_reason=h_raw["trigger_reason"],
                recommended_window=h_raw.get("recommended_window", "anytime"),
                relevance_score=float(h_raw.get("relevance_score", 0.8)),
                timing_urgency=float(h_raw.get("timing_urgency", 0.8)),
                confidence_score=float(h_raw.get("confidence_score", 0.8)),
                intrusion_cost=float(h_raw.get("intrusion_cost", 0.15)),
                icebreaker_draft=h_raw["icebreaker_draft"],
                related_belief_id=h_raw.get("related_belief_id"),
                status="PENDING",
            )
            hooks.append(hook)
            mutations_log.append(
                f"[主动破冰钩子] 生成 `{hook.hook_id}` (综合效用 U={hook.net_utility:.2f}): {hook.trigger_reason}"
            )
        self.store.save_hooks(hooks)

        # 4. 标记情节切片已处理并重编译 L1 置顶工作记忆
        ep_ids = [ep.episode_id for ep in unprocessed]
        self.store.mark_episodes_processed(ep_ids)
        self.store.compile_working_memory()

        # 5. 保存第一人称复盘日记供人类审计
        diary_text = rem_result.get("first_person_diary", "完成了例行跨周期因果反思。")
        diary_path = self.store.save_reflection_diary(cycle_id, diary_text, mutations_log)

        # 6. 自动创建 Git 版本快照（支持一键防幻觉回滚）
        commit_hash = self.store.git_snapshot(f"REM reflection cycle {cycle_id} ({len(ep_ids)} episodes)")

        return {
            "status": "completed",
            "cycle_id": cycle_id,
            "processed_episodes": ep_ids,
            "mutations": mutations_log,
            "diary_path": str(diary_path),
            "diary_text": diary_text,
            "git_commit": commit_hash,
        }