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
- For user-facing README prose, write for molecular simulation users who may not be programmers. Prefer ClearML terms that users see in the UI, such as Task, Pipeline, Agent, queue, artifact, and metrics, and pair them with plain molecular-simulation wording.
- In Japanese README prose, prefer `分子シミュレーションソフト` over `シミュレーター`, and `ClearMLタスク投入用スクリプト` over a bare `投入用スクリプト`.
- Keep development terms such as callback, source diff, wrapper, and artifact preview when they are needed for developer notes or skills, but avoid making them the main vocabulary in quick-start or user-level sections.
- When explaining ClearML architecture, distinguish official ClearML responsibilities from this tutorial's GAMESS-specific workflow. ClearML Server provides the UI/backend and manages Task/workflow records plus artifact metadata/locations, queues hold Tasks, and Agents pull Tasks from queues and execute the recorded code. A "submission PC" is the user's machine running SDK/scripts, not a separate ClearML server component.
- Prioritize technical accuracy and reader task clarity over mechanical wording rules. If a term rule makes a sentence awkward or misleading, rewrite the sentence instead of forcing the term.
