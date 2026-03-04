# GUI 计划（M0 冻结版）

## 1. 结论

- 结论：**Proceed with conditions**（可启动 GUI，但必须先满足前置条件）。
- 原因：CLI 主链路已稳定（生成/质量/发布/回归），适合作为 GUI 的复用后端；但若不先冻结边界与 gate，容易出现双实现和回归失配。

## 2. 目标与非目标

### 目标

- 面向非技术用户提供可视化流程：素材输入 -> 生成 -> 质量检查 -> 发布 -> 结果追踪。
- GUI 仅做壳层与编排，复用现有业务能力，避免重写核心逻辑。

### 非目标（MVP 不做）

- 不做账号体系、多人协作、云端部署。
- 不重写生成器、质量检测器、发布器。

## 3. 硬约束（必须遵守）

- 分支与发布：`feature/* -> PR -> CI(system-regression) -> review -> merge main -> release`。
- 中文优先：界面文案、帮助、文档默认中文（代码/命令/路径保持英文）。
- 质量门禁：每阶段 PR 必过 `python forge.py test`；涉及 GUI 路径变更时必须覆盖非技术验收回归。
- 发布器改动约束：若触及知乎发布链路，必须通过两个知乎回归脚本。

## 4. 调用边界（M0 关键冻结）

### 4.1 边界原则

- GUI 不直接复制业务逻辑；只调用已有服务/入口。
- 禁止在 GUI 层新增第二套生成、质量、发布实现。

### 4.2 推荐调用路径

- 生成：复用 `cmd_generate` 对应能力（底层 `ContentGenerator`）。
- 快速生成：复用 `cmd_quick` 推断策略。
- 向导/交互：GUI 表单映射 `cmd_wizard` / `cmd_interactive` 的字段与默认值策略。
- 质量检查：复用 `QualityChecker`。
- 发布：复用 `publish_results` 与发布器结构化反馈（错误码 + 下一步）。
- 回归：复用 `python forge.py test` 与 `scripts/nontech_acceptance_regression.py`。

## 5. 分阶段计划（修订版）

| Phase | 交付物 | 通过门槛（Gate） | 主要风险 |
|---|---|---|---|
| P0 需求冻结 | 本文档 + 页面流转 + 调用边界 + 状态策略 | 文档评审通过；进入 `feature/*` 实施 | 边界不清导致后续返工 |
| P1 最小壳层 | GUI shell、健康检查、统一中文错误区 | `python forge.py test` 通过 | GUI 与 CLI 行为不一致 |
| P2 生成路径 MVP | 平台/类型/素材表单 + 生成预览 + 保存 | `python forge.py test` + 非技术验收用例通过 | 长任务状态丢失 |
| P3 质量工作台 | 质量分、Top3 建议、回填重试 | 质量输出与 CLI 一致性检查通过 | 双标准评估 |
| P4 发布中心 | 发布前检查、发布执行、结果摘要 | 发布回归脚本通过（含知乎场景） | 自动化发布不稳定 |
| P5 非技术验收与 beta | GUI 验收脚本接入 CI，发 beta 版 | `system-regression` 全绿 + 发布清单完成 | 体验漂移 |

## 6. 每阶段统一验收清单

- [ ] 功能改动在 `feature/*` 分支完成。
- [ ] PR 中说明「变更亮点 / 风险提示 / 验证命令」。
- [ ] `python3 -m py_compile <changed-files>` 通过。
- [ ] `python forge.py test` 通过。
- [ ] 涉及非技术路径改动时，`python3 scripts/nontech_acceptance_regression.py` 通过。
- [ ] 若触及知乎发布链路，两个知乎回归脚本通过。
- [ ] 文档同步更新（至少 `AIEF/context/experience/INDEX.md` 与相关使用文档）。

## 7. GUI 技术与状态策略（MVP）

- 技术方向：`FastAPI + Jinja/HTMX`（本地优先）。
- 状态策略：
  - 长任务（生成/发布）必须落本地任务状态（开始时间、状态、错误码、下一步建议）。
  - 页面刷新后可恢复最近一次任务结果。
  - 失败提供可执行动作，不只显示异常原文。

## 8. 风险与回滚

- 风险 1：GUI/CLI 分叉
  - 预防：严格复用已有能力；禁止 duplicate implementation。
  - 回滚：GUI 层可回退到仅调用 CLI 的最小壳层。
- 风险 2：发布链路不稳定
  - 预防：发布前检查 + 结构化错误码 + 手动兜底。
  - 回滚：保留 CLI 发布通道为主通道。
- 风险 3：非技术体验退化
  - 预防：每次变更同步更新非技术验收脚本。
  - 回滚：以 `wizard`/`interactive` 作为稳定 fallback。

## 9. 下一步（执行顺序）

1. 开 `feature/gui-p1-shell`，完成最小壳层与中文错误展示。
2. 在 PR 中绑定 gate：`python forge.py test` + 非技术验收（核心/全量按变更范围）。
3. 通过后再进入 `feature/gui-p2-generate-workspace`。
