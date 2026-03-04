"""
知乎发布器
通过 zhihu.com 发布文章或回答

排版方案：
  Markdown → HTML → 模拟 paste 事件插入富文本编辑器
  兜底：paste 失败时降级为 keyboard.type() 纯文本输入
"""

import re
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
            avatar = self.page.query_selector(".AppHeader-userAvatar, .Avatar")
            return avatar is not None
        except Exception:
            return False

    # ------------------------------------------------------------------
    # Markdown → HTML 转换
    # ------------------------------------------------------------------
    def _markdown_to_html(self, md_text: str) -> str:
        """将 Markdown 转换为知乎编辑器兼容的 HTML"""
        try:
            import markdown

            return markdown.markdown(
                md_text,
                extensions=["extra", "nl2br", "sane_lists"],
            )
        except ImportError:
            return self._markdown_to_html_builtin(md_text)

    def _markdown_to_html_builtin(self, md_text: str) -> str:
        """内置简易 Markdown → HTML（不依赖第三方库）"""

        def _inline(text: str) -> str:
            """处理行内格式：加粗、斜体、行内代码、链接"""
            text = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", text)
            text = re.sub(r"\*(.+?)\*", r"<em>\1</em>", text)
            text = re.sub(r"`(.+?)`", r"<code>\1</code>", text)
            text = re.sub(r"\[(.+?)\]\((.+?)\)", r'<a href="\2">\1</a>', text)
            return text

        lines = md_text.split("\n")
        html_parts: list[str] = []
        in_list = False
        list_tag = ""  # "ul" | "ol"
        in_code = False
        code_buf: list[str] = []

        for line in lines:
            stripped = line.strip()

            # ---- 代码块 ----
            if stripped.startswith("```"):
                if in_code:
                    html_parts.append(
                        f"<pre><code>{chr(10).join(code_buf)}</code></pre>"
                    )
                    code_buf.clear()
                    in_code = False
                else:
                    in_code = True
                continue
            if in_code:
                code_buf.append(line)
                continue

            # ---- 空行：关闭列表 ----
            if not stripped:
                if in_list:
                    html_parts.append(f"</{list_tag}>")
                    in_list = False
                continue

            # ---- 标题 ----
            m = re.match(r"^(#{1,3})\s+(.+)$", stripped)
            if m:
                level = len(m.group(1))
                html_parts.append(f"<h{level}>{_inline(m.group(2))}</h{level}>")
                continue

            # ---- 无序列表 ----
            if re.match(r"^[-*]\s+", stripped):
                item = re.sub(r"^[-*]\s+", "", stripped)
                if not in_list or list_tag != "ul":
                    if in_list:
                        html_parts.append(f"</{list_tag}>")
                    html_parts.append("<ul>")
                    in_list, list_tag = True, "ul"
                html_parts.append(f"<li>{_inline(item)}</li>")
                continue

            # ---- 有序列表 ----
            if re.match(r"^\d+\.\s+", stripped):
                item = re.sub(r"^\d+\.\s+", "", stripped)
                if not in_list or list_tag != "ol":
                    if in_list:
                        html_parts.append(f"</{list_tag}>")
                    html_parts.append("<ol>")
                    in_list, list_tag = True, "ol"
                html_parts.append(f"<li>{_inline(item)}</li>")
                continue

            # ---- 普通段落 ----
            if in_list:
                html_parts.append(f"</{list_tag}>")
                in_list = False
            html_parts.append(f"<p>{_inline(stripped)}</p>")

        if in_list:
            html_parts.append(f"</{list_tag}>")

        return "\n".join(html_parts)

    # ------------------------------------------------------------------
    # 粘贴 HTML 到富文本编辑器
    # ------------------------------------------------------------------
    def _paste_html(self, html: str, plain_text: str) -> bool:
        """
        通过模拟 paste 事件将 HTML 插入知乎富文本编辑器。

        原理：构造一个携带 clipboardData 的 paste Event，
        Draft.js / Quill 的 paste handler 会读取 text/html 并渲染为富文本。
        """
        return self.page.evaluate(
            """({html, plainText}) => {
                const editor = document.querySelector(
                    '.public-DraftEditor-content [contenteditable="true"], ' +
                    '.ql-editor[contenteditable="true"], ' +
                    '[contenteditable="true"]'
                );
                if (!editor) return false;
                editor.focus();

                // 构造 paste 事件（mock clipboardData）
                const event = new Event('paste', { bubbles: true, cancelable: true });
                event.clipboardData = {
                    getData(type) {
                        if (type === 'text/html') return html;
                        if (type === 'text/plain') return plainText;
                        return '';
                    },
                    types: ['text/html', 'text/plain'],
                    items: [],
                    files: [],
                };

                // dispatchEvent 返回 false 表示 preventDefault 被调用 → 编辑器已处理
                const wasHandled = !editor.dispatchEvent(event);

                if (!wasHandled) {
                    // 编辑器没拦截 paste，用 execCommand 兜底
                    document.execCommand('insertHTML', false, html);
                }
                return true;
            }""",
            {"html": html, "plainText": plain_text},
        )

    def _get_editor_text_length(self) -> int:
        """获取编辑器当前文本长度"""
        return self.page.evaluate(
            """() => {
                const el = document.querySelector('[contenteditable="true"]');
                return el ? el.innerText.trim().length : 0;
            }"""
        )

    # ------------------------------------------------------------------
    # 发布主流程
    # ------------------------------------------------------------------
    def _do_publish(self, content: PublishContent) -> PublishResult:
        """发布知乎文章"""
        print("  → 正在打开知乎写文章页面...")

        self.page.goto(self.PUBLISH_URL, wait_until="networkidle", timeout=30000)
        time.sleep(2)

        # 检查是否需要登录
        if "signin" in self.page.url or "sign" in self.page.url:
            print("  ⚠ 需要登录知乎")
            self._wait_for_login()
            self.page.goto(self.PUBLISH_URL, wait_until="networkidle", timeout=30000)
            time.sleep(2)

        print("  → 正在填写内容...")

        # ---- 标题 ----
        try:
            title_input = self.page.wait_for_selector(
                'textarea[placeholder*="请输入标题"], textarea[placeholder*="标题"], '
                ".WriteIndex-titleInput textarea, .PublishEditor-title textarea",
                timeout=10000,
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

        # ---- 正文（Markdown → HTML → paste） ----
        try:
            body_editor = self.page.wait_for_selector(
                '.public-DraftEditor-content, [contenteditable="true"], '
                ".WriteIndex-editor [contenteditable], .ql-editor",
                timeout=10000,
            )
            if body_editor:
                body_editor.click()
                time.sleep(0.3)

                # 转换并粘贴
                html_content = self._markdown_to_html(content.content)
                self._paste_html(html_content, content.content)
                time.sleep(1)

                # 验证：检查编辑器是否有内容
                text_len = self._get_editor_text_length()
                if text_len > 10:
                    print(f"  ✓ 正文已填写（富文本格式，{len(content.content)} 字）")
                else:
                    # 降级为纯文本逐字输入
                    print("  ⚠ 富文本粘贴未生效，降级为纯文本输入")
                    body_editor.click()
                    time.sleep(0.3)
                    self.page.keyboard.type(content.content, delay=5)
                    print(f"  ✓ 正文已填写（纯文本降级，{len(content.content)} 字）")
                time.sleep(0.5)
        except Exception as e:
            print(f"  ⚠ 正文填写失败: {e}")

        # ---- 确认发布 ----
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
                    confirm_btn = self.page.query_selector(
                        '.PublishPanel button:has-text("确认并发布"), '
                        'button:has-text("确认发布")'
                    )
                    if confirm_btn:
                        confirm_btn.click()
                        time.sleep(3)
                    print("  ✓ 已点击发布按钮")
                    return PublishResult(
                        platform=self.PLATFORM_NAME,
                        success=True,
                        message="文章已提交发布",
                    )
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
