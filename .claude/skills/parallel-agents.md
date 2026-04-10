# Parallel Agents Skill

Dùng khi task có nhiều phần lớn, độc lập với nhau.

## Luôn Hỏi Trước

KHÔNG dispatch agents mà không có confirmation. Present:
- Agent nào làm gì
- File nào mỗi agent owns
- Tradeoffs của parallel vs sequential

Chờ explicit approval.

## Dispatching

Mỗi agent prompt phải include:
1. Mô tả task chính xác
2. File paths agent owns
3. File paths agent KHÔNG được touch
4. Cách run tests
5. Definition of done

## Sau khi Hoàn Thành

1. Review tất cả changes cùng nhau
2. Chạy `python main.py` để verify app khởi động được
3. Resolve conflicts
4. Commit cùng nhau
