from langchain_ollama import ChatOllama

from src.modules.logger import logger

from .state import TribunalState
from .tools import TOOLS

_llm = ChatOllama(model="qwen2.5", base_url="http://localhost:11434")
_llm_with_tools = _llm.bind_tools(TOOLS)

_WORKER_SYSTEM = (
    "You are a capable AI agent. Complete the task you are given. "
    "Use tools when needed. When finished, provide your final answer directly. "
    "Each tool call runs in an isolated environment with no memory of previous calls. "
    "Always include all necessary definitions and context within a single tool call."
)

_INSPECTOR_SYSTEM = (
    "You are an adversarial inspector. You receive a task and a proposed solution. "
    "Find specific, concrete flaws: logical errors, unhandled edge cases, security issues, "
    "inefficiencies, or places where the solution does not match the task requirements. "
    "If the solution is correct, say so briefly. Otherwise, list each flaw precisely. "
    "Do NOT write code or suggest fixes — plain text critique only."
)

_JUDGE_SYSTEM = (
    "You are a judge. Given a task, a solution, and a critique, reply with exactly one word: "
    "'accept' if the solution is correct, and corresponds to the task given by the user "
    "'retry' if it has fixable issues important enough to guarantee another cycle, "
    "'escalate' if the problem is unsolvable or requires human intervention. "
    "No punctuation, no explanation."
)


def _task_content(state: TribunalState) -> str:
    content = state["task"]
    if state.get("iterations", 0) > 0 and state.get("inspector_critique"):
        content += f"\n\nYour previous output:\n{state['worker_output']}"
        content += f"\n\nInspector critique:\n{state['inspector_critique']}"
        content += "\n\nAddress the critique and redo your work."
    return content


def _current_cycle_messages(messages: list) -> list:
    for i in range(len(messages) - 1, -1, -1):
        if getattr(messages[i], "tool_calls", None):
            return list(messages[i:])
    return []


def worker(state: TribunalState) -> dict:
    all_messages = state.get("messages", [])
    is_continuation = bool(all_messages) and getattr(all_messages[-1], "type", None) == "tool"

    if is_continuation:
        llm_messages = [
            {"role": "system", "content": _WORKER_SYSTEM},
            {"role": "user", "content": _task_content(state)},
            *_current_cycle_messages(all_messages),
        ]
        iterations_delta = 0
    else:
        llm_messages = [
            {"role": "system", "content": _WORKER_SYSTEM},
            {"role": "user", "content": _task_content(state)},
        ]
        iterations_delta = 1
        logger.info("Worker — cycle %d/%d", state.get("iterations", 0) + 1, state.get("max_iterations", 3))

    response = _llm_with_tools.invoke(llm_messages)

    updates: dict = {
        "messages": [response],
        "iterations": state.get("iterations", 0) + iterations_delta,
    }
    if not getattr(response, "tool_calls", None):
        updates["worker_output"] = response.content

    return updates


def inspector(state: TribunalState) -> dict:
    logger.info("Inspector — reviewing output")
    messages = [
        {"role": "system", "content": _INSPECTOR_SYSTEM},
        {"role": "user", "content": f"Task:\n{state['task']}\n\nSolution:\n{state['worker_output']}"},
    ]
    response = _llm.invoke(messages)
    return {"inspector_critique": response.content}


def judge(state: TribunalState) -> dict:
    logger.info("Judge — evaluating")
    messages = [
        {"role": "system", "content": _JUDGE_SYSTEM},
        {"role": "user", "content": (
            f"Task:\n{state['task']}\n\n"
            f"Solution:\n{state['worker_output']}\n\n"
            f"Critique:\n{state['inspector_critique']}"
        )},
    ]
    response = _llm.invoke(messages)
    verdict = response.content.strip().lower()
    logger.info("Judge — verdict: %s", verdict)
    return {"judge_verdict": verdict}


def escalate(_state: TribunalState) -> dict:
    return {}
