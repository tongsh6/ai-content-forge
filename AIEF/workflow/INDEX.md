# 工作流索引

标准流程：`proposal -> design -> implement -> review`

## 何时可以跳过阶段

- 仅当任务是纯文案修订、无逻辑变更时，可简化 `design`
- 涉及生成逻辑、评分逻辑、发布流程变更时，不可跳过任何阶段

## 阶段产物要求

- proposal
  - 问题定义、目标、验收标准
- design
  - 修改文件清单、方案对比、风险与回滚策略
- implement
  - 实际变更 + 最小可验证脚本
- review
  - 验证结果、风险说明、issue/release 同步记录

## 本项目强制验证项

- `python3 -m py_compile` 覆盖本次改动文件
- 若涉及知乎发布器，必须运行：
  - `python3 scripts/zhihu_format_regression.py`
  - `python3 scripts/zhihu_e2e_regression.py`
