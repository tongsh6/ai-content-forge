"""
小红书发布器
通过 creator.xiaohongshu.com 发布笔记

页面流程：
1. 默认打开"上传视频"tab
2. 点击"上传图文"tab（注意有两个同名tab，需选择可见的那个）
3. 上传至少一张图片（必须，否则编辑器不会出现）
4. 编辑器出现后填写标题和正文
5. 点击发布
"""

import os
import time
import tempfile
from pathlib import Path
from .base import BasePublisher, PublishContent, PublishResult


# 默认占位图尺寸
PLACEHOLDER_WIDTH = 800
PLACEHOLDER_HEIGHT = 600


def _create_placeholder_image() -> str:
    """创建一张简单的白色占位图片，返回文件路径"""
    try:
        from PIL import Image

        img = Image.new(
            "RGB", (PLACEHOLDER_WIDTH, PLACEHOLDER_HEIGHT), color=(255, 255, 255)
        )
        path = os.path.join(tempfile.gettempdir(), "xhs_placeholder.png")
        img.save(path)
        return path
    except ImportError:
        # 没有 PIL，用最小合法 PNG (1x1 白色)
        import struct
        import zlib

        def _minimal_png(path):
            """写一个最小的 1x1 白色 PNG"""
            signature = b"\x89PNG\r\n\x1a\n"

            def chunk(ctype, data):
                c = ctype + data
                crc = struct.pack(">I", zlib.crc32(c) & 0xFFFFFFFF)
                return struct.pack(">I", len(data)) + c + crc

            ihdr = struct.pack(">IIBBBBB", 1, 1, 8, 2, 0, 0, 0)
            raw = zlib.compress(b"\x00\xff\xff\xff")
            with open(path, "wb") as f:
                f.write(signature)
                f.write(chunk(b"IHDR", ihdr))
                f.write(chunk(b"IDAT", raw))
                f.write(chunk(b"IEND", b""))

        path = os.path.join(tempfile.gettempdir(), "xhs_placeholder.png")
        _minimal_png(path)
        return path


class XiaohongshuPublisher(BasePublisher):
    """小红书内容发布器"""

    PLATFORM_NAME = "小红书"
    LOGIN_URL = "https://creator.xiaohongshu.com/login"
    PUBLISH_URL = "https://creator.xiaohongshu.com/publish/publish"

    def _check_logged_in(self) -> bool:
        """检查是否已登录小红书创作服务平台"""
        try:
            url = self.page.url
            # 如果不在登录页，大概率已登录
            if "login" not in url and "creator.xiaohongshu.com" in url:
                return True
            # 检查页面中是否有用户头像等已登录元素
            avatar = self.page.query_selector(".user-avatar, .avatar, .header-user")
            return avatar is not None
        except Exception:
            return False

    def _click_image_text_tab(self):
        """
        点击"上传图文" tab。
        页面上有两个同名 .creator-tab 元素，一个 x<0（隐藏），一个 x>100（可见）。
        需要选择可见的那个。
        """
        tabs = self.page.query_selector_all(".creator-tab")
        for tab in tabs:
            text = (tab.inner_text() or "").strip()
            if "上传图文" in text:
                box = tab.bounding_box()
                if box and box["x"] > 0:
                    tab.click()
                    time.sleep(1)
                    print("  ✓ 已切换到「上传图文」模式")
                    return True
        # fallback: 直接用文字定位
        try:
            tab = self.page.locator(".creator-tab", has_text="上传图文").first
            tab.click()
            time.sleep(1)
            print("  ✓ 已切换到「上传图文」模式 (fallback)")
            return True
        except Exception:
            print("  ⚠ 未找到「上传图文」tab")
            return False

    def _upload_image(self, content: PublishContent) -> bool:
        """
        上传封面图片。小红书必须先上传图片，编辑器才会出现。
        优先使用 content.images 中的文件，否则创建占位图。
        """
        # 确定要上传的图片路径
        image_path = None
        if content.images:
            for img in content.images:
                if os.path.isfile(img):
                    image_path = img
                    break

        if not image_path:
            print("  → 未提供封面图，生成占位图片...")
            image_path = _create_placeholder_image()

        if not os.path.isfile(image_path):
            print(f"  ⚠ 图片文件不存在: {image_path}")
            return False

        try:
            # 小红书的文件上传 input 是 hidden 的，不能用 wait_for_selector（默认等 visible）
            # 直接用 locator + set_input_files，Playwright 允许对 hidden file input 操作
            file_input = self.page.locator('input[type="file"][accept*=".jpg"]')
            file_input.set_input_files(image_path)
            print(f"  ✓ 已上传图片: {os.path.basename(image_path)}")
            # 等待图片处理完成和编辑器出现
            time.sleep(5)
            return True
        except Exception as e:
            print(f"  ⚠ 图片上传失败: {e}")

        return False

    def _do_publish(self, content: PublishContent) -> PublishResult:
        """发布小红书笔记"""
        print("  → 正在打开小红书创作服务平台...")

        # 1. 导航到发布页
        self.page.goto(self.PUBLISH_URL, wait_until="networkidle", timeout=30000)
        time.sleep(2)

        # 检查是否需要登录
        if "login" in self.page.url:
            print("  ⚠ 需要登录小红书")
            self._wait_for_login()
            self.page.goto(self.PUBLISH_URL, wait_until="networkidle", timeout=30000)
            time.sleep(2)

        # 2. 切换到"上传图文"tab
        self._click_image_text_tab()
        time.sleep(1)

        # 3. 上传图片（必须，否则编辑器不出现）
        if not self._upload_image(content):
            return PublishResult(
                platform=self.PLATFORM_NAME,
                success=False,
                message="图片上传失败，无法继续发布",
            )

        print("  → 正在填写内容...")

        # 4. 填写标题
        try:
            title_input = self.page.wait_for_selector(
                'input[placeholder*="填写标题"]',
                timeout=15000,
            )
            if title_input:
                title_input.fill(content.title)
                print(f"  ✓ 标题已填写: {content.title[:30]}...")
                time.sleep(0.5)
        except Exception as e:
            print(f"  ⚠ 标题填写失败: {e}")

        # 5. 填写正文 — TipTap ProseMirror 编辑器
        try:
            body_editor = self.page.wait_for_selector(
                'div.tiptap.ProseMirror[contenteditable="true"]',
                timeout=10000,
            )
            if body_editor:
                body_editor.click()
                time.sleep(0.3)
                # 正文限制 1000 字，截断
                body_text = content.content[:1000]
                self.page.keyboard.type(body_text, delay=5)
                print(f"  ✓ 正文已填写 ({len(body_text)} 字)")
                time.sleep(0.5)
        except Exception as e:
            print(f"  ⚠ 正文填写失败: {e}")

        # 6. 添加话题标签
        if content.tags:
            try:
                topic_btn = self.page.query_selector("#topicBtn")
                if topic_btn:
                    for tag in content.tags[:5]:
                        topic_btn.click()
                        time.sleep(0.5)
                        # 话题搜索弹窗中输入标签
                        topic_input = self.page.wait_for_selector(
                            'input[placeholder*="搜索话题"], input[placeholder*="话题"]',
                            timeout=5000,
                        )
                        if topic_input:
                            topic_input.fill(tag)
                            time.sleep(1)
                            # 选择第一个搜索结果
                            first_result = self.page.query_selector(
                                ".topic-item, .search-item, [class*='topic'] li"
                            )
                            if first_result:
                                first_result.click()
                                time.sleep(0.5)
                            else:
                                # 没有搜索结果，按 Escape 关闭
                                self.page.keyboard.press("Escape")
                                time.sleep(0.3)
                    print(f"  ✓ 话题标签已添加: {len(content.tags[:5])} 个")
            except Exception as e:
                print(f"  ⚠ 话题标签添加失败（可手动添加）: {e}")

        # 7. 确认发布
        confirm = self._wait_for_confirm()

        if confirm is True:
            try:
                # 红色发布按钮
                publish_btn = self.page.query_selector("button.custom-button.bg-red")
                if not publish_btn:
                    # fallback
                    publish_btn = self.page.query_selector('button:has-text("发布")')
                if publish_btn:
                    publish_btn.click()
                    time.sleep(3)
                    print("  ✓ 已点击发布按钮")
                    return PublishResult(
                        platform=self.PLATFORM_NAME,
                        success=True,
                        message="内容已提交发布",
                    )
                else:
                    print("  ⚠ 未找到发布按钮，请手动点击")
                    input("     完成后按 Enter...")
            except Exception as e:
                print(f"  ⚠ 自动点击发布失败: {e}")
                print("     请在浏览器中手动点击发布按钮")
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
