"""
配置加载模块 - 加载 YAML 配置文件
"""

import yaml
from pathlib import Path
from typing import Any, Dict, Optional

# 配置目录（相对于项目根目录）
CONFIG_DIR = Path(__file__).parent.parent / "config"


def load_yaml(file_path: Path) -> Dict[str, Any]:
    """加载 YAML 文件"""
    if not file_path.exists():
        return {}
    with open(file_path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def load_config(name: str) -> Dict[str, Any]:
    """
    加载指定名称的配置文件

    Args:
        name: 配置文件名（不含扩展名）
              如 "personas", "platforms"
    """
    file_path = CONFIG_DIR / f"{name}.yaml"
    if not file_path.exists():
        raise FileNotFoundError(f"配置文件不存在: {file_path}")
    return load_yaml(file_path)


def load_prompt(platform: str) -> Dict[str, Any]:
    """
    加载平台 Prompt 模板

    Args:
        platform: 平台标识 (xiaohongshu/wechat/zhihu/toutiao)
    """
    file_path = CONFIG_DIR / "prompts" / f"{platform}.yaml"
    if not file_path.exists():
        raise FileNotFoundError(f"Prompt 模板不存在: {file_path}")
    return load_yaml(file_path)


def load_scenario(category: str, scenario_name: Optional[str] = None) -> Dict[str, Any]:
    """
    加载场景模板

    Args:
        category: 场景类别 (outdoor/lifestyle/tech)
        scenario_name: 具体场景名称（可选）
    """
    file_path = CONFIG_DIR / "prompts" / "scenarios" / f"{category}.yaml"
    if not file_path.exists():
        raise FileNotFoundError(f"场景模板不存在: {file_path}")

    data = load_yaml(file_path)

    if scenario_name and "scenarios" in data:
        return data["scenarios"].get(scenario_name, {})
    return data


def load_anti_ai_rules() -> Dict[str, Any]:
    """加载去 AI 味规则"""
    file_path = CONFIG_DIR / "prompts" / "anti_ai_rules.yaml"
    return load_yaml(file_path)


class ConfigManager:
    """配置管理器 - 缓存和统一访问配置"""

    _instance = None
    _cache: Dict[str, Any] = {}

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._cache = {}
        return cls._instance

    def get_personas(self) -> Dict[str, Any]:
        """获取人设配置"""
        if "personas" not in self._cache:
            self._cache["personas"] = load_config("personas")
        return self._cache["personas"]

    def get_platforms(self) -> Dict[str, Any]:
        """获取平台配置"""
        if "platforms" not in self._cache:
            self._cache["platforms"] = load_config("platforms")
        return self._cache["platforms"]

    def get_platform_config(self, platform: str) -> Dict[str, Any]:
        """获取单个平台的配置"""
        platforms = self.get_platforms()
        return platforms.get("platforms", {}).get(platform, {})

    def get_prompt_template(self, platform: str) -> Dict[str, Any]:
        """获取平台 Prompt 模板"""
        cache_key = f"prompt_{platform}"
        if cache_key not in self._cache:
            self._cache[cache_key] = load_prompt(platform)
        return self._cache[cache_key]

    def get_anti_ai_rules(self) -> Dict[str, Any]:
        """获取去 AI 味规则"""
        if "anti_ai_rules" not in self._cache:
            self._cache["anti_ai_rules"] = load_anti_ai_rules()
        return self._cache["anti_ai_rules"]

    def get_main_persona(self) -> Dict[str, Any]:
        """获取主人设"""
        personas = self.get_personas()
        return personas.get("main_persona", {})

    def get_persona_for_platform(self, platform: str) -> Dict[str, Any]:
        """获取针对特定平台调整后的人设"""
        main_persona = self.get_main_persona()
        personas = self.get_personas()
        adjustments = personas.get("platform_adjustments", {}).get(platform, {})

        return {"main": main_persona, "adjustments": adjustments}

    def get_scenario(self, category: str, scenario_name: str) -> Dict[str, Any]:
        """获取场景配置"""
        cache_key = f"scenario_{category}_{scenario_name}"
        if cache_key not in self._cache:
            self._cache[cache_key] = load_scenario(category, scenario_name)
        return self._cache[cache_key]

    def clear_cache(self):
        """清除缓存"""
        self._cache.clear()


# 全局配置管理器实例
config = ConfigManager()


if __name__ == "__main__":
    # 测试
    print("=== 测试配置加载 ===\n")

    # 测试加载人设
    print("主人设:")
    persona = config.get_main_persona()
    print(f"  名称: {persona.get('name')}")
    print(f"  身份: {persona.get('identity', '')[:50]}...")

    # 测试加载平台配置
    print("\n平台配置:")
    for platform in ["xiaohongshu", "wechat", "zhihu", "toutiao"]:
        pc = config.get_platform_config(platform)
        print(f"  {platform}: {pc.get('name')}")

    # 测试加载去 AI 味规则
    print("\n去 AI 味规则:")
    rules = config.get_anti_ai_rules()
    avoid = rules.get("avoid", {}).get("connectors", [])[:3]
    print(f"  避免词汇示例: {avoid}")

    print("\n✓ 配置加载测试完成")
