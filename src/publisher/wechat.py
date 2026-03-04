"""
公众号发布器
通过 mp.weixin.qq.com 发布图文消息
"""

import time
from .base import BasePublisher, PublishContent, PublishResult


class WechatPublisher(BasePublisher):
    """微信公众号内容发布器"""

    PLATFORM_NAME = "公众号"
    LOGIN_URL = "https://mp.weixin.qq.com/"
    PUBLISH_URL = "https://mp.weixin.qq.com/"

    def _check_logged_in(self) -> bool:
        """检查是否已登录公众号后台"""
        try:
            url = self.page.url
            # 登录后会跳转到管理后台
            if "cgi-bin" in url or "home" in url:
                return True
            return False
        except Exception:
            return False

    def _do_publish(self, content: PublishContent) -> PublishResult:
        """发布公众号图文"""
        print(f"  → 正在打开公众号后台...")

        # 导航到公众号后台
        self.page.goto(self.LOGIN_URL, wait_until="networkidle", timeout=30000)
        time.sleep(2)

        # 检查是否需要登录（公众号需要扫码登录）
        if not self._check_logged_in():
            print(f"  ⚠ 需要登录公众号后台（请扫码）")
            self._wait_for_login()

        # 导航到创建图文页面
        print(f"  → 正在导航到创建图文页面...")
        try:
            # 点击左侧菜单 "创作管理" -> "图文消息"
            # 或直接访问创建页面
            create_url = "https://mp.weixin.qq.com/cgi-bin/appmsg?t=media/appmsg_edit&action=edit&type=77"
            self.page.goto(create_url, wait_until="networkidle", timeout=30000)
            time.sleep(2)

            # 如果上面URL不对，尝试通过菜单
            if "appmsg_edit" not in self.page.url:
                # 点击 "创作管理"
                create_menu = self.page.query_selector(
                    'a:has-text("创作管理"), a:has-text("图文消息"), a[href*="appmsg"]'
                )
                if create_menu:
                    create_menu.click()
                    time.sleep(2)

                # 点击 "写新图文" 按钮
                new_btn = self.page.query_selector(
                    'a:has-text("写新图文"), button:has-text("新建"), '
                    'a:has-text("创建图文")'
                )
                if new_btn:
                    new_btn.click()
                    time.sleep(2)
        except Exception as e:
            print(f"  ⚠ 导航到创建页失败: {e}")

        print(f"  → 正在填写内容...")

        # 填写标题
        try:
            title_input = self.page.wait_for_selector(
                '#title, input[placeholder*="请在这里输入标题"], '
                'input[name="title"], .title_input input',
                timeout=10000,
            )
            if title_input:
                title_input.fill(content.title)
                print(f"  ✓ 标题已填写: {content.title[:30]}...")
                time.sleep(0.5)
        except Exception as e:
            print(f"  ⚠ 标题填写失败: {e}")

        # 填写正文
        try:
            # 公众号编辑器是一个 iframe 内的富文本编辑器
            body_editor = self.page.wait_for_selector(
                '#edui_body, [contenteditable="true"], .edui-body-container, '
                "#ueditor_0, .ProseMirror",
                timeout=10000,
            )
            if body_editor:
                body_editor.click()
                time.sleep(0.3)
                # 输入内容
                self.page.keyboard.type(content.content, delay=5)
                print(f"  ✓ 正文已填写 ({len(content.content)} 字)")
                time.sleep(0.5)
        except Exception as e:
            print(f"  ⚠ 正文填写失败: {e}")
            print(f"     公众号编辑器比较复杂，建议手动粘贴内容")

        # 填写摘要
        if content.summary:
            try:
                summary_input = self.page.query_selector(
                    'textarea[name="digest"], #digest, textarea[placeholder*="摘要"]'
                )
                if summary_input:
                    summary_input.fill(content.summary)
                    print(f"  ✓ 摘要已填写")
            except Exception:
                pass

        # 确认发布
        confirm = self._wait_for_confirm()

        if confirm is True:
            try:
                # 公众号通常有 "群发" 或 "保存并群发" 按钮
                # 先保存为草稿更安全
                save_btn = self.page.query_selector(
                    'button:has-text("保存"), a:has-text("保存为草稿"), '
                    "#js_submit, .weui-desktop-btn_primary"
                )
                if save_btn:
                    save_btn.click()
                    time.sleep(3)
                    print(f"  ✓ 已保存为草稿（建议手动检查后再群发）")
                    return PublishResult(
                        platform=self.PLATFORM_NAME,
                        success=True,
                        message="已保存为草稿，请手动检查后群发",
                    )
            except Exception as e:
                print(f"  ⚠ 自动保存失败: {e}")
                print(f"     请在浏览器中手动操作")
                input("     完成后按 Enter...")

        elif confirm == "manual":
            return PublishResult(
                platform=self.PLATFORM_NAME,
                success=True,
                message="用户手动操作",
            )

        return PublishResult(
            platform=self.PLATFORM_NAME,
            success=False,
            message="用户跳过发布",
        )
