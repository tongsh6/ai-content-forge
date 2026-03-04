# AI Content Forge

多平台内容自动生成工具，利用 AI 生成高质量、去 AI 味的内容。

## 特性

- **多平台支持**: 小红书、公众号、知乎、今日头条
- **人设驱动**: 基于配置的人设系统，保持内容风格一致
- **去 AI 味**: 内置去 AI 味规则，让内容更像真人写的
- **场景模板**: 预设户外/生活/科技等场景，一份素材生成多平台内容

## 快速开始

```bash
# 1. 安装依赖
pip install -r requirements.txt

# 2. 配置 API Key
cp .env.example .env
# 编辑 .env 填入 DEEPSEEK_API_KEY

# 3. 测试系统
python forge.py test

# 4. 生成内容
python forge.py generate -p xiaohongshu -t route_guide -k "莫干山徒步" -s
```

## 使用方式

### 命令行生成

```bash
# 生成小红书路线攻略
python forge.py generate -p xiaohongshu -t route_guide -k "莫干山徒步"

# 生成知乎问答
python forge.py generate -p zhihu -t question_answer -k "徒步装备推荐"

# 带额外素材
python forge.py generate -p xiaohongshu -t gear_review -k "登山杖测评" \
  -m '{"brand": "Black Diamond", "price": "299元"}'

# 保存到文件
python forge.py generate -p xiaohongshu -t route_guide -k "千岛湖骑行" -s
```

### 模板化素材输入（推荐非技术用户）

先复制模板，再把字段替换成你的信息：

```bash
# 路线攻略模板
cp config/material_templates/route_guide.json data/materials/my_route.json

# 装备测评模板
cp config/material_templates/gear_review.json data/materials/my_gear.json

# 知乎问答模板
cp config/material_templates/question_answer.json data/materials/my_qa.json

# 项目推广模板
cp config/material_templates/project_promotion.json data/materials/my_project.json
```

编辑完成后，直接用素材文件生成：

```bash
python forge.py generate -p xiaohongshu -t route_guide -m data/materials/my_route.json -s
python forge.py generate -p xiaohongshu -t gear_review -m data/materials/my_gear.json -s
python forge.py generate -p zhihu -t question_answer -m data/materials/my_qa.json -s
python forge.py generate -p zhihu -t project_promotion -m data/materials/my_project.json -s
```

说明：
- 模板里已经包含 `keywords` 字段，通常不需要再额外传 `-k`
- 只改你有的信息即可，留空字段会自动忽略
- `project_promotion` 默认开启严格事实模式，请仅填写真实可验证信息

### 交互式模式

```bash
python forge.py interactive
```

### 场景生成

```bash
# 根据场景批量生成
python forge.py scenario -c outdoor -n hiking_trip -k "天目山徒步" \
  -m '{"distance": "12公里", "duration": "5小时"}'
```

## 协作与发布流程（强制）

- 禁止直接向 `main` 推送改动
- 所有改动必须走：`feature/*` 分支 -> PR -> CI -> review -> merge 到 `main`
- 仅允许基于已合并的 `main` 创建版本发布
- 详细检查项见：`AIEF/docs/project/release-checklist.md`

## 非技术发布一页纸（推荐照抄）

下面是最短可执行流程，按顺序执行即可：

```bash
# 0) 切到新功能分支（不要在 main 直接改）
git checkout -b feature/your-change

# 1) 完成改动后做基础验证
python3 -m py_compile src/generator/content_generator.py src/generator/prompt_builder.py src/generator/quality_checker.py src/publisher/zhihu.py
python forge.py test

# 2) 提交并推送分支
git add .
git commit -m "feat: your change summary"
git push -u origin feature/your-change

# 3) 在 GitHub 创建 PR，等待 CI + review 后合并到 main

# 4) 切回 main 并同步最新
git checkout main
git pull

# 5) 打版本 tag 并推送（示例 v0.3.4）
git tag v0.3.4
git push origin v0.3.4
```

发布前请再核对一次：
- 分支是否为 `main` 且是最新代码
- `system-regression` 是否已通过
- release notes 是否包含「变更亮点 / 风险提示 / 验证命令」

## 项目结构

```
ai-content-forge/
├── config/
│   ├── personas.yaml          # 人设配置
│   ├── platforms.yaml         # 平台规则
│   └── prompts/
│       ├── xiaohongshu.yaml   # 小红书模板
│       ├── wechat.yaml        # 公众号模板
│       ├── zhihu.yaml         # 知乎模板
│       ├── toutiao.yaml       # 头条模板
│       ├── anti_ai_rules.yaml # 去AI味规则
│       └── scenarios/         # 场景模板
├── src/
│   ├── config_loader.py       # 配置加载
│   └── generator/
│       ├── llm_client.py      # LLM 客户端
│       ├── prompt_builder.py  # Prompt 构建
│       └── content_generator.py # 内容生成
├── data/
│   ├── materials/             # 素材存放
│   └── generated/             # 生成内容
├── forge.py                   # 主入口
├── requirements.txt
└── .env.example
```

## 配置说明

### 人设配置 (config/personas.yaml)

定义创作者身份、性格、写作风格等。

### 去 AI 味规则 (config/prompts/anti_ai_rules.yaml)

- 避免词汇: "首先"、"其次"、"值得一提"等
- 推荐表达: 口语化动词、情绪词、不确定表达
- 写作技巧: 短句、括号吐槽、具体细节

## 支持的内容类型

| 平台 | 内容类型 |
|------|----------|
| 小红书 | route_guide, gear_review, experience_share, beginner_guide |
| 公众号 | life_reflection, career_insight, slash_life |
| 知乎 | question_answer, gear_recommendation, experience_sharing |
| 头条 | micro_post, practical_guide, life_skill |

## License

MIT
