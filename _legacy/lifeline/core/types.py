from typing import Dict, Any, TypeVar

# Type aliases for IDs to make intention clear
EventID = str
WorkflowID = str
AgentID = str
TaskID = str
ExecutionID = str

# State is generally represented as a dictionary, but we can make it more specific later if needed
State = Dict[str, Any]

# Context references like document IDs, memory chunks
ContextReferences = Dict[str, Any]

TEvent = TypeVar('TEvent')
