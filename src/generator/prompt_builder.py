"""
Prompt 构建器 - 根据配置构建完整的 Prompt
"""

from pathlib import Path
from typing import Dict, Any, Optional, Tuple
import sys

# 确保可以导入同级模块
sys.path.insert(0, str(Path(__file__).parent.parent))

from config_loader import config


class PromptBuilder:
    """
    Prompt 构建器

    根据人设配置、平台规则、去 AI 味规则，构建完整的 Prompt
    """

    def __init__(self):
        self.config = config

    def build(
        self,
        platform: str,
        content_type: str,
        materials: Dict[str, Any],
        extra_context: Optional[Dict[str, Any]] = None,
    ) -> Tuple[str, str]:
        """
        构建完整的 Prompt

        Args:
            platform: 目标平台 (xiaohongshu/wechat/zhihu/toutiao)
            content_type: 内容类型 (route_guide/gear_review/experience_share 等)
            materials: 素材信息
            extra_context: 额外上下文

        Returns:
            (system_prompt, user_prompt) 元组
        """
        # 获取配置
        prompt_template = self.config.get_prompt_template(platform)
        persona_config = self.config.get_persona_for_platform(platform)
        anti_ai_rules = self.config.get_anti_ai_rules()

        # 构建 system prompt
        system_prompt = prompt_template.get(
            "system_prompt", "你是一个专业的内容创作助手。"
        )

        # 构建 user prompt
        user_prompt = self._build_user_prompt(
            platform=platform,
            template=prompt_template.get("user_prompt_template", ""),
            content_type=content_type,
            content_type_config=prompt_template.get("content_types", {}).get(
                content_type, {}
            ),
            persona=persona_config,
            anti_ai_rules=anti_ai_rules,
            materials=materials,
            extra_context=extra_context,
        )

        return system_prompt, user_prompt

    def _build_user_prompt(
        self,
        platform: str,
        template: str,
        content_type: str,
        content_type_config: Dict[str, Any],
        persona: Dict[str, Any],
        anti_ai_rules: Dict[str, Any],
        materials: Dict[str, Any],
        extra_context: Optional[Dict[str, Any]] = None,
    ) -> str:
        """构建 user prompt"""

        main_persona = persona.get("main", {})
        adjustments = persona.get("adjustments", {})
        platform_adjustments = anti_ai_rules.get("platform_adjustments", {})

        # 准备替换变量
        variables = {
            # 人设信息
            "persona_identity": main_persona.get("identity", ""),
            "persona_profession": main_persona.get("background", {}).get(
                "profession", ""
            ),
            "persona_outdoor": self._format_outdoor_experience(main_persona),
            "persona_hobbies": self._format_hobbies(main_persona),
            "persona_voice_style": self._format_voice_style(main_persona, adjustments),
            # 去 AI 味规则
            "avoid_words": self._format_avoid_words(anti_ai_rules),
            # 内容类型
            "content_type": content_type,
            "content_type_instructions": content_type_config.get(
                "extra_instructions", ""
            ),
            # 素材信息
            "keywords": materials.get("keywords", ""),
            "materials": self._format_materials(materials),
            "transcript": materials.get("transcript", "无"),
            "photo_descriptions": materials.get("photo_descriptions", "无"),
            "topic": materials.get("topic", ""),
            "main_point": materials.get("main_point", ""),
            "question": materials.get("question", ""),
            # 项目推广素材
            "project_info": self._format_project_info(materials),
        }

        # 添加额外上下文
        if extra_context:
            variables.update(extra_context)

        # 替换模板变量
        result = template
        for key, value in variables.items():
            result = result.replace(f"{{{key}}}", str(value))

        # 添加内容类型特定指令
        if content_type_config.get("extra_instructions"):
            result += (
                f"\n\n【内容类型特别要求】\n{content_type_config['extra_instructions']}"
            )

        platform_rules = self._format_platform_adjustments(
            platform, platform_adjustments.get(platform, {})
        )
        if platform_rules:
            result += f"\n\n【平台差异化去AI味要求】\n{platform_rules}"

        result += "\n\n【真实性硬约束】\n- 正文至少加入2个可核验细节（时间/地点/数字/品牌/操作步骤）\n- 至少加入1处不完美细节（遗憾/失误/不确定）\n- 优先保留具体事实，不要只给抽象结论"

        return result

    def _format_outdoor_experience(self, persona: Dict[str, Any]) -> str:
        """格式化户外经验"""
        outdoor = persona.get("background", {}).get("outdoor", {})
        if not outdoor:
            return ""

        role = outdoor.get("role", "")
        years = outdoor.get("years", "")
        count = outdoor.get("activities_count", "")
        types = outdoor.get("types", [])

        parts = []
        if role:
            parts.append(role)
        if years:
            parts.append(f"{years}年经验")
        if count:
            parts.append(f"带队{count}次")
        if types:
            parts.append(f"擅长{'/'.join(types)}")

        return "，".join(parts)

    def _format_hobbies(self, persona: Dict[str, Any]) -> str:
        """格式化爱好"""
        hobbies = persona.get("background", {}).get("hobbies", [])
        if not hobbies:
            return ""

        parts = []
        for hobby in hobbies:
            name = hobby.get("name", "")
            level = hobby.get("level", "")
            if name and level:
                parts.append(f"{name}（{level}）")
            elif name:
                parts.append(name)

        return "、".join(parts)

    def _format_voice_style(
        self, persona: Dict[str, Any], adjustments: Dict[str, Any]
    ) -> str:
        """格式化写作风格"""
        voice_style = persona.get("voice_style", {})
        general = voice_style.get("general", [])

        # 加入平台调整
        special_notes = adjustments.get("special_notes", [])
        tone = adjustments.get("tone", "")

        parts = []
        if tone:
            parts.append(f"整体风格：{tone}")
        parts.extend([f"- {item}" for item in general])
        if special_notes:
            parts.append("\n平台特别注意：")
            parts.extend([f"- {note}" for note in special_notes])

        return "\n".join(parts)

    def _format_avoid_words(self, anti_ai_rules: Dict[str, Any]) -> str:
        """格式化避免词汇 - 按分类完整展示"""
        avoid = anti_ai_rules.get("avoid", {})

        category_names = {
            "connectors": "连接过渡词",
            "ai_phrases": "AI套话",
            "self_references": "自称",
            "openings": "开场白",
            "endings": "结尾套话",
            "modifiers": "程度修饰词",
            "parallel_patterns": "排比句式",
        }

        lines = []
        for category, words in avoid.items():
            if isinstance(words, list) and words:
                label = category_names.get(category, category)
                lines.append(f"【{label}】{' / '.join(words)}")

        return "\n".join(lines)

    def _format_platform_adjustments(
        self, platform: str, platform_adjustment: Dict[str, Any]
    ) -> str:
        if not platform_adjustment:
            return ""

        lines = [f"平台：{platform}"]
        labels = {
            "more_colloquial": "更口语化",
            "very_colloquial": "非常口语化",
            "slightly_formal": "略正式",
            "more_professional": "更专业",
            "simple_language": "语言简洁易懂",
            "storytelling": "注重叙事",
            "support_with_evidence": "观点需有依据",
            "can_use_data": "可适当引用数据",
            "can_be_literary": "可适度文学化",
            "can_use_network_slang": "可适度使用网络用语",
            "accessible": "面向大众易读",
            "evidence_required": "必须包含可核验细节",
            "avoid_emotion_slang": "避免情绪化网络词堆砌",
            "allow_mild_slang": "允许轻度网络词",
            "require_scene_detail": "必须有场景细节",
        }

        for key, value in platform_adjustment.items():
            if isinstance(value, bool):
                if value:
                    lines.append(f"- {labels.get(key, key)}")
            else:
                lines.append(f"- {labels.get(key, key)}: {value}")

        return "\n".join(lines)

    def _format_materials(self, materials: Dict[str, Any]) -> str:
        """格式化素材信息"""
        parts = []

        # 基本信息字段映射
        field_labels = {
            "route_name": "路线",
            "location": "地点",
            "distance": "距离",
            "duration": "用时",
            "difficulty": "难度",
            "elevation_gain": "爬升",
            "participants": "人数",
            "weather": "天气",
            "highlight": "亮点",
            "regret": "遗憾/教训",
            "gear_name": "装备",
            "brand": "品牌",
            "price": "价格",
            "cocktail_name": "鸡尾酒",
            "song_name": "歌曲",
            "tool_name": "工具",
            "project_name": "项目名称",
            "github_url": "GitHub",
            "one_liner": "一句话介绍",
        }

        for key, label in field_labels.items():
            if key in materials and materials[key]:
                parts.append(f"- {label}: {materials[key]}")

        # 详细描述
        if "description" in materials:
            parts.append(f"\n详细描述：\n{materials['description']}")

        return "\n".join(parts) if parts else "无"

    def _format_project_info(self, materials: Dict[str, Any]) -> str:
        """格式化项目推广素材信息"""
        parts = []

        # 基本信息
        if materials.get("project_name"):
            parts.append(f"## 项目名称\n{materials['project_name']}")
        if materials.get("github_url"):
            parts.append(f"\n## GitHub 地址\n{materials['github_url']}")
        if materials.get("one_liner"):
            parts.append(f"\n## 一句话介绍\n{materials['one_liner']}")
        if materials.get("init_command"):
            parts.append(f"\n## 快速开始\n{materials['init_command']}")

        # 核心价值
        if materials.get("core_value"):
            parts.append(f"\n## 核心价值\n{materials['core_value']}")

        # 痛点
        if materials.get("pain_points"):
            pain_points = materials["pain_points"]
            if isinstance(pain_points, list):
                formatted = "\n".join(f"- {p}" for p in pain_points)
                parts.append(f"\n## 核心痛点\n{formatted}")
            else:
                parts.append(f"\n## 核心痛点\n{pain_points}")

        # 与现有工具的对比（如 rules vs 框架）
        if materials.get("rules_vs_aief"):
            rv = materials["rules_vs_aief"]
            parts.append(f"\n## 与现有 rules 的区别")
            if isinstance(rv, dict):
                if rv.get("description"):
                    parts.append(rv["description"])
                if rv.get("comparison") and isinstance(rv["comparison"], list):
                    for item in rv["comparison"]:
                        dim = item.get("dimension", "")
                        rules = item.get("rules", "")
                        aief = item.get("aief", "")
                        parts.append(f"\n### {dim}")
                        parts.append(f"- 传统 rules：{rules}")
                        parts.append(f"- AIEF：{aief}")
                if rv.get("key_insight"):
                    parts.append(f"\n**关键洞察**：{rv['key_insight']}")
            else:
                parts.append(str(rv))

        # 关键特性
        if materials.get("key_features"):
            features = materials["key_features"]
            if isinstance(features, list):
                formatted = "\n".join(f"- {f}" for f in features)
                parts.append(f"\n## 关键特性\n{formatted}")

        # 技术细节
        if materials.get("tech_details"):
            details = materials["tech_details"]
            if isinstance(details, list):
                formatted = "\n".join(f"- {d}" for d in details)
                parts.append(f"\n## 技术细节\n{formatted}")

        # 作者背景
        if materials.get("author_background"):
            parts.append(f"\n## 作者背景\n{materials['author_background']}")

        # 推广角度（平台相关）
        if materials.get("promotion_angles"):
            angles = materials["promotion_angles"]
            if isinstance(angles, dict):
                parts.append(f"\n## 推广角度建议")
                for platform, info in angles.items():
                    if isinstance(info, dict):
                        angle = info.get("angle", "")
                        focus = info.get("focus", "")
                        parts.append(f"- {platform}: {angle}（{focus}）")

        if not parts:
            return "无项目信息"

        return "\n".join(parts)


# 便捷函数
def build_prompt(
    platform: str,
    content_type: str,
    materials: Dict[str, Any],
    extra_context: Optional[Dict[str, Any]] = None,
) -> Tuple[str, str]:
    """便捷函数：构建 Prompt"""
    builder = PromptBuilder()
    return builder.build(platform, content_type, materials, extra_context)


if __name__ == "__main__":
    # 测试
    print("=== Prompt 构建器测试 ===\n")

    builder = PromptBuilder()

    # 测试素材
    test_materials = {
        "keywords": "莫干山徒步",
        "route_name": "莫干山环线",
        "location": "浙江德清莫干山",
        "distance": "15公里",
        "duration": "6小时",
        "difficulty": "中级",
        "elevation_gain": "800米",
        "highlight": "竹林小道特别美，偶遇一只松鼠",
        "regret": "没带够水，最后2公里渴死了",
    }

    # 构建小红书 Prompt
    system_prompt, user_prompt = builder.build(
        platform="xiaohongshu", content_type="route_guide", materials=test_materials
    )

    print("【System Prompt】")
    print(system_prompt[:200] + "...")
    print("\n【User Prompt 片段】")
    print(user_prompt[:500] + "...")

    print("\n✓ Prompt 构建测试完成")
