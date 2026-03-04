"""
内容生成器 - 核心生成模块
"""

import re
from pathlib import Path
from typing import Dict, Any, Optional, List
from datetime import datetime
from dataclasses import dataclass, field
import sys
import json

# 确保可以导入同级模块
sys.path.insert(0, str(Path(__file__).parent.parent))

from config_loader import config, load_scenario
from generator.llm_client import DeepSeekClient, get_client
from generator.prompt_builder import PromptBuilder
from generator.quality_checker import QualityChecker, QualityReport


# 默认配置
DEFAULT_MIN_SCORE = 70  # 最低合格分数
DEFAULT_MAX_RETRIES = 3  # 最大重试次数


@dataclass
class GeneratedContent:
    """生成的内容结构"""

    platform: str
    content_type: str
    title: str
    content: str
    tags: List[str] = field(default_factory=list)
    summary: str = ""
    image_suggestions: str = ""
    raw_output: str = ""
    quality_score: int = 0  # 质量分数
    quality_grade: str = ""  # 质量等级
    generation_attempts: int = 1  # 生成尝试次数
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())

    def to_dict(self) -> Dict[str, Any]:
        return {
            "platform": self.platform,
            "content_type": self.content_type,
            "title": self.title,
            "content": self.content,
            "tags": self.tags,
            "summary": self.summary,
            "image_suggestions": self.image_suggestions,
            "quality_score": self.quality_score,
            "quality_grade": self.quality_grade,
            "generation_attempts": self.generation_attempts,
            "timestamp": self.timestamp,
        }

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), ensure_ascii=False, indent=2)

    def __str__(self) -> str:
        lines = [
            f"📱 平台: {self.platform}",
            f"📝 类型: {self.content_type}",
            f"📌 标题: {self.title}",
            "",
            "正文:",
            self.content,
            "",
        ]
        if self.tags:
            lines.append(f"🏷️ 标签: {' '.join(['#' + t for t in self.tags])}")
        if self.image_suggestions:
            lines.append(f"🖼️ 配图建议: {self.image_suggestions}")
        if self.quality_score:
            grade_emoji = {"A": "🌟", "B": "✅", "C": "⚠️", "D": "⛔", "F": "💀"}.get(
                self.quality_grade, "❓"
            )
            lines.append(
                f"📊 质量: {self.quality_score}/100 {grade_emoji} ({self.quality_grade}级)"
            )
            if self.generation_attempts > 1:
                lines.append(f"🔄 生成次数: {self.generation_attempts}")
        return "\n".join(lines)


class ContentGenerator:
    """
    内容生成器

    负责根据素材生成多平台内容
    """

    PLATFORM_NAMES = {
        "xiaohongshu": "小红书",
        "wechat": "公众号",
        "zhihu": "知乎",
        "toutiao": "今日头条",
    }

    def __init__(self, client: Optional[DeepSeekClient] = None):
        self.client = client or get_client()
        self.prompt_builder = PromptBuilder()
        self.quality_checker = QualityChecker()

    def generate(
        self,
        platform: str,
        content_type: str,
        materials: Dict[str, Any],
        extra_context: Optional[Dict[str, Any]] = None,
        min_score: Optional[int] = None,
        max_retries: int = DEFAULT_MAX_RETRIES,
        auto_retry: bool = True,
        ai_disclaimer: bool = True,
    ) -> GeneratedContent:
        """
        为单个平台生成内容（带自检和自动重试）

        Args:
            platform: 目标平台
            content_type: 内容类型
            materials: 素材信息
            extra_context: 额外上下文
            min_score: 最低合格分数 (0-100)，不传则按平台阈值
            max_retries: 最大重试次数
            auto_retry: 是否自动重试（不合格时）
            ai_disclaimer: 是否在末尾追加 AI 辅助生成声明

        Returns:
            GeneratedContent 对象
        """
        platform_name = self.PLATFORM_NAMES.get(platform, platform)
        effective_min_score = (
            min_score
            if min_score is not None
            else self._get_platform_min_score(platform)
        )

        best_result = None
        best_score = 0
        attempts = 0
        last_report = None
        last_unsupported_claims: List[str] = []

        for attempt in range(max_retries):
            attempts = attempt + 1

            if attempt == 0:
                print(
                    f"正在生成 {platform_name} 内容... (目标阈值: {effective_min_score}/100)"
                )
            else:
                print(f"  ↻ 重新生成 (第 {attempts} 次)...")

            # 构建 Prompt
            system_prompt, user_prompt = self.prompt_builder.build(
                platform=platform,
                content_type=content_type,
                materials=materials,
                extra_context=extra_context,
            )

            # 如果是重试，增加动态去 AI 味提示
            if attempt > 0:
                retry_hint = self._build_retry_hint(
                    last_report, attempts, last_unsupported_claims
                )
                user_prompt += retry_hint

            # 调用 LLM
            response = self.client.chat(
                prompt=user_prompt,
                system_prompt=system_prompt,
                temperature=0.8 + (attempt * 0.05),  # 每次重试稍微提高温度
            )

            # 解析输出
            parsed = self._parse_output(response.content, platform)

            # 质量检测
            report = self.quality_checker.check(
                parsed.get("content", ""),
                parsed.get("title", ""),
                platform,
            )
            last_report = report

            strict_factual = self._is_strict_factual_mode(content_type, materials)
            unsupported_claims = []
            if strict_factual:
                unsupported_claims = self._find_unsupported_claims(
                    parsed.get("content", ""), materials
                )
                last_unsupported_claims = unsupported_claims

            result = GeneratedContent(
                platform=platform,
                content_type=content_type,
                title=parsed.get("title", ""),
                content=parsed.get("content", ""),
                tags=parsed.get("tags", []),
                summary=parsed.get("summary", ""),
                image_suggestions=parsed.get("image_suggestions", ""),
                raw_output=response.content,
                quality_score=report.score,
                quality_grade=report.grade,
                generation_attempts=attempts,
            )

            # 更新最佳结果
            if report.score > best_score:
                best_score = report.score
                best_result = result

            # 检查是否达标
            factual_ok = not strict_factual or len(unsupported_claims) == 0
            if report.score >= effective_min_score and factual_ok:
                print(
                    f"✓ {platform_name} 内容生成完成 (质量: {report.score}/100 {report.grade_emoji})"
                )
                if ai_disclaimer:
                    result.content += "\n\n---\n*本文由AI辅助生成*"
                return result
            else:
                gap = effective_min_score - report.score
                if strict_factual and unsupported_claims:
                    print(
                        "  ⚠ 严格事实模式未通过，检测到无依据声明: "
                        + "；".join(unsupported_claims[:3])
                    )
                if auto_retry and attempt < max_retries - 1:
                    print(
                        f"  ⚠ 质量不达标 ({report.score}/100，还差 {gap} 分)，发现 AI 味词汇: {', '.join(report.ai_words_found[:3])}"
                    )
                else:
                    print(
                        f"✓ {platform_name} 内容生成完成 (质量: {report.score}/100 {report.grade_emoji})"
                    )

        # 返回最佳结果
        if best_result:
            if best_score < effective_min_score:
                print(f"  ⚠ 已达最大重试次数，返回最佳结果 (分数: {best_score}/100)")
            if ai_disclaimer:
                best_result.content += "\n\n---\n*本文由AI辅助生成*"
            return best_result

        raise Exception("生成失败")

    def generate_multi(
        self,
        platforms: List[str],
        content_types: Dict[str, str],
        materials: Dict[str, Any],
    ) -> Dict[str, GeneratedContent]:
        """
        为多个平台生成内容

        Args:
            platforms: 目标平台列表
            content_types: 每个平台的内容类型 {platform: content_type}
            materials: 素材信息

        Returns:
            {platform: GeneratedContent} 字典
        """
        results = {}

        for platform in platforms:
            content_type = content_types.get(platform, "general")
            try:
                results[platform] = self.generate(
                    platform=platform, content_type=content_type, materials=materials
                )
            except Exception as e:
                print(f"✗ {self.PLATFORM_NAMES.get(platform, platform)} 生成失败: {e}")

        return results

    def generate_from_scenario(
        self,
        scenario_category: str,
        scenario_name: str,
        materials: Dict[str, Any],
        platforms: Optional[List[str]] = None,
    ) -> Dict[str, List[GeneratedContent]]:
        """
        根据场景模板生成内容

        Args:
            scenario_category: 场景类别 (outdoor/lifestyle/tech)
            scenario_name: 场景名称 (hiking_trip/cocktail_making 等)
            materials: 素材信息
            platforms: 指定平台（可选，默认全部）

        Returns:
            {platform: [GeneratedContent, ...]} 字典
        """
        scenario = load_scenario(scenario_category, scenario_name)
        if not scenario:
            raise ValueError(f"未找到场景: {scenario_category}/{scenario_name}")

        output_matrix = scenario.get("output_matrix", {})

        if platforms:
            output_matrix = {p: v for p, v in output_matrix.items() if p in platforms}

        results = {}

        for platform, content_configs in output_matrix.items():
            results[platform] = []

            for content_config in content_configs:
                content_type = content_config.get("type", "general")

                # 检查条件
                condition = content_config.get("conditional")
                if condition and not self._check_condition(condition, materials):
                    continue

                try:
                    content = self.generate(
                        platform=platform,
                        content_type=content_type,
                        materials=materials,
                        extra_context={
                            "title_template": content_config.get("title_template", ""),
                            "focus": content_config.get("focus", ""),
                        },
                    )
                    results[platform].append(content)
                except Exception as e:
                    print(f"✗ {platform}/{content_type} 生成失败: {e}")

        return results

    def _build_retry_hint(
        self,
        report: Optional[QualityReport],
        attempt: int,
        unsupported_claims: Optional[List[str]] = None,
    ) -> str:
        """根据上次检测报告动态构建重试提示"""
        hints = []

        dimension_hints = {
            "ai_words": "绝对不要用AI套话（如'首先/其次/最后'、'值得一提'、'综上所述'等）",
            "sentence_repetition": "句子开头不要重复，变换句式，别每句都用同样的开头",
            "parallel_structure": "不要用排比句式（不仅...还...、一方面...另一方面），减少列表罗列",
            "structure_repetition": "不要连续使用同一种句式结构（如一直'因为...所以...'），多切换表达逻辑",
            "paragraph_uniformity": "段落长度要参差不齐，不要每段都差不多长",
            "rhythm_variation": "长短句交替，不要整篇都是同一节奏",
            "opening_ending": "开头直接切入主题，结尾不要用套话（如'希望对大家有帮助'）",
            "summary_structure": "结尾别做总结升华，改成开放式收束或一句真实感受",
            "lexical_diversity": "用词要丰富，不要反复使用相同的词",
            "good_expressions": "多用口语：整、弄、折腾、说实话、但是吧",
            "specific_details": "加入具体细节：128块、15公里、早上6点",
            "evidence_density": "至少写入2个可核验锚点：时间/地点/数字/品牌/操作步骤",
            "short_sentences": "适当使用短句增加节奏感，如'累。但值。'",
            "uncertainty": "加入不确定表达：好像是、大概、记不太清了",
            "personal_voice": "用第一人称'我'讲述，加入个人经历和感受",
            "emotion_layers": "加入不同情感：既有开心也有遗憾或吐槽",
        }

        if report and report.dimension_scores:
            # 按分数从低到高排序，取最差的维度
            sorted_dims = sorted(report.dimension_scores.items(), key=lambda x: x[1])
            for dim, score in sorted_dims:
                if score < 0 and dim in dimension_hints:
                    hints.append(f"- {dimension_hints[dim]}")
                if len(hints) >= 4:
                    break

            # 如果扣分维度不够，补充加分为0的维度
            for dim, score in sorted_dims:
                if score == 0 and dim in dimension_hints:
                    hints.append(f"- {dimension_hints[dim]}")
                if len(hints) >= 6:
                    break

            # 如果 ai_words 扣分严重，列出具体词汇
            if report.ai_words_found:
                words_str = "、".join(report.ai_words_found[:5])
                hints.append(f"- 上次发现了这些AI味词汇，务必避免：{words_str}")

            if unsupported_claims:
                hints.append(
                    "- 严格事实模式：删除或改写无依据声明："
                    + "；".join(unsupported_claims[:4])
                )
        else:
            # 没有报告时的通用提示
            hints = [
                "- 绝对不要用'首先/其次/最后'这类词",
                "- 多用口语：整、弄、折腾、说实话、但是吧",
                "- 用括号吐槽：（腿已经不是我的了）",
                "- 加入具体细节：128块、15公里、早上6点",
            ]

        hint_text = "\n".join(hints[:6])
        return f"""

【重要提醒 - 第 {attempt} 次生成】
先锁定内容通道：保留事实点和核心观点，不要改掉真实信息。
再重写表达通道：只调整句式、节奏和段落组织，让语气更自然。
上次生成的内容质量不达标，请特别注意：
{hint_text}
"""

    def _is_strict_factual_mode(
        self, content_type: str, materials: Dict[str, Any]
    ) -> bool:
        if content_type != "project_promotion":
            return False
        return bool(materials.get("strict_factual", True))

    def _extract_numbers(self, value: Any) -> List[str]:
        numbers: List[str] = []
        if isinstance(value, dict):
            for v in value.values():
                numbers.extend(self._extract_numbers(v))
            return numbers
        if isinstance(value, list):
            for v in value:
                numbers.extend(self._extract_numbers(v))
            return numbers
        if value is None:
            return numbers
        text = str(value)
        numbers.extend(re.findall(r"\d+(?:\.\d+)?", text))
        return numbers

    def _find_unsupported_claims(
        self, content: str, materials: Dict[str, Any]
    ) -> List[str]:
        allowed_numbers = set(self._extract_numbers(materials))
        unsupported: List[str] = []

        quantitative_patterns = [
            r"(\d+(?:\.\d+)?\s*(?:个|位|人|万|k|K)?\s*(?:用户|人使用|star|stars|issue|下载|反馈))",
            r"(已有\d+(?:\.\d+)?\s*(?:个|位|人|万|k|K)?\s*(?:用户|反馈|下载))",
            r"(\d+(?:\.\d+)?\s*%\s*(?:提升|降低|减少|增长))",
        ]

        for pattern in quantitative_patterns:
            for match in re.finditer(pattern, content, flags=re.IGNORECASE):
                claim = match.group(1)
                nums = re.findall(r"\d+(?:\.\d+)?", claim)
                if any(num not in allowed_numbers for num in nums):
                    unsupported.append(claim)

        social_proof_phrases = [
            "大量用户",
            "很多人反馈",
            "广受好评",
            "社区一致认可",
            "爆火",
            "口碑很好",
            "大家都在用",
        ]
        material_text = str(materials)
        for phrase in social_proof_phrases:
            if phrase in content and phrase not in material_text:
                unsupported.append(phrase)

        dedup = []
        seen = set()
        for item in unsupported:
            key = item.strip()
            if key and key not in seen:
                seen.add(key)
                dedup.append(key)

        return dedup[:8]

    def _parse_output(self, raw_output: str, platform: str) -> Dict[str, Any]:
        """解析 LLM 输出"""
        result = {
            "title": "",
            "content": "",
            "tags": [],
            "summary": "",
            "image_suggestions": "",
        }

        # 尝试按格式解析
        lines = raw_output.split("\n")
        current_section = None
        current_content = []

        for line in lines:
            line_stripped = line.strip()

            # 检测段落标记
            if line_stripped.startswith("标题：") or line_stripped.startswith(
                "【标题】"
            ):
                if current_section and current_content:
                    result[current_section] = "\n".join(current_content).strip()
                current_section = "title"
                current_content = [
                    line_stripped.replace("标题：", "").replace("【标题】", "").strip()
                ]

            elif line_stripped.startswith("正文：") or line_stripped.startswith(
                "【正文】"
            ):
                if current_section and current_content:
                    result[current_section] = "\n".join(current_content).strip()
                current_section = "content"
                current_content = []

            elif line_stripped.startswith("回答：") or line_stripped.startswith(
                "【回答】"
            ):
                if current_section and current_content:
                    result[current_section] = "\n".join(current_content).strip()
                current_section = "content"
                current_content = []

            elif line_stripped.startswith("标签：") or line_stripped.startswith(
                "【标签】"
            ):
                if current_section and current_content:
                    result[current_section] = "\n".join(current_content).strip()
                current_section = "tags_raw"
                current_content = [
                    line_stripped.replace("标签：", "").replace("【标签】", "").strip()
                ]

            elif line_stripped.startswith("摘要：") or line_stripped.startswith(
                "【摘要】"
            ):
                if current_section and current_content:
                    result[current_section] = "\n".join(current_content).strip()
                current_section = "summary"
                current_content = [
                    line_stripped.replace("摘要：", "").replace("【摘要】", "").strip()
                ]

            elif line_stripped.startswith("配图建议：") or line_stripped.startswith(
                "【配图建议】"
            ):
                if current_section and current_content:
                    result[current_section] = "\n".join(current_content).strip()
                current_section = "image_suggestions"
                current_content = [
                    line_stripped.replace("配图建议：", "")
                    .replace("【配图建议】", "")
                    .strip()
                ]

            elif line_stripped == "---":
                # 分隔符，保存当前内容
                if current_section and current_content:
                    result[current_section] = "\n".join(current_content).strip()
                    current_section = None
                    current_content = []

            elif current_section:
                current_content.append(line)

        # 保存最后一段
        if current_section and current_content:
            result[current_section] = "\n".join(current_content).strip()

        # 解析标签
        if "tags_raw" in result:
            tags_raw = result.pop("tags_raw")
            result["tags"] = re.findall(r"#(\S+)", tags_raw)

        # 如果解析失败，使用原始输出
        if not result["title"] and not result["content"]:
            # 尝试简单分割
            parts = raw_output.split("\n\n", 1)
            if len(parts) >= 2:
                result["title"] = parts[0].strip()[:50]
                result["content"] = parts[1].strip()
            else:
                result["content"] = raw_output

        return result

    def _check_condition(self, condition: str, materials: Dict[str, Any]) -> bool:
        """检查条件是否满足"""
        # 简单的条件检查
        if "距离超过" in condition:
            try:
                match = re.search(r"\d+", condition)
                if match:
                    threshold = int(match.group())
                    distance = materials.get("distance", "0")
                    distance_match = re.search(r"\d+", str(distance))
                    if distance_match:
                        distance_num = int(distance_match.group())
                        return distance_num > threshold
            except:
                return True

        if "参与人数超过" in condition:
            try:
                match = re.search(r"\d+", condition)
                if match:
                    threshold = int(match.group())
                    participants = materials.get("participants", "0")
                    participants_match = re.search(r"\d+", str(participants))
                    if participants_match:
                        participants_num = int(participants_match.group())
                        return participants_num > threshold
            except:
                return True

        return True

    def _get_platform_min_score(self, platform: str) -> int:
        rules = config.get_anti_ai_rules()
        thresholds = rules.get("platform_quality_thresholds", {})
        if isinstance(thresholds, dict):
            if platform in thresholds:
                return int(thresholds[platform])
            if "default" in thresholds:
                return int(thresholds["default"])
        return DEFAULT_MIN_SCORE

    def get_stats(self) -> Dict[str, Any]:
        """获取 LLM 使用统计"""
        return self.client.get_stats()


# 便捷函数
def generate(
    platform: str,
    content_type: str,
    materials: Dict[str, Any],
) -> GeneratedContent:
    """快速生成内容"""
    generator = ContentGenerator()
    return generator.generate(platform, content_type, materials)


if __name__ == "__main__":
    # 测试
    print("=== 内容生成器测试 ===\n")

    # 测试素材
    test_materials = {
        "keywords": "莫干山徒步",
        "route_name": "莫干山环线",
        "location": "浙江德清莫干山",
        "distance": "15公里",
        "duration": "6小时",
        "difficulty": "中级",
        "elevation_gain": "800米",
        "participants": "25人",
        "highlight": "竹林小道特别美，偶遇一只松鼠",
        "regret": "没带够水，最后2公里渴死了",
        "transcript": "今天带队去莫干山，走了15公里，累但值。竹林那段真的太美了，拍了好多照片。就是忘带水了，最后差点渴死。",
    }

    try:
        generator = ContentGenerator()

        # 生成小红书内容
        result = generator.generate(
            platform="xiaohongshu", content_type="route_guide", materials=test_materials
        )

        print("\n【生成结果】")
        print(result)

        # 打印统计
        print("\n【API 统计】")
        print(generator.get_stats())

    except Exception as e:
        print(f"测试失败: {e}")
        import traceback

        traceback.print_exc()
