# 发布检查清单

## 版本准备

- [ ] `git status` 干净
- [ ] 变更在 `feature/*` 分支完成并已推送
- [ ] 已创建 PR，且通过 review/CI 后再合并到 `main`
- [ ] 发布动作基于已合并的 `main` 执行（禁止直接从 feature 分支发版）
- [ ] `main` 分支保护保持开启（至少包含：1 个审批 + `system-regression` 必过）
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

## 一页式命令回放（可直接执行）

```bash
git checkout -b feature/your-change
# 完成改动...
python3 -m py_compile <changed-files>
python forge.py test
git add .
git commit -m "feat: your change summary"
git push -u origin feature/your-change
# 创建 PR，等待 CI/review，合并到 main
git checkout main
git pull
git tag vX.Y.Z
git push origin vX.Y.Z
```
