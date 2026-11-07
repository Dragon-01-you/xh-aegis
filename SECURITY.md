# 安全策略与漏洞披露 (Security Policy)

## 支持的版本 (Supported Versions)

| 版本 | 支持状态 |
| --- | --- |
| `1.0.x` | ✅ 持续维护与安全更新 |

## 密钥与本地隐私数据安全声明

1. **零遥测与纯本地存储**：`xh-aegis` 默认将所有记忆切片（`data/`）存储在本地文件系统中，绝不向任何第三方服务器上传遥测数据。
2. **环境变量隔离**：所有外部大模型 API 凭证均通过系统环境变量（`OPENAI_API_KEY`）读取，严禁写入 `config/settings.yaml` 或提交至 Git 历史。
3. **防止记忆投毒（Memory Poisoning Guardrails）**：系统通过 `falsification_condition`（反事实证伪条件）与每次 REM 周期的自动 Git 快照，防止单次恶意 Prompt 注入永久篡改 Agent 的核心工作记忆。

## 报告安全漏洞 (Reporting a Vulnerability)

如果你在 `xh-aegis` 中发现了潜在的安全漏洞（例如 Prompt 注入导致的任意文件写入或 Git 命令注入），**请勿直接提交公开 Issue**：

- 请通过 GitHub Security Advisories（**Security -> Report a vulnerability**）私密提交报告。
- 我们将在 **48 小时内** 确认收到报告，并在 **7 个工作日内** 评估修复方案与发布安全补丁。
