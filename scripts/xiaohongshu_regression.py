from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.publisher.base import PublishContent
from src.publisher.xiaohongshu import XiaohongshuPublisher, _create_placeholder_image


class FakeElement:
    def __init__(self):
        self.value = ""

    def fill(self, text: str):
        self.value = text

    def click(self):
        return None


class FakeKeyboard:
    def __init__(self):
        self.typed = ""

    def type(self, text: str, delay: int = 0):
        self.typed += text

    def press(self, key: str):
        return None


class FakePage:
    def __init__(self):
        self.url = "https://creator.xiaohongshu.com/publish/publish"
        self.keyboard = FakeKeyboard()
        self._title = FakeElement()
        self._body = FakeElement()

    def goto(self, url: str, wait_until: str = "networkidle", timeout: int = 30000):
        self.url = url
        return None

    def wait_for_selector(self, selector: str, timeout: int = 10000):
        if "填写标题" in selector:
            return self._title
        return self._body

    def query_selector(self, selector: str):
        if "发布" in selector:
            return FakeElement()
        return None

    def query_selector_all(self, selector: str):
        return []

    def locator(self, selector: str, has_text: str = ""):
        return FakeElement()


def test_placeholder_image_generation():
    path = _create_placeholder_image()
    assert Path(path).exists()


def test_skip_publish_path():
    p = XiaohongshuPublisher(headless=True, auto_confirm=False)
    p.page = FakePage()
    p._check_logged_in = lambda: True
    p._click_image_text_tab = lambda: True
    p._upload_image = lambda content: True
    p._wait_for_confirm = lambda: False

    result = p._do_publish(PublishContent(title="标题", content="正文", tags=["测试"]))
    assert result.success is False
    assert "跳过发布" in result.message


def run():
    test_placeholder_image_generation()
    test_skip_publish_path()
    print("Xiaohongshu regression checks passed.")


if __name__ == "__main__":
    run()
