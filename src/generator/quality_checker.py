"""
内容质量检测器 - 检测 AI 味并打分
"""

import re
from pathlib import Path
from typing import Dict, Any, List, Tuple
from collections import Counter
from dataclasses import dataclass, field
import sys

sys.path.insert(0, str(Path(__file__).parent.parent))

from config_loader import config


@dataclass
class QualityReport:
    """质量检测报告"""

    score: int  # 0-100 分，越高越好
    ai_words_found: List[str] = field(default_factory=list)
    good_expressions_found: List[str] = field(default_factory=list)
    suggestions: List[str] = field(default_factory=list)
    details: Dict[str, Any] = field(default_factory=dict)
    dimension_scores: Dict[str, int] = field(default_factory=dict)

    @property
    def grade(self) -> str:
        """评级"""
        if self.score >= 90:
            return "A"
        elif self.score >= 80:
            return "B"
        elif self.score >= 70:
            return "C"
        elif self.score >= 60:
            return "D"
        else:
            return "F"

    @property
    def grade_emoji(self) -> str:
        """评级 emoji"""
        grades = {"A": "🌟", "B": "✅", "C": "⚠️", "D": "⛔", "F": "💀"}
        return grades.get(self.grade, "❓")

    def __str__(self) -> str:
        lines = [
            f"质量评分: {self.score}/100 {self.grade_emoji} ({self.grade}级)",
        ]

        if self.ai_words_found:
            lines.append(f"")
            lines.append(f"发现 AI 味词汇 ({len(self.ai_words_found)} 个):")
            for word in self.ai_words_found[:10]:  # 最多显示10个
                lines.append(f"  ⚠ {word}")
            if len(self.ai_words_found) > 10:
                lines.append(f"  ... 还有 {len(self.ai_words_found) - 10} 个")

        if self.good_expressions_found:
            lines.append(f"")
            lines.append(f"发现优质表达 ({len(self.good_expressions_found)} 个):")
            for expr in self.good_expressions_found[:5]:
                lines.append(f"  ✓ {expr}")

        if self.suggestions:
            lines.append(f"")
            lines.append(f"改进建议:")
            for sug in self.suggestions:
                lines.append(f"  → {sug}")

        if self.dimension_scores:
            lines.append(f"")
            lines.append(f"维度明细:")
            for dim, score in self.dimension_scores.items():
                sign = "+" if score > 0 else ""
                lines.append(f"  {dim}: {sign}{score}")

        return "\n".join(lines)


class QualityChecker:
    """内容质量检测器"""

    def __init__(self):
        self.anti_ai_rules = config.get_anti_ai_rules()
        self._build_patterns()

    def _build_patterns(self):
        """构建检测模式"""
        avoid = self.anti_ai_rules.get("avoid", {})

        # AI 味词汇列表
        self.ai_words = []
        for category, words in avoid.items():
            if isinstance(words, list):
                self.ai_words.extend(words)

        # 按分类存储避免词（用于开头结尾检测）
        self.ai_words_by_category = {}
        for category, words in avoid.items():
            if isinstance(words, list):
                self.ai_words_by_category[category] = words

        # 好的表达列表
        should_use = self.anti_ai_rules.get("should_use", {})
        self.good_expressions = []

        # 口语化动词
        colloquial = should_use.get("colloquial", {})
        self.good_expressions.extend(colloquial.get("verbs", []))

        # 语气词列表
        self.colloquial_fillers = colloquial.get("fillers", [])

        # 情绪词
        emotions = should_use.get("emotions", {})
        for emotion_type, words in emotions.items():
            if isinstance(words, list):
                self.good_expressions.extend(words)

        # 不确定表达
        self.uncertainty_words = should_use.get("uncertainty", [])
        self.good_expressions.extend(self.uncertainty_words)

        # 转折词
        self.good_expressions.extend(should_use.get("transitions", []))

        # 个人经历标记
        self.personal_markers = should_use.get("personal_markers", [])

    def check(self, content: str, title: str = "", platform: str = "") -> QualityReport:
        """
        检测内容质量 - 16 个维度评分

        Args:
            content: 正文内容
            title: 标题（可选）

        Returns:
            QualityReport 对象
        """
        full_text = f"{title}\n{content}" if title else content

        # 检测 AI 味词汇
        ai_words_found = []
        for word in self.ai_words:
            if word in full_text:
                ai_words_found.append(word)

        # 检测好的表达
        good_found = []
        for expr in self.good_expressions:
            if expr in full_text:
                good_found.append(expr)

        # 计算分数
        score = 100
        details = {}
        suggestions = []
        dimension_scores = {}

        # === 扣分维度 ===

        # 1. AI 味词汇扣分 (每个扣 5 分，最多扣 40 分)
        ai_penalty = min(len(ai_words_found) * 5, 40)
        score -= ai_penalty
        details["ai_word_penalty"] = ai_penalty
        dimension_scores["ai_words"] = -ai_penalty

        if ai_words_found:
            suggestions.append(f"替换 AI 味词汇: {', '.join(ai_words_found[:3])}")

        # 2. 句式重复检测（句头重复）
        repetition_penalty = self._check_sentence_repetition(content)
        score -= repetition_penalty
        details["repetition_penalty"] = repetition_penalty
        dimension_scores["sentence_repetition"] = -repetition_penalty

        if repetition_penalty > 0:
            suggestions.append("句子开头太重复，尝试变换句式")

        # 3. 排比过度检测
        parallel_penalty = self._check_parallel_structure(content)
        score -= parallel_penalty
        details["parallel_penalty"] = parallel_penalty
        dimension_scores["parallel_structure"] = -parallel_penalty

        if parallel_penalty > 0:
            suggestions.append("排比/并列结构过多，减少模板化句式")

        # 4. 句式模板重复检测（因果/对比/递进连续出现）
        structure_penalty = self._check_structure_repetition(content)
        score -= structure_penalty
        details["structure_repetition_penalty"] = structure_penalty
        dimension_scores["structure_repetition"] = -structure_penalty

        if structure_penalty > 0:
            suggestions.append("句式结构过于单一，避免连续使用因果/对比/递进句式")

        # 5. 段落均匀扣分（使用变异系数）
        paragraphs = [p for p in content.split("\n") if p.strip()]
        uniformity_penalty = self._check_paragraph_uniformity(paragraphs)
        score -= uniformity_penalty
        details["structure_penalty"] = uniformity_penalty
        dimension_scores["paragraph_uniformity"] = -uniformity_penalty

        if uniformity_penalty > 0:
            suggestions.append("段落长度太均匀，建议长短不一")

        rhythm_penalty = self._check_rhythm_variation(content)
        score -= rhythm_penalty
        details["rhythm_variation_penalty"] = rhythm_penalty
        dimension_scores["rhythm_variation"] = -rhythm_penalty

        if rhythm_penalty > 0:
            suggestions.append("节奏过于平直，增加长短句和段落起伏")

        opening_ending_penalty = self._check_opening_ending(content)
        score -= opening_ending_penalty
        details["opening_ending_penalty"] = opening_ending_penalty
        dimension_scores["opening_ending"] = -opening_ending_penalty

        if opening_ending_penalty > 0:
            suggestions.append("开头或结尾太模板化，直接切入主题")

        summary_penalty = self._check_summary_structure(content)
        score -= summary_penalty
        details["summary_structure_penalty"] = summary_penalty
        dimension_scores["summary_structure"] = -summary_penalty

        if summary_penalty > 0:
            suggestions.append("结尾有总结/升华套路，改为开放式收束或个人感受")

        diversity_penalty = self._check_lexical_diversity(content)
        score -= diversity_penalty
        details["diversity_penalty"] = diversity_penalty
        dimension_scores["lexical_diversity"] = -diversity_penalty

        if diversity_penalty > 0:
            suggestions.append("用词重复度高，尝试更丰富的表达")

        # === 加分维度 ===

        good_count = len(good_found)
        if good_count <= 6:
            good_bonus = min(good_count * 2, 8)
        else:
            # 超过 6 个开始扣回，鼓励自然分布而非堆砌
            good_bonus = max(8 - (good_count - 6) * 2, 0)
        score += good_bonus
        details["good_expression_bonus"] = good_bonus
        dimension_scores["good_expressions"] = good_bonus

        if good_count > 6:
            suggestions.append("口语词/情绪词堆砌过多，减少刻意使用")

        detail_bonus = self._check_specific_details(content)
        score += detail_bonus
        details["detail_bonus"] = detail_bonus
        dimension_scores["specific_details"] = detail_bonus

        if detail_bonus == 0:
            suggestions.append("加入具体数字（距离、价格、时间等）")

        evidence_score = self._check_evidence_density(content)
        score += evidence_score
        details["evidence_density_score"] = evidence_score
        dimension_scores["evidence_density"] = evidence_score

        if evidence_score < 0:
            suggestions.append("可核验细节不足，补充时间/地点/数字/品牌/步骤")

        short_bonus = self._check_short_sentences(content)
        score += short_bonus
        details["short_sentence_bonus"] = short_bonus
        dimension_scores["short_sentences"] = short_bonus

        if short_bonus == 0:
            suggestions.append("适当使用短句增加节奏感")

        uncertainty_bonus = self._check_uncertainty(content)
        score += uncertainty_bonus
        details["uncertainty_bonus"] = uncertainty_bonus
        dimension_scores["uncertainty"] = uncertainty_bonus

        personal_bonus = self._check_personal_voice(content)
        score += personal_bonus
        details["personal_bonus"] = personal_bonus
        dimension_scores["personal_voice"] = personal_bonus

        if personal_bonus == 0:
            suggestions.append("加入第一人称视角和个人经历")

        emotion_bonus = self._check_emotion_layers(content)
        score += emotion_bonus
        details["emotion_bonus"] = emotion_bonus
        dimension_scores["emotion_layers"] = emotion_bonus

        platform_score = self._apply_platform_adjustments(
            platform=platform,
            good_count=good_count,
            detail_bonus=detail_bonus,
            evidence_score=evidence_score,
            short_bonus=short_bonus,
            rhythm_penalty=rhythm_penalty,
        )
        score += platform_score
        details["platform_adjustment"] = platform_score
        dimension_scores["platform_adjustment"] = platform_score

        bonus_cap = self._get_bonus_cap(platform)
        total_bonus = (
            max(good_bonus, 0)
            + max(detail_bonus, 0)
            + max(evidence_score, 0)
            + max(short_bonus, 0)
            + max(uncertainty_bonus, 0)
            + max(personal_bonus, 0)
            + max(emotion_bonus, 0)
            + max(platform_score, 0)
        )
        bonus_overflow = max(0, total_bonus - bonus_cap)
        if bonus_overflow > 0:
            score -= bonus_overflow
            details["bonus_overflow_penalty"] = bonus_overflow
            details["bonus_cap"] = bonus_cap
            dimension_scores["bonus_overflow"] = -bonus_overflow

        if score > 90:
            score = 90 + (score - 90) * 0.25
            details["high_score_compression"] = True

        # 确保分数在 0-100 范围内
        score = int(max(0, min(100, score)))

        return QualityReport(
            score=score,
            ai_words_found=ai_words_found,
            good_expressions_found=good_found,
            suggestions=suggestions,
            details=details,
            dimension_scores=dimension_scores,
        )

    def _apply_platform_adjustments(
        self,
        platform: str,
        good_count: int,
        detail_bonus: int,
        evidence_score: int,
        short_bonus: int,
        rhythm_penalty: int,
    ) -> int:
        if not platform:
            return 0

        platform_rules = self.anti_ai_rules.get("platform_adjustments", {}).get(
            platform, {}
        )
        if not isinstance(platform_rules, dict):
            return 0

        score = 0

        if platform_rules.get("support_with_evidence") or platform_rules.get(
            "evidence_required"
        ):
            if evidence_score <= 0:
                score -= 3
            else:
                score += 1

        if platform_rules.get("can_use_data") and evidence_score < 1:
            score -= 2

        if platform_rules.get("require_scene_detail"):
            if detail_bonus == 0 or evidence_score < 1:
                score -= 3
            else:
                score += 1

        if platform_rules.get("very_colloquial") and short_bonus == 0:
            score -= 2

        if platform_rules.get("avoid_emotion_slang") and good_count > 4:
            score -= 2

        if (
            platform_rules.get("can_use_network_slang")
            or platform_rules.get("allow_mild_slang")
        ) and 1 <= good_count <= 4:
            score += 1

        if platform_rules.get("storytelling") and rhythm_penalty > 0:
            score -= 1

        return max(-6, min(4, score))

    def _get_bonus_cap(self, platform: str) -> int:
        if not platform:
            return 22

        platform_rules = self.anti_ai_rules.get("platform_adjustments", {}).get(
            platform, {}
        )
        if not isinstance(platform_rules, dict):
            return 22

        if platform_rules.get("support_with_evidence") or platform_rules.get(
            "evidence_required"
        ):
            return 20

        if platform_rules.get("very_colloquial"):
            return 24

        return 22

    def _check_sentence_repetition(self, content: str) -> int:
        """检测句式重复 - 统计句头前2字的重复率"""
        sentences = re.split(r"[。！？\n]", content)
        sentences = [s.strip() for s in sentences if len(s.strip()) >= 4]

        if len(sentences) < 5:
            return 0

        # 提取每句开头前2个字符
        heads = [s[:2] for s in sentences]
        counter = Counter(heads)
        most_common_count = counter.most_common(1)[0][1] if counter else 0
        repetition_rate = most_common_count / len(heads)

        if repetition_rate > 0.4:
            return 15
        elif repetition_rate > 0.3:
            return 10
        elif repetition_rate > 0.2:
            return 5
        return 0

    def _check_structure_repetition(self, content: str) -> int:
        """检测句式模板重复 - 因果/对比/递进句式连续出现"""
        sentences = re.split(r"[。！？\n]", content)
        sentences = [s.strip() for s in sentences if len(s.strip()) >= 6]

        if len(sentences) < 4:
            return 0

        # 因果句式
        causal_patterns = [r"因为.{2,}所以", r"由于.{2,}因此", r"既然.{2,}那"]
        # 对比句式
        contrast_patterns = [r"虽然.{2,}但是", r"尽管.{2,}却", r"虽说.{2,}可"]
        # 递进句式
        progressive_patterns = [r"不但.{2,}而且", r"不光.{2,}还", r"不只.{2,}更"]

        all_patterns = causal_patterns + contrast_patterns + progressive_patterns

        # 统计每句命中的句式类别
        pattern_hits = []
        for s in sentences:
            hit = None
            for i, p in enumerate(all_patterns):
                if re.search(p, s):
                    hit = i // 3  # 0=因果, 1=对比, 2=递进
                    break
            pattern_hits.append(hit)

        # 检测连续相同类型
        consecutive = 1
        max_consecutive = 1
        for i in range(1, len(pattern_hits)):
            if pattern_hits[i] is not None and pattern_hits[i] == pattern_hits[i - 1]:
                consecutive += 1
                max_consecutive = max(max_consecutive, consecutive)
            else:
                consecutive = 1

        if max_consecutive >= 3:
            return 8
        elif max_consecutive >= 2:
            return 4
        return 0

    def _check_parallel_structure(self, content: str) -> int:
        """检测排比过度 - 检测并列关联词+连续列表结构"""
        penalty = 0

        # 检测并列关联词模式
        parallel_patterns = self.ai_words_by_category.get("parallel_patterns", [])
        for pattern in parallel_patterns:
            # 把 "不仅...还..." 转为正则
            regex = pattern.replace("...", r".{1,20}")
            if re.search(regex, content):
                penalty += 3

        # 检测连续列表结构（如连续 3 行以上以数字或 - 开头）
        lines = content.split("\n")
        consecutive_list = 0
        max_consecutive = 0
        for line in lines:
            stripped = line.strip()
            if re.match(r"^(\d+[.、）)]|[-•·])\s*", stripped):
                consecutive_list += 1
                max_consecutive = max(max_consecutive, consecutive_list)
            else:
                consecutive_list = 0

        if max_consecutive >= 5:
            penalty += 4
        elif max_consecutive >= 3:
            penalty += 2

        return min(penalty, 10)

    def _check_paragraph_uniformity(self, paragraphs: List[str]) -> int:
        """检测段落均匀度 - 使用变异系数（标准化方差）"""
        if len(paragraphs) < 3:
            return 0

        lengths = [len(p) for p in paragraphs]
        avg_len = sum(lengths) / len(lengths)
        if avg_len == 0:
            return 0

        # 变异系数 = 标准差 / 均值
        variance = sum((l - avg_len) ** 2 for l in lengths) / len(lengths)
        cv = (variance**0.5) / avg_len

        # CV < 0.3 说明段落过于均匀
        if cv < 0.2:
            return 8
        elif cv < 0.3:
            return 5
        return 0

    def _check_rhythm_variation(self, content: str) -> int:
        penalty = 0

        sentences = [
            s.strip() for s in re.split(r"[。！？\n]", content) if len(s.strip()) >= 2
        ]
        if len(sentences) >= 5:
            lengths = [len(s) for s in sentences]
            mean_len = sum(lengths) / len(lengths)
            if mean_len > 0:
                variance = sum((l - mean_len) ** 2 for l in lengths) / len(lengths)
                std = variance**0.5
                if std < 4:
                    penalty += 5
                elif std < 6:
                    penalty += 3

        paragraphs = [p.strip() for p in content.split("\n") if p.strip()]
        if len(paragraphs) >= 3:
            p_lengths = [len(p) for p in paragraphs]
            p_mean = sum(p_lengths) / len(p_lengths)
            if p_mean > 0:
                p_variance = sum((l - p_mean) ** 2 for l in p_lengths) / len(p_lengths)
                p_cv = (p_variance**0.5) / p_mean
                if p_cv < 0.22:
                    penalty += 3

        return min(penalty, 8)

    def _check_opening_ending(self, content: str) -> int:
        """检测开头结尾模板化"""
        penalty = 0
        paragraphs = [p.strip() for p in content.split("\n") if p.strip()]

        if not paragraphs:
            return 0

        first_para = paragraphs[0]
        last_para = paragraphs[-1]

        # 检查首段是否含 openings 词
        openings = self.ai_words_by_category.get("openings", [])
        for word in openings:
            if word in first_para:
                penalty += 5
                break

        # 检查末段是否含 endings 词
        endings = self.ai_words_by_category.get("endings", [])
        for word in endings:
            if word in last_para:
                penalty += 5
                break

        return min(penalty, 10)

    def _check_summary_structure(self, content: str) -> int:
        """检测总-分-总结构 - 末段是否有总结语气或升华套路"""
        paragraphs = [p.strip() for p in content.split("\n") if p.strip()]
        if len(paragraphs) < 3:
            return 0

        penalty = 0
        last_para = paragraphs[-1]

        # 总结语气词（与 endings 互补，侧重结构性总结）
        summary_words = [
            "总的来说",
            "整体来看",
            "归纳一下",
            "回顾一下",
            "写在最后",
            "一句话总结",
            "最后说一句",
        ]
        for word in summary_words:
            if word in last_para:
                penalty += 5
                break

        # 检测末段是否是"升华式"结尾（过于正式的感慨/号召）
        formal_ending_patterns = [
            r"让我们.{2,}吧",
            r"愿.{2,}都能",
            r"希望每个人",
            r"人生就是",
            r"生活本该如此",
        ]
        for pattern in formal_ending_patterns:
            if re.search(pattern, last_para):
                penalty += 3
                break

        return min(penalty, 8)

    def _check_lexical_diversity(self, content: str) -> int:
        """检测词汇多样性 - 字符 bigram TTR + 高频词惩罚"""
        penalty = 0

        # 提取中文字符
        chinese_chars = re.findall(r"[\u4e00-\u9fff]", content)
        if len(chinese_chars) < 20:
            return 0

        # 构建 bigram TTR
        bigrams = [
            chinese_chars[i] + chinese_chars[i + 1]
            for i in range(len(chinese_chars) - 1)
        ]
        if not bigrams:
            return 0

        ttr = len(set(bigrams)) / len(bigrams)

        # 根据文本长度动态调整阈值（长文 TTR 自然偏低）
        length_factor = min(len(chinese_chars) / 500, 1.0)
        adjusted_threshold_low = 0.35 + length_factor * 0.05
        adjusted_threshold_mid = 0.45 + length_factor * 0.05

        if ttr < adjusted_threshold_low:
            penalty += 10
        elif ttr < adjusted_threshold_mid:
            penalty += 5

        # 高频词惩罚：某个 bigram 占比超 5%
        bigram_counter = Counter(bigrams)
        total_bigrams = len(bigrams)
        if total_bigrams > 0:
            top_freq = bigram_counter.most_common(1)[0][1] / total_bigrams
            if top_freq > 0.05:
                penalty += 3

        return min(penalty, 15)

    def _check_specific_details(self, content: str) -> int:
        """检测具体细节（数字、时间、括号吐槽）"""
        bonus = 0

        has_numbers = bool(re.search(r"\d+", content))
        has_time = bool(re.search(r"\d+[点时分秒]|\d+:\d+|早上|下午|晚上", content))
        has_brackets = "（" in content or "(" in content

        if has_numbers:
            bonus += 3
        if has_time:
            bonus += 2
        if has_brackets:
            bonus += 3

        return min(bonus, 8)

    def _check_evidence_density(self, content: str) -> int:
        hits = 0

        if re.search(r"\d+", content):
            hits += 1
        if re.search(
            r"\d+[点时分秒]|\d+:\d+|早上|下午|晚上|周[一二三四五六日天]", content
        ):
            hits += 1
        if re.search(r"在.{1,12}(山|市|区|路|店|站|景区|公园|营地)", content):
            hits += 1
        if re.search(r"第[一二三四五六七八九十1-9]步|先|再|然后|最后", content):
            hits += 1
        if re.search(r"[A-Za-z]{2,}|元|块|公里|km", content):
            hits += 1

        if hits >= 4:
            return 4
        if hits >= 2:
            return 1
        return -5

    def _check_short_sentences(self, content: str) -> int:
        """检测短句节奏 - 支持句首/句尾/独立短段"""
        # 中间短句（夹在标点之间）
        mid_short = len(re.findall(r"[。！？][^。！？]{1,10}[。！？]", content))

        # 开头短句（文本以短句开始）
        opening_match = re.match(r"^[^。！？\n]{1,10}[。！？]", content.strip())

        # 独立短段落（整段 ≤ 15 字）
        paragraphs = [p.strip() for p in content.split("\n") if p.strip()]
        short_paras = sum(1 for p in paragraphs if 2 <= len(p) <= 15)

        total = mid_short + (1 if opening_match else 0) + short_paras
        if total >= 3:
            return 5
        elif total >= 1:
            return 3
        return 0

    def _check_uncertainty(self, content: str) -> int:
        """检测不确定表达"""
        for word in self.uncertainty_words:
            if word in content:
                return 3
        return 0

    def _check_personal_voice(self, content: str) -> int:
        """检测个人视角 - 第一人称精确匹配 + 个人标记词"""
        bonus = 0

        # 精确匹配独立的 "我"（排除 "我们"）
        personal_i = len(re.findall(r"我(?!们)", content))
        if personal_i >= 3:
            bonus += 2
        elif personal_i >= 1:
            bonus += 1

        # 个人标记词
        for marker in self.personal_markers:
            if marker in content:
                bonus += 2
                break

        return min(bonus, 4)

    def _check_emotion_layers(self, content: str) -> int:
        """检测情感层次 - 含2种以上情感极性"""
        emotions = self.anti_ai_rules.get("should_use", {}).get("emotions", {})

        polarities_found = 0
        for polarity, words in emotions.items():
            if isinstance(words, list):
                for word in words:
                    if word in content:
                        polarities_found += 1
                        break

        if polarities_found >= 2:
            return 3
        return 0

    def check_and_print(
        self, content: str, title: str = "", platform: str = ""
    ) -> QualityReport:
        """检测并打印报告"""
        report = self.check(content, title, platform)
        print("\n【内容质量检测】")
        print(report)
        return report


# 便捷函数
def check_quality(content: str, title: str = "", platform: str = "") -> QualityReport:
    """检测内容质量"""
    checker = QualityChecker()
    return checker.check(content, title, platform)


if __name__ == "__main__":
    # 测试
    print("=== 内容质量检测器测试 ===\n")

    # 测试文本 1: AI 味重
    ai_text = """
    首先，让我来介绍一下莫干山徒步路线。
    其次，这条路线非常适合新手。
    最后，希望对大家有所帮助。
    综上所述，这是一条值得一提的路线。
    """

    print("测试 1: AI 味重的文本")
    print("-" * 30)
    checker = QualityChecker()
    report = checker.check(ai_text)
    print(report)

    print("\n" + "=" * 50 + "\n")

    # 测试文本 2: 自然风格
    natural_text = """
    上周带队去莫干山，走了15公里，腿差点废了（但是值）。

    说实话这条线真的绝了。竹林那段美哭，我拍了200多张照片。

    emmm 唯一的遗憾是忘带够水，最后3公里渴得我怀疑人生。
    下次一定多带两瓶，别学我。
    """

    print("测试 2: 自然风格的文本")
    print("-" * 30)
    report = checker.check(natural_text)
    print(report)
