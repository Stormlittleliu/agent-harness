# -*- coding: utf-8 -*-
"""本地 trace：记录一次 run 的模型/工具调用、token 与耗时。

不依赖 LangSmith / OpenTelemetry；每次调用追加写入
`outputs/traces/trace_YYYYMMDD.jsonl`。一行一个事件，便于 grep 和后续聚合。

用法：
    tracer = TraceCallbackHandler(trace_id="...", thread_id="...")
    agent.invoke(..., config={"configurable": {"thread_id": ...}, "callbacks": [tracer]})
"""
from __future__ import annotations

import json
import threading
import time
from datetime import datetime
from pathlib import Path

import yaml
from langchain_core.callbacks import BaseCallbackHandler

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_TRACE_DIR = "outputs/traces"
_WRITE_LOCK = threading.Lock()


def _load_config() -> dict:
    path = ROOT / "config" / "observability.yml"
    if not path.exists():
        return {}
    try:
        return yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    except Exception:
        return {}


class TraceCallbackHandler(BaseCallbackHandler):
    """把一个 run 的模型/工具事件写成 JSONL。"""

    def __init__(self, trace_id: str, thread_id: str | None = None):
        self.trace_id = trace_id
        self.thread_id = thread_id
        self.started_at = time.time()
        self.model_calls = 0
        self.tool_calls = 0
        self.prompt_tokens = 0
        self.completion_tokens = 0
        self.total_tokens = 0
        self.cost_est = 0.0

        self._model_start: dict[str, float] = {}
        self._tool_start: dict[str, float] = {}
        self._tool_names: dict[str, str] = {}
        self._last_model = "unknown"
        self._finalized = False

        config = _load_config()
        self._trace_dir = ROOT / config.get("trace_dir", DEFAULT_TRACE_DIR)
        self._pricing = config.get("pricing") or {}

    # ===================== 写入 =====================
    def _write(self, event: str, **fields) -> None:
        row = {
            "trace_id": self.trace_id,
            "thread_id": self.thread_id,
            "event": event,
            "ts": datetime.now().isoformat(timespec="milliseconds"),
            **fields,
        }
        try:
            with _WRITE_LOCK:
                self._trace_dir.mkdir(parents=True, exist_ok=True)
                path = self._trace_dir / f"trace_{datetime.now():%Y%m%d}.jsonl"
                with path.open("a", encoding="utf-8") as f:
                    f.write(json.dumps(row, ensure_ascii=False) + "\n")
        except Exception:
            # trace 不能影响主流程
            pass

    # ===================== 模型事件 =====================
    def on_chat_model_start(self, serialized, messages, *, run_id, parent_run_id=None, **kwargs):
        self.model_calls += 1
        self._model_start[str(run_id)] = time.time()
        model = self._model_name(serialized, kwargs)
        self._last_model = model
        self._write("model_start", run_id=str(run_id), model=model, messages=len(messages or []))

    def on_llm_end(self, response, *, run_id, parent_run_id=None, **kwargs):
        start = self._model_start.pop(str(run_id), None)
        latency_ms = int((time.time() - start) * 1000) if start else None
        prompt, completion, total = self._extract_usage(response)
        self.prompt_tokens += prompt
        self.completion_tokens += completion
        self.total_tokens += total

        model = self._model_name_from_response(response) or self._last_model
        cost = self._estimate_cost(model, prompt, completion)
        if not cost and self._last_model != model:
            # 响应里的模型名可能和配置名不同（如 deepseek-flash vs deepseek-chat）
            cost = self._estimate_cost(self._last_model, prompt, completion)
        self.cost_est += cost
        self._write(
            "model_end",
            run_id=str(run_id),
            model=model,
            latency_ms=latency_ms,
            prompt_tokens=prompt,
            completion_tokens=completion,
            total_tokens=total,
            cost_est=round(cost, 6),
        )

    def on_llm_error(self, error, *, run_id, parent_run_id=None, **kwargs):
        self._model_start.pop(str(run_id), None)
        self._write("model_error", run_id=str(run_id), error=str(error))

    # ===================== 工具事件 =====================
    def on_tool_start(self, serialized, input_str, *, run_id, parent_run_id=None, **kwargs):
        self.tool_calls += 1
        name = (serialized or {}).get("name", "unknown")
        self._tool_names[str(run_id)] = name
        self._tool_start[str(run_id)] = time.time()
        self._write("tool_start", run_id=str(run_id), tool=name, input=input_str)

    def on_tool_end(self, output, *, run_id, parent_run_id=None, **kwargs):
        name = self._tool_names.pop(str(run_id), "unknown")
        start = self._tool_start.pop(str(run_id), None)
        latency_ms = int((time.time() - start) * 1000) if start else None
        status = getattr(output, "status", "success") or "success"
        self._write("tool_end", run_id=str(run_id), tool=name, latency_ms=latency_ms, status=status)

    def on_tool_error(self, error, *, run_id, parent_run_id=None, **kwargs):
        name = self._tool_names.pop(str(run_id), "unknown")
        self._tool_start.pop(str(run_id), None)
        self._write("tool_error", run_id=str(run_id), tool=name, error=str(error))

    # ===================== run 结束 =====================
    def on_chain_end(self, outputs, *, run_id, parent_run_id=None, **kwargs):
        if parent_run_id is None:
            status = "interrupted" if isinstance(outputs, dict) and "__interrupt__" in outputs else "completed"
            self.finalize(status)

    def on_chain_error(self, error, *, run_id, parent_run_id=None, **kwargs):
        if parent_run_id is None:
            self.finalize("error", error=str(error))

    def finalize(self, status: str = "completed", error: str | None = None) -> None:
        """写 run_end；重复调用只写一次。"""
        if self._finalized:
            return
        self._finalized = True
        self._write(
            "run_end",
            status=status,
            error=error,
            model_calls=self.model_calls,
            tool_calls=self.tool_calls,
            prompt_tokens=self.prompt_tokens,
            completion_tokens=self.completion_tokens,
            total_tokens=self.total_tokens,
            duration_ms=int((time.time() - self.started_at) * 1000),
            cost_est=round(self.cost_est, 6),
        )

    def finalize_if_needed(self) -> None:
        """在 invoke/stream 的 finally 中兜底，避免中断时没有 run_end。"""
        self.finalize("unknown")

    # ===================== 解析辅助 =====================
    @staticmethod
    def _model_name(serialized, kwargs: dict) -> str:
        params = kwargs.get("invocation_params") or {}
        return (
            params.get("model")
            or params.get("model_name")
            or (serialized or {}).get("name", "unknown")
        )

    @staticmethod
    def _model_name_from_response(response) -> str | None:
        llm_output = getattr(response, "llm_output", None) or {}
        return llm_output.get("model_name") or llm_output.get("model")

    @staticmethod
    def _extract_usage(response) -> tuple[int, int, int]:
        """兼容 OpenAI 的 token_usage 与 LangChain 的 usage_metadata。"""
        llm_output = getattr(response, "llm_output", None) or {}
        usage = llm_output.get("token_usage") or llm_output.get("usage") or {}
        if not usage:
            try:
                message = response.generations[0][0].message
                usage = getattr(message, "usage_metadata", None) or {}
            except Exception:
                usage = {}
        prompt = usage.get("prompt_tokens") or usage.get("input_tokens") or 0
        completion = usage.get("completion_tokens") or usage.get("output_tokens") or 0
        total = usage.get("total_tokens") or (prompt + completion)
        return int(prompt), int(completion), int(total)

    def _estimate_cost(self, model: str, prompt: int, completion: int) -> float:
        """按 config/observability.yml 的价格估算；未配置时返回 0。"""
        price = self._pricing.get(model) or {}
        if not price:
            return 0.0
        return (
            prompt / 1_000_000 * float(price.get("input_per_1m", 0))
            + completion / 1_000_000 * float(price.get("output_per_1m", 0))
        )
