# Compress Context Skill

Chạy khi conversation quá dài (50+ messages) hoặc bắt đầu session mới.

## Steps

1. **Summarize:** Đã làm gì, decisions được đưa ra, tasks đang làm, blockers
2. **Archive:** Save vào `.claude/memory/archive/YYYY-MM-DD-HH-summary.md`
3. **Rewrite MEMORY.md:** Fresh, concise (dưới 200 lines)
4. **Update decisions.md:** Append any new decisions
5. **Confirm:** "Context compressed. Archive saved to [path]."
