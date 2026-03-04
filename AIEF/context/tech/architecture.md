# 架构

## 系统概览

`ai-content-forge` 是一个 Python CLI 系统，用于多平台内容生成与浏览器辅助发布。

主链路：

1. 命令行入参解析（`forge.py`）
2. 素材归一化与场景/内容类型路由
3. Prompt 组装（`src/generator/prompt_builder.py`）
4. LLM 生成与重试（`src/generator/content_generator.py`）
5. 质量评分（`src/generator/quality_checker.py`）
6. 可选平台发布（`src/publisher/*.py`）

## 模块职责

- `forge.py`
  - 命令路由与顶层编排
  - 平台/内容类型/素材字段别名映射
  - 可选发布流程调用

- `src/config_loader.py`
  - 读取人设、平台模板、去 AI 规则、场景配置

- `src/generator/llm_client.py`
  - DeepSeek API 调用封装

- `src/generator/prompt_builder.py`
  - 合并平台模板、人设、去 AI 规则、平台差异化参数

- `src/generator/content_generator.py`
  - 生成重试、平台阈值、严格事实模式
  - 基于最差维度构建重试提示

- `src/generator/quality_checker.py`
  - 多维质量评分
  - 模板化惩罚、证据密度、节奏变化、平台加权

- `src/publisher/base.py`
  - Playwright 生命周期与发布抽象契约

- `src/publisher/zhihu.py`
  - 知乎内容归一化与发布状态机
  - 处理 `signin` / `unhuman` / `write` 状态迁移

- `config/prompts/*.yaml`
  - 平台 Prompt 和去 AI 味配置

## 边界定义

- 生成边界
  - 输入：关键词/素材/场景
  - 输出：结构化内容 + 质量元数据

- 发布边界
  - 输入：生成内容
  - 输出：`PublishResult`（状态、URL、草稿定位）

- 配置边界
  - 可配置策略优先落在 YAML
  - 仅当配置无法表达时再改 Python 逻辑

## 当前风险

- 浏览器自动化脆弱性
  - 页面结构变更会导致 selector 失效
- LLM 事实漂移
  - 严格事实模式可缓解但不能完全消除
- 评分启发式局限
  - 质量分可控但不等同于事实真值校验
- 平台策略漂移
  - 知乎安全验证与发布页面行为可能随时变化
