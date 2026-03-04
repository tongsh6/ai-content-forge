from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.publisher.zhihu import ZhihuPublisher


def run():
    source = """**加粗** + `inline` + [链接](https://example.com)

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

    normalized = ZhihuPublisher._normalize_for_zhihu(source)

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
    assert "列表后普通段落" in normalized

    print("Zhihu formatting regression checks passed.")


if __name__ == "__main__":
    run()
