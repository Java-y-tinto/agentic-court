from typing import TypedDict
from langgraph.graph import StateGraph, START, END
from langchain_ollama import ChatOllama

class TribunalState(TypedDict):
    task : str # Original task set by user
    worker_output: str # Output from the worker
    inspector_critique: str # Critique from the inspector
    judge_verdict: str # "accept", "retry", "escalate"
    iterations: int # Number of iterations
    max_iterations: int # Maximum number of iterations. Hard ceiling, set at start

# Constants
llm = ChatOllama(model="qwen2.5", base_url = "http://localhost:11434")

# Agents

def worker (state: TribunalState) -> dict:
    """ AI Agent that writes code """
    content = state["task"]
    print("State:")
    print(f"\nTask: {state['task']}")
    print(f"Worker Output: {state.get('worker_output', 'Not available')}")
    print(f"Inspector Critique: {state.get('inspector_critique', 'Not available')}")
    print(f"Judge Verdict: {state.get('judge_verdict', 'Not available')}")
    print(f"Iterations: {state['iterations']}")
    print(f"Max Iterations: {state['max_iterations']}")
    print("\n")
    # If this is a retry ordered by the judge, include the previous output and critique in the message
    if state["iterations"] > 0 and state["inspector_critique"]:
        print("Worker is retrying")
        content += f"\n\nYour previous Output: {state['worker_output']}"
        content += f"\n\nInspector Critique: {state['inspector_critique']}"
        content += "\n\nPlease fix the issues identified by the inspector and redo your code"


    messages = [
        {"role": "system", "content": "You are a code writing agent. You are given a task and you must write code to solve it. Do not include any extra text, no markdown, nothing. Only the code. You will receive critique from the inspector agent and an order from the judge agent. Redo your code taking that feedback into account"},
        {"role": "user", "content": content}
    ]
    response = llm.invoke(messages)
    print(f"Worker output: {response.content}")
    return {"worker_output": response.content, "iterations": state["iterations"] + 1}


def inspector (state: TribunalState) -> dict:
    """Agent that critiques the worker's output and watches for edge cases, errors... etc"""
    messages =[
        {"role": "system", "content": 
        """You are a code inspector agent. You receive a task description and a solution from the worker. Your job is to find specific, concrete flaws - logical errors, edge cases not handled,untested functions,
        inefficiencies, security issues, style violations, linting errors, unhandled exceptions, race conditions, or cases where the solution given does not match the task.
        You are here not to praise the work. If the solution is correct, say so briefly.
        If it has problems, like (not limited to) the aforementioned, list them precisely.
        Remember: You are an adversarial inspector. Your default assumption is that the worker's
        output has a problem. Look hard for it. Only conclude the output is correct if
        you genuinely cannot find a flaw after careful examination.
        You must only critique the solution against the requirements stated in the task.
        Do not invent requirements that are not explicitly stated. If the task does not 
        specify behaviour for a case, do not penalise the worker for it.
        You are not mean to write code, just to critique it. Writing code is the worker's task, not yours.
        Again, You must NOT write or suggest any code. Do not provide improved versions, 
        code snippets, or examples under any circumstances. Your output must be 
        plain text critique only. If you find yourself about to write a code block, 
        stop and describe the issue in words instead. """},
        {"role": "user", "content": f"Task: {state['task']}\nWorker Output: {state['worker_output']}"}
    ]
    response = llm.invoke(messages)
    print(f"Inspector critique: {response.content}")
    return {"inspector_critique": response.content}


def judge(state: TribunalState) -> dict:
    """Agent that decides whether to accept, retry, or escalate the worker's output"""
    messages = [
        {"role": "system", "content": 
        """
        You are a judge agent. 
        You receive a task description, a solution from the worker, and a critique from the inspector.
        Your job is to decide whether to accept, retry, or escalate the solution to the human user.
        For this, you must reply with exactly one word: "accept", "retry", or "escalate". No punctuation, no explanation, no extra words. Just the single word.
        The critique is not absolute truth. It is just a suggestion. You are the final arbiter.
        - Reply with exactly 'accept' if the output correctly solves the task
        - Reply with exactly 'retry' if the output has fixable issues
        - Reply with exactly 'escalate' if the problem cannot be solved or the max attempts are reached
        """
        },
        {"role": "user", "content": f"Task: {state['task']}\nWorker Output: {state['worker_output']}\nInspector Critique: {state['inspector_critique']}"}
    ]
    response = llm.invoke(messages)
    verdict = response.content.strip().lower()
    print(f"Judge verdict: {verdict}")
    return {"judge_verdict": verdict}


# Conditional edge

def route_verdict(state: TribunalState) -> str:
    """Decide whether to accept, retry, or escalate the worker's output"""
    if state['iterations'] >= state['max_iterations']:
        return "escalate"
    return state['judge_verdict']

# Escalate node (This will do for now)

def escalate(state: TribunalState) -> str:
    print("The judge has decided that the human needs to intervene")
    print(f"Task: {state['task']}")
    print(f"Worker Output: {state['worker_output']}")
    print(f"Inspector Critique: {state['inspector_critique']}")
    return {}


# Build the graph

graph = StateGraph(TribunalState)
graph.add_node("worker", worker)
graph.add_node("inspector", inspector)
graph.add_node("judge", judge)
graph.add_node("escalate", escalate)

# Connect the nodes
# The graph starts with the worker creating a solution to the given task

graph.add_edge(START, "worker")

# Then the worker sends its output to the inspector for critique

graph.add_edge("worker", "inspector")

# finally, we send both output and critique to the judge

graph.add_edge("inspector", "judge")

# We send the judge's verdict to the conditional edge that decides the next step based on its verdict
# We map the verdicts to the corresponding nodes

graph.add_conditional_edges("judge", route_verdict, {"accept": END, "retry": "worker", "escalate": "escalate"})

graph.add_edge("escalate", END)

# Compile the graph
app = graph.compile()

# Now we test

app.invoke({"task": """
Write a Python function that takes a list of integers and returns the two numbers 
that sum closest to zero. If there are multiple pairs with the same sum, return 
the pair with the smallest absolute values. The function must handle edge cases: 
empty lists, lists with one element, and lists with all positive or all negative numbers.
""", "max_iterations": 3, "iterations": 0})