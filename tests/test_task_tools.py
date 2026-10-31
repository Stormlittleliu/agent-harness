# -*- coding: utf-8 -*-
from core.runtime.task_tools import build_task_tools
from core.runtime.tasks import TaskStore


def test_task_tools_create_claim_complete():
    store = TaskStore(":memory:")
    tools = {item.name: item for item in build_task_tools(store)}

    assert "已创建" in tools["create_task"].invoke({"subject": "A"})
    task_id = store.list()[0].id

    blocked = store.create("B", blocked_by=[task_id])
    assert "阻塞" in tools["claim_task"].invoke({"task_id": blocked.id})

    assert "已认领" in tools["claim_task"].invoke({"task_id": task_id})
    assert "已完成" in tools["complete_task"].invoke({"task_id": task_id, "result": "done"})
    assert "B" in tools["list_tasks"].invoke({})
    assert "已认领" in tools["claim_task"].invoke({"task_id": blocked.id})
