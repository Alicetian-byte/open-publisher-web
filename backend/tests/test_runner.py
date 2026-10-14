"""运行器测试：artifact 持久化、revision 保存、失败路径。"""

from app.agents.runner import run_workflow
from app.models.project import Project
from app.models.artifact import TweetArtifact
from app.models.revision import TweetRevision
from app.models.run import TweetRun
from tests.conftest import FakeEvents, FakeLLM


def _create_run(factory, project_id="p1"):
    with factory() as db:
        db.add(Project(id=project_id, name="Shot2API"))
        run = TweetRun(id="run-1", project_id=project_id, status="pending", input_snapshot={"project": {"name": "Shot2API"}})
        db.add(run)
        db.commit()


def test_runner_persists_artifacts_and_revisions(db_session_factory, fake_llm_responses):
    _create_run(db_session_factory)
    fake = FakeLLM(fake_llm_responses)
    events = FakeEvents()

    run_workflow(
        "run-1",
        "p1",
        {"project": {"name": "Shot2API"}, "extra": {}},
        session_factory=db_session_factory,
        llm=fake,
        events=events,
    )

    with db_session_factory() as db:
        run = db.get(TweetRun, "run-1")
        assert run.status == "completed"
        assert run.llm_calls == 7
        artifacts = db.query(TweetArtifact).filter(TweetArtifact.run_id == "run-1").all()
        types = {a.artifact_type for a in artifacts}
        assert {
            "product_profile",
            "audience_profile",
            "tweet_strategy",
            "tweet_candidates",
            "quality_report",
            "safety_report",
            "platform_variants",
        } <= types
        revisions = db.query(TweetRevision).filter(TweetRevision.project_id == "p1").all()
        assert len(revisions) == 2
        assert revisions[0].version == 1 and revisions[1].version == 2
        assert revisions[0].source == "ai_generated"
        assert revisions[0].risk_level == "low"

    event_types = [e["eventType"] for e in events.published]
    assert "run.started" in event_types
    assert "node.completed" in event_types
    assert "run.completed" in event_types
    assert events.statuses == ["running", "completed"]


def test_runner_marks_failed_on_llm_error(db_session_factory):
    class BrokenLLM:
        call_count = 0

        def complete_json(self, system, user, *, temperature=0.7):
            raise RuntimeError("boom")

    _create_run(db_session_factory)
    events = FakeEvents()
    run_workflow(
        "run-1",
        "p1",
        {"project": {}},
        session_factory=db_session_factory,
        llm=BrokenLLM(),
        events=events,
    )
    with db_session_factory() as db:
        run = db.get(TweetRun, "run-1")
        assert run.status == "failed"
        assert "boom" in (run.error_message or "")
    assert events.statuses == ["running", "failed"]


