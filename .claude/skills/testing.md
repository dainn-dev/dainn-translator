# Testing Skill

## Framework

Project chưa có test setup. Khi thêm tests, dùng **pytest**.

## Setup pytest

```bash
pip install pytest pytest-mock
```

Tạo thư mục `tests/` ở root. Đặt file `tests/conftest.py` cho shared fixtures.

## Run Tests

```bash
pytest -v
pytest tests/ -v
pytest tests/test_text_processing.py -v  # test file cụ thể
```

## Test Patterns cho Project này

### Test TextProcessor (core logic)
```python
# tests/test_text_processing.py
from unittest.mock import MagicMock, patch
from src.text_processing import TextProcessor

def test_translate_returns_text_on_error():
    processor = TextProcessor()
    result = processor.translate_text("", "vi")
    assert result == ""

def test_csv_dictionary_exact_match():
    processor = TextProcessor()
    processor.set_dictionary([("Hello", "Xin chào")])
    result = processor.lookup_dictionary("hello")  # normalized lowercase
    assert result is not None
    assert result[0] == "Xin chào"
```

### Test ConfigManager
```python
# tests/test_config_manager.py
import tempfile, os
from src.config_manager import ConfigManager

def test_default_translation_mode():
    with tempfile.TemporaryDirectory() as tmpdir:
        config_path = os.path.join(tmpdir, "config.ini")
        manager = ConfigManager(config_file=config_path)
        assert manager.get_translation_mode() == 'google'
```

### Test Translators (mock HTTP)
```python
# tests/test_libretranslate.py
from unittest.mock import patch, MagicMock
from src.translator.libretranslate_translator import LibreTranslateTranslator

def test_translate_success():
    translator = LibreTranslateTranslator("http://localhost:5000")
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {"translatedText": "Xin chào"}

    with patch("requests.post", return_value=mock_response):
        result = translator.translate("Hello", "en", "vi")
    assert result == "Xin chào"
```

## Test Requirements

- **Bug fix:** Viết regression test trước khi fix
- **New translator:** Test happy path + connection failure + empty text
- **New config key:** Test default value + read/write cycle
- **UI thay đổi:** Không cần unit test — dùng `.claude/skills/ui-review.md` thay thế

## Sau khi test

Report: "pytest: X/X passing."
Nếu có failure: fix trước khi tiếp tục.
