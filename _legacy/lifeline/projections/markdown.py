from typing import AsyncIterator
from lifeline.core.events import EventBase, AgentEvent, ToolExecutionEvent, SystemEvent, WorkflowEvent

class MarkdownProjection:
    """
    Projects a stream of events into a human-readable Markdown format.
    Useful for observability, debugging, and sharing reasoning paths.
    """

    @staticmethod
    def _format_event(event: EventBase) -> str:
        timestamp = event.timestamp.strftime("%Y-%m-%d %H:%M:%S")
        
        if isinstance(event, AgentEvent):
            md = f"### 🧠 Agent Action: {event.action} | {timestamp}\n"
            if event.completion:
                md += f"**Completion:**\n```text\n{event.completion}\n```\n"
            return md

        elif isinstance(event, ToolExecutionEvent):
            md = f"### 🛠️ Tool Executed: {event.tool_name} | {timestamp}\n"
            md += f"**Args:** `{event.tool_args}`\n"
            if event.error:
                md += f"**Error:** ❌ `{event.error}`\n"
            elif event.tool_result is not None:
                md += f"**Result:**\n```text\n{event.tool_result}\n```\n"
            return md

        elif isinstance(event, SystemEvent):
            return f"--- ⚙️ **System:** {event.action} | {timestamp} ---\n"

        elif isinstance(event, WorkflowEvent):
            return f"--- 🔄 **Workflow Status:** {event.status} | {timestamp} ---\n"

        else:
            return f"- 📄 **Generic Event** ({getattr(event, 'event_type', 'unknown')}): {event.event_id} | {timestamp}\n"

    @classmethod
    async def generate_from_stream(cls, stream: AsyncIterator[EventBase], title: str = "Execution Trace") -> str:
        """Consumes an async stream of events and returns a complete Markdown document."""
        doc = [f"# {title}\n\n"]
        async for event in stream:
            doc.append(cls._format_event(event))
            doc.append("\n")
        return "".join(doc)
