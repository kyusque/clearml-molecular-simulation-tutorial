# Agent Instructions

Follow the repository `.editorconfig` settings when reading or writing files.

- Treat Markdown and source files as UTF-8.
- Do not transcode Japanese text through the system console encoding.
- When checking Japanese Markdown from PowerShell, prefer an explicit UTF-8 reader such as Python:

```powershell
uv run python -c "from pathlib import Path; print(Path('draft.md').read_text(encoding='utf-8'))"
```

- Avoid adding YAML front matter solely to declare encoding. Encoding policy belongs in `.editorconfig` and this file.
- When editing documentation, update both Japanese and English counterparts together by default unless the user explicitly asks for one language only.
- Do not insert half-width spaces between Japanese and English text (for example, write `ClearMLで` not `ClearML で`).
- When possible, run Python entry points and scripts via `uv run` instead of invoking `python` directly.
