"""
Agent 主循环调用接口演示脚本
==============================

演示「同一个 Agent,如何用不同接口调用它的主循环」,每次演示对应一种观察口径:

  --demo invoke    一次跑到头,只拿最终状态
  --demo values    逐步推进,每步输出当时的完整状态(项目 execute_stream 用的模式)
  --demo updates   逐步推进,只输出每一步的增量
  --demo messages  只流式输出 LLM 产生的消息/token(打字机效果)
  --demo events    消费底层事件总线(astream_events v2),看工具/图节点事件
                   (当前 LangGraph 版本未透传 chat model 事件,token 流请看 --demo messages)
  --demo batch     一次发起多个请求
  --demo memory    演示 thread_id 会话记忆 + get_state / get_state_history(内核级接口)
  --demo report    完整报告流程:多工具组合 + 意图路由动态切换提示词(项目最大亮点)
  --demo all       依次跑 invoke/values/updates/messages/events/batch(默认)

用法示例:
  python examples/demo_agent_interfaces.py                      # 跑 all
  python examples/demo_agent_interfaces.py --demo events        # 只看事件流
  python examples/demo_agent_interfaces.py --demo values --question "深圳天气怎么样"   # 自定义问题

运行前提:
  1. 环境变量 DEEPSEEK_API_KEY 已配置(或项目根目录存在 .env 文件)
  2. 向量库已初始化(执行 README 中的知识库初始化命令,data/runtime/chroma_db 与 data/runtime/md5.txt 已生成)
"""

import argparse
import asyncio
import os
import sys
import uuid

# 把项目根目录加入 sys.path,支持从任意目录运行本脚本
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Windows 控制台默认 gbk,统一为 utf-8 避免中文乱码
try:
    sys.stdout.reconfigure(encoding="utf-8")
except AttributeError:
    pass

# 尝试加载 .env 中的 API Key(没装 python-dotenv 则依赖系统环境变量)
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

from agent.react_agent import ReactAgent

# 演示默认使用的问题:触发一次工具调用,能完整看到 model → tools → model 的循环
DEFAULT_QUESTION = "现在几月份?"


def _get_agent():
    """create_agent() 返回的编译图,本质是 Runnable"""
    return ReactAgent().agent


def _input(question: str) -> dict:
    return {"messages": [{"role": "user", "content": question}]}


def _config(thread_id: str | None = None) -> dict:
    return {"configurable": {"thread_id": thread_id or f"demo-{uuid.uuid4().hex}"}}


def _print_message(msg, indent: str = "    "):
    """打印一条消息:类型 + 内容(截断)+ 工具调用信息"""
    content = str(msg.content).strip()
    preview = content[:60] + ("..." if len(content) > 60 else "")
    print(f"{indent}[{type(msg).__name__}] {preview}")
    if getattr(msg, "tool_calls", None):
        for tc in msg.tool_calls:
            print(f"{indent}    -> 调用工具: {tc['name']}({tc['args']})")


def demo_invoke(question: str):
    """[1] invoke:一次跑到头,返回最终状态"""
    print("=" * 60)
    print("[invoke] 一次跑到头,返回最终状态 final_state['messages']")
    print("=" * 60)
    final_state = _get_agent().invoke(_input(question), config=_config(), context={"intent": None})
    for msg in final_state["messages"]:
        _print_message(msg)
    print(f"\n→ 最终回答: {final_state['messages'][-1].content}")


def demo_stream_values(question: str):
    """[2] stream(values):每推进一步,输出当时的完整状态快照"""
    print("=" * 60)
    print("[stream] stream_mode='values':每一步输出当时的完整状态")
    print("=" * 60)
    for i, chunk in enumerate(_get_agent().stream(_input(question), config=_config(), stream_mode="values", context={"intent": None}), 1):
        print(f"--- 第 {i} 步状态快照,共 {len(chunk['messages'])} 条消息,最新一条:")
        _print_message(chunk["messages"][-1])


def demo_stream_updates(question: str):
    """[3] stream(updates):只输出每一步的增量,看到谁被更新了"""
    print("=" * 60)
    print("[stream] stream_mode='updates':只输出每一步的增量")
    print("=" * 60)
    for i, chunk in enumerate(_get_agent().stream(_input(question), config=_config(), stream_mode="updates", context={"intent": None}), 1):
        print(f"--- 第 {i} 步增量,被更新的节点: {list(chunk.keys())}")
        for node, update in chunk.items():
            print(f"    [{node}] 输出:")
            if isinstance(update, dict) and "messages" in update:
                for m in update["messages"]:
                    _print_message(m)
            elif isinstance(update, list):
                for m in update:
                    _print_message(m)
            else:
                print(f"      {str(update)[:80]}")


def demo_stream_messages(question: str):
    """[4] stream(messages):只流 LLM 产出的消息,适合打字机效果"""
    print("=" * 60)
    print("[stream] stream_mode='messages':只流 LLM 产出的消息/token")
    print("=" * 60)
    for chunk in _get_agent().stream(_input(question), config=_config(), stream_mode="messages", context={"intent": None}):
        # 该模式下每个 chunk 是 (message, metadata) 元组
        if isinstance(chunk, tuple) and len(chunk) == 2:
            message, _ = chunk
        else:
            message = chunk
        if message.content:
            print(message.content, end="", flush=True)
        if getattr(message, "tool_calls", None):
            for tc in message.tool_calls:
                print(f"\n[调用工具] {tc['name']}({tc['args']})")
    print()


def demo_events(question: str):
    """[5] astream_events:消费底层事件总线,查看工具与图节点事件

    注意:当前 LangGraph 版本在 create_agent 内部不会透传 on_chat_model_* 事件;
    想看模型 token 流请使用 --demo messages。本演示仍能完整看到工具调用事件。
    """
    print("=" * 60)
    print("[astream_events] version='v2':消费底层事件总线(工具/图节点事件)")
    print("=" * 60)

    async def _run():
        event_counter = {}
        async for event in _get_agent().astream_events(_input(question), config=_config(), version="v2", context={"intent": None}):
            kind = event["event"]
            event_counter[kind] = event_counter.get(kind, 0) + 1

            if kind == "on_chat_model_start":
                print("  [事件] on_chat_model_start —— 模型开始思考")
            elif kind == "on_chat_model_stream":
                # 逐 token 到达的事件,这就是流式输出的底层来源
                print(event["data"]["chunk"].content, end="", flush=True)
            elif kind == "on_tool_start":
                print(f"  [事件] on_tool_start —— 准备调用工具: {event.get('name', '')}")
            elif kind == "on_tool_end":
                print(f"  [事件] on_tool_end —— 工具 {event.get('name', '')} 执行完成")

        print("\n\n本次运行收到的事件类型统计(即内核总线上的消息种类):")
        for kind, count in sorted(event_counter.items()):
            print(f"    {kind}: {count} 次")

    asyncio.run(_run())


def demo_batch():
    """[6] batch:一次发起多个请求,内核并行执行"""
    print("=" * 60)
    print("[batch] 一次发起多个请求")
    print("=" * 60)
    questions = ["现在几月份?", "你好,你是谁?"]
    # batch 的所有输入共享同一份 run context；本例都是普通问答，不受影响。
    # 若需要每个请求独立的意图，请改为逐条 invoke，并为每条请求传入新的 context。
    results = _get_agent().batch(
        [_input(q) for q in questions],
        config=[_config() for _ in questions],
        context={"intent": None},
    )
    for i, (q, res) in enumerate(zip(questions, results), 1):
        print(f"  请求{i}({q}) → {res['messages'][-1].content}")


def demo_memory():
    """[7] thread_id 会话记忆 + 内核级状态接口(get_state / get_state_history)

    注意:项目里的 ReactAgent 没传 checkpointer,所以本演示用 InMemorySaver
    现场组装一个"带记忆"的 Agent,展示接口本身的能力(也是项目的改进方向)。
    """
    print("=" * 60)
    print("[memory] thread_id 会话记忆 + get_state / get_state_history")
    print("=" * 60)
    try:
        from langgraph.checkpoint.memory import InMemorySaver
        from langchain.agents import create_agent
        from model.factory import chat_model
        from utils.prompt_loader import load_system_prompts
        from agent.tools.agent_tools import (rag_summarize, get_weather, get_user_location,
                                             get_user_id, get_current_month,
                                             fetch_external_data)
        from agent.tools.middleware import monitor_tool, log_before_model, report_prompt_switch
    except ImportError as e:
        print(f"  当前环境不支持(checkpointer 相关依赖缺失):{e}")
        return

    agent_with_memory = create_agent(
        model=chat_model,
        system_prompt=load_system_prompts(),
        tools=[rag_summarize, get_weather, get_user_location, get_user_id,
               get_current_month, fetch_external_data],
        # 为聚焦会话记忆接口，这里只挂载日志与提示词中间件
        middleware=[monitor_tool, log_before_model, report_prompt_switch],
        checkpointer=InMemorySaver(),
    )
    config = {"configurable": {"thread_id": "demo_thread_001"}}

    print("  第 1 轮:告诉它我的名字(不带任何历史)")
    r1 = agent_with_memory.invoke(_input("我叫小明,请记住我的名字"), config=config, context={"intent": None})
    print(f"    → {r1['messages'][-1].content}")

    print("\n  第 2 轮:追问(仍然只发一句话,历史由内核按 thread_id 自动加载)")
    r2 = agent_with_memory.invoke(_input("我叫什么名字?"), config=config, context={"intent": None})
    print(f"    → {r2['messages'][-1].content}")

    print("\n  [get_state] 查看该线程当前状态:")
    state = agent_with_memory.get_state(config)
    print(f"    消息总数: {len(state.values['messages'])} 条")
    print(f"    下一步将执行: {state.next}")

    print("\n  [get_state_history] 该线程的所有历史快照:")
    history = list(agent_with_memory.get_state_history(config))
    print(f"    共 {len(history)} 个快照(每完成一轮就留一个检查点,这就是断点续跑的根基)")


def demo_report():
    """[8] 完整报告流程:多工具组合 + 意图路由动态切换提示词(项目最大亮点)

    流程:intent_router 命中「报告」关键词 → report_prompt_switch 切换为报告提示词
         → get_user_id → get_current_month → fetch_external_data → 生成报告
    同时打开 logs/ 目录当天日志,可看到完整的推理轨迹:
    intent_router_*.log(意图与命中关键词)、agent_*.log(工具调用与步数)。
    """
    print("=" * 60)
    print("[report] 完整报告流程:意图路由 + 动态提示词切换")
    print("=" * 60)
    question = "给我生成我的使用报告"
    for i, chunk in enumerate(_get_agent().stream(_input(question), config=_config(), stream_mode="values", context={"intent": None}), 1):
        print(f"--- 第 {i} 步状态快照,最新一条消息:")
        _print_message(chunk["messages"][-1])
    print("\n→ 提示:打开 logs/ 目录的 intent_router_*.log 与 agent_*.log,回放意图切换和工具调用全过程")


DEMOS = {
    "invoke": demo_invoke,
    "values": demo_stream_values,
    "updates": demo_stream_updates,
    "messages": demo_stream_messages,
    "events": demo_events,
    "batch": demo_batch,
    "memory": demo_memory,
    "report": demo_report,
}


def main():
    parser = argparse.ArgumentParser(description="Agent 主循环调用接口演示")
    parser.add_argument("--demo", choices=DEMOS.keys(), default="all",
                        help="选择演示项,默认 all(依次跑 invoke/values/updates/messages/events/batch)")
    parser.add_argument("--question", default=None,
                        help="自定义问题,默认「现在几月份?」")
    args = parser.parse_args()

    if not os.environ.get("DASHSCOPE_API_KEY"):
        print("警告:未检测到环境变量 DASHSCOPE_API_KEY,调用模型会失败。")
        print("请先 export DASHSCOPE_API_KEY=xxx 或在项目根目录放置 .env 文件。")
        return

    question = args.question or DEFAULT_QUESTION

    if args.demo == "all":
        for name in ("invoke", "values", "updates", "messages", "events", "batch"):
            demo = DEMOS[name]
            demo(question) if name != "batch" else demo()
            print()
        print("更多演示:--demo memory(会话记忆)/ --demo report(完整报告流程)")
        print("提示:--demo report 和 --demo memory 会消耗较多 token,按需单独运行。")
        return

    demo = DEMOS[args.demo]
    demo(question) if args.demo not in ("batch", "memory", "report") else demo()


if __name__ == "__main__":
    main()
