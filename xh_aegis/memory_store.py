"""Four-Tier Cognitive Memory Store with Git Versioned Rollback & Strict Line Budget."""
from __future__ import annotations
import json
import subprocess
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Any

from .models import (
    CausalBelief,
    UserCommitment,
    EpisodeDigest,
    ProactiveHook,
    EpistemicState,
    CommitmentStatus,
    StateTransition,
)


class CognitiveMemoryStore:
    """
    四层记忆存储引擎（本地 Markdown + JSON 双态存储 + Git 认知时间机器）：
    - L0: Raw Session Buffer (内存/短期滑窗)
    - L1: Working Memory (`working_memory.md`，严格限制 < 200 行，常驻系统提示词)
    - L2: Structured Causal Store & Topic Capsules (`causal_beliefs.json`, `commitments.json`, `topics/*.md`)
    - L3: Cold Episodic Archive & Audit Diaries (`episodes/*.json`, `reflections/*.md`, Git Commit Snapshots)
    """

    def __init__(self, data_dir: Path, config: Dict[str, Any]):
        self.data_dir = Path(data_dir)
        self.config = config
        self.topics_dir = self.data_dir / "topics"
        self.episodes_dir = self.data_dir / "episodes"
        self.reflections_dir = self.data_dir / "reflections"

        for d in (self.data_dir, self.topics_dir, self.episodes_dir, self.reflections_dir):
            d.mkdir(parents=True, exist_ok=True)

        self.persona_path = self.data_dir / "persona.md"
        self.working_memory_path = self.data_dir / "working_memory.md"
        self.beliefs_path = self.data_dir / "causal_beliefs.json"
        self.commitments_path = self.data_dir / "commitments.json"
        self.hooks_path = self.data_dir / "proactive_hooks.json"
        self.episodes_index_path = self.episodes_dir / "_index.json"
        self.topics_index_path = self.topics_dir / "_index.json"
        self.reflections_index_path = self.reflections_dir / "_index.json"

        self.session_buffer: List[Dict[str, str]] = []
        self._init_storage_files()
        if self.config.get("system", {}).get("git_auto_snapshot", True):
            self._ensure_git_repo()

    def _init_storage_files(self) -> None:
        if not self.persona_path.exists():
            self.persona_path.write_text("# 核心人设\n你是用户的深度共创伙伴 Aegis。\n", encoding="utf-8")
        for path in (
            self.beliefs_path,
            self.commitments_path,
            self.hooks_path,
            self.episodes_index_path,
            self.topics_index_path,
            self.reflections_index_path,
        ):
            if not path.exists():
                path.write_text("[]", encoding="utf-8")
        if not self.working_memory_path.exists():
            self.compile_working_memory()

    def reset_dynamic_stores(self) -> None:
        """清空动态运行期记忆数据（保留只读 persona.md），用于可重复的仿真测试"""
        for path in (
            self.beliefs_path,
            self.commitments_path,
            self.hooks_path,
            self.episodes_index_path,
            self.topics_index_path,
            self.reflections_index_path,
        ):
            path.write_text("[]", encoding="utf-8")
        self.session_buffer.clear()
        self.compile_working_memory()
        if (self.data_dir / ".git" / "refs" / "heads" / "master").exists():
            try:
                (self.data_dir / ".git" / "refs" / "heads" / "master").unlink()
            except Exception:
                pass
        self.git_snapshot("Initial cognitive memory baseline")

    def _tracked_relative_files(self) -> List[str]:
        rels = [
            "persona.md",
            "working_memory.md",
            "causal_beliefs.json",
            "commitments.json",
            "proactive_hooks.json",
            "episodes/_index.json",
            "topics/_index.json",
            "reflections/_index.json",
        ]
        for ep_id in json.loads(self.episodes_index_path.read_text(encoding="utf-8")):
            rels.append(f"episodes/{ep_id}.json")
        for topic in json.loads(self.topics_index_path.read_text(encoding="utf-8")):
            rels.append(f"topics/{topic}.md")
        for ref_id in json.loads(self.reflections_index_path.read_text(encoding="utf-8")):
            rels.append(f"reflections/{ref_id}.md")
        return [r for r in rels if (self.data_dir / r).exists()]

    def _ensure_git_repo(self) -> None:
        git_dir = self.data_dir / ".git"
        if not (git_dir / "HEAD").exists():
            subprocess.run(["git", "init"], cwd=self.data_dir, capture_output=True, check=False)
            subprocess.run(["git", "config", "user.name", "Aegis Memory Daemon"], cwd=self.data_dir, capture_output=True, check=False)
            subprocess.run(["git", "config", "user.email", "aegis@local.agent"], cwd=self.data_dir, capture_output=True, check=False)
            self.git_snapshot("Initial cognitive memory baseline")

    def git_snapshot(self, message: str) -> Optional[str]:
        """每次后台做梦修改长期记忆后自动生成 Git 快照，支持一行命令回滚模型幻觉投毒"""
        try:
            rel_files = self._tracked_relative_files()
            if not rel_files:
                return None
            subprocess.run(
                ["git", "update-index", "--add", *rel_files],
                cwd=self.data_dir,
                capture_output=True,
                check=True,
            )
            tree_res = subprocess.run(
                ["git", "write-tree"],
                cwd=self.data_dir,
                capture_output=True,
                text=True,
                check=True,
            )
            tree_hash = tree_res.stdout.strip()

            prefix = self.config.get("sleep_daemon", {}).get("audit_git_commit_prefix", "[REM-Cycle]")
            full_msg = f"{prefix} {message}"

            head_check = subprocess.run(
                ["git", "rev-parse", "--verify", "HEAD"],
                cwd=self.data_dir,
                capture_output=True,
                text=True,
                check=False,
            )
            cmd = ["git", "commit-tree", tree_hash, "-m", full_msg]
            if head_check.returncode == 0 and head_check.stdout.strip():
                cmd.extend(["-p", head_check.stdout.strip()])

            commit_res = subprocess.run(
                cmd,
                cwd=self.data_dir,
                capture_output=True,
                text=True,
                check=True,
            )
            commit_hash = commit_res.stdout.strip()
            subprocess.run(
                ["git", "update-ref", "refs/heads/master", commit_hash],
                cwd=self.data_dir,
                capture_output=True,
                check=True,
            )
            return commit_hash[:7]
        except Exception:
            return None

    def get_git_history(self, limit: int = 10) -> List[str]:
        try:
            res = subprocess.run(
                ["git", "log", f"-n{limit}", "--oneline"],
                cwd=self.data_dir,
                capture_output=True,
                text=True,
                check=True,
            )
            return [line.strip() for line in res.stdout.splitlines() if line.strip()]
        except Exception:
            return []

    def rollback_last_snapshot(self) -> bool:
        """一键回滚最近一次后台反思引入的记忆变更"""
        try:
            prev = subprocess.run(
                ["git", "rev-parse", "--verify", "HEAD~1"],
                cwd=self.data_dir,
                capture_output=True,
                text=True,
                check=True,
            ).stdout.strip()
            subprocess.run(
                ["git", "read-tree", "-u", "--reset", prev],
                cwd=self.data_dir,
                capture_output=True,
                check=True,
            )
            subprocess.run(
                ["git", "update-ref", "refs/heads/master", prev],
                cwd=self.data_dir,
                capture_output=True,
                check=True,
            )
            return True
        except Exception:
            return False

    # -------------------- L0: Session Buffer --------------------
    def append_turn(self, role: str, content: str, timestamp: Optional[str] = None) -> None:
        ts = timestamp or datetime.now().isoformat(timespec="seconds")
        self.session_buffer.append({"role": role, "content": content, "timestamp": ts})

    def pop_session_buffer(self) -> List[Dict[str, str]]:
        turns = list(self.session_buffer)
        self.session_buffer.clear()
        return turns

    # -------------------- L2: Causal Beliefs & Commitments --------------------
    def load_beliefs(self) -> List[CausalBelief]:
        raw = json.loads(self.beliefs_path.read_text(encoding="utf-8"))
        return [CausalBelief.from_dict(item) for item in raw]

    def save_beliefs(self, beliefs: List[CausalBelief]) -> None:
        data = [b.to_dict() for b in beliefs]
        self.beliefs_path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")

    def load_commitments(self) -> List[UserCommitment]:
        raw = json.loads(self.commitments_path.read_text(encoding="utf-8"))
        return [UserCommitment.from_dict(item) for item in raw]

    def save_commitments(self, commitments: List[UserCommitment]) -> None:
        data = [c.to_dict() for c in commitments]
        self.commitments_path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")

    def load_hooks(self) -> List[ProactiveHook]:
        raw = json.loads(self.hooks_path.read_text(encoding="utf-8"))
        return [ProactiveHook.from_dict(item) for item in raw]

    def save_hooks(self, hooks: List[ProactiveHook]) -> None:
        data = [h.to_dict() for h in hooks]
        self.hooks_path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")

    # -------------------- L3: Episodes & Diaries --------------------
    def save_episode(self, episode: EpisodeDigest) -> Path:
        path = self.episodes_dir / f"{episode.episode_id}.json"
        path.write_text(json.dumps(episode.to_dict(), ensure_ascii=False, indent=2), encoding="utf-8")
        idx: List[str] = json.loads(self.episodes_index_path.read_text(encoding="utf-8"))
        if episode.episode_id not in idx:
            idx.append(episode.episode_id)
            self.episodes_index_path.write_text(json.dumps(idx, ensure_ascii=False, indent=2), encoding="utf-8")
        return path

    def load_unprocessed_episodes(self) -> List[EpisodeDigest]:
        episodes: List[EpisodeDigest] = []
        idx: List[str] = json.loads(self.episodes_index_path.read_text(encoding="utf-8"))
        for ep_id in idx:
            p = self.episodes_dir / f"{ep_id}.json"
            if p.exists():
                ep = EpisodeDigest.from_dict(json.loads(p.read_text(encoding="utf-8")))
                if not ep.processed_by_rem:
                    episodes.append(ep)
        return episodes

    def mark_episodes_processed(self, episode_ids: List[str]) -> None:
        for ep_id in episode_ids:
            p = self.episodes_dir / f"{ep_id}.json"
            if p.exists():
                data = json.loads(p.read_text(encoding="utf-8"))
                data["processed_by_rem"] = True
                p.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")

    def save_reflection_diary(self, cycle_id: str, diary_text: str, mutations_summary: List[str]) -> Path:
        ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        ref_id = f"rem_diary_{cycle_id}"
        path = self.reflections_dir / f"{ref_id}.md"
        lines = [
            f"# REM 睡眠深度反思日记 ({cycle_id})",
            f"- **生成时间**: {ts}",
            "",
            "## 一、 第一人称认知复盘 (Self-Reflection)",
            diary_text.strip(),
            "",
            "## 二、 本轮记忆与因果信念变更审计 (Memory Mutations)",
        ]
        for m in mutations_summary:
            lines.append(f"- {m}")
        path.write_text("\n".join(lines) + "\n", encoding="utf-8")

        r_idx: List[str] = json.loads(self.reflections_index_path.read_text(encoding="utf-8"))
        if ref_id not in r_idx:
            r_idx.append(ref_id)
            self.reflections_index_path.write_text(json.dumps(r_idx, ensure_ascii=False, indent=2), encoding="utf-8")
        return path

    # -------------------- Epistemic Evolution Engine --------------------
    def apply_belief_mutation(self, mutation: Dict[str, Any], now_iso: Optional[str] = None) -> str:
        """
        核心认知演化逻辑：
        - 新建假说强制受限于 initial_hypothesis_confidence，防止单次脑补定性
        - 已有假说根据新证据增减置信度，自动触发 HYPOTHESIS -> VERIFIED_PATTERN 或 DEPRECATED 状态跃迁
        - 保留完整双时间线演化轨迹 (evolution_history)
        """
        now = now_iso or datetime.now().isoformat(timespec="seconds")
        rules = self.config["epistemic_rules"]
        beliefs = {b.belief_id: b for b in self.load_beliefs()}

        b_id = mutation["belief_id"]
        delta = float(mutation.get("confidence_delta", 0.15))
        reason = mutation.get("evolution_reason", "REM 周期跨天因果归纳更新")
        ev_ids = mutation.get("evidence_episode_ids", [])

        if b_id not in beliefs:
            init_conf = (
                0.80
                if mutation.get("override_state") == "VERIFIED_PATTERN"
                else float(rules["initial_hypothesis_confidence"])
            )
            init_state = (
                EpistemicState(mutation["override_state"])
                if mutation.get("override_state")
                else EpistemicState.HYPOTHESIS
            )
            new_belief = CausalBelief(
                belief_id=b_id,
                topic=mutation.get("topic", "general"),
                state=init_state,
                confidence=round(init_conf, 2),
                surface_pattern=mutation["surface_pattern"],
                latent_causal_mechanism=mutation["latent_causal_mechanism"],
                predicted_next_behavior=mutation["predicted_next_behavior"],
                falsification_condition=mutation["falsification_condition"],
                created_at=now,
                updated_at=now,
                last_verified_at=now,
                evidence_episode_ids=list(ev_ids),
                evolution_history=[
                    StateTransition(
                        timestamp=now,
                        from_state="NONE",
                        to_state=init_state.value,
                        confidence_before=0.0,
                        confidence_after=round(init_conf, 2),
                        reason=reason,
                        evidence_episodes=list(ev_ids),
                    )
                ],
            )
            beliefs[b_id] = new_belief
            self.save_beliefs(list(beliefs.values()))
            self._sync_topic_capsule(new_belief)
            return f"[新增因果认知] `{b_id}` ({init_state.value}, 置信度={init_conf:.2f}): {new_belief.latent_causal_mechanism}"

        existing = beliefs[b_id]
        old_conf = existing.confidence
        old_state = existing.state
        new_conf = max(0.05, min(0.98, round(old_conf + delta, 2)))

        if mutation.get("override_state"):
            new_state = EpistemicState(mutation["override_state"])
        elif new_conf >= float(rules["verified_threshold"]):
            new_state = EpistemicState.VERIFIED_PATTERN
        elif new_conf <= float(rules["deprecation_threshold"]):
            new_state = EpistemicState.DEPRECATED
        elif delta < 0:
            new_state = EpistemicState.CONTESTED
        else:
            new_state = existing.state

        existing.surface_pattern = mutation.get("surface_pattern", existing.surface_pattern)
        existing.latent_causal_mechanism = mutation.get("latent_causal_mechanism", existing.latent_causal_mechanism)
        existing.predicted_next_behavior = mutation.get("predicted_next_behavior", existing.predicted_next_behavior)
        existing.falsification_condition = mutation.get("falsification_condition", existing.falsification_condition)
        existing.confidence = new_conf
        existing.state = new_state
        existing.updated_at = now
        existing.last_verified_at = now
        for eid in ev_ids:
            if eid not in existing.evidence_episode_ids:
                existing.evidence_episode_ids.append(eid)

        existing.evolution_history.append(
            StateTransition(
                timestamp=now,
                from_state=old_state.value,
                to_state=new_state.value,
                confidence_before=old_conf,
                confidence_after=new_conf,
                reason=reason,
                evidence_episodes=list(ev_ids),
            )
        )

        self.save_beliefs(list(beliefs.values()))
        self._sync_topic_capsule(existing)
        return (
            f"[演进因果认知] `{b_id}` 状态 {old_state.value}->{new_state.value} "
            f"(置信度 {old_conf:.2f}->{new_conf:.2f}): {reason}"
        )

    def _sync_topic_capsule(self, belief: CausalBelief) -> None:
        """将结构化因果记忆同步渲染为人类可读的 L2 主题档案 (`data/topics/<topic>.md`)"""
        topic_file = self.topics_dir / f"{belief.topic}.md"
        all_topic_beliefs = [b for b in self.load_beliefs() if b.topic == belief.topic]

        lines = [
            f"# 主题深层认知档案：{belief.topic}",
            "> 自动由 REM 睡眠引擎同步维护 | 包含活跃规律与已证伪/过时的历史演化链",
            "",
        ]
        for b in sorted(all_topic_beliefs, key=lambda x: x.confidence, reverse=True):
            status_badge = "🟢 已印证规律" if b.state == EpistemicState.VERIFIED_PATTERN else (
                "🟡 待验证假说" if b.state == EpistemicState.HYPOTHESIS else "⚪ 已过时/修正"
            )
            lines.extend([
                f"## [{status_badge}] {b.belief_id} (置信度: {b.confidence:.2f} | 状态: `{b.state.value}`)",
                f"- **表面言行模式 (Surface Pattern)**: {b.surface_pattern}",
                f"- **深层因果机制 (Latent Mechanism)**: {b.latent_causal_mechanism}",
                f"- **未来行为预判 (Prediction)**: {b.predicted_next_behavior}",
                f"- **反事实证伪条件 (Falsification Guardrail)**: {b.falsification_condition}",
                f"- **支撑证据切片**: `{', '.join(b.evidence_episode_ids)}`",
                "- **双时间线演化轨迹 (Evolution Timeline)**:",
            ])
            for t in b.evolution_history:
                lines.append(
                    f"  - `{t.timestamp}`: `{t.from_state}` -> `{t.to_state}` "
                    f"({t.confidence_before:.2f} -> {t.confidence_after:.2f}) | 原因：{t.reason}"
                )
            lines.append("")

        topic_file.write_text("\n".join(lines), encoding="utf-8")
        t_idx: List[str] = json.loads(self.topics_index_path.read_text(encoding="utf-8"))
        if belief.topic not in t_idx:
            t_idx.append(belief.topic)
            self.topics_index_path.write_text(json.dumps(t_idx, ensure_ascii=False, indent=2), encoding="utf-8")

    # -------------------- L1: Working Memory Compiler (< 200 Lines) --------------------
    def compile_working_memory(self) -> str:
        """
        将高置信度因果信念与活跃 Flag 编译为置顶核心记忆 `working_memory.md`，
        严格执行行数预算截断（默认 <= 160 行，绝对不超过 200 行红线）。
        """
        budget = self.config["memory_budget"]
        max_lines = int(budget["l1_working_memory_max_lines"])
        max_beliefs = int(budget["l1_max_active_beliefs"])
        max_commitments = int(budget["l1_max_open_commitments"])

        beliefs = self.load_beliefs()
        commitments = self.load_commitments()

        verified = [
            b for b in beliefs
            if b.state == EpistemicState.VERIFIED_PATTERN
        ]
        verified.sort(key=lambda x: x.confidence, reverse=True)

        hypotheses = [
            b for b in beliefs
            if b.state in (EpistemicState.HYPOTHESIS, EpistemicState.CONTESTED)
        ]
        hypotheses.sort(key=lambda x: x.confidence, reverse=True)

        lines: List[str] = [
            "# L1 核心工作记忆快照 (Working Memory Snapshot)",
            f"> 自动编译时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} | 严格受限于 {max_lines} 行预算内",
            "",
            "## 一、 经跨周期印证的深层因果画像 (Verified Causal Patterns)",
        ]

        if not verified:
            lines.append("- *(暂无高置信度定性规律，正处于观察积累期)*")
        else:
            for b in verified[:max_beliefs]:
                lines.extend([
                    f"### 1. [{b.topic}] `{b.belief_id}` (置信度: {b.confidence:.2f})",
                    f"- **表象特征**: {b.surface_pattern}",
                    f"- **深层因果**: {b.latent_causal_mechanism}",
                    f"- **协作预判**: {b.predicted_next_behavior}",
                    f"- **纠偏证伪条件**: {b.falsification_condition}",
                ])

        lines.extend(["", "## 二、 待检验的深层假说 (Active Hypotheses - 仅试探不盲信)"])
        if not hypotheses:
            lines.append("- *(暂无待验证假说)*")
        else:
            for h in hypotheses[:5]:
                lines.extend([
                    f"- **`{h.belief_id}` (置信度: {h.confidence:.2f})**: {h.latent_causal_mechanism} "
                    f"*(证伪边界: {h.falsification_condition})*"
                ])

        lines.extend(["", "## 三、 言行一致性追踪台账 (Commitments & Flags Audit)"])
        if not commitments:
            lines.append("- *(暂无追踪中的 Flag)*")
        else:
            for c in commitments[-max_commitments:]:
                badge = {
                    CommitmentStatus.ACTIVE: "⏳ 进行中",
                    CommitmentStatus.FULFILLED: "✅ 已兑现",
                    CommitmentStatus.ABANDONED_WITH_EXCUSE: "⚠️ 疑似借口弃坑",
                    CommitmentStatus.POSTPONED: "🔄 已顺延",
                    CommitmentStatus.SUPERSEDED: "⏹️ 已替代",
                }.get(c.status, c.status.value)
                note_str = f" | **审计结论**: {c.audit_note}" if c.audit_note else ""
                lines.append(
                    f"- [{badge}] `{c.commitment_id}` ({c.deadline_hint}): {c.statement}{note_str}"
                )

        if len(lines) > max_lines:
            lines = lines[: max_lines - 2] + [
                "",
                f"> [系统截断保护] 已达到 {max_lines} 行上限，更早条目已下沉至 L2 主题档案。",
            ]

        content = "\n".join(lines) + "\n"
        self.working_memory_path.write_text(content, encoding="utf-8")
        return content

    def retrieve_relevant_l2_context(self, query: str) -> str:
        """轻量按需检索：根据用户当前输入匹配相关的 L2 主题档案，避免全量塞入上下文"""
        top_k = int(self.config["memory_budget"].get("l2_topic_retrieval_top_k", 2))
        scored: List[tuple[int, Path]] = []
        q_lower = query.lower()

        t_idx: List[str] = json.loads(self.topics_index_path.read_text(encoding="utf-8"))
        for topic_name in t_idx:
            p = self.topics_dir / f"{topic_name}.md"
            if not p.exists():
                continue
            text = p.read_text(encoding="utf-8")
            score = 0
            for token in ("rust", "go", "重构", "网关", "报错", "生命周期", "flag", "learning", "architecture"):
                if token in q_lower and token in text.lower():
                    score += 2
            if score > 0:
                scored.append((score, p))

        scored.sort(key=lambda x: x[0], reverse=True)
        selected = [p.read_text(encoding="utf-8") for _, p in scored[:top_k]]
        if not selected:
            return "*(当前对话无需额外挂载 L2 历史档案，仅依赖 L1 核心记忆即可)*"
        return "\n\n".join(selected)
