from langgraph.graph import MessagesState


class TribunalState(MessagesState):
    task: str
    worker_output: str
    inspector_critique: str
    judge_verdict: str          # "accept" | "retry" | "escalate"
    iterations: int
    max_iterations: int
