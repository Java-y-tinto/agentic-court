import uuid

from langgraph.types import Command

from src.tribunal.graph import app
from src.tribunal.state import TribunalState


def _drain_interrupts(config: dict) -> dict:
    """Resume any pending governance approvals and return the final state."""
    while True:
        snapshot = app.get_state(config)
        pending = [iv for t in snapshot.tasks for iv in t.interrupts]
        if not pending:
            return snapshot.values

        iv = pending[0]
        print(f"\n  [Approval required]")
        print(f"  Tool : {iv.value['tool']}")
        print(f"  Args : {iv.value['args']}")
        decision = input("  Approve? (yes/no): ").strip()
        app.invoke(Command(resume=decision), config=config)


def main():
    print("SentinelAI — type 'exit' to quit\n")

    while True:
        task = input("Task: ").strip()
        if not task or task.lower() == "exit":
            break

        config = {"configurable": {"thread_id": str(uuid.uuid4())}}

        initial: TribunalState = {
            "task": task,
            "messages": [],
            "worker_output": "",
            "inspector_critique": "",
            "judge_verdict": "",
            "iterations": 0,
            "max_iterations": 3,
        }

        print()
        app.invoke(initial, config=config)
        state = _drain_interrupts(config)

        verdict = state.get("judge_verdict", "")
        output = state.get("worker_output", "No output.")

        if verdict == "accept":
            print(f"\n[Accepted]\n{output}\n")
        elif verdict == "escalate":
            print(f"\n[Escalated — human review needed]\n{output}")
            print(f"\nInspector: {state.get('inspector_critique', '')}\n")
        else:
            print(f"\n[Output]\n{output}\n")


if __name__ == "__main__":
    main()
