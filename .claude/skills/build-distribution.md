# Build & Distribution Skill

## Hiện trạng

App hiện chạy từ source (`python main.py`). Có sẵn:
- `DainnScreenTranslator.spec` — PyInstaller spec file
- `installer.iss` — Inno Setup installer script
- `run.bat` / `run.sh` — Script chạy từ source

## Option 1: PyInstaller (hiện tại)

```bash
pip install pyinstaller
pyinstaller DainnScreenTranslator.spec
```

Output tại `dist/`. **Kích thước:** ~100-300MB (PyQt5 + numpy + cv2 rất nặng).

## Option 2: Nuitka (nhẹ hơn PyInstaller ~30-40%)

```bash
pip install nuitka
python -m nuitka --standalone --onefile \
  --enable-plugin=pyqt5 \
  --windows-icon-from-ico=resources/logo.ico \
  --output-filename=DainnTranslator.exe \
  main.py
```

**Kích thước:** ~70-150MB. Vẫn nặng do PyQt5.

## Option 3: Launcher nhỏ + package riêng (đề xuất cho mục tiêu < 1MB)

Kiến trúc tách biệt:
1. **Launcher.exe** (~500KB): File exe nhỏ viết bằng Go hoặc C, chỉ làm nhiệm vụ:
   - Kiểm tra Python có sẵn không
   - Download + cài dependencies nếu chưa có
   - Chạy `python main.py`
2. **Source package** (zip ~50KB): Source code Python không include deps

```go
// launcher.go (Go)
package main
import (
    "os/exec"
    "os"
)
func main() {
    cmd := exec.Command("python", "main.py")
    cmd.Stdout = os.Stdout
    cmd.Stderr = os.Stderr
    cmd.Run()
}
```

**Kích thước launcher:** ~1-2MB với Go, ~300KB với C.

## Option 4: Script cài đặt + shortcut

Thay vì exe, cung cấp:
1. `install.bat` — cài Python + pip install requirements
2. `DainnTranslator.bat` — shortcut chạy app
3. Hướng dẫn rõ ràng trong README

**Đây là cách thực tế nhất** nếu target user (gamer) không ngại cài Python.

## Khuyến nghị

Với constraint < 1MB exe thuần Python là **không thể** do PyQt5. Lựa chọn tốt nhất:
- **Short term:** Cải thiện `run.bat` + README rõ hơn
- **Long term:** Launcher Go/C nhỏ (~1MB) + zip source

## Build Installer (Inno Setup)

Sau khi có `dist/` từ PyInstaller:
1. Mở `installer.iss` bằng Inno Setup Compiler
2. Build → ra file `.exe` installer (~150-300MB)
3. Người dùng chạy installer, không cần Python

## Update Settings.json cho Python

```json
{
  "permissions": {
    "allow": [
      "Bash(python:*)",
      "Bash(pip:*)",
      "Bash(pyinstaller:*)"
    ]
  }
}
```
