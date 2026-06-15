from langgraph.graph import MessagesState


class AgentState(MessagesState):
    """Day-to-day agent state. The conversation lives in `messages`; tribunal
    delegations run in their own isolated state and never appear here, so this
    channel stays a clean user-facing transcript."""
