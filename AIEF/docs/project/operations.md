# 项目运维手册（AI Content Forge）

## 1. 本地启动与基础检查

- 安装依赖：`pip install -r requirements.txt`
- 配置密钥：`cp .env.example .env`，填入 `DEEPSEEK_API_KEY`
- 基础测试：`python forge.py test`

## 2. 常用生成命令

- 单平台生成：
  - `python forge.py generate -p xiaohongshu -t route_guide -k "关键词"`
- 场景批量生成：
  - `python forge.py scenario -c outdoor -n hiking_trip -k "关键词"`
- AI 味检测：
  - `python forge.py check "待检测文本"`

## 3. 知乎发布链路验证

- 格式回归：`python3 scripts/zhihu_format_regression.py`
- E2E 回归：`python3 scripts/zhihu_e2e_regression.py`

若发布器逻辑有改动，这两项必须都通过。

## 4. 质量门槛检查

- 质量阈值来自：`config/prompts/anti_ai_rules.yaml`
- 平台阈值不同，生成失败重试行为应符合平台策略
- `project_promotion` 默认严格事实模式，不允许无依据量化/社会证明声明

## 5. 发布前检查

- 分支流程：
  - 在 `feature/*` 分支开发
  - 提 PR 合并到 `main`
  - 仅在 `main` 合并完成后执行 release
- 语法：`python3 -m py_compile <changed-files>`
- 回归：运行受影响平台脚本
- Issue 同步：修复项与 issue 关联并更新状态
- Release 说明：包含变更摘要和验证命令
