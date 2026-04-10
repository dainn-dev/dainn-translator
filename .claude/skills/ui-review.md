# UI Review Skill

Chạy sau khi implement bất kỳ UI changes nào.

## Step 1: Start App

```bash
python main.py
```

Chờ main window xuất hiện. Nếu không có Google credentials, app vẫn mở được (hiển thị warning).

**Lưu ý:** App cần môi trường Windows với display. Không chạy được trên headless server.

## Step 2: Mở Browser với Playwright (nếu có web component)

Project này là desktop app — không có web UI. Dùng Playwright MCP tool chỉ nếu có component web được thêm vào sau.

## Step 3: Dừng lại và Chờ

Báo user:
- "Tôi đã chạy `python main.py`"
- "Main window đang hiển thị tại [mô tả vị trí/layout]"
- "Bạn review UI và cho tôi biết cần điều chỉnh gì"

**DỪNG TẠI ĐÂY. Chờ user response.**

## Step 4: Iterate

Nếu user yêu cầu thay đổi: apply → restart app → hỏi review lại.
Nếu user approve: tiếp tục tạo PR.

## Các UI Elements Cần Check

Sau khi thay đổi `main_window.py`:
- [ ] Layout không bị vỡ khi resize
- [ ] Hotkey display đúng với config
- [ ] Area list hiển thị đúng

Sau khi thay đổi `translation_window.py`:
- [ ] Overlay trong suốt, text đọc được
- [ ] Window stays-on-top khi chuyển sang game
- [ ] Font/màu áp dụng đúng từ config
- [ ] Không block mouse click (passthrough)
