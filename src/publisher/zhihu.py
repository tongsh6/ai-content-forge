"""
知乎发布器
通过 zhihu.com 发布文章或回答
"""

import time
from .base import BasePublisher, PublishContent, PublishResult


class ZhihuPublisher(BasePublisher):
    """知乎内容发布器"""

    PLATFORM_NAME = "知乎"
    LOGIN_URL = "https://www.zhihu.com/signin"
    PUBLISH_URL = "https://zhuanlan.zhihu.com/write"

    def _check_logged_in(self) -> bool:
        """检查是否已登录知乎"""
        try:
            url = self.page.url
            if "signin" in url or "signup" in url:
                return False
            # 检查是否有用户头像
            avatar = self.page.query_selector(".AppHeader-userAvatar, .Avatar")
            return avatar is not None
        except Exception:
            return False

    def _do_publish(self, content: PublishContent) -> PublishResult:
        """发布知乎文章"""
        print(f"  → 正在打开知乎写文章页面...")

        # 导航到写文章页
        self.page.goto(self.PUBLISH_URL, wait_until="networkidle", timeout=30000)
        time.sleep(2)

        # 检查是否需要登录
        if "signin" in self.page.url or "sign" in self.page.url:
            print(f"  ⚠ 需要登录知乎")
            self._wait_for_login()
            self.page.goto(self.PUBLISH_URL, wait_until="networkidle", timeout=30000)
            time.sleep(2)

        print(f"  → 正在填写内容...")

        # 填写标题
        try:
            title_input = self.page.wait_for_selector(
                'textarea[placeholder*="请输入标题"], textarea[placeholder*="标题"], '
                ".WriteIndex-titleInput textarea, .PublishEditor-title textarea",
                timeout=10000,
            )
            if title_input:
                # 知乎文章标题可以用推广项目名 + 角度
                title = content.title or "印象笔记导出为 Markdown ，我用这个工具我的数据"
                title_input.fill(title)
                print(f"  ✓ 标题已填写: {title[:30]}...")
                time.sleep(0.5)
        except Exception as e:
            print(f"  ⚠ 标题填写失败: {e}")

        # 填写正文
        try:
            body_editor = self.page.wait_for_selector(
                '.public-DraftEditor-content, [contenteditable="true"], '
                ".WriteIndex-editor [contenteditable], .ql-editor",
                timeout=10000,
            )
            if body_editor:
                body_editor.click()
                time.sleep(0.3)
                self.page.keyboard.type(content.content, delay=5)
                print(f"  ✓ 正文已填写 ({len(content.content)} 字)")
                time.sleep(0.5)
        except Exception as e:
            print(f"  ⚠ 正文填写失败: {e}")

        # 确认发布
        confirm = self._wait_for_confirm()

        if confirm is True:
            try:
                publish_btn = self.page.query_selector(
                    'button:has-text("发布"), button:has-text("发布文章"), '
                    ".PublishPanel-triggerButton"
                )
                if publish_btn:
                    publish_btn.click()
                    time.sleep(2)
                    # 可能有二次确认
                    confirm_btn = self.page.query_selector(
                        '.PublishPanel button:has-text("确认并发布"), '
                        'button:has-text("确认发布")'
                    )
                    if confirm_btn:
                        confirm_btn.click()
                        time.sleep(3)
                    print(f"  ✓ 已点击发布按钮")
                    return PublishResult(
                        platform=self.PLATFORM_NAME,
                        success=True,
                        message="文章已提交发布",
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
        )
