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

## 待补充

- 公众号/小红书/头条发布链路的对应回归脚本
- 回归脚本纳入统一测试入口（例如 `python forge.py test` 扩展）
