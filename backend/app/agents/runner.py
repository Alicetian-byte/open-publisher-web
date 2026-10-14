"""工作流运行器：把 LangGraph 执行与 DB 持久化、Redis 事件打通。

在后台线程中运行（由 API 层启动）。每个节点完成后：
- 发布 node.completed 事件
- 按 artifact 映射保存 TweetArtifact
运行结束按结果保存 TweetRevision 并更新 TweetRun 状态。
"""

import logging
from datetime import datetime, timezone
from uuid import uuid4

from sqlalchemy import func
from sqlalchemy.orm import Session, sessionmaker

from app.agents.events import RunEventPublisher
from app.agents.graph import build_workflow_graph
from app.agents.llm_client import LLMClient
from app.agents.nodes.context import StopWorkflowError
from app.core.config import get_settings
from app.db.session import SessionLocal
from app.models.artifact import TweetArtifact
from app.models.revision import TweetRevision
from app.models.run import TweetRun

logger = logging.getLogger(__name__)

# node → (state_key, artifact_type, title)
ARTIFACT_MAP: dict[str, tuple[str, str, str]] = {
    "product_analyst": ("product_profile", "product_profile", "产品画像"),
    "audience_analyst": ("audience_profile", "audience_profile", "受众分析"),
    "strategy_planner": ("strategy", "tweet_strategy", "推文策略"),
    "copywriter": ("candidates", "tweet_candidates", "候选推文"),
    "critic": ("critiques", "quality_report", "质量评审报告"),
    "rewriter": ("candidates", "tweet_candidates_optimized", "优化后候选"),
    "safety_checker": ("safety_report", "safety_report", "风险检查报告"),
    "formatter": ("platform_variants", "platform_variants", "平台版本"),
}


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def run_workflow(
    run_id: str,
    project_id: str,
    user_input: dict,
    *,
    session_factory: sessionmaker[Session] | None = None,
    llm: LLMClient | None = None,
    graph_builder=None,
    events: RunEventPublisher | None = None,
) -> None:
    """同步执行工作流；设计为后台线程入口，永不向外抛异常。"""
    settings = get_settings()
    session_factory = session_factory or SessionLocal
    events = events or RunEventPublisher(run_id)
    llm = llm or LLMClient()

    def update_run(**fields: object) -> None:
        with session_factory() as db:
            run = db.get(TweetRun, run_id)
            if run is not None:
                for key, value in fields.items():
                    setattr(run, key, value)
                db.commit()

    def save_artifact(artifact_type: str, title: str, content: object) -> None:
        with session_factory() as db:
            db.add(
                TweetArtifact(
                    id=uuid4().hex,
                    run_id=run_id,
                    artifact_type=artifact_type,
                    title=title,
                    content_json=content,  # type: ignore[arg-type]
                )
            )
            db.commit()

    update_run(status="running", started_at=_utcnow(), error_message=None)
    events.set_status("running")
    events.publish("run.started", payload={"project_id": project_id})

    initial_state: dict = {
        "run_id": run_id,
        "project_id": project_id,
        "user_input": user_input,
        "errors": [],
        "iteration_count": 0,
        "_max_iterations": settings.workflow_max_iterations,
    }

    final_state: dict = dict(initial_state)
    graph_builder = graph_builder or build_workflow_graph

    try:
        graph = graph_builder(llm, events)
        for chunk in graph.stream(
            initial_state, config={"recursion_limit": 30}
        ):
            for node_name, updates in chunk.items():
                if not isinstance(updates, dict):
                    continue
                final_state.update(updates)
                mapping = ARTIFACT_MAP.get(node_name)
                if mapping:
                    state_key, artifact_type, title = mapping
                    value = updates.get(state_key) or final_state.get(state_key)
                    if value:
                        save_artifact(artifact_type, title, value)
                events.publish(
                    "node.completed",
                    node_id=node_name,
                    payload={
                        "artifactType": mapping[1] if mapping else None,
                        "currentStep": final_state.get("current_step"),
                    },
                )
    except StopWorkflowError:
        update_run(status="cancelled", finished_at=_utcnow(), llm_calls=llm.call_count)
        events.set_status("cancelled")
        events.publish("run.cancelled", message="用户停止了本次生成")
        return
    except Exception as exc:  # noqa: BLE001 - 后台线程兜底
        logger.exception("workflow run %s failed", run_id)
        update_run(
            status="failed",
            error_message=str(exc),
            finished_at=_utcnow(),
            llm_calls=llm.call_count,
        )
        events.set_status("failed")
        events.publish("run.failed", payload={"message": str(exc)})
        return

    variants = final_state.get("platform_variants") or []
    with session_factory() as db:
        max_version = (
            db.query(func.max(TweetRevision.version))
            .filter(TweetRevision.project_id == project_id)
            .scalar()
        ) or 0
        for offset, variant in enumerate(variants):
            if not isinstance(variant, dict) or not variant.get("content"):
                continue
            db.add(
                TweetRevision(
                    id=uuid4().hex,
                    project_id=project_id,
                    run_id=run_id,
                    content=str(variant["content"]),
                    platform=variant.get("platform"),
                    tone=variant.get("tone"),
                    score=variant.get("score"),
                    risk_level=variant.get("risk_level") or "low",
                    version=max_version + offset + 1,
                    source="ai_generated",
                )
            )
        db.commit()
        saved_count = len(variants)

    update_run(
        status="completed",
        current_node="done",
        finished_at=_utcnow(),
        llm_calls=llm.call_count,
    )
    events.set_status("completed")
    events.publish(
        "run.completed", payload={"revisions": saved_count, "llmCalls": llm.call_count}
    )
