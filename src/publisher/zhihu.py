"""
知乎发布器
通过 zhihu.com 发布文章或回答

排版方案：
  知乎编辑器原生支持 Markdown 语法（底栏显示"Markdown 语法输入中"）。
  逐行输入内容，按 Enter 触发编辑器的 Markdown 解析。

  关键行为（经实测验证）：
  - **加粗** / *斜体*: keyboard.type() 自动渲染 ✓
  - 列表: 首项 `- ` / `1. ` 触发列表模式，后续 Enter 自动创建新列表项
         （后续项不能再带 `- ` 前缀，否则会重复）
  - 代码块: ``` 触发/退出代码块模式 ✓
  - [链接](url): 编辑器不渲染，需转为纯文本
"""

import re
import time
from .base import BasePublisher, PublishContent, PublishResult


class ZhihuPublisher(BasePublisher):
    """知乎内容发布器"""

    PLATFORM_NAME = "知乎"
    LOGIN_URL = "https://www.zhihu.com/signin"
    PUBLISH_URL = "https://zhuanlan.zhihu.com/write"

    def _handle_security_check_if_needed(self):
        assert self.page is not None
        url = self.page.url
        if "unhuman" in url:
            print(
                "  ⚠ 触发知乎安全验证（unhuman）。请在浏览器中完成验证，程序会自动继续..."
            )
            start = time.time()
            while time.time() - start < 180:
                if "unhuman" not in self.page.url:
                    break
                time.sleep(1)

    def _check_logged_in(self) -> bool:
        """检查是否已登录知乎"""
        try:
            assert self.page is not None
            url = self.page.url
            if "signin" in url or "signup" in url:
                return False
            avatar = self.page.query_selector(".AppHeader-userAvatar, .Avatar")
            return avatar is not None
        except Exception:
            return False

    def _is_publish_button_enabled(self) -> bool:
        """检查发布按钮是否可用"""
        assert self.page is not None
        page = self.page
        return page.evaluate(
            """() => {
                for (const b of document.querySelectorAll('button')) {
                    if (b.textContent.trim() === '发布') return !b.disabled;
                }
                return false;
            }"""
        )

    def _click_publish_button(self) -> bool:
        """点击可用的发布按钮"""
        assert self.page is not None
        page = self.page
        return page.evaluate(
            """() => {
                for (const b of document.querySelectorAll('button')) {
                    if (b.textContent.trim() === '发布' && !b.disabled) {
                        b.click();
                        return true;
                    }
                }
                return false;
            }"""
        )

    # ------------------------------------------------------------------
    # Markdown 预处理 + 逐行输入
    # ------------------------------------------------------------------

    @staticmethod
    def _convert_links(text: str) -> str:
        """将 Markdown 链接转为纯文本：[text](url) → text（url）"""
        return re.sub(r"\[(.+?)\]\((.+?)\)", r"\1（\2）", text)

    @staticmethod
    def _normalize_for_zhihu(text: str) -> str:
        text = ZhihuPublisher._convert_links(text)
        text = re.sub(r"\*\*(.+?)\*\*", r"\1", text)
        text = re.sub(r"`([^`]+)`", r"「\1」", text)

        out_lines = []
        in_code = False
        for raw in text.split("\n"):
            stripped = raw.strip()

            if stripped.startswith("```"):
                in_code = not in_code
                if in_code:
                    out_lines.append("代码示例：")
                out_lines.append("")
                continue

            if stripped == "---":
                out_lines.append("")
                continue

            if in_code:
                out_lines.append(f"    {raw}")
                continue

            if re.match(r"^[-*]\s+", stripped):
                item = re.sub(r"^[-*]\s+", "", stripped)
                out_lines.append(f"• {item}")
                continue

            if re.match(r"^\d+\.\s+", stripped):
                item = re.sub(r"^\d+\.\s+", "", stripped)
                out_lines.append(f"- {item}")
                continue

            out_lines.append(raw)

        return "\n".join(out_lines)

    def _type_content(self, text: str):
        text = self._normalize_for_zhihu(text)

        assert self.page is not None
        page = self.page

        for line in text.split("\n"):
            page.keyboard.type(line, delay=5)
            page.keyboard.press("Enter")
            time.sleep(0.02)

    # ------------------------------------------------------------------
    # 发布主流程
    # ------------------------------------------------------------------

    def _do_publish(self, content: PublishContent) -> PublishResult:
        """发布知乎文章"""
        assert self.page is not None
        print("  → 正在打开知乎写文章页面...")

        self.page.goto(self.PUBLISH_URL, wait_until="domcontentloaded", timeout=30000)
        time.sleep(2)
        self._handle_security_check_if_needed()
        if "/write" not in self.page.url:
            self.page.goto(
                self.PUBLISH_URL, wait_until="domcontentloaded", timeout=30000
            )
            time.sleep(2)
            self._handle_security_check_if_needed()

        # 检查是否需要登录
        if "signin" in self.page.url or "sign" in self.page.url:
            print("  ⚠ 需要登录知乎")
            self._wait_for_login()
            self.page.goto(
                self.PUBLISH_URL, wait_until="domcontentloaded", timeout=30000
            )
            time.sleep(2)
            self._handle_security_check_if_needed()

        print("  → 正在填写内容...")

        # ---- 标题 ----
        try:
            title_input = self.page.wait_for_selector(
                'textarea[placeholder*="请输入标题"], textarea[placeholder*="标题"], '
                ".WriteIndex-titleInput textarea, .PublishEditor-title textarea",
                timeout=30000,
            )
            if title_input:
                title = content.title
                if not title:
                    title = content.content[:20].replace("\n", " ") + "..."
                    print("  ⚠ 未提供标题，截取正文前 20 字")
                title_input.fill(title)
                print(f"  ✓ 标题已填写: {title[:40]}{'...' if len(title) > 40 else ''}")
                time.sleep(0.5)
        except Exception as e:
            print(f"  ⚠ 标题填写失败: {e}")

        # ---- 正文（逐行输入 Markdown） ----
        try:
            body_editor = self.page.wait_for_selector(
                '[contenteditable="true"]',
                timeout=30000,
            )
            if body_editor:
                body_editor.click()
                time.sleep(0.3)

                self._type_content(content.content)
                time.sleep(1)

                # 验证
                text_len = self.page.evaluate(
                    """() => {
                        const el = document.querySelector('[contenteditable="true"]');
                        return el ? el.innerText.trim().length : 0;
                    }"""
                )
                print(f"  ✓ 正文已填写（{text_len} 字）")
                time.sleep(0.5)
        except Exception as e:
            print(f"  ⚠ 正文填写失败: {e}")

        # ---- 检查发布按钮 ----
        time.sleep(1)
        if not self._is_publish_button_enabled():
            print("  ✗ 发布按钮 disabled，内容可能未被编辑器识别")
            return PublishResult(
                platform=self.PLATFORM_NAME,
                success=False,
                message="发布按钮未激活（已保存为草稿）",
            )

        print("  ✓ 发布按钮已激活")

        # ---- 确认发布 ----
        confirm = self._wait_for_confirm()

        if confirm is True:
            try:
                if not self._click_publish_button():
                    print("  ⚠ 未找到可用的发布按钮")
                    return PublishResult(
                        platform=self.PLATFORM_NAME,
                        success=False,
                        message="未找到可用的发布按钮",
                    )

                time.sleep(3)

                # 二次确认弹窗
                confirm_btn = self.page.query_selector(
                    'button:has-text("确认并发布"), button:has-text("确认发布")'
                )
                if confirm_btn:
                    confirm_btn.click()
                    time.sleep(3)

                # 验证：发布成功会跳转离开 /write
                time.sleep(2)
                current_url = self.page.url
                if "/write" not in current_url:
                    print(f"  ✓ 发布成功: {current_url}")
                    return PublishResult(
                        platform=self.PLATFORM_NAME,
                        success=True,
                        message="文章已发布",
                        url=current_url,
                    )
                else:
                    print("  ✓ 已点击发布（仍在编辑页，可能需审核）")
                    return PublishResult(
                        platform=self.PLATFORM_NAME,
                        success=True,
                        message="文章已提交发布",
                    )
            except Exception as e:
                print(f"  ⚠ 发布失败: {e}")
                print("     请在浏览器中手动发布")
                input("     完成后按 Enter...")

        elif confirm == "manual":
            return PublishResult(
                platform=self.PLATFORM_NAME,
                success=True,
                message="用户手动发布",
            )

        return PublishResult(
            platform=self.PLATFORM_NAME,
            success=False,
            message="用户跳过发布",
        )
