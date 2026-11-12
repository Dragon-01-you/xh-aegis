"""Unit & Integration Tests for the Cognitive Memory & Reflective Evolution System."""
import shutil
import tempfile
import unittest
from pathlib import Path

import sys
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from xh_aegis.agent import CognitiveAgent
from xh_aegis.models import EpistemicState, CommitmentStatus


class TestCognitiveMemorySystem(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp_dir = Path(tempfile.mkdtemp(prefix="aegis_test_"))
        project_root = Path(__file__).resolve().parent.parent
        for rel in (
            "config/settings.yaml",
            "config/prompts/front_chat.yaml",
            "config/prompts/nrem_distiller.yaml",
            "config/prompts/rem_reflector.yaml",
            "config/prompts/proactive_outreach.yaml",
            "data/persona.md",
        ):
            src = project_root / rel
            dst = self.tmp_dir / rel
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(src, dst)
        self.agent = CognitiveAgent(base_dir=self.tmp_dir, mock_mode=True)

    def tearDown(self) -> None:
        shutil.rmtree(self.tmp_dir, ignore_errors=True)

    def test_end_to_end_causal_evolution_and_falsification(self) -> None:
        # 1. Day 1: 立下宏大 Flag
        self.agent.chat("我决定用 Rust 彻底重构核心网关，今天立个 Flag 周三前写完！")
        ep1 = self.agent.sleep_engine.run_nrem_light_sleep(episode_id="ep_day1", timestamp_override="2026-11-02T23:30:00")
        self.assertIsNotNone(ep1)
        commitments = self.agent.store.load_commitments()
        self.assertEqual(len(commitments), 1)
        self.assertEqual(commitments[0].status, CommitmentStatus.ACTIVE)

        # 2. Day 3: 受挫报错后找借口弃坑换 Go
        self.agent.chat("跟生命周期报错死磕了三小时，Rust 生态太不成熟了，我决定换 Go 重写！")
        ep2 = self.agent.sleep_engine.run_nrem_light_sleep(episode_id="ep_day3", timestamp_override="2026-11-04T23:10:00")
        self.assertIsNotNone(ep2)

        # 3. 运行 REM 深度做梦：应识别出 ABANDONED_WITH_EXCUSE 并建立深层因果信念
        rem1 = self.agent.sleep_engine.run_rem_deep_dreaming(cycle_label="cycle_1")
        self.assertEqual(rem1["status"], "completed")

        commitments_after = self.agent.store.load_commitments()
        self.assertEqual(commitments_after[0].status, CommitmentStatus.ABANDONED_WITH_EXCUSE)

        beliefs = self.agent.store.load_beliefs()
        self.assertEqual(len(beliefs), 1)
        self.assertEqual(beliefs[0].belief_id, "blf_perf_avoidance")
        # 单次 REM（2 段证据）只能得到假说：晋升权在规则里，不在模型手里
        self.assertEqual(beliefs[0].state, EpistemicState.HYPOTHESIS)
        self.assertAlmostEqual(beliefs[0].confidence, 0.45)
        self.assertTrue(len(beliefs[0].falsification_condition) > 10)

        # 4. 检验主动唤醒引擎：净效用大于阈值且非免打扰时段应成功触发
        quiet_res = self.agent.proactive_engine.evaluate_and_trigger(current_hour=2)
        self.assertFalse(quiet_res["triggered"])

        wake_res = self.agent.proactive_engine.evaluate_and_trigger(current_hour=20)
        self.assertTrue(wake_res["triggered"])
        self.assertIn("15 分钟", wake_res["message"])

        # 5. 检验 L1 工作记忆行数控制 (< 200 行)
        wm_lines = self.agent.store.working_memory_path.read_text(encoding="utf-8").splitlines()
        self.assertLess(len(wm_lines), 200)

        # 6. 检验反事实修正（Falsification & Evolution History）
        self.agent.chat("刚才按你说的死磕了两个小时，终于把生命周期报错调通了！")
        self.agent.sleep_engine.run_nrem_light_sleep(episode_id="ep_day4", timestamp_override="2026-11-06T22:00:00")
        rem2 = self.agent.sleep_engine.run_rem_deep_dreaming(cycle_label="cycle_2")
        self.assertEqual(rem2["status"], "completed")

        updated_belief = self.agent.store.load_beliefs()[0]
        self.assertEqual(len(updated_belief.evolution_history), 2)
        self.assertEqual(updated_belief.state, EpistemicState.HYPOTHESIS)  # 3 段证据 + 0.67 < 0.75，仍未晋升
        self.assertAlmostEqual(updated_belief.confidence, 0.67)
        self.assertIn("反事实修正", updated_belief.evolution_history[-1].reason)


if __name__ == "__main__":
    unittest.main()
