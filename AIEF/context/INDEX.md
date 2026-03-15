# Context Index

这是 `ai-content-forge` 的长期项目上下文入口。

语言约定：
- 以中文为主
- 代码、命令、标识符保持英文
- 后续如需英文文档，采用并行文件方式（如 `xxx.en.md`）

## 建议阅读顺序

1. `context/tech/REPO_SNAPSHOT.md`
2. `context/tech/architecture.md`
3. `context/business/domain-model.md`
4. `context/experience/INDEX.md`
5. `AIEF/docs/project/gui-plan.md`（GUI 技术选型与分阶段实施）

## 目录职责

- `context/tech/`
  - 代码结构、关键命令、技术风险与约束
- `context/business/`
  - 业务目标、核心实体、平台规则、质量标准
- `context/experience/`
  - 关键经验、踩坑记录、可复用做法

## 更新规则

- 命令、目录、模块有变化时，更新 `REPO_SNAPSHOT.md`
- 数据流或职责边界变化时，更新 `architecture.md`
- 内容策略/发布策略变化时，更新 `domain-model.md`
- 修复重大问题或发布版本后，补充 `experience/INDEX.md`
