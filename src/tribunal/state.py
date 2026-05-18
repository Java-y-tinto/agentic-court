from typing import TypedDict


class TribunalState(TypedDict):
    task: str
    worker_messages: list       # in-progress tool-call exchange for the current cycle
    worker_output: str          # final answer produced by worker each cycle
    inspector_critique: str
    judge_verdict: str          # "accept" | "retry" | "escalate"
    iterations: int
    max_iterations: int
