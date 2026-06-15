# JSON with two fields
# Example: 
# {tool_name: "", args: ""}

# This is the same format as what LangGraph already returns. This is just to serialize the governance decisions

from dataclasses import asdict, dataclass
import json

@dataclass
class ToolCall:
    name: str
    args: dict


    def to_json(self) -> str:
        return json.dumps(asdict(self))