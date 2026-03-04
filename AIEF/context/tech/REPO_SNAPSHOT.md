# Repo Snapshot

## 技术栈

- 语言：Python 3
- 依赖管理：`pip` + `requirements.txt`
- AI 服务：DeepSeek API
- 自动化发布：Playwright（浏览器自动化）
- CI：GitHub Actions（已接入 Zhihu regression workflow）

## 顶层目录（当前）

- `AIEF/`：项目级 AIEF 资产
- `config/`：平台规则、Prompt、人设、场景配置
- `data/`：素材、生成结果、发布登录态
- `scripts/`：回归脚本和辅助脚本
- `src/`：核心业务代码
- `forge.py`：CLI 主入口

## 核心模块

- `src/config_loader.py`
  - 配置读取入口
- `src/generator/`
  - `llm_client.py`：LLM 调用
  - `prompt_builder.py`：多平台 Prompt 组装
  - `quality_checker.py`：质量评分与平台差异化
  - `content_generator.py`：生成重试、严格事实模式
- `src/publisher/`
  - `base.py`：发布器基类
  - `zhihu.py`：知乎发布实现（含状态机恢复）
  - `wechat.py` / `xiaohongshu.py` / `toutiao.py`

## 关键命令

- 安装依赖：`pip install -r requirements.txt`
- 功能测试：`python forge.py test`
- 生成内容：`python forge.py generate -p xiaohongshu -t route_guide -k "关键词"`
- 质量检测：`python forge.py check "待检测文本"`
- 场景生成：`python forge.py scenario -c outdoor -n hiking_trip -k "关键词"`

## 发布/回归命令

- 知乎格式回归：`python3 scripts/zhihu_format_regression.py`
- 知乎 E2E 回归：`python3 scripts/zhihu_e2e_regression.py`
- 语法编译检查：
  - `python3 -m py_compile src/publisher/zhihu.py src/generator/content_generator.py scripts/zhihu_format_regression.py scripts/zhihu_e2e_regression.py`

## 当前已知风险

- 平台页面结构变化会影响发布器选择器稳定性
- LLM 仍可能产生轻度事实漂移（已由严格事实模式缓解）
- 规则驱动评分不等价于事实真值判断，需结合回归脚本与人工抽检
