"""Two-Stage Bio-Inspired Sleep Consolidation & Causal Reflection Engine (NREM + REM)."""
from __future__ import annotations
import json
import re
from datetime import datetime, timedelta
from difflib import SequenceMatcher
from pathlib import Path
from typing import Dict, Any, List, Optional
import yaml

from .models import (
    EpisodeDigest,
    UserCommitment,
    CommitmentStatus,
    EpistemicState,
    ProactiveHook,
)
from .memory_store import CognitiveMemoryStore
from .llm_router import DualTierLLMRouter
from .util import is_safe_id, one_line, parse_json_response


class SleepCycleError(RuntimeError):
    """后台睡眠阶段失败：模型无返回、JSON 非法或结构不合格。失败时不会清空缓冲、不会标记已处理。"""


def _norm(text: str) -> str:
    return re.sub(r"[\s\W_]+", "", text or "").lower()


def _str_list(raw: Any, limit: int = 8, max_len: int = 300) -> List[str]:
    if not isinstance(raw, list):
        return []
    return [one_line(x, max_len) for x in raw if isinstance(x, (str, int, float)) and str(x).strip()][:limit]


class SleepConsolidationEngine:
    """
    双阶段仿生睡眠反思引擎：
    - Phase 1 (NREM 浅睡眠 - 轻量模型 Fast Tier):
      将 L0 原始对话清洗为客观【情节切片 EpisodeDigest】，提取字面主张、立下的 Flag 与情绪行为信号。
    - Phase 2 (REM 深度做梦 - 强推理模型 Deep Tier):
      跨天读取多个 EpisodeDigest 与现有长期记忆，执行【言行一致性比对】、【反事实因果溯源】与【证伪检验】，
      更新因果状态机、重编译 L1 工作记忆、生成第一人称审计日记，并自动触发 Git 快照。

    可靠性约定：模型输出必须通过结构校验才会落盘；任何一步失败都不会吞掉用户对话、
    也不会把情节标记为"已反思"。REM 前后各打一个 Git 快照，中途异常自动回退。
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

    # ------------------------------------------------------------------ NREM
    def _validate_nrem(self, parsed: Any) -> Dict[str, Any]:
        if not isinstance(parsed, dict):
            raise SleepCycleError("NREM 输出不是 JSON 对象")
        summary = one_line(parsed.get("summary", ""), 500)
        if not summary:
            raise SleepCycleError("NREM 输出缺少 summary")
        commitments: List[Dict[str, str]] = []
        raw_c = parsed.get("commitments_made", [])
        if isinstance(raw_c, list):
            for item in raw_c[:5]:
                if isinstance(item, dict) and str(item.get("statement", "")).strip():
                    commitments.append({
                        "statement": one_line(item["statement"], 300),
                        "deadline_hint": one_line(item.get("deadline_hint", "unspecified"), 60),
                    })
        known = {c.commitment_id for c in self.store.load_commitments()}
        resolved = [c for c in _str_list(parsed.get("commitments_resolved"), 10, 40) if c in known]
        return {
            "summary": summary,
            "topic_tags": [t for t in _str_list(parsed.get("topic_tags"), 6, 40)],
            "emotional_valence": one_line(parsed.get("emotional_valence", "neutral"), 60),
            "explicit_claims": _str_list(parsed.get("explicit_claims")),
            "behavioral_signals": _str_list(parsed.get("behavioral_signals")),
            "commitments_made": commitments,
            "commitments_resolved": resolved,
        }

    def _unique_episode_id(self, requested: Optional[str]) -> str:
        if requested:
            if not is_safe_id(requested):
                raise ValueError(f"非法 episode_id: {requested!r}")
            if self.store.episode_exists(requested):
                raise ValueError(f"episode_id `{requested}` 已存在，拒绝覆盖历史切片")
            return requested
        base = f"ep_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        ep_id, n = base, 1
        while self.store.episode_exists(ep_id):
            n += 1
            ep_id = f"{base}_{n}"
        return ep_id

    def run_nrem_light_sleep(
        self,
        episode_id: Optional[str] = None,
        timestamp_override: Optional[str] = None,
    ) -> Optional[EpisodeDigest]:
        """阶段一：NREM 浅睡眠清洗。先校验再落盘，成功后才从 L0 缓冲区移除这批对话。"""
        raw_turns = self.store.peek_session_buffer()
        if not raw_turns:
            return None

        now_str = timestamp_override or datetime.now().isoformat(timespec="seconds")
        ep_id = self._unique_episode_id(episode_id)

        dialogue_text = "\n".join(
            f"[{t.get('timestamp', '')}] {str(t.get('role', '')).upper()}: {t.get('content', '')}" for t in raw_turns
        )
        open_cmts = [
            f"- {c.commitment_id}: {c.statement}" for c in self.store.load_commitments()
            if c.status in (CommitmentStatus.ACTIVE, CommitmentStatus.POSTPONED)
        ]
        cmt_block = ("\n\n【进行中的承诺（commitments_resolved 只能引用这里的 ID）】\n" + "\n".join(open_cmts)) if open_cmts else ""
        resp = self.router.chat_completion(
            tier="fast_tier",
            system_prompt=self._load_prompt("nrem_distiller"),
            user_prompt=f"请清洗以下原始对话切片：\n\n{dialogue_text}{cmt_block}",
            response_format="json",
            mock_context_hint="nrem",
        )
        try:
            data = self._validate_nrem(parse_json_response(resp))
        except ValueError as e:
            raise SleepCycleError(f"NREM 输出无法解析: {e}（对话仍保留在 L0 缓冲区）") from e

        episode = EpisodeDigest(
            episode_id=ep_id,
            timestamp=now_str,
            summary=data["summary"],
            topic_tags=data["topic_tags"],
            emotional_valence=data["emotional_valence"],
            explicit_claims=data["explicit_claims"],
            behavioral_signals=data["behavioral_signals"],
            commitments_made=data["commitments_made"],
            raw_messages=raw_turns,
            processed_by_rem=False,
            commitments_resolved=data["commitments_resolved"],
        )
        self.store.save_episode(episode)

        # 承诺入账：与仍在进行的承诺近似重复则跳过，避免同一句话被反复记成新 Flag
        commitments = self.store.load_commitments()
        open_norms = [
            _norm(c.statement) for c in commitments
            if c.status in (CommitmentStatus.ACTIVE, CommitmentStatus.POSTPONED)
        ]
        max_num = max(
            (int(m.group(1)) for c in commitments if (m := re.fullmatch(r"cmt_(\d+)", c.commitment_id))),
            default=0,
        )
        for c_item in episode.commitments_made:
            n = _norm(c_item["statement"])
            if any(SequenceMatcher(None, n, o).ratio() >= 0.8 for o in open_norms):
                continue
            max_num += 1
            open_norms.append(n)
            commitments.append(
                UserCommitment(
                    commitment_id=f"cmt_{max_num:03d}",
                    statement=c_item["statement"],
                    created_at=now_str,
                    deadline_hint=c_item.get("deadline_hint", "unspecified"),
                    status=CommitmentStatus.ACTIVE,
                    source_episode_id=ep_id,
                    updated_at=now_str,
                )
            )
        self.store.save_commitments(commitments)
        self.store.consume_turns(len(raw_turns))
        self.store.compile_working_memory()
        return episode

    # ------------------------------------------------------------------ REM
    def should_run_rem(self) -> bool:
        need = int(self.config.get("sleep_daemon", {}).get("deep_rem_min_episodes", 2))
        return len(self.store.load_unprocessed_episodes()) >= need

    @staticmethod
    def _episode_for_rem(ep: EpisodeDigest) -> Dict[str, Any]:
        """送进深度模型的是蒸馏后的切片，不带 raw_messages 原文（省 token，也减少原文里的注入面）。"""
        d = ep.to_dict()
        d.pop("raw_messages", None)
        d.pop("processed_by_rem", None)
        return d

    def run_rem_deep_dreaming(
        self,
        cycle_label: Optional[str] = None,
        now: Optional[datetime] = None,
    ) -> Dict[str, Any]:
        """
        阶段二：REM 深度睡眠。返回 status: completed / skipped / failed。
        failed 时：未写入任何长期记忆，情节保持未处理，下次可重试。
        """
        unprocessed = self.store.load_unprocessed_episodes()
        if not unprocessed:
            return {"status": "skipped", "reason": "No unprocessed episodes for REM cycle."}

        now = now or datetime.now()
        now_iso = now.isoformat(timespec="seconds")
        cycle_id = cycle_label or now.strftime("%Y%m%d_%H%M%S")

        existing_beliefs = [
            {k: v for k, v in b.to_dict().items() if k != "evolution_history"}
            for b in self.store.load_beliefs() if b.state != EpistemicState.DEPRECATED
        ]
        rem_input = json.dumps(
            {
                "unprocessed_episodes": [self._episode_for_rem(ep) for ep in unprocessed],
                "existing_causal_beliefs": existing_beliefs,
                "existing_commitments": [c.to_dict() for c in self.store.load_commitments()],
            },
            ensure_ascii=False,
            indent=2,
        )

        try:
            resp = self.router.chat_completion(
                tier="deep_tier",
                system_prompt=self._load_prompt("rem_reflector"),
                user_prompt=f"请对以下跨周期情节切片与现有信念库进行深度因果反思与言行一致性审计：\n\n{rem_input}",
                response_format="json",
                mock_context_hint="rem",
            )
            rem_result = parse_json_response(resp)
        except Exception as e:  # 网络 / 格式错误：不动任何记忆
            return {"status": "failed", "reason": f"REM 模型调用或解析失败: {e}"}
        if not isinstance(rem_result, dict):
            return {"status": "failed", "reason": "REM 输出不是 JSON 对象"}
        if not any(k in rem_result for k in ("commitment_updates", "belief_mutations", "proactive_hooks", "first_person_diary")):
            return {"status": "failed", "reason": "REM 输出不含任何约定字段（疑似空结果），本轮不标记已处理"}

        pre_commit = self.store.git_snapshot(f"pre-REM {cycle_id}")
        try:
            outcome = self._apply_rem_result(rem_result, unprocessed, cycle_id, now, now_iso)
        except Exception as e:
            if pre_commit:
                self.store.discard_changes_since_snapshot()
            return {"status": "failed", "reason": f"REM 落盘中途异常，已回退到快照 {pre_commit}: {e}"}

        outcome["git_commit"] = self.store.git_snapshot(f"REM reflection cycle {cycle_id} ({len(unprocessed)} episodes)")
        outcome["pre_commit"] = pre_commit
        return outcome

    def _apply_rem_result(
        self,
        rem_result: Dict[str, Any],
        unprocessed: List[EpisodeDigest],
        cycle_id: str,
        now: datetime,
        now_iso: str,
    ) -> Dict[str, Any]:
        mutations_log: List[str] = []

        # 1. 承诺状态：枚举值与 ID 必须合法；只有进行中 / 顺延的承诺才允许被裁决；审计结论不能为空
        commitments = self.store.load_commitments()
        cmap = {c.commitment_id: c for c in commitments}
        for c_upd in rem_result.get("commitment_updates", []) or []:
            if not isinstance(c_upd, dict):
                continue
            cid = str(c_upd.get("commitment_id", ""))
            try:
                new_st = CommitmentStatus(str(c_upd.get("new_status", "")).upper())
            except ValueError:
                mutations_log.append(f"[拒绝] Flag `{cid}` 非法状态 {c_upd.get('new_status')!r}")
                continue
            note = one_line(c_upd.get("audit_note", ""), 400)
            c = cmap.get(cid)
            if c is None:
                mutations_log.append(f"[拒绝] 不存在的 Flag `{cid}`")
            elif c.status not in (CommitmentStatus.ACTIVE, CommitmentStatus.POSTPONED):
                mutations_log.append(f"[忽略] Flag `{cid}` 已是 `{c.status.value}`，不重复裁决")
            elif new_st == CommitmentStatus.ACTIVE or not note:
                mutations_log.append(f"[拒绝] Flag `{cid}` 缺少审计结论或状态未变化")
            else:
                old = c.status.value
                c.status, c.audit_note, c.updated_at = new_st, note, now_iso
                mutations_log.append(f"[言行审计] Flag `{cid}` 状态由 `{old}` 更新为 `{new_st.value}` | 结论：{note}")
        self.store.save_commitments(commitments)

        # 2. 因果信念：全部交给 store 的确定性规则裁决
        for b_mut in rem_result.get("belief_mutations", []) or []:
            mutations_log.append(self.store.apply_belief_mutation(b_mut, now_iso=now_iso))

        # 3. 主动关怀钩子：必须锚定真实存在的承诺或信念；置信度被锚点封顶；同一锚点不重复排队
        beliefs = {b.belief_id: b for b in self.store.load_beliefs()}
        cmt_ids = {c.commitment_id for c in self.store.load_commitments()}
        hooks = self.store.load_hooks()
        ttl = int(self.config.get("proactive_engine", {}).get("hook_ttl_hours", 72))
        for h_raw in rem_result.get("proactive_hooks", []) or []:
            if not isinstance(h_raw, dict):
                continue
            cid = h_raw.get("related_commitment_id")
            bid = h_raw.get("related_belief_id")
            cid = cid if cid in cmt_ids else None
            belief = beliefs.get(bid) if isinstance(bid, str) else None
            if belief is not None and belief.state == EpistemicState.DEPRECATED:
                belief = None
            if cid is None and belief is None:
                mutations_log.append("[拒绝钩子] 未锚定到真实的承诺或信念")
                continue
            if not str(h_raw.get("icebreaker_draft", "")).strip() or not str(h_raw.get("trigger_reason", "")).strip():
                mutations_log.append("[拒绝钩子] 缺少 trigger_reason 或 icebreaker_draft")
                continue
            if any(
                h.status == "PENDING" and h.related_commitment_id == cid and h.related_belief_id == (belief.belief_id if belief else None)
                for h in hooks
            ):
                mutations_log.append("[忽略钩子] 同一锚点已有待触发钩子")
                continue

            def clamp(key: str, default: float) -> float:
                try:
                    return max(0.0, min(1.0, float(h_raw.get(key, default))))
                except (TypeError, ValueError):
                    return default

            conf = clamp("confidence_score", 0.5)
            if belief is not None:
                conf = min(conf, belief.confidence)  # 模型自评的把握度不得高于该信念的真实置信度
            hook_id = str(h_raw.get("hook_id", "")).strip()
            existing_ids = {h.hook_id for h in hooks}
            if not is_safe_id(hook_id) or hook_id in existing_ids:
                n = len(hooks) + 1
                while f"hk_{n:03d}" in existing_ids:
                    n += 1
                hook_id = f"hk_{n:03d}"
            hook = ProactiveHook(
                hook_id=hook_id,
                created_at=now_iso,
                trigger_reason=one_line(h_raw["trigger_reason"], 300),
                recommended_window=one_line(h_raw.get("recommended_window", "anytime"), 40),
                relevance_score=clamp("relevance_score", 0.5),
                timing_urgency=clamp("timing_urgency", 0.5),
                confidence_score=conf,
                intrusion_cost=clamp("intrusion_cost", 0.3),
                icebreaker_draft=one_line(h_raw["icebreaker_draft"], 400),
                related_belief_id=belief.belief_id if belief else None,
                related_commitment_id=cid,
                status="PENDING",
                expires_at=(now + timedelta(hours=ttl)).isoformat(timespec="seconds"),
            )
            hooks.append(hook)
            mutations_log.append(
                f"[主动破冰钩子] 生成 `{hook.hook_id}` (综合效用 U={hook.net_utility:.2f}): {hook.trigger_reason}"
            )
        self.store.save_hooks(hooks)

        # 4. 全部成功后才标记已处理并重编译 L1
        ep_ids = [ep.episode_id for ep in unprocessed]
        self.store.mark_episodes_processed(ep_ids)
        self.store.compile_working_memory()

        # 5. 第一人称复盘日记（只给人看，不回灌模型）
        diary_text = str(rem_result.get("first_person_diary") or "完成了例行跨周期因果反思。")
        diary_path = self.store.save_reflection_diary(cycle_id, diary_text, mutations_log)

        return {
            "status": "completed",
            "cycle_id": cycle_id,
            "processed_episodes": ep_ids,
            "mutations": mutations_log,
            "diary_path": str(diary_path),
            "diary_text": diary_text,
        }
