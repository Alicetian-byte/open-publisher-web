"""编辑器 AI 改写：蓝本 RewriteService 的 Python 移植。

蓝本核心约束：改写只产生"候选"，绝不直接改文章——编辑器确认后才由用户保存。
输出 JSON {replacements: [...], summary}，replacements 与待替换目标一一对应。
"""

from __future__ import annotations

import threading

from sqlalchemy.orm import Session, sessionmaker

from app.agents.llm_client import LLMClient
from app.services.run_journal import RunJournal

_SYSTEM = (
    "你是稿流编辑助手。你只能提出修改建议，绝不能声称或尝试保存、发布、修改文章。\n"
    "保持原文事实、Markdown 结构、链接、图片与代码块，除非用户明确要求修改它们。\n"
    "只输出 JSON 对象：{\"replacements\": [与待替换目标一一对应的完整替换文本], "
    "\"summary\": 一句话说明改了什么}。"
)


class RewriteService:
    def __init__(self, db: Session, llm: LLMClient | None = None,
                 session_factory: sessionmaker | None = None):
        self.db = db
        self.journal = RunJournal(db)
        self.llm = llm or LLMClient()
        bind = db.get_bind()
        self._session_factory = session_factory or sessionmaker(
            bind=bind, autoflush=False, autocommit=False,
        )

    def start_rewrite(self, *, article_id: str, markdown: str, instruction: str,
                      selected_texts: list[str],
                      conversation: list[dict] | None = None,
                      owner_user_id: str | None = None) -> dict:
        if not instruction.strip():
            raise ValueError("修改要求不能为空")
        targets = [t for t in selected_texts if t.strip()] or [markdown]
        run = self.journal.create_run(
            article_id=article_id, agent_id="writer", operation="rewrite_candidate",
            session_id=f"rewrite:{article_id}"[:36], owner_user_id=owner_user_id,
        )
        thread = threading.Thread(
            target=self._execute_in_own_session,
            args=(run["id"],),
            kwargs=dict(markdown=markdown, instruction=instruction, targets=targets,
                        conversation=conversation or []),
            daemon=True,
        )
        thread.start()
        return run

    def _execute_in_own_session(self, run_id: str, **kwargs) -> None:
        with self._session_factory() as session:
            worker = RewriteService(session, llm=self.llm,
                                    session_factory=self._session_factory)
            worker._execute(run_id, **kwargs)

    def _execute(self, run_id: str, *, markdown: str, instruction: str,
                 targets: list[str], conversation: list[dict]) -> None:
        journal = RunJournal(self.db)
        try:
            journal.transition(run_id, "running")
            journal.append(run_id, "run.started", {"operation": "rewrite_candidate"})
            journal.append(run_id, "tool.started",
                           {"toolCallId": "submit", "toolName": "submit_rewrite_candidate"})
            conversation_text = "\n\n".join(
                f"{'编辑' if m.get('role') == 'assistant' else '用户'}：{str(m.get('text', ''))[:2000]}"
                for m in conversation[-16:]
            )
            user_prompt = "\n\n".join(filter(None, [
                f"修改要求：\n{instruction.strip()}",
                f"既有对话（仅作上下文）：\n{conversation_text}" if conversation_text else "",
                f"完整文章（只用于理解上下文）：\n---\n{markdown[:120_000]}\n---",
                "待替换目标（共 "
                + str(len(targets))
                + " 段，按顺序逐一给出完整替换文本）：\n"
                + "\n\n".join(
                    f"目标 {i + 1}：\n---\n{t[:20_000]}\n---"
                    for i, t in enumerate(targets)
                ),
            ]))
            data = self.llm.complete_json(_SYSTEM, user_prompt, temperature=0.5)
            replacements = data.get("replacements")
            if not isinstance(replacements, list) or not replacements:
                raise RuntimeError("模型没有返回 replacements")
            candidate = {
                "replacements": [str(r) for r in replacements][:32],
                "summary": str(data.get("summary", "")),
                "provider": "openai-compatible",
                "model": self.llm.model,
                "mocked": False,
            }
            journal.append(run_id, "rewrite.candidate_ready", candidate)
            journal.append(run_id, "tool.completed",
                           {"toolCallId": "submit", "toolName": "submit_rewrite_candidate"})
            journal.transition(run_id, "completed")
            journal.append(run_id, "run.completed", {"candidateReady": True})
        except Exception as exc:  # noqa: BLE001 - 后台线程兜底
            latest = journal.get_run(run_id)
            if latest and latest["status"] == "stopping":
                journal.transition(run_id, "stopped")
                journal.append(run_id, "run.stopped", {"reason": "user_requested"})
                return
            journal.transition(run_id, "failed", {
                "code": "REWRITE_RUN_FAILED", "message": str(exc), "retryable": True,
            })
            journal.append(run_id, "run.failed", {
                "code": "REWRITE_RUN_FAILED", "message": str(exc),
            })
