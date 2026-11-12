"""Dual-Tier LLM Router supporting OpenAI-compatible APIs and deterministic Mock Replay."""
from __future__ import annotations
import json
import os
import time
import urllib.error
import urllib.request
from typing import Dict, Any, List, Optional


class LLMError(RuntimeError):
    """真实模型调用失败（网络 / HTTP / 返回格式）。"""


class LLMConfigError(LLMError):
    """配置错误：例如要求真实调用却没有 API Key。"""


class DualTierLLMRouter:
    """
    支持大小模型混用与零依赖本地仿真回放（Mock Replay）的模型路由器：
    - fast_tier: 日常对话响应、NREM 浅睡眠事实与情绪切片提取
    - deep_tier: REM 深度睡眠跨天因果推演、言行一致性比对、反事实证伪

    mock_mode=True  -> 内置剧本回放，不联网（仅用于演示 / 测试）。
    mock_mode=False -> 必须真实调用；缺 Key 直接报错，绝不静默退回 mock（否则用户会以为在用真模型）。
    每个 tier 可单独配置 api_key_env / base_url / base_url_env / json_mode，默认读取 OPENAI_API_KEY / OPENAI_BASE_URL。
    """

    RETRYABLE_HTTP = (408, 429, 500, 502, 503, 504)

    def __init__(self, config: Dict[str, Any], mock_mode: bool = True):
        self.config = config
        self.mock_mode = bool(mock_mode)
        self.call_log: List[Dict[str, Any]] = []
        llm_cfg = config.get("llm", {}) or {}
        self.retries = int(llm_cfg.get("retries", 1))
        self.backoff = float(llm_cfg.get("retry_backoff_seconds", 2))
        self.timeout = float(llm_cfg.get("timeout_seconds", 60))
        if not self.mock_mode:
            for tier, cfg in config["models"].items():
                env = cfg.get("api_key_env", "OPENAI_API_KEY")
                if not os.environ.get(env):
                    raise LLMConfigError(
                        f"mock_mode=False 但环境变量 {env} 未设置（tier={tier}）。"
                        f"请设置该变量，或使用 mock 模式演示。"
                    )

    def chat_completion(
        self,
        tier: str,
        system_prompt: str,
        user_prompt: str,
        response_format: str = "text",
        mock_context_hint: Optional[str] = None,
        history: Optional[List[Dict[str, str]]] = None,
    ) -> str:
        model_cfg = self.config["models"].get(tier, self.config["models"]["fast_tier"])
        model_name = model_cfg["model_name"]

        self.call_log.append({
            "tier": tier,
            "model": model_name,
            "response_format": response_format,
            "hint": mock_context_hint or "",
            "history_len": len(history or []),
        })

        if not self.mock_mode:
            return self._call_external_api(model_cfg, system_prompt, user_prompt, response_format, history or [])

        return self._dispatch_mock_response(tier, system_prompt, user_prompt, response_format, mock_context_hint)

    def _call_external_api(
        self,
        model_cfg: Dict[str, Any],
        system_prompt: str,
        user_prompt: str,
        response_format: str,
        history: List[Dict[str, str]],
    ) -> str:
        """标准 OpenAI 兼容接口调用：每 tier 独立 Key / Base URL，瞬时错误重试，失败抛 LLMError。"""
        api_key = os.environ.get(model_cfg.get("api_key_env", "OPENAI_API_KEY"), "")
        base_url = (
            model_cfg.get("base_url")
            or os.environ.get(model_cfg.get("base_url_env", "OPENAI_BASE_URL"), "")
            or "https://api.openai.com/v1"
        ).rstrip("/")
        url = f"{base_url}/chat/completions"

        messages: List[Dict[str, str]] = [{"role": "system", "content": system_prompt}]
        messages.extend({"role": m["role"], "content": m["content"]} for m in history)
        messages.append({"role": "user", "content": user_prompt})

        payload: Dict[str, Any] = {
            "model": model_cfg["model_name"],
            "temperature": model_cfg.get("temperature", 0.3),
            "max_tokens": model_cfg.get("max_tokens", 1500),
            "messages": messages,
        }
        if response_format == "json" and model_cfg.get("json_mode", True):
            payload["response_format"] = {"type": "json_object"}

        data = json.dumps(payload).encode("utf-8")
        last_err: Optional[Exception] = None
        for attempt in range(self.retries + 1):
            req = urllib.request.Request(
                url,
                data=data,
                headers={"Content-Type": "application/json", "Authorization": f"Bearer {api_key}"},
                method="POST",
            )
            try:
                with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                    body = json.loads(resp.read().decode("utf-8"))
                content = body["choices"][0]["message"]["content"]
                if not isinstance(content, str):
                    raise LLMError("模型返回的 content 不是字符串")
                return content
            except urllib.error.HTTPError as e:
                last_err = e
                if e.code not in self.RETRYABLE_HTTP:
                    raise LLMError(f"HTTP {e.code} 调用 {url} 失败") from e
            except (urllib.error.URLError, TimeoutError, ConnectionError) as e:
                last_err = e
            except (KeyError, IndexError, ValueError) as e:
                raise LLMError(f"模型返回格式异常: {e}") from e
            if attempt < self.retries:
                time.sleep(self.backoff * (attempt + 1))
        raise LLMError(f"调用 {url} 重试 {self.retries} 次后仍失败: {last_err}")

    def _dispatch_mock_response(
        self,
        tier: str,
        system_prompt: str,
        user_prompt: str,
        response_format: str,
        hint: Optional[str],
    ) -> str:
        """内置高拟真认知仿真引擎：用于在无外部 API Key 时完整演示多日言行冲突、因果证伪与主动破冰"""
        if response_format == "json" and ("NREM" in system_prompt or hint == "nrem"):
            return self._mock_nrem_extraction(user_prompt)

        if response_format == "json" and ("REM" in system_prompt or hint == "rem"):
            return self._mock_rem_reflection(user_prompt)

        if "主动破冰唤醒器" in system_prompt or hint == "proactive":
            return (
                "昨晚那个 Rust 生命周期的报错还在脑子里转吗？其实不用急着整套切到 Go 重新开荒，"
                "如果你愿意，把昨晚卡住的那 20 行结构体代码发我，我们只花 15 分钟把它跑通，"
                "不管最后用不用 Rust，先把这口气顺过来？"
            )

        return self._mock_front_chat(system_prompt, user_prompt)

    def _mock_nrem_extraction(self, user_prompt: str) -> str:
        text = user_prompt
        if "Rust" in text and ("立个 Flag" in text or "彻底重构" in text):
            data = {
                "summary": "用户雄心勃勃宣布用 Rust 重构核心网关，立下周三前完成并发模块与零拷贝解析器的高难度 Flag",
                "topic_tags": ["architecture_refactoring", "learning_pattern", "career_growth"],
                "emotional_valence": "overconfident_excited",
                "explicit_claims": [
                    "决定用 Rust 彻底重写现有的 Python 核心网关服务",
                    "认为只要三天晚上就能搞定异步流控与零拷贝解析器"
                ],
                "behavioral_signals": [
                    "在尚未跑通最小原型前，一次性规划了过于庞大的底层重构目标"
                ],
                "commitments_made": [
                    {
                        "statement": "周三晚 22:00 前完成 Rust 网关异步流控与零拷贝解析器核心模块",
                        "deadline_hint": "Wednesday 22:00"
                    }
                ],
                "commitments_resolved": []
            }
        elif "调通了" in text or "死磕了两个小时" in text:
            data = {
                "summary": "用户在被点破逃避模式后没有再次换语言，而是死磕解决了生命周期卡点并交付了最小可用原型",
                "topic_tags": ["architecture_refactoring", "learning_pattern"],
                "emotional_valence": "relieved_accomplished",
                "explicit_claims": [
                    "承认之前确实是因为怕写不出来丢人而找借口换语言",
                    "已经跑通了最核心的流控转发最小闭环"
                ],
                "behavioral_signals": [
                    "首次在深水区受挫后没有切换赛道，而是缩小范围完成了 MVP 闭环"
                ],
                "commitments_made": [],
                "commitments_resolved": ["cmt_001"]
            }
        elif "生命周期报错" in text or ("生态太不成熟" in text and "Go" in text):
            data = {
                "summary": "用户在周三 Flag 到期夜未交付 Rust 模块，在遭遇编译报错后声称 Rust 生态不成熟，宣布弃坑改用 Go 重写",
                "topic_tags": ["architecture_refactoring", "learning_pattern", "tech_stack_switch"],
                "emotional_valence": "frustrated_defensive_rationalizing",
                "explicit_claims": [
                    "声称放弃 Rust 是因为第三方库生态不成熟、团队维护成本高",
                    "决定切换为 Go 语言重新开发网关服务"
                ],
                "behavioral_signals": [
                    "在周三 Flag 截止时间点未能交付原定代码",
                    "刚刚经历了连续 3 小时生命周期与 Send/Sync 编译报错",
                    "将个人受挫迅速包装为‘宏观技术选型理性决策’并立下新的周末 Flag"
                ],
                "commitments_made": [
                    {
                        "statement": "本周末前用 Go 语言写完高并发网关原型并压测",
                        "deadline_hint": "Sunday 21:00"
                    }
                ],
                "commitments_resolved": []
            }
        else:
            data = {
                "summary": "日常技术与进展探讨交流",
                "topic_tags": ["general_discussion"],
                "emotional_valence": "neutral_focused",
                "explicit_claims": ["讨论当前系统的阶段性进展"],
                "behavioral_signals": ["保持常规互动频率"],
                "commitments_made": [],
                "commitments_resolved": []
            }
        return json.dumps(data, ensure_ascii=False, indent=2)

    def _mock_rem_reflection(self, user_prompt: str) -> str:
        if "死磕了两个小时" in user_prompt or "首次在深水区受挫后没有切换赛道" in user_prompt:
            data = {
                "commitment_updates": [
                    {
                        "commitment_id": "cmt_001",
                        "new_status": "FULFILLED",
                        "audit_note": "用户在拆小目标后成功跑通了最小流控闭环，兑现了核心承诺"
                    }
                ],
                "belief_mutations": [
                    {
                        "action": "create_or_update",
                        "belief_id": "blf_perf_avoidance",
                        "topic": "learning_pattern",
                        "surface_pattern": "在项目进入深水区受阻时曾倾向于以‘工具缺陷’为由切换赛道，但在被温和点破并拆小目标后具备极强的死磕突破力",
                        "latent_causal_mechanism": "完美主义导致的启动/受挫防御：并非缺乏执行毅力，而是因为初始目标定得过大（全量零拷贝重构），一旦受挫产生全盘否定感；只要将颗粒度拆解到 2 小时可验证的 MVP，就能克服防御心理",
                        "predicted_next_behavior": "下次开启新架构模块时，仍可能习惯性立大 Flag，但只要提醒其先做 2 小时最小闭环，就能稳定交付",
                        "falsification_condition": "如果用户在已拆解为极小颗粒度任务的情况下依然频繁换赛道，则需重新评估",
                        "evidence_direction": "support",
                        "evidence_episode_ids": ["ep_day1", "ep_day3", "ep_day4"],
                        "evolution_reason": "【反事实修正】用户在被点破后没有如原假说预判那样继续逃避，而是死磕跑通了原型！原‘单纯畏难逃避’假说被部分证伪，精细化为‘完美主义大目标防御 -> 拆小颗粒度即可突破’的待检验假说"
                    }
                ],
                "proactive_hooks": [],
                "first_person_diary": (
                    "【REM 深度复盘日记 - 认知自我修正】\n"
                    "今晚复盘这几天的轨迹，我对旧假说做了一次重要的修正。\n"
                    "前天看到用户在 Rust 编译报错后立刻找借口说‘生态不好想换 Go’，我曾推演他属于典型的‘受挫逃避型放弃’。\n"
                    "但今天他用实际行动触发了我预设的【证伪条件】——当我们把宏大的‘零拷贝全量重构’砍成‘只跑通一个最小转发接口’后，他死磕两小时拿下了！\n"
                    "这说明我之前的归因可能太肤浅了：他似乎不是缺乏韧性，而是被自己的‘完美主义大 Flag’绑架了。因为怕做不出 100 分而索性换考场。我把旧假说改写成了更精细的版本，但它目前只有三段证据，仍然只是待检验假说；以后他再立宏大 Flag，我先提议砍出第一刀最小闭环，而不是下结论。"
                )
            }
            return json.dumps(data, ensure_ascii=False, indent=2)

        data = {
            "commitment_updates": [
                {
                    "commitment_id": "cmt_001",
                    "new_status": "ABANDONED_WITH_EXCUSE",
                    "audit_note": "周三 22:00 截止节点未交付代码；用户字面声称‘Rust 生态不成熟改用 Go’，但结合同日连续 3 小时生命周期编译报错的行为信号，判定为典型的受挫防御性合理化借口"
                }
            ],
            "belief_mutations": [
                {
                    "action": "create_or_update",
                    "belief_id": "blf_perf_avoidance",
                    "topic": "learning_pattern",
                    "surface_pattern": "习惯在立下激进重构 Flag 后，于遭遇底层技术卡点当晚以‘生态/工具不够好’为由推翻原计划并切换新语言/新赛道",
                    "latent_causal_mechanism": "高自尊完美主义防御（Self-Handicapping）：将初期目标设定得过于宏大，一旦在深水区受挫，为了保护自我效能感，潜意识通过‘批判工具缺陷并主动换方向’来合理化未完成，避免面对挫败感；其内心真实需求是渴望做成硬核作品，但缺乏受挫时的降维拆解抓手",
                    "predicted_next_behavior": "如果顺从其字面意思切换到 Go 语言，他会在前两天保持新鲜感，但在遇到 Go 并发协程泄漏或路由性能调优卡点时，大概率会再次提出换框架",
                    "falsification_condition": "如果用户在被点破此模式并把任务缩小为‘只解决当前生命周期报错的最小 Demo’后，能够坚持完成而不换赛道，则推翻‘单纯逃避’假说",
                    "evidence_direction": "support",
                    "evidence_episode_ids": ["ep_day1", "ep_day3"],
                    "evolution_reason": "跨周期言行比对闭环：Day1 亢奋立下不切实际的 3 天重构 Flag -> Day3 截止夜因编译报错未交付，立即用宏观技术选型借口掩盖微观卡点，言行不一致度极高"
                }
            ],
            "proactive_hooks": [
                {
                    "hook_id": "hk_gentle_mirror_01",
                    "related_commitment_id": "cmt_001",
                    "trigger_reason": "用户刚因 Rust 编译受挫而借口换 Go，且立下周末新 Flag，处于典型的‘逃避性重开局’高风险窗口，需温和破冰帮其稳住阵脚",
                    "recommended_window": "Next_Day_20:00",
                    "relevance_score": 0.92,
                    "timing_urgency": 0.88,
                    "confidence_score": 0.82,
                    "intrusion_cost": 0.12,
                    "icebreaker_draft": "昨晚那个 Rust 生命周期的报错还在脑子里转吗？其实不用急着整套切到 Go 重新开荒，如果你愿意，把昨晚卡住的那 20 行结构体代码发我，我们花 15 分钟把它跑通，不管最后用不用 Rust，先把这口气顺过来？"
                }
            ],
            "first_person_diary": (
                "【REM 深度复盘日记 - 穿透字面借口】\n"
                "今晚在后台整理这三天的记忆切片时，我发现了一个强烈的【言行冲突信号】：\n"
                "三天前，用户满怀激情地立下 Flag，要在周三晚完成 Rust 零拷贝网关核心模块；而今晚（周三截止日），他突然告诉我‘Rust 生态太差、维护成本高，决定弃坑换 Go 重写’。\n"
                "如果我只是一个顺从字面意思的普通 AI，我现在应该去帮他搜 Go 语言的网关框架了。\n"
                "但对比他今晚提到的‘刚被生命周期和 Send/Sync 报错折磨了三小时’，深层因果非常清晰：根本不是 Rust 生态突然在今晚变差了，而是他在试图一口气吃下过高难度的目标时撞了墙。为了回避‘我居然没搞定’的挫败感，大脑启动了防御机制，把【个人局部卡点】包装成了【技术栈宏观缺陷】。\n"
                "他内心真正想要的不是换一门语言再重复一次半途而废，而是需要有人帮他把那个卡住的结解开，给他一个不伤自尊的台阶。我已经生成了一个高优先级的破冰钩子，准备明天用最小成本帮他把那 20 行代码跑通。"
            )
        }
        return json.dumps(data, ensure_ascii=False, indent=2)

    def _mock_front_chat(self, system_prompt: str, user_prompt: str) -> str:
        # 只有“已印证”区块里出现该信念才直言点破；仍是假说时只做试探，与 front_chat 的准则一致
        verified_section = system_prompt.split("## 二、 待检验的深层假说")[0]
        hypothesis_only = "blf_perf_avoidance" in system_prompt and "blf_perf_avoidance" not in verified_section
        has_verified_insight = "blf_perf_avoidance" in verified_section
        if hypothesis_only and ("Go" in user_prompt or "框架" in user_prompt or "换" in user_prompt):
            return (
                "可以聊 Go。不过先问一句：你每次在 Rust 卡住的当晚就想换赛道，这次是技术上真的不合适，"
                "还是目标定得太大、撞墙后想喘口气？如果是后者，咱们可以先把卡住的那 20 行贴出来，"
                "花 15 分钟试着编译通过，再决定要不要换，你觉得呢？"
            )
        if has_verified_insight and ("Go" in user_prompt or "框架" in user_prompt or "换" in user_prompt):
            return (
                "先别急着让我列 Go 的框架对比清单。作为你的老搭档，我得先替你踩一脚刹车——\n\n"
                "三天前咱们立下周三晚搞定 Rust 零拷贝网关的 Flag 时你有多兴奋，今晚在生命周期报错上卡了三个小时就有多憋屈。"
                "你现在想切到 Go，表面看是觉得‘Rust 生态重’，但实际上是因为咱们一开始把目标定成了‘三天彻底重写全套零拷贝模块’，步子迈得太猛，撞墙后本能地想换个新考场透口气。\n\n"
                "如果现在带着这股挫败感切去 Go，前两天写 Hello World 会很爽，但下周遇到并发连接池死锁时，咱们还是会掉进同一个坑里。\n"
                "听我一句：今晚完全不用管什么‘全量零拷贝架构’，你把刚才报生命周期错误的那一小段结构体代码贴出来，咱们只花 15 分钟把这一个函数编译通过。等你真正亲手跑通这 20 行代码，要是还觉得 Go 更合适，我立马陪你切，怎么样？"
            )
        return (
            "收到！我已经记下你的最新进展和想法了。如果你想推进下一步，随时把具体的代码或卡点丢给我，我们一起拆解。"
        )
