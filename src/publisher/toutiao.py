"""
今日头条发布器
通过 mp.toutiao.com 发布微头条或文章
"""

import time
from .base import BasePublisher, PublishContent, PublishResult


class ToutiaoPublisher(BasePublisher):
    """今日头条内容发布器"""

    PLATFORM_NAME = "今日头条"
    LOGIN_URL = "https://mp.toutiao.com/auth/page/login"
    PUBLISH_URL = "https://mp.toutiao.com/profile_v4/weitoutiao/publish"

    def _check_logged_in(self) -> bool:
        """检查是否已登录头条号"""
        try:
            url = self.page.url
            if "login" in url or "auth" in url:
                return False
            # 检查是否有用户相关元素
            user_el = self.page.query_selector(".user-info, .avatar, .header-user-name")
            return user_el is not None or "profile" in url
        except Exception:
            return False

    def _do_publish(self, content: PublishContent) -> PublishResult:
        """发布头条微头条"""
        print(f"  → 正在打开头条号后台...")

        # 导航到微头条发布页
        self.page.goto(self.PUBLISH_URL, wait_until="networkidle", timeout=30000)
        time.sleep(2)

        # 检查是否需要登录
        if "login" in self.page.url or "auth" in self.page.url:
            print(f"  ⚠ 需要登录头条号")
            self._wait_for_login()
            self.page.goto(self.PUBLISH_URL, wait_until="networkidle", timeout=30000)
            time.sleep(2)

        print(f"  → 正在填写内容...")

        # 微头条不需要标题，直接填写正文
        # 组合标题和正文
        full_content = content.content
        if content.title:
            full_content = f"{content.title}\n\n{content.content}"

        try:
            body_editor = self.page.wait_for_selector(
                '[contenteditable="true"], .ql-editor, '
                "textarea, .ProseMirror, .editor-content [contenteditable]",
                timeout=10000,
            )
            if body_editor:
                body_editor.click()
                time.sleep(0.3)
                self.page.keyboard.type(full_content, delay=5)
                print(f"  ✓ 内容已填写 ({len(full_content)} 字)")
                time.sleep(0.5)
        except Exception as e:
            print(f"  ⚠ 内容填写失败: {e}")

        # 确认发布
        confirm = self._wait_for_confirm()

        if confirm is True:
            try:
                publish_btn = self.page.query_selector(
                    'button:has-text("发布"), button:has-text("发表"), '
                    '.publish-btn, [class*="submit"] button'
                )
                if publish_btn:
                    publish_btn.click()
                    time.sleep(3)
                    print(f"  ✓ 已点击发布按钮")
                    return PublishResult(
                        platform=self.PLATFORM_NAME,
                        success=True,
                        message="微头条已提交发布",
                    )
            except Exception as e:
                print(f"  ⚠ 自动点击发布失败: {e}")
                print(f"     请在浏览器中手动点击发布按钮")
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
            error_code="USER_CANCELLED",
            next_action="这是主动取消操作；如需发布，请重新执行并确认。",
        )
