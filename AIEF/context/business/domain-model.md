# Domain Model

## 核心实体

- `Material`
  - 输入素材（关键词、JSON 字段、场景信息、项目资料）
- `PromptTemplate`
  - 平台模板（小红书/公众号/知乎/头条）
- `Persona`
  - 写作人设与语气偏好
- `GeneratedContent`
  - 生成结果（标题、正文、标签、质量评分、生成次数）
- `QualityReport`
  - 多维评分明细与建议
- `PublishContent`
  - 面向发布器的标准内容结构
- `PublishResult`
  - 发布结果（成功状态、消息、URL/草稿定位）

## 关键关系

- `Material + PromptTemplate + Persona -> GeneratedContent`
- `GeneratedContent -> QualityReport`
- `GeneratedContent -> PublishContent -> PublishResult`
- `anti_ai_rules + platform_adjustments -> PromptBuilder + QualityChecker`

## 业务规则

- 去 AI 味
  - 通过模板约束 + 质量评分 + 重试提示联合控制
- 平台差异化
  - 不同平台使用不同评分倾向与达标阈值
- 严格事实模式（`project_promotion`）
  - 默认开启
  - 检测到无依据量化/社会证明声明时强制重试
- 发布行为
  - 半自动模式允许用户跳过发布并保留草稿定位信息
  - 遇到知乎 `unhuman` 页面时尝试恢复到可写页面

## 质量门槛

- 默认平台阈值由 `config/prompts/anti_ai_rules.yaml` 控制
- 当前策略：知乎阈值最高，小红书次之，头条相对宽松

## 成功判定

- 生成成功
  - 质量分 >= 平台阈值
  - 严格事实模式下无无依据声明
- 发布成功
  - 点击发布成功并返回发布 URL，或明确返回已提交状态
