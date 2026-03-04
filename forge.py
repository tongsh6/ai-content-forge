#!/usr/bin/env python3
"""
AI Content Forge - 多平台内容自动生成工具

用法:
    python forge.py gen -p xhs -t 攻略 -k "莫干山"           # 生成小红书攻略
    python forge.py gen -p xhs -t 攻略 -k "莫干山" 距离=15km  # 带行内素材
    python forge.py s hiking_trip -k "莫干山"                 # 场景生成(自动推断)
    python forge.py list                                     # 查看所有平台/类型/场景
    python forge.py quick "莫干山徒步攻略"                    # 快速生成
    python forge.py check "要检测的文本内容"                  # 检测AI味
"""

import argparse
import sys
import json
import subprocess
from types import SimpleNamespace
from pathlib import Path
from datetime import datetime

# 添加 src 目录到 path
sys.path.insert(0, str(Path(__file__).parent / "src"))

# ============================================================
# 映射表：缩写/中文别名 → 标准名称
# ============================================================

# 平台缩写 → 全名
PLATFORM_ALIASES = {
    "xhs": "xiaohongshu",
    "wx": "wechat",
    "zh": "zhihu",
    "tt": "toutiao",
}

# 平台全名 → 中文名（用于显示）
PLATFORM_CN = {
    "xiaohongshu": "小红书",
    "wechat": "公众号",
    "zhihu": "知乎",
    "toutiao": "头条",
}

# 所有合法平台名
VALID_PLATFORMS = set(PLATFORM_CN.keys())

# 内容类型：中文别名 → 代码
CONTENT_TYPE_ALIASES = {
    "攻略": "route_guide",
    "测评": "gear_review",
    "分享": "experience_share",
    "入门": "beginner_guide",
    "感悟": "life_reflection",
    "职场": "career_insight",
    "问答": "question_answer",
    "推荐": "gear_recommendation",
    "微头条": "micro_post",
    "教程": "practical_guide",
    "推广": "project_promotion",
    "斜杠": "slash_life",
}

# 素材 key：中文 → 英文
MATERIAL_KEY_ALIASES = {
    "距离": "distance",
    "用时": "duration",
    "难度": "difficulty",
    "地点": "location",
    "爬升": "elevation_gain",
    "人数": "participants",
    "天气": "weather",
    "亮点": "highlight",
    "遗憾": "regret",
    "装备": "gear_name",
    "品牌": "brand",
    "价格": "price",
    "问题": "question",
    "话题": "topic",
    "记录": "transcript",
}

# 平台对应的内容类型（用于 list 命令）
PLATFORM_CONTENT_TYPES = {
    "xiaohongshu": [
        ("route_guide", "攻略"),
        ("gear_review", "测评"),
        ("experience_share", "分享"),
        ("beginner_guide", "入门"),
        ("project_promotion", "推广"),
    ],
    "wechat": [
        ("life_reflection", "感悟"),
        ("career_insight", "职场"),
        ("slash_life", "斜杠"),
        ("project_promotion", "推广"),
    ],
    "zhihu": [
        ("question_answer", "问答"),
        ("gear_recommendation", "推荐"),
        ("experience_sharing", "分享"),
        ("project_promotion", "推广"),
    ],
    "toutiao": [
        ("micro_post", "微头条"),
        ("practical_guide", "教程"),
        ("life_skill", "生活技能"),
        ("project_promotion", "推广"),
    ],
}


def print_user_error(problem: str, fix: str = "", example: str = ""):
    print(f"错误: {problem}")
    if fix:
        print(f"修复: {fix}")
    if example:
        print(f"示例: {example}")


def print_user_warning(problem: str, fix: str = "", example: str = ""):
    print(f"警告: {problem}")
    if fix:
        print(f"建议: {fix}")
    if example:
        print(f"参考: {example}")


def resolve_platform(name: str) -> str:
    """解析平台名：支持缩写和全名"""
    resolved = PLATFORM_ALIASES.get(name, name)
    if resolved not in VALID_PLATFORMS:
        valid = ", ".join(f"{a}={PLATFORM_CN[f]}" for a, f in PLATFORM_ALIASES.items())
        print_user_error(
            problem=f"未知平台 '{name}'",
            fix="请使用支持的平台缩写或全名",
            example=f'python forge.py generate -p xhs -t 攻略 -k "莫干山"（可选平台: {valid}）',
        )
        sys.exit(1)
    return resolved


def resolve_content_type(name: str) -> str:
    """解析内容类型：支持中文别名和英文代码"""
    return CONTENT_TYPE_ALIASES.get(name, name)


def parse_kv_materials(args_list: list) -> dict:
    """解析 key=value 行内素材，支持中文 key"""
    result = {}
    for item in args_list:
        if "=" not in item:
            print_user_warning(
                problem=f"忽略无效参数 '{item}'（格式应为 key=value）",
                fix="请按“字段=值”填写补充素材",
                example="地点=杭州,距离=12公里",
            )
            continue
        key, _, value = item.partition("=")
        key = MATERIAL_KEY_ALIASES.get(key, key)
        result[key] = value
    return result


def build_scenario_index() -> dict:
    """扫描 scenario YAML 文件，构建 scenario_name → category 的反向索引"""
    import yaml

    index = {}
    scenario_dir = Path(__file__).parent / "config" / "prompts" / "scenarios"
    if not scenario_dir.exists():
        return index
    for yaml_file in scenario_dir.glob("*.yaml"):
        try:
            with open(yaml_file, "r", encoding="utf-8") as f:
                data = yaml.safe_load(f)
            category = data.get("category", yaml_file.stem)
            for scenario_name in data.get("scenarios", {}):
                index[scenario_name] = category
        except Exception:
            continue
    return index


def load_materials(materials_arg: str) -> dict:
    """
    加载素材：支持 JSON 文件路径或内联 JSON 字符串

    Args:
        materials_arg: JSON 文件路径（如 data/materials/aief.json）或 JSON 字符串

    Returns:
        解析后的 dict
    """
    if not materials_arg:
        return {}

    # 先检查是否是文件路径
    materials_path = Path(materials_arg)
    if materials_path.exists() and materials_path.suffix == ".json":
        try:
            with open(materials_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            print(f"✓ 已加载素材文件: {materials_path}")
            return data
        except json.JSONDecodeError as e:
            print_user_error(
                problem=f"素材文件 JSON 格式错误: {e}",
                fix="请检查 JSON 语法（逗号、引号、括号）",
                example='{"keywords": "莫干山徒步", "distance": "12公里"}',
            )
            sys.exit(1)

    # 尝试作为内联 JSON 解析
    try:
        return json.loads(materials_arg)
    except json.JSONDecodeError:
        print_user_warning(
            problem=f"无法解析 materials: {materials_arg}",
            fix="请传入 JSON 文件路径或合法 JSON 字符串；否则该项将被忽略",
            example='python forge.py generate -p xhs -t 攻略 -m data/materials/demo.json -k "莫干山"',
        )
        return {}


def publish_results(results, platforms, auto_confirm=False):
    """
    将生成的内容发布到各平台

    Args:
        results: {platform: GeneratedContent} 或 {platform: [GeneratedContent, ...]} 字典
        platforms: 要发布的平台列表
        auto_confirm: 是否自动确认发布
    """
    from publisher.base import PublishContent
    from publisher.xiaohongshu import XiaohongshuPublisher
    from publisher.zhihu import ZhihuPublisher
    from publisher.wechat import WechatPublisher
    from publisher.toutiao import ToutiaoPublisher

    PUBLISHER_MAP = {
        "xiaohongshu": XiaohongshuPublisher,
        "zhihu": ZhihuPublisher,
        "wechat": WechatPublisher,
        "toutiao": ToutiaoPublisher,
    }

    PLATFORM_NAMES = {
        "xiaohongshu": "小红书",
        "zhihu": "知乎",
        "wechat": "公众号",
        "toutiao": "今日头条",
    }

    print(f"\n{'=' * 60}")
    print("开始发布到各平台...")
    print("=" * 60)

    all_publish_results = []

    for platform in platforms:
        publisher_cls = PUBLISHER_MAP.get(platform)
        if not publisher_cls:
            print(f"  ⚠ 未知平台: {platform}，跳过")
            continue

        platform_name = PLATFORM_NAMES.get(platform, platform)

        # 统一处理 results 格式：可能是单个 GeneratedContent 或列表
        platform_results = results.get(platform)
        if platform_results is None:
            continue

        if not isinstance(platform_results, list):
            platform_results = [platform_results]

        for generated in platform_results:
            # 将 GeneratedContent 转换为 PublishContent
            publish_content = PublishContent(
                title=generated.title,
                content=generated.content,
                tags=generated.tags,
                summary=generated.summary,
            )

            print(f"\n{'─' * 60}")
            print(f"发布到 {platform_name}...")
            print(
                f"  标题: {publish_content.title[:40]}{'...' if len(publish_content.title) > 40 else ''}"
            )
            print(f"  正文: {len(publish_content.content)} 字")
            if publish_content.tags:
                print(
                    f"  标签: {', '.join(publish_content.tags[:5])}{'...' if len(publish_content.tags) > 5 else ''}"
                )
            print("─" * 60)

            publisher = publisher_cls(headless=False, auto_confirm=auto_confirm)
            result = publisher.publish(publish_content)
            all_publish_results.append(result)

            status = "✓ 成功" if result.success else "✗ 失败"
            print(f"  {status}: {result.message}")
            if result.error:
                print(f"    错误: {result.error}")

    # 发布结果汇总
    print(f"\n{'=' * 60}")
    print("【发布结果汇总】")
    for r in all_publish_results:
        icon = "✓" if r.success else "✗"
        print(f"  {icon} {r.platform}: {r.message}")
    success_count = sum(1 for r in all_publish_results if r.success)
    print(f"\n  成功: {success_count}/{len(all_publish_results)}")
    print("=" * 60)


def copy_to_clipboard(text: str) -> bool:
    """复制文本到剪贴板 (macOS)"""
    try:
        process = subprocess.Popen(
            ["pbcopy"], stdin=subprocess.PIPE, env={"LANG": "en_US.UTF-8"}
        )
        process.communicate(text.encode("utf-8"))
        return process.returncode == 0
    except Exception:
        return False


def format_copyable_content(result) -> str:
    """格式化可复制的内容"""
    lines = []
    if result.title:
        lines.append(result.title)
        lines.append("")
    lines.append(result.content)
    if result.tags:
        lines.append("")
        lines.append(" ".join(["#" + t for t in result.tags]))
    return "\n".join(lines)


def cmd_generate(args):
    """生成内容命令"""
    from generator.content_generator import ContentGenerator
    from generator.quality_checker import QualityChecker

    # 解析平台和内容类型（支持缩写/中文别名）
    args.platform = resolve_platform(args.platform)
    args.type = resolve_content_type(args.type)

    # 构建素材
    materials = {}

    # 解析额外素材（支持 JSON 文件路径或内联 JSON）
    if args.materials:
        extra = load_materials(args.materials)
        materials.update(extra)

    # 解析行内 key=value 素材
    if args.extra_args:
        kv = parse_kv_materials(args.extra_args)
        materials.update(kv)

    # CLI 的 keywords 优先级最高
    if args.keywords:
        materials["keywords"] = args.keywords

    # 检查是否有 keywords
    if "keywords" not in materials:
        print_user_error(
            problem="缺少关键词",
            fix="请通过 -k/--keywords 传入关键词，或在素材文件中提供 keywords 字段",
            example='python forge.py generate -p xhs -t 攻略 -k "莫干山徒步"',
        )
        sys.exit(1)

    # 生成
    try:
        generator = ContentGenerator()
        result = generator.generate(
            platform=args.platform,
            content_type=args.type,
            materials=materials,
        )

        # 输出结果
        print("\n" + "=" * 50)
        print(result)
        print("=" * 50)

        # 质量检测
        if not args.no_check:
            checker = QualityChecker()
            report = checker.check(result.content, result.title)
            print("\n【内容质量检测】")
            print(report)

        # 复制到剪贴板
        if args.copy:
            copyable = format_copyable_content(result)
            if copy_to_clipboard(copyable):
                print("\n✓ 已复制到剪贴板")
            else:
                print("\n✗ 复制到剪贴板失败")

        # 保存到文件
        if args.save:
            output_dir = Path(__file__).parent / "data" / "generated"
            output_dir.mkdir(parents=True, exist_ok=True)

            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"{args.platform}_{args.type}_{timestamp}.json"
            output_path = output_dir / filename

            with open(output_path, "w", encoding="utf-8") as f:
                f.write(result.to_json())

            print(f"\n✓ 已保存到: {output_path}")

        # 发布到平台
        if args.publish:
            publish_results(
                results={args.platform: result},
                platforms=[args.platform],
                auto_confirm=args.auto,
            )

        # 打印统计
        print("\n【API 统计】")
        stats = generator.get_stats()
        print(f"  请求次数: {stats['total_requests']}")
        print(f"  输入 tokens: {stats['total_input_tokens']}")
        print(f"  输出 tokens: {stats['total_output_tokens']}")
        print(f"  估算费用: ¥{stats['estimated_cost_cny']}")

    except Exception as e:
        print_user_error(
            problem=f"生成失败: {e}",
            fix="请先检查关键词和素材是否完整，再重试；必要时加 --debug 查看详细堆栈",
            example='python forge.py generate -p xhs -t 攻略 -k "莫干山" --debug',
        )
        if args.debug:
            import traceback

            traceback.print_exc()
        sys.exit(1)


def cmd_quick(args):
    """快速生成命令 - 一行搞定"""
    from generator.content_generator import ContentGenerator
    from generator.quality_checker import QualityChecker

    prompt = args.prompt

    # 智能解析 prompt，判断平台和类型
    platform = "xiaohongshu"  # 默认小红书
    content_type = "experience_share"  # 默认感受分享
    inference_notes = ["平台默认: 小红书", "类型默认: experience_share"]

    prompt_lower = prompt.lower()

    # 平台检测
    if "知乎" in prompt or "zhihu" in prompt_lower:
        platform = "zhihu"
        content_type = "question_answer"
        inference_notes.append("命中平台词: 知乎/zhihu")
        inference_notes.append("平台联动类型: question_answer")
    elif "公众号" in prompt or "wechat" in prompt_lower:
        platform = "wechat"
        content_type = "life_reflection"
        inference_notes.append("命中平台词: 公众号/wechat")
        inference_notes.append("平台联动类型: life_reflection")
    elif "头条" in prompt or "toutiao" in prompt_lower:
        platform = "toutiao"
        content_type = "micro_post"
        inference_notes.append("命中平台词: 头条/toutiao")
        inference_notes.append("平台联动类型: micro_post")
    elif "小红书" in prompt or "xhs" in prompt_lower:
        inference_notes.append("命中平台词: 小红书/xhs")

    # 内容类型检测
    if "攻略" in prompt or "路线" in prompt:
        content_type = "route_guide"
        inference_notes.append("命中类型词: 攻略/路线 -> route_guide")
    elif "测评" in prompt or "装备" in prompt:
        content_type = "gear_review"
        inference_notes.append("命中类型词: 测评/装备 -> gear_review")
    elif "入门" in prompt or "新手" in prompt:
        content_type = "beginner_guide"
        inference_notes.append("命中类型词: 入门/新手 -> beginner_guide")

    # 清理 prompt 中的平台关键词
    keywords = prompt
    for word in ["小红书", "知乎", "公众号", "头条", "攻略", "测评", "入门"]:
        keywords = keywords.replace(word, "").strip()

    if not keywords:
        keywords = prompt

    platform_names = {
        "xiaohongshu": "小红书",
        "wechat": "公众号",
        "zhihu": "知乎",
        "toutiao": "头条",
    }

    print(f"🚀 快速生成: {platform_names[platform]} / {content_type}")
    print(f"   关键词: {keywords}")
    print("\n【推断解释】")
    for note in inference_notes:
        print(f"   - {note}")
    print("\n【如何手动覆盖】")
    print(
        f'   指定平台和类型: python forge.py generate -p {platform} -t {content_type} -k "{keywords}"'
    )
    print("   查看所有可选值: python forge.py list")
    print("   若希望更少参数输入: python forge.py wizard")
    print("-" * 40)

    try:
        generator = ContentGenerator()
        result = generator.generate(
            platform=platform,
            content_type=content_type,
            materials={"keywords": keywords},
        )

        # 输出结果
        print("\n" + "=" * 50)
        print(result)
        print("=" * 50)

        # 质量检测
        checker = QualityChecker()
        report = checker.check(result.content, result.title)
        print("\n【内容质量检测】")
        print(report)

        # 自动复制到剪贴板
        copyable = format_copyable_content(result)
        if copy_to_clipboard(copyable):
            print("\n✓ 已复制到剪贴板")

        # 打印统计
        print("\n【API 统计】")
        stats = generator.get_stats()
        print(f"  估算费用: ¥{stats['estimated_cost_cny']}")

    except Exception as e:
        print_user_error(
            problem=f"生成失败: {e}",
            fix="请尝试改用 wizard 模式，减少参数输入错误",
            example="python forge.py wizard",
        )
        if args.debug:
            import traceback

            traceback.print_exc()
        sys.exit(1)


def cmd_check(args):
    """检测内容质量"""
    from generator.quality_checker import QualityChecker

    text = args.text

    # 如果是文件路径，读取文件
    if Path(text).exists():
        with open(text, "r", encoding="utf-8") as f:
            text = f.read()

    checker = QualityChecker()
    report = checker.check(text)

    print("=" * 50)
    print("AI Content Forge - 内容质量检测")
    print("=" * 50)
    print()
    print(report)


def cmd_interactive(args):
    """交互式模式"""
    from generator.content_generator import ContentGenerator
    from generator.quality_checker import QualityChecker

    print("=" * 50)
    print("AI Content Forge - 交互式内容生成")
    print("=" * 50)

    # 选择平台
    platforms = {
        "1": ("xiaohongshu", "小红书"),
        "2": ("wechat", "公众号"),
        "3": ("zhihu", "知乎"),
        "4": ("toutiao", "今日头条"),
    }

    print("\n选择目标平台:")
    for key, (_, name) in platforms.items():
        print(f"  {key}. {name}")

    choice = input("\n请输入数字 (1-4): ").strip()
    if choice not in platforms:
        print("无效选择")
        return

    platform, platform_name = platforms[choice]

    # 选择内容类型
    content_types = {
        "xiaohongshu": {
            "1": ("route_guide", "路线攻略"),
            "2": ("gear_review", "装备测评"),
            "3": ("experience_share", "感受分享"),
            "4": ("beginner_guide", "新手入门"),
        },
        "wechat": {
            "1": ("life_reflection", "生活感悟"),
            "2": ("career_insight", "职场思考"),
            "3": ("slash_life", "斜杠人生"),
        },
        "zhihu": {
            "1": ("question_answer", "问答"),
            "2": ("gear_recommendation", "装备推荐"),
            "3": ("experience_sharing", "经验分享"),
        },
        "toutiao": {
            "1": ("micro_post", "微头条"),
            "2": ("practical_guide", "实用教程"),
            "3": ("life_skill", "生活技能"),
        },
    }

    print(f"\n选择 {platform_name} 内容类型:")
    for key, (_, name) in content_types[platform].items():
        print(f"  {key}. {name}")

    choice = input("\n请输入数字: ").strip()
    if choice not in content_types[platform]:
        print("无效选择")
        return

    content_type, type_name = content_types[platform][choice]

    # 输入素材
    print(f"\n准备生成 {platform_name} - {type_name}")
    print("-" * 30)

    materials = {}

    keywords = input("关键词 (必填): ").strip()
    if not keywords:
        print("关键词不能为空")
        return
    materials["keywords"] = keywords

    # 根据内容类型收集更多信息
    if content_type in ["route_guide", "experience_share"]:
        materials["location"] = input("地点: ").strip() or None
        materials["distance"] = input("距离: ").strip() or None
        materials["duration"] = input("用时: ").strip() or None
        materials["highlight"] = input("亮点: ").strip() or None
        materials["regret"] = input("遗憾/教训: ").strip() or None

    elif content_type == "gear_review":
        materials["gear_name"] = input("装备名称: ").strip() or None
        materials["brand"] = input("品牌: ").strip() or None
        materials["price"] = input("价格: ").strip() or None

    elif content_type in ["question_answer", "experience_sharing"]:
        materials["question"] = input("问题: ").strip() or None

    # 语音记录
    transcript = input("语音记录 (可选，直接回车跳过): ").strip()
    if transcript:
        materials["transcript"] = transcript

    # 清理空值
    materials = {k: v for k, v in materials.items() if v}

    print("\n正在生成...")

    try:
        generator = ContentGenerator()
        result = generator.generate(
            platform=platform,
            content_type=content_type,
            materials=materials,
        )

        print("\n" + "=" * 50)
        print(result)
        print("=" * 50)

        # 质量检测
        checker = QualityChecker()
        report = checker.check(result.content, result.title)
        print("\n【内容质量检测】")
        print(report)

        # 询问是否复制
        copy_choice = input("\n复制到剪贴板? (y/n): ").strip().lower()
        if copy_choice == "y":
            copyable = format_copyable_content(result)
            if copy_to_clipboard(copyable):
                print("✓ 已复制到剪贴板")

        # 询问是否保存
        save = input("保存到文件? (y/n): ").strip().lower()
        if save == "y":
            output_dir = Path(__file__).parent / "data" / "generated"
            output_dir.mkdir(parents=True, exist_ok=True)

            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"{platform}_{content_type}_{timestamp}.json"
            output_path = output_dir / filename

            with open(output_path, "w", encoding="utf-8") as f:
                f.write(result.to_json())

            print(f"✓ 已保存到: {output_path}")

        # 打印统计
        print("\n【API 统计】")
        stats = generator.get_stats()
        print(f"  请求次数: {stats['total_requests']}")
        print(f"  输入 tokens: {stats['total_input_tokens']}")
        print(f"  输出 tokens: {stats['total_output_tokens']}")
        print(f"  估算费用: ¥{stats['estimated_cost_cny']}")

    except Exception as e:
        print_user_error(
            problem=f"生成失败: {e}",
            fix="请检查必填项（关键词）和可选素材是否有效",
            example="python forge.py wizard",
        )
        import traceback

        traceback.print_exc()


def _input_yes_no(prompt: str, default: bool = False) -> bool:
    suffix = "Y/n" if default else "y/N"
    raw = input(f"{prompt} ({suffix}): ").strip().lower()
    if not raw:
        return default
    return raw in ("y", "yes")


def _input_non_empty(prompt: str) -> str:
    while True:
        value = input(prompt).strip()
        if value:
            return value
        print("该项不能为空，请重新输入。")


def cmd_wizard(args):
    """向导模式：面向非技术用户的最简生成流程"""
    print("=" * 50)
    print("AI Content Forge - 向导模式")
    print("=" * 50)

    platforms = {
        "1": "xiaohongshu",
        "2": "wechat",
        "3": "zhihu",
        "4": "toutiao",
    }

    print("\n第 1 步：选择平台")
    for idx, key in enumerate(["xiaohongshu", "wechat", "zhihu", "toutiao"], 1):
        print(f"  {idx}. {PLATFORM_CN[key]}")
    platform_choice = input("请选择平台（默认 1）: ").strip() or "1"
    if platform_choice not in platforms:
        print("无效选择，默认使用小红书。")
        platform_choice = "1"
    platform = platforms[platform_choice]

    print(f"\n第 2 步：选择内容类型（{PLATFORM_CN[platform]}）")
    type_options = PLATFORM_CONTENT_TYPES.get(platform, [])
    for i, (code, alias) in enumerate(type_options, 1):
        print(f"  {i}. {alias} ({code})")
    type_choice = input("请选择内容类型（默认 1）: ").strip() or "1"
    if not type_choice.isdigit() or not (1 <= int(type_choice) <= len(type_options)):
        print("无效选择，默认使用第 1 项。")
        type_choice = "1"
    content_type = type_options[int(type_choice) - 1][0]

    print("\n第 3 步：输入关键词")
    keywords = _input_non_empty("请输入关键词（必填）: ")

    print("\n第 4 步：可选补充")
    materials_path = input("素材 JSON 文件路径（可选，直接回车跳过）: ").strip() or None
    kv_text = input("补充素材（可选，格式：地点=杭州,距离=12公里）: ").strip()
    extra_args = []
    if kv_text:
        parts = [p.strip() for p in kv_text.split(",") if p.strip()]
        extra_args = parts

    print("\n第 5 步：输出方式")
    need_save = _input_yes_no("是否保存到文件", default=True)
    need_copy = _input_yes_no("是否复制到剪贴板", default=False)
    need_publish = _input_yes_no("是否发布到平台（半自动）", default=False)
    auto_publish = False
    if need_publish:
        auto_publish = _input_yes_no("是否全自动发布（无确认）", default=False)

    cmd_generate(
        SimpleNamespace(
            platform=platform,
            type=content_type,
            keywords=keywords,
            materials=materials_path,
            save=need_save,
            copy=need_copy,
            no_check=False,
            publish=need_publish,
            auto=auto_publish,
            extra_args=extra_args,
            debug=args.debug,
        )
    )


def cmd_test(args):
    """测试系统"""
    print("=" * 50)
    print("AI Content Forge - 系统测试")
    print("=" * 50)

    # 测试配置加载
    print("\n1. 测试配置加载...")
    try:
        from config_loader import config

        persona = config.get_main_persona()
        print(f"   ✓ 人设: {persona.get('name')}")

        for platform in ["xiaohongshu", "wechat", "zhihu", "toutiao"]:
            pc = config.get_platform_config(platform)
            print(f"   ✓ 平台配置: {pc.get('name')}")

        rules = config.get_anti_ai_rules()
        avoid_count = sum(
            len(v) for v in rules.get("avoid", {}).values() if isinstance(v, list)
        )
        print(f"   ✓ 去AI味规则: {avoid_count} 条")

    except Exception as e:
        print(f"   ✗ 配置加载失败: {e}")
        return

    # 测试 Prompt 构建
    print("\n2. 测试 Prompt 构建...")
    try:
        from generator.prompt_builder import PromptBuilder

        builder = PromptBuilder()
        system_prompt, user_prompt = builder.build(
            platform="xiaohongshu",
            content_type="route_guide",
            materials={"keywords": "测试"},
        )
        print(f"   ✓ System Prompt: {len(system_prompt)} 字符")
        print(f"   ✓ User Prompt: {len(user_prompt)} 字符")

    except Exception as e:
        print(f"   ✗ Prompt 构建失败: {e}")
        return

    # 测试质量检测
    print("\n3. 测试质量检测...")
    try:
        from generator.quality_checker import QualityChecker

        checker = QualityChecker()

        # AI 味重的文本
        ai_text = "首先，让我来介绍一下。其次，这很重要。综上所述，值得一提的是。"
        report1 = checker.check(ai_text)
        print(f"   ✓ AI味文本评分: {report1.score}/100 ({report1.grade})")

        # 自然风格的文本
        natural_text = "说实话这条线真的绝了（腿差点废了）。走了15公里，但是吧，值！"
        report2 = checker.check(natural_text)
        print(f"   ✓ 自然文本评分: {report2.score}/100 ({report2.grade})")

    except Exception as e:
        print(f"   ✗ 质量检测失败: {e}")
        return

    # 测试 LLM 连接
    print("\n4. 测试 LLM 连接...")
    try:
        from generator.llm_client import DeepSeekClient

        client = DeepSeekClient()
        print("   ✓ DeepSeek API 配置正常")

        if args.full:
            print("   正在测试 API 调用...")
            response = client.chat("你好，请用一句话回复。", max_tokens=50)
            print(f"   ✓ API 响应: {response.content[:50]}...")

    except ValueError as e:
        print(f"   ✗ API 配置错误: {e}")
        print("   请在 .env 文件中设置 DEEPSEEK_API_KEY")
    except Exception as e:
        print(f"   ✗ API 测试失败: {e}")

    # 测试剪贴板
    print("\n5. 测试剪贴板...")
    try:
        test_text = "AI Content Forge 测试"
        if copy_to_clipboard(test_text):
            print("   ✓ 剪贴板功能正常")
        else:
            print("   ✗ 剪贴板功能异常")
    except Exception as e:
        print(f"   ✗ 剪贴板测试失败: {e}")

    # 测试回归脚本
    print("\n6. 测试回归脚本...")
    script_dir = Path(__file__).parent / "scripts"
    regression_scripts = [
        script_dir / "xiaohongshu_regression.py",
        script_dir / "wechat_regression.py",
        script_dir / "toutiao_regression.py",
        script_dir / "zhihu_format_regression.py",
        script_dir / "zhihu_e2e_regression.py",
    ]

    for script in regression_scripts:
        if not script.exists():
            print(f"   ⚠ 跳过（文件不存在）: {script.name}")
            continue

        print(f"   → 运行: {script.name}")
        result = subprocess.run(
            [sys.executable, str(script)], capture_output=True, text=True
        )
        if result.returncode == 0:
            print(f"   ✓ 通过: {script.name}")
        else:
            print(f"   ✗ 失败: {script.name}")
            if result.stdout.strip():
                print(result.stdout.strip())
            if result.stderr.strip():
                print(result.stderr.strip())
            return

    print("\n" + "=" * 50)
    print("测试完成!")


def cmd_list(args):
    """列出可用的平台、内容类型和场景"""
    target = args.target

    if target in (None, "platforms"):
        print("【平台】")
        parts = [f"  {a} = {PLATFORM_CN[f]}" for a, f in PLATFORM_ALIASES.items()]
        print("\n".join(parts))
        if target == "platforms":
            return
        print()

    if target in (None, "types"):
        print("【内容类型】")
        for platform, types in PLATFORM_CONTENT_TYPES.items():
            cn = PLATFORM_CN[platform]
            type_strs = [f"{alias}({code})" for code, alias in types]
            print(f"  {cn}: {' '.join(type_strs)}")
        if target == "types":
            return
        print()

    if target in (None, "scenarios"):
        import yaml

        print("【场景】")
        scenario_dir = Path(__file__).parent / "config" / "prompts" / "scenarios"
        if scenario_dir.exists():
            for yaml_file in sorted(scenario_dir.glob("*.yaml")):
                try:
                    with open(yaml_file, "r", encoding="utf-8") as f:
                        data = yaml.safe_load(f)
                    cat = data.get("category", yaml_file.stem)
                    cat_name = data.get("name", cat)
                    scenarios = data.get("scenarios", {})
                    items = [
                        f"{name}({info.get('name', name)})"
                        for name, info in scenarios.items()
                    ]
                    print(f"  {cat}({cat_name}): {' '.join(items)}")
                except Exception:
                    continue


def cmd_scenario(args):
    """根据场景生成内容"""
    from generator.content_generator import ContentGenerator
    from generator.quality_checker import QualityChecker

    # 从剩余参数中分离 scenario_name 和 key=value 素材
    scenario_name = args.name
    extra_kv_args = []
    for arg in args.extra_args:
        if "=" in arg:
            extra_kv_args.append(arg)
        elif scenario_name is None:
            scenario_name = arg
        else:
            extra_kv_args.append(arg)

    if not scenario_name:
        print_user_error(
            problem="缺少场景名称",
            fix="请通过位置参数或 -n 指定场景名称",
            example="forge.py s hiking_trip 或 forge.py s -n hiking_trip",
        )
        print("可用场景: 运行 forge.py list scenarios")
        sys.exit(1)

    # 自动推断 category（如果未指定 -c）
    category = args.category
    if not category:
        index = build_scenario_index()
        category = index.get(scenario_name)
        if not category:
            print_user_error(
                problem=f"未找到场景 '{scenario_name}'",
                fix="请先查看可用场景名称，再使用 -n 指定",
                example="forge.py list scenarios",
            )
            sys.exit(1)

    # 构建素材（支持 JSON 文件路径或内联 JSON）
    materials = {}
    if args.materials:
        materials = load_materials(args.materials)

    # 解析行内 key=value 素材
    if extra_kv_args:
        materials.update(parse_kv_materials(extra_kv_args))

    # 添加关键词（CLI 参数优先）
    if args.keywords:
        materials["keywords"] = args.keywords

    # 解析平台（支持缩写）
    platforms = None
    if args.platforms:
        platforms = [resolve_platform(p.strip()) for p in args.platforms.split(",")]

    try:
        generator = ContentGenerator()
        checker = QualityChecker()

        results = generator.generate_from_scenario(
            scenario_category=category,
            scenario_name=scenario_name,
            materials=materials,
            platforms=platforms,
        )

        # 输出结果
        for platform, contents in results.items():
            print(f"\n{'=' * 50}")
            print(f"平台: {platform}")
            print("=" * 50)
            for content in contents:
                print(content)

                # 质量检测
                report = checker.check(content.content, content.title)
                print(f"\n质量: {report.score}/100 {report.grade_emoji}")
                print("-" * 30)

        # 保存到文件
        if args.save:
            output_dir = Path(__file__).parent / "data" / "generated"
            output_dir.mkdir(parents=True, exist_ok=True)

            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

            for platform, contents in results.items():
                for i, content in enumerate(contents):
                    suffix = f"_{i}" if len(contents) > 1 else ""
                    filename = (
                        f"{platform}_{content.content_type}{suffix}_{timestamp}.json"
                    )
                    output_path = output_dir / filename

                    with open(output_path, "w", encoding="utf-8") as f:
                        f.write(content.to_json())

                    print(f"\n✓ 已保存: {output_path}")

        # 发布到各平台
        if args.publish:
            publish_platforms = list(results.keys())
            publish_results(
                results=results,
                platforms=publish_platforms,
                auto_confirm=args.auto,
            )

        # 打印统计
        print("\n【API 统计】")
        stats = generator.get_stats()
        print(f"  请求次数: {stats['total_requests']}")
        print(f"  估算费用: ¥{stats['estimated_cost_cny']}")

    except Exception as e:
        print_user_error(
            problem=f"生成失败: {e}",
            fix="请检查场景参数与素材字段；必要时加 --debug 获取详细错误",
            example='forge.py s hiking_trip -k "莫干山" --debug',
        )
        if args.debug:
            import traceback

            traceback.print_exc()
        sys.exit(1)


def main():
    parser = argparse.ArgumentParser(
        description="AI Content Forge - 多平台内容自动生成工具",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  forge.py list                                        # 查看可用平台/类型/场景
  forge.py wizard                                      # 向导模式（推荐）
  forge.py gen -p xhs -t 攻略 -k "莫干山" --copy       # 小红书攻略
  forge.py gen -p xhs -t 攻略 -k "莫干山" 距离=15km    # 带行内素材
  forge.py gen -p zh -t 问答 -k "徒步装备"             # 知乎问答
  forge.py s hiking_trip -k "莫干山"                    # 场景生成(自动推断)
  forge.py s project_promotion -m data/materials/aief.json  # 项目推广
  forge.py quick "莫干山徒步攻略"                       # 快速生成
  forge.py check "要检测的文本"                         # 检测AI味

平台缩写: xhs=小红书 wx=公众号 zh=知乎 tt=头条
        """,
    )
    parser.add_argument("--debug", action="store_true", help="显示调试信息")

    subparsers = parser.add_subparsers(dest="command", help="可用命令")

    # quick 命令 - 最简单的方式
    quick_parser = subparsers.add_parser(
        "quick", aliases=["q"], help="快速生成 (自动识别平台和类型)"
    )
    quick_parser.add_argument("prompt", help="生成提示，如 '莫干山徒步攻略'")
    quick_parser.set_defaults(func=cmd_quick)

    # generate 命令
    gen_parser = subparsers.add_parser(
        "generate", aliases=["gen", "g"], help="生成内容"
    )
    gen_parser.add_argument(
        "-p",
        "--platform",
        required=True,
        help="目标平台 (xhs/wx/zh/tt 或全名)",
    )
    gen_parser.add_argument(
        "-t",
        "--type",
        required=True,
        help="内容类型 (攻略/测评/分享 或英文代码)",
    )
    gen_parser.add_argument("-k", "--keywords", help="关键词（素材文件包含时可省略）")
    gen_parser.add_argument(
        "-m", "--materials", help="额外素材 (JSON 字符串或 JSON 文件路径)"
    )
    gen_parser.add_argument("-s", "--save", action="store_true", help="保存到文件")
    gen_parser.add_argument("-c", "--copy", action="store_true", help="复制到剪贴板")
    gen_parser.add_argument("--no-check", action="store_true", help="跳过质量检测")
    gen_parser.add_argument(
        "--publish", action="store_true", help="生成后发布到平台（半自动）"
    )
    gen_parser.add_argument(
        "--auto",
        action="store_true",
        help="全自动发布（跳过确认，需配合 --publish）",
    )
    gen_parser.set_defaults(func=cmd_generate)

    # wizard 命令
    wizard_parser = subparsers.add_parser(
        "wizard", aliases=["w"], help="向导模式（推荐非技术用户）"
    )
    wizard_parser.set_defaults(func=cmd_wizard)

    # list 命令
    list_parser = subparsers.add_parser(
        "list", aliases=["ls"], help="列出可用平台/类型/场景"
    )
    list_parser.add_argument(
        "target",
        nargs="?",
        choices=["platforms", "types", "scenarios"],
        help="要查看的类别 (不填则显示全部)",
    )
    list_parser.set_defaults(func=cmd_list)

    # check 命令
    check_parser = subparsers.add_parser("check", help="检测内容质量 (AI味程度)")
    check_parser.add_argument("text", help="要检测的文本或文件路径")
    check_parser.set_defaults(func=cmd_check)

    # interactive 命令
    int_parser = subparsers.add_parser("interactive", aliases=["i"], help="交互式模式")
    int_parser.set_defaults(func=cmd_interactive)

    # scenario 命令
    scn_parser = subparsers.add_parser("scenario", aliases=["s"], help="根据场景生成")
    scn_parser.add_argument("-c", "--category", help="场景类别（可选，自动推断）")
    scn_parser.add_argument("-n", "--name", help="场景名称")
    scn_parser.add_argument("-k", "--keywords", help="关键词")
    scn_parser.add_argument(
        "-m",
        "--materials",
        help="素材 (JSON 字符串或 JSON 文件路径)",
    )
    scn_parser.add_argument("--platforms", help="指定平台 (逗号分隔，如 xhs,zh)")
    scn_parser.add_argument("-s", "--save", action="store_true", help="保存到文件")
    scn_parser.add_argument(
        "--publish", action="store_true", help="生成后发布到各平台（半自动）"
    )
    scn_parser.add_argument(
        "--auto",
        action="store_true",
        help="全自动发布（跳过确认，需配合 --publish）",
    )
    scn_parser.set_defaults(func=cmd_scenario)

    # test 命令
    test_parser = subparsers.add_parser("test", help="测试系统")
    test_parser.add_argument(
        "--full", action="store_true", help="完整测试（包括 API 调用）"
    )
    test_parser.set_defaults(func=cmd_test)

    args, remaining = parser.parse_known_args()

    if not args.command:
        parser.print_help()
        sys.exit(0)

    # 只有 generate 和 scenario 支持行内 key=value 参数
    if args.command in ("generate", "gen", "g", "scenario", "s"):
        args.extra_args = remaining
    elif remaining:
        print_user_error(
            problem=f"无法识别的参数: {' '.join(remaining)}",
            fix="请检查参数拼写，或运行 -h 查看命令帮助",
            example="python forge.py generate -h",
        )
        parser.print_help()
        sys.exit(2)
    else:
        args.extra_args = []

    args.func(args)


if __name__ == "__main__":
    main()
