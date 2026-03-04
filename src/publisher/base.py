"""
发布器基类 - 定义通用的发布流程和接口
"""

from __future__ import annotations

import json
import time
from abc import ABC, abstractmethod
from pathlib import Path
from dataclasses import dataclass, field
from typing import Optional, List, Dict, Any, TYPE_CHECKING

if TYPE_CHECKING:
    from playwright.sync_api import Browser, BrowserContext, Page, Playwright

# 登录态存储目录
AUTH_DIR = Path(__file__).parent.parent.parent / "data" / "auth"


@dataclass
class PublishContent:
    """待发布内容"""

    title: str = ""
    content: str = ""
    tags: List[str] = field(default_factory=list)
    summary: str = ""  # 公众号摘要
    images: List[str] = field(default_factory=list)  # 图片路径


@dataclass
class PublishResult:
    """发布结果"""

    platform: str
    success: bool
    url: str = ""  # 发布后的链接
    message: str = ""
    error: str = ""


class BasePublisher(ABC):
    """
    发布器基类

    所有平台发布器继承此类，实现具体的发布逻辑。
    使用 Playwright 浏览器自动化。
    """

    PLATFORM_NAME: str = ""
    LOGIN_URL: str = ""
    PUBLISH_URL: str = ""

    def __init__(self, headless: bool = False, auto_confirm: bool = False):
        """
        Args:
            headless: 是否无头模式（不显示浏览器窗口）
            auto_confirm: 是否自动确认发布（False=半自动，需手动点发布）
        """
        self.headless = headless
        self.auto_confirm = auto_confirm
        self.browser: Browser | None = None
        self.context: BrowserContext | None = None
        self.page: Page | None = None

    @property
    def auth_file(self) -> Path:
        """登录态文件路径"""
        AUTH_DIR.mkdir(parents=True, exist_ok=True)
        return AUTH_DIR / f"{self.__class__.__name__.lower()}_auth.json"

    def _init_browser(self, playwright: Playwright):
        """初始化浏览器"""
        self.browser = playwright.chromium.launch(
            headless=self.headless,
            args=["--disable-blink-features=AutomationControlled"],
        )

        # 尝试加载登录态
        if self.auth_file.exists():
            try:
                self.context = self.browser.new_context(
                    storage_state=str(self.auth_file),
                    viewport={"width": 1280, "height": 800},
                    user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
                )
                print(f"  ✓ 已加载 {self.PLATFORM_NAME} 登录态")
            except Exception:
                self.context = self._new_context()
        else:
            self.context = self._new_context()

        self.page = self.context.new_page()

    def _new_context(self):
        """创建新的浏览器上下文"""
        assert self.browser is not None
        return self.browser.new_context(
            viewport={"width": 1280, "height": 800},
            user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
        )

    def _save_auth(self):
        """保存登录态"""
        if self.context:
            try:
                self.context.storage_state(path=str(self.auth_file))
                print(f"  ✓ 已保存 {self.PLATFORM_NAME} 登录态")
            except Exception as e:
                print(f"  ⚠ 保存登录态失败: {e}")

    def _wait_for_login(self, timeout: int = 120):
        """等待用户手动登录"""
        print(f"\n  ⏳ 请在浏览器中登录 {self.PLATFORM_NAME}...")
        print(f"     登录完成后按 Enter 继续（超时 {timeout} 秒）")

        # 等待用户输入或超时
        import select
        import sys

        start = time.time()
        while time.time() - start < timeout:
            # 检查页面是否已登录
            if self._check_logged_in():
                print(f"  ✓ 检测到已登录 {self.PLATFORM_NAME}")
                self._save_auth()
                return True
            time.sleep(2)

        print(f"  ⚠ 登录超时")
        return False

    @abstractmethod
    def _check_logged_in(self) -> bool:
        """检查是否已登录"""
        pass

    @abstractmethod
    def _do_publish(self, content: PublishContent) -> PublishResult:
        """执行发布操作"""
        pass

    def publish(self, content: PublishContent) -> PublishResult:
        """
        发布内容（主入口）

        流程：
        1. 启动浏览器
        2. 检查登录态，未登录则等待手动登录
        3. 导航到发布页
        4. 填写内容
        5. 半自动模式下等待确认 / 全自动模式下直接发布
        6. 返回结果
        """
        from playwright.sync_api import sync_playwright

        with sync_playwright() as p:
            try:
                self._init_browser(p)
                result = self._do_publish(content)
                return result
            except Exception as e:
                return PublishResult(
                    platform=self.PLATFORM_NAME,
                    success=False,
                    error=str(e),
                    message=f"发布失败: {e}",
                )
            finally:
                if self.context:
                    self._save_auth()
                if self.browser:
                    self.browser.close()

    def _wait_for_confirm(self):
        """等待用户确认发布"""
        if self.auto_confirm:
            return True

        print(f"\n  📝 {self.PLATFORM_NAME} 内容已填写完毕")
        print(f"     请在浏览器中检查内容，然后：")
        print(f"     - 输入 'y' 或按 Enter：自动点击发布")
        print(f"     - 输入 'n'：跳过发布（保持页面打开）")
        print(f"     - 输入 'm'：手动发布（在浏览器中自行操作）")

        choice = (
            input(f"\n  是否发布到 {self.PLATFORM_NAME}? [Y/n/m]: ").strip().lower()
        )

        if choice in ("", "y", "yes"):
            return True
        elif choice == "m":
            print(f"  ⏳ 请在浏览器中手动发布，完成后按 Enter...")
            input()
            return "manual"
        else:
            return False


def parse_generated_content(raw_text: str) -> PublishContent:
    """从生成器的原始输出中解析出结构化内容"""
    content = PublishContent()
    lines = raw_text.split("\n")

    current_section = None
    current_lines = []

    for line in lines:
        stripped = line.strip()

        if stripped == "---":
            if current_section and current_lines:
                text = "\n".join(current_lines).strip()
                if current_section == "title":
                    content.title = text
                elif current_section == "content":
                    content.content = text
                elif current_section == "tags":
                    import re

                    content.tags = re.findall(r"#(\S+)", text)
                elif current_section == "summary":
                    content.summary = text
            current_section = None
            current_lines = []
            continue

        if stripped.startswith("标题："):
            if current_section and current_lines:
                text = "\n".join(current_lines).strip()
                if current_section == "content":
                    content.content = text
            current_section = "title"
            current_lines = [stripped.replace("标题：", "").strip()]
        elif stripped.startswith("正文：") or stripped.startswith("回答："):
            if current_section and current_lines:
                text = "\n".join(current_lines).strip()
                if current_section == "title":
                    content.title = text
            current_section = "content"
            current_lines = []
        elif stripped.startswith("标签："):
            if current_section and current_lines:
                text = "\n".join(current_lines).strip()
                if current_section == "content":
                    content.content = text
            current_section = "tags"
            current_lines = [stripped.replace("标签：", "").strip()]
        elif stripped.startswith("摘要："):
            if current_section and current_lines:
                text = "\n".join(current_lines).strip()
                if current_section == "content":
                    content.content = text
            current_section = "summary"
            current_lines = [stripped.replace("摘要：", "").strip()]
        elif current_section:
            current_lines.append(line)

    # 保存最后一段
    if current_section and current_lines:
        text = "\n".join(current_lines).strip()
        if current_section == "title":
            content.title = text
        elif current_section == "content":
            content.content = text
        elif current_section == "tags":
            import re

            content.tags = re.findall(r"#(\S+)", text)
        elif current_section == "summary":
            content.summary = text

    return content
