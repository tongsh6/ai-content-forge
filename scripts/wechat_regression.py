from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.publisher.base import PublishContent
from src.publisher.wechat import WechatPublisher


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


class FakePage:
    def __init__(self):
        self.url = "https://mp.weixin.qq.com/cgi-bin/home"
        self.keyboard = FakeKeyboard()
        self._title = FakeElement()
        self._body = FakeElement()

    def goto(self, url: str, wait_until: str = "networkidle", timeout: int = 30000):
        self.url = url
        return None

    def wait_for_selector(self, selector: str, timeout: int = 10000):
        if "title" in selector or "标题" in selector:
            return self._title
        return self._body

    def query_selector(self, selector: str):
        if "保存" in selector or "submit" in selector:
            return FakeElement()
        return None


def test_logged_in_detection():
    p = WechatPublisher(headless=True, auto_confirm=False)
    p.page = FakePage()
    assert p._check_logged_in() is True


def test_skip_publish_path():
    p = WechatPublisher(headless=True, auto_confirm=False)
    p.page = FakePage()
    p._check_logged_in = lambda: True
    p._wait_for_confirm = lambda: False
    result = p._do_publish(PublishContent(title="标题", content="正文"))
    assert result.success is False
    assert "跳过发布" in result.message


def run():
    test_logged_in_detection()
    test_skip_publish_path()
    print("Wechat regression checks passed.")


if __name__ == "__main__":
    run()
