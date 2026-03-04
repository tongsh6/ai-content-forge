from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.publisher.base import PublishContent
from src.publisher.zhihu import ZhihuPublisher


class FakeElement:
    def __init__(self):
        self.value = ""

    def fill(self, text: str):
        self.value = text

    def click(self):
        return None


class FakeKeyboard:
    def __init__(self, page: "FakePage"):
        self.page = page

    def type(self, text: str, delay: int = 0):
        self.page.body_lines.append(text)

    def press(self, key: str):
        if key == "Enter":
            self.page.body_lines.append("\n")


class FakePage:
    def __init__(self, url: str):
        self.url = url
        self.title_element = FakeElement()
        self.body_element = FakeElement()
        self.body_lines = []
        self.keyboard = FakeKeyboard(self)

    def goto(
        self, url: str, wait_until: str = "domcontentloaded", timeout: int = 30000
    ):
        self.url = url
        return None

    def wait_for_selector(self, selector: str, timeout: int = 30000):
        if "textarea" in selector:
            return self.title_element
        return self.body_element

    def query_selector(self, selector: str):
        return None

    def evaluate(self, script: str):
        if "return !b.disabled" in script:
            return True
        if "b.click();" in script:
            return True
        if "innerText.trim().length" in script:
            return max(0, len("".join(self.body_lines).strip()))
        return None


def test_formatting_paths():
    src = """**加粗** + `inline` + [链接](https://example.com)

---

1. 第一项
2. 第二项
- 无序一
* 无序二

```python
print('hello')
```

列表后普通段落
"""

    normalized = ZhihuPublisher._normalize_for_zhihu(src)
    assert "**" not in normalized
    assert "```" not in normalized
    assert "---" not in normalized
    assert "[链接](https://example.com)" not in normalized
    assert "链接（https://example.com）" in normalized
    assert "「inline」" in normalized
    assert "1）第一项" in normalized
    assert "2）第二项" in normalized
    assert "• 无序一" in normalized
    assert "• 无序二" in normalized
    assert "代码示例：" in normalized
    assert "    print('hello')" in normalized


def test_skip_publish_returns_draft_locator():
    publisher = ZhihuPublisher(headless=True, auto_confirm=False)
    fake_page = FakePage("https://zhuanlan.zhihu.com/write")
    publisher.page = fake_page
    publisher._ensure_write_page = lambda max_attempts=4: True
    publisher._wait_for_confirm = lambda: False
    publisher._is_publish_button_enabled = lambda: True

    result = publisher._do_publish(
        PublishContent(title="测试标题", content="**内容**\n---\n1. 条目")
    )

    assert result.success is False
    assert "草稿" in result.message
    assert "/write" in result.url


def test_unhuman_recovery_state_machine():
    publisher = ZhihuPublisher(headless=True, auto_confirm=True)
    fake_page = FakePage("https://www.zhihu.com/account/unhuman")
    publisher.page = fake_page
    publisher._handle_security_check_if_needed = lambda: setattr(
        publisher.page, "url", "https://zhuanlan.zhihu.com/write"
    )

    ok = publisher._ensure_write_page(max_attempts=2)
    assert ok is True
    assert "/write" in publisher.page.url


def run():
    test_formatting_paths()
    test_skip_publish_returns_draft_locator()
    test_unhuman_recovery_state_machine()
    print("Zhihu E2E regression checks passed.")


if __name__ == "__main__":
    run()
