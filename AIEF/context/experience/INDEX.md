# Experience Index

## 经验记录原则

- 记录可复现问题，不记录主观感受
- 每条经验必须包含：触发条件、修复动作、回归方式
- 优先沉淀可脚本化的防回归措施

## 已沉淀经验

1. 知乎 Markdown 渲染不稳定
   - 触发：代码围栏、分隔线、列表混用时出现解析异常
   - 修复：发布前做安全子集归一化（链接、列表、围栏）
   - 回归：`scripts/zhihu_format_regression.py`

2. 知乎安全验证跳转导致发布中断
   - 触发：跳到 `account/unhuman` 后 selector timeout
   - 修复：显式状态机 `signin/unhuman/write` + 有界重试恢复
   - 回归：`scripts/zhihu_e2e_regression.py`

3. 项目推广文案事实漂移
   - 触发：模型补充无依据用户数/反馈等社会证明
   - 修复：严格事实模式拦截无依据声明，失败强制重试
   - 回归：生成器 smoke 检查 + 质量门槛验证

4. 发布流程不一致（main 直接开发/发布）
   - 触发：历史操作中出现主分支直接开发后发版，流程不可审计
   - 修复：固化 `feature/* -> PR -> main -> release` 规则到发布清单与运维手册
   - 回归：发布前按 `AIEF/docs/project/release-checklist.md` 逐项勾选

5. 本地与 CI 测试入口分叉
   - 触发：CI 与本地分别维护不同测试命令，回归覆盖不一致
   - 修复：统一入口为 `python forge.py test`，并接入四平台回归脚本
   - 回归：本地执行 `python forge.py test`，CI 统一调用同一命令

6. 非技术用户流程缺少可持续验收
   - 触发：CLI 在持续迭代后，非技术路径（首次安装/首次生成/失败恢复）容易退化
   - 修复：新增 `scripts/nontech_acceptance_regression.py`，覆盖 5 条验收用例；CI 至少执行核心 2 条（`--core-only`）
   - 回归：
     - CI：`python forge.py test`（内部触发 `nontech_acceptance_regression.py --core-only`）
     - 发版前：手动执行 `python3 scripts/nontech_acceptance_regression.py` 全量验收
   - 更新频率：每次修改 CLI 交互/错误提示/模板输入后，必须同步更新该验收脚本

## 待补充

- 为四平台回归补充更真实的浏览器 E2E（当前以最小可执行回归为主）
- 将发布后复盘模板化（失败案例、回滚路径、影响范围）
