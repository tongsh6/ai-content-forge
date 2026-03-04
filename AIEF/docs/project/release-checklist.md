# 发布检查清单

## 版本准备

- [ ] `git status` 干净
- [ ] 变更已推送到目标分支
- [ ] 关联 issue 已更新状态

## 验证

- [ ] `python3 -m py_compile` 覆盖本次变更文件
- [ ] 生成链路相关自检已通过
- [ ] 若涉及知乎发布器：两个回归脚本都通过

## Release 产物

- [ ] 版本号符合语义化（如 `v0.2.0`）
- [ ] Release notes 包含：
  - [ ] 变更亮点
  - [ ] 风险提示
  - [ ] 验证命令
- [ ] 发布后链接可访问

## 发布后

- [ ] 记录到 `AIEF/context/experience/INDEX.md`（如有关键经验）
- [ ] 若有新增流程，更新 `AIEF/workflow/` 文档
