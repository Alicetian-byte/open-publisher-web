"""Agent 运行日志：蓝本 RunJournal（runs/run-journal.ts）的 Python 移植。

语义保持一致：
- 状态机转换白名单（pending → running → ...），非法转换抛错
- 事件序列号 per-run 自增，UNIQUE(run_id, sequence) 兜底
- eventsAfter 支持断线续读（SSE 轮询基础）
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.agent_runtime import AgentRun, AgentRunEvent


class RunJournalError(Exception):
    pass


TERMINAL_STATUSES = {"completed", "failed", "stopped", "interrupted"}

ALLOWED_TRANSITIONS: dict[str, set[str]] = {
    "pending": {"running", "waiting_user", "stopping", "failed", "interrupted"},
    "running": {"waiting_user", "stopping", "completed", "failed", "interrupted"},
    "waiting_user": {"running", "stopping", "failed", "interrupted"},
    "stopping": {"stopped", "failed", "interrupted"},
    "stopped": set(),
    "completed": set(),
    "failed": set(),
    "interrupted": set(),
}


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class RunJournal:
    def __init__(self, db: Session):
        self.db = db

    def create_run(self, *, article_id: str | None, agent_id: str,
                   operation: str, base_revision_id: str | None = None,
                   session_id: str | None = None,
                   owner_user_id: str | None = None) -> dict:
        run = AgentRun(
            id="run:" + uuid4().hex,
            article_id=article_id,
            session_id=session_id,
            agent_id=agent_id,
            operation=operation,
            status="pending",
            base_revision_id=base_revision_id,
            owner_user_id=owner_user_id,
            created_at=utcnow(),
        )
        self.db.add(run)
        self.db.commit()
        return self._map(run)

    def active_run_for_article(self, article_id: str) -> dict | None:
        """蓝本 run lock：同一文章同一时刻只允许一个活动 writer run。"""
        run = self.db.scalars(
            select(AgentRun)
            .where(
                AgentRun.article_id == article_id,
                AgentRun.status.in_(("pending", "running", "stopping")),
            )
            .order_by(AgentRun.created_at.desc())
            .limit(1)
        ).first()
        return self._map(run) if run else None

    def get_run(self, run_id: str) -> dict | None:
        run = self.db.get(AgentRun, run_id, populate_existing=True)
        return self._map(run) if run else None

    def transition(self, run_id: str, status: str,
                   error: dict | None = None) -> dict:
        run = self.db.get(AgentRun, run_id, populate_existing=True)
        if run is None:
            raise RunJournalError(f"Unknown run: {run_id}")
        if run.status == status:
            return self._map(run)
        if status not in ALLOWED_TRANSITIONS[run.status]:
            raise RunJournalError(
                f"Invalid agent run transition: {run.status} -> {status}"
            )
        now = utcnow()
        run.status = status
        if run.started_at is None and status == "running":
            run.started_at = now
        if status in TERMINAL_STATUSES:
            run.completed_at = now
        run.error_json = json.dumps(error, ensure_ascii=False) if error else None
        self.db.commit()
        return self._map(run)

    def append(self, run_id: str, event_type: str, payload,
               agent_id: str | None = None) -> dict:
        run = self.db.get(AgentRun, run_id, populate_existing=True)
        if run is None:
            raise RunJournalError(f"Unknown run: {run_id}")
        last = self.db.scalar(
            select(AgentRunEvent.sequence)
            .where(AgentRunEvent.run_id == run_id)
            .order_by(AgentRunEvent.sequence.desc())
            .limit(1)
        )
        sequence = (last or 0) + 1
        timestamp = utcnow()
        event_id = "evt:" + uuid4().hex  # "event:"+hex 为 38 字符，超出 CHAR(36)
        self.db.add(AgentRunEvent(
            id=event_id, run_id=run_id, sequence=sequence,
            event_type=event_type,
            payload_json=json.dumps(payload, ensure_ascii=False),
            created_at=timestamp,
        ))
        self.db.commit()
        return {
            "id": event_id,
            "runId": run_id,
            "sequence": sequence,
            "timestamp": timestamp.isoformat(),
            "articleId": run.article_id,
            "agentId": agent_id or run.agent_id,
            "parentAgentId": None,
            "operation": run.operation,
            "type": event_type,
            "payload": payload,
        }

    def events_after(self, run_id: str, after_sequence: int) -> list[dict]:
        run = self.db.get(AgentRun, run_id, populate_existing=True)
        if run is None:
            raise RunJournalError(f"Unknown run: {run_id}")
        rows = self.db.scalars(
            select(AgentRunEvent)
            .where(AgentRunEvent.run_id == run_id,
                   AgentRunEvent.sequence > after_sequence)
            .order_by(AgentRunEvent.sequence)
        ).all()
        return [
            {
                "id": r.id,
                "runId": r.run_id,
                "sequence": r.sequence,
                "timestamp": r.created_at.isoformat(),
                "articleId": run.article_id,
                "agentId": run.agent_id,
                "parentAgentId": None,
                "operation": run.operation,
                "type": r.event_type,
                "payload": json.loads(r.payload_json),
            }
            for r in rows
        ]

    @staticmethod
    def _map(run: AgentRun) -> dict:
        return {
            "id": run.id,
            "articleId": run.article_id,
            "sessionId": run.session_id,
            "agentId": run.agent_id,
            "operation": run.operation,
            "status": run.status,
            "baseRevisionId": run.base_revision_id,
            "ownerUserId": run.owner_user_id,
            "createdAt": run.created_at.isoformat(),
            "startedAt": run.started_at.isoformat() if run.started_at else None,
            "completedAt": run.completed_at.isoformat() if run.completed_at else None,
            "error": json.loads(run.error_json) if run.error_json else None,
        }
