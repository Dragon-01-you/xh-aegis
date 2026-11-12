"""Data schemas and epistemic state machines for the Cognitive Memory System."""
from __future__ import annotations
from dataclasses import dataclass, field, asdict, fields
from enum import Enum
from typing import List, Optional, Dict, Any


class EpistemicState(str, Enum):
    """认知信念演化状态机（防止单次脑补直接固化为绝对真理）"""
    OBSERVATION = "OBSERVATION"            # L0/L1 客观言行切片（未做深层归因）
    HYPOTHESIS = "HYPOTHESIS"              # 后台初筛推演出的因果假说（新建恒为 initial_hypothesis_confidence，仅观察不盲信）
    VERIFIED_PATTERN = "VERIFIED_PATTERN"  # 跨周期多次言行印证的深层规律（Confidence >= 0.75，置顶入 L1）
    CONTESTED = "CONTESTED"                # 近期出现反例、处于摇摆修正期的规律
    DEPRECATED = "DEPRECATED"              # 已过时或被证伪的历史规律（归档入 L3，保留演化链）


class CommitmentStatus(str, Enum):
    """用户立下的 Flag / 承诺状态追踪"""
    ACTIVE = "ACTIVE"                                # 进行中待检验
    FULFILLED = "FULFILLED"                          # 言行一致已兑现
    POSTPONED = "POSTPONED"                          # 合理顺延
    ABANDONED_WITH_EXCUSE = "ABANDONED_WITH_EXCUSE"  # 疑似找借口弃坑（触发因果深挖）
    SUPERSEDED = "SUPERSEDED"                        # 被更高优目标替代


@dataclass
class StateTransition:
    """双时间线轨迹：记录认知状态或信念每次演化的原因与证据"""
    timestamp: str
    from_state: str
    to_state: str
    confidence_before: float
    confidence_after: float
    reason: str
    evidence_episodes: List[str] = field(default_factory=list)


@dataclass
class CausalBelief:
    """结构化长期因果记忆节点（超越原话记录，包含表象、深层因果、预判与证伪条件）"""
    belief_id: str
    topic: str
    state: EpistemicState
    confidence: float
    surface_pattern: str             # 用户表象与常见原话模式
    latent_causal_mechanism: str     # 推演出的深层因果机制 / 真实意图
    predicted_next_behavior: str     # 对未来行为的预判
    falsification_condition: str     # 【核心风控】证伪条件：出现什么情况说明此推演错误
    created_at: str
    updated_at: str
    last_verified_at: Optional[str] = None
    evidence_episode_ids: List[str] = field(default_factory=list)
    superseded_by: Optional[str] = None
    evolution_history: List[StateTransition] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        data = asdict(self)
        data["state"] = self.state.value
        return data

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "CausalBelief":
        transitions = [
            StateTransition(**t) if isinstance(t, dict) else t
            for t in data.get("evolution_history", [])
        ]
        return cls(
            belief_id=data["belief_id"],
            topic=data["topic"],
            state=EpistemicState(data["state"]),
            confidence=float(data["confidence"]),
            surface_pattern=data["surface_pattern"],
            latent_causal_mechanism=data["latent_causal_mechanism"],
            predicted_next_behavior=data["predicted_next_behavior"],
            falsification_condition=data["falsification_condition"],
            created_at=data["created_at"],
            updated_at=data["updated_at"],
            last_verified_at=data.get("last_verified_at"),
            evidence_episode_ids=list(data.get("evidence_episode_ids", [])),
            superseded_by=data.get("superseded_by"),
            evolution_history=transitions,
        )


@dataclass
class UserCommitment:
    """言行一致性校验锚点：追踪用户立下的 Flag 与实际行动对比"""
    commitment_id: str
    statement: str
    created_at: str
    deadline_hint: str
    status: CommitmentStatus = CommitmentStatus.ACTIVE
    source_episode_id: str = ""
    audit_note: str = ""
    updated_at: str = ""

    def to_dict(self) -> Dict[str, Any]:
        data = asdict(self)
        data["status"] = self.status.value
        return data

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "UserCommitment":
        return cls(
            commitment_id=data["commitment_id"],
            statement=data["statement"],
            created_at=data["created_at"],
            deadline_hint=data.get("deadline_hint", ""),
            status=CommitmentStatus(data.get("status", "ACTIVE")),
            source_episode_id=data.get("source_episode_id", ""),
            audit_note=data.get("audit_note", ""),
            updated_at=data.get("updated_at", data["created_at"]),
        )


@dataclass
class EpisodeDigest:
    """NREM 浅睡眠生成的单次会话蒸馏切片"""
    episode_id: str
    timestamp: str
    summary: str
    topic_tags: List[str]
    emotional_valence: str
    explicit_claims: List[str]
    behavioral_signals: List[str]
    commitments_made: List[Dict[str, str]]
    raw_messages: List[Dict[str, str]] = field(default_factory=list)
    processed_by_rem: bool = False
    commitments_resolved: List[str] = field(default_factory=list)  # NREM 声称已完成的承诺 ID，仅作线索交给 REM 裁决

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "EpisodeDigest":
        known = {f.name for f in fields(cls)}
        return cls(**{k: v for k, v in data.items() if k in known})


@dataclass
class ProactiveHook:
    """后台做梦生成的待关心/主动唤醒钩子"""
    hook_id: str
    created_at: str
    trigger_reason: str
    recommended_window: str
    relevance_score: float       # V_relevance (0~1)
    timing_urgency: float        # U_timing (0~1)
    confidence_score: float      # C_confidence (0~1)
    intrusion_cost: float        # Cost_intrusion (0~1)
    icebreaker_draft: str
    related_belief_id: Optional[str] = None
    status: str = "PENDING"      # PENDING / TRIGGERED / EXPIRED / SUPPRESSED
    related_commitment_id: Optional[str] = None  # 钩子必须锚定在用户自己说过的承诺或已有信念上
    expires_at: Optional[str] = None             # 过期未触发的钩子自动作废，避免一周后还追问旧事

    @property
    def net_utility(self) -> float:
        """计算主动唤醒综合净效用：U = V * U_timing * C - Cost_intrusion"""
        raw = (self.relevance_score * self.timing_urgency * self.confidence_score) - self.intrusion_cost
        return round(raw, 4)

    def to_dict(self) -> Dict[str, Any]:
        data = asdict(self)
        data["net_utility"] = self.net_utility
        return data

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ProactiveHook":
        known = {f.name for f in fields(cls)}
        return cls(**{k: v for k, v in data.items() if k in known})
