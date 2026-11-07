## 1. 本次 PR 改了什么？ (Summary)
- 

## 2. 本地验证证据 (Verification Evidence)
- [ ] `ruff check . --select F,E9` 零报错
- [ ] `python3 tests/test_cognitive_memory.py -v` 全部通过
- [ ] `python3 cli_demo.py --auto-demo` 5 天跨周期仿真正常完成且 `working_memory.md` $\le 160$ 行

## 3. 安全与脱敏自检 (Security Checklist)
- [ ] 我已确认本次提交不包含任何真实 API Key（`sk-`, `ghp_`）、私人未脱敏对话或具体客户域名。
