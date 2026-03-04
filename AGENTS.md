# AI Guide

这是本项目的 AI 协作入口规范。

## 语言约束（强制）

- 默认使用中文沟通（回答、说明、评审、文档描述）
- 仅以下内容保持英文：代码、命令、路径、标识符、配置键名、报错原文
- 若用户明确要求英文，可切换为英文；未明确要求时保持中文
- 新增项目文档默认写中文；如需英文，采用并行文件（如 `xxx.en.md`）

## 项目定位

- 一句话：多平台内容自动生成与发布工具，强调去 AI 味与可验证质量
- 核心价值：稳定生成、平台差异化、可回归验证

## 常用命令

- build: `python3 -m py_compile src/generator/content_generator.py src/generator/prompt_builder.py src/generator/quality_checker.py src/publisher/zhihu.py`
- test: `python forge.py test`
- run: `python forge.py generate -p xiaohongshu -t route_guide -k "关键词"`

## 上下文入口

- `AIEF/context/INDEX.md`
