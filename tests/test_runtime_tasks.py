# -*- coding: utf-8 -*-
from langchain_core.messages import AIMessage

from core.runtime.runner import TaskRunner
from core.runtime.tasks import TaskStore


def test_dependency_blocks_and_unblocks():
    store = TaskStore(":memory:")
    first = store.create("first")
    second = store.create("second", blocked_by=[first.id])

    assert [task.id for task in store.ready()] == [first.id]
    try:
        store.claim(second.id)
    except ValueError:
        pass
    else:
        raise AssertionError("blocked task should not be claimable")

    store.claim(first.id)
    unblocked = store.complete(first.id, "done")
    assert [task.id for task in unblocked] == [second.id]
    assert [task.id for task in store.ready()] == [second.id]


def test_store_persists_across_reopen(tmp_path):
    db = tmp_path / "tasks.sqlite"
    store = TaskStore(db)
    task = store.create("persisted", description="hello")
    store.close()

    reopened = TaskStore(db)
    loaded = reopened.get(task.id)
    assert loaded.subject == "persisted"
    assert loaded.description == "hello"
    assert loaded.status == "pending"


def test_runner_claims_and_completes():
    class FakeAgent:
        hook_manager = None

        def invoke(self, query, thread_id=None):
            return {"messages": [AIMessage(content="fake done")]}

    store = TaskStore(":memory:")
    task = store.create("run me")
    result = TaskRunner(FakeAgent(), store).run_task(task.id)
    assert result["status"] == "completed"
    assert store.get(task.id).status == "completed"
    assert store.get(task.id).result == "fake done"
