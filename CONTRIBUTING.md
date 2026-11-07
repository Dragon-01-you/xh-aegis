# 参与贡献指南 (Contributing to XH-Aegis)

感谢你对 **芯火·灵镜 XH-Aegis (`xh-aegis`)** 的关注与贡献！为了保持代码库的高可靠性与门面质量，请遵循以下五步提交流程与安全铁律。

## 1. 提交流程 (5-Step PR Workflow)

1. Fork 本仓库并从 `main` 创建功能分支（例如 `feat/sqlite-l3-search` 或 `fix/rem-confidence-decay`）。
2. 保持修改聚焦：每次 PR 只解决一个明确的架构或工程问题。
3. 如果新增或修改了 Prompt 模板，请同步更新 `config/prompts/*.yaml` 与 `xh_aegis/llm_router.py` 中的离线仿真回放用例。
4. 在本地运行全量验证命令（见下方），确保单元测试、端到端仿真与 `audit.py` 门面评分（$\ge 90$ 分）全部通过。
5. 提交 Pull Request 并附上清晰的验证输出。

## 2. 本地必跑验证命令

```bash
# 1. 语法与静态错误检查
ruff check . --select F,E9

# 2. 运行端到端单元测试（含反事实证伪与行数红线检验）
python3 tests/test_cognitive_memory.py -v

# 3. 运行 5 天跨周期全自动仿真演示
python3 cli_demo.py --auto-demo
```

## 3. 脱敏与安全铁律 (Sanitization Iron Rules)

- **严禁提交任何真实密钥**：提交前必须确认暂存区不含 `sk-`、`ghp_`、`AKIA` 等 API 凭证。
- **严禁泄露个人隐私日记**：`data/episodes/` 与 `data/reflections/` 中随仓库分发的样例必须为 100% 虚构或完全脱敏的技术演示数据，不得包含真实姓名、邮箱、内网域名或私人敏感信息。
- **`.gitignore` 泛化原则**：公开的 `.gitignore` 只能写泛化通配规则（如 `*.log`、`.env`），任何包含具体业务域名的排除项必须写在本地 `.git/info/exclude` 中。
