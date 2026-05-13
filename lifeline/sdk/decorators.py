import asyncio
import functools
import inspect
import time
from contextvars import ContextVar
from typing import Any, Callable

from lifeline.core.events import AgentEvent, ToolExecutionEvent
from lifeline.sdk.client import LifelineClient

# Context variable to hold the active Lifeline client and execution context
current_client: ContextVar[LifelineClient] = ContextVar("current_client")
current_agent_id: ContextVar[str] = ContextVar("current_agent_id", default="unknown_agent")
current_workflow_id: ContextVar[str] = ContextVar("current_workflow_id", default="unknown_workflow")


def set_lifeline_context(client: LifelineClient, workflow_id: str, agent_id: str):
    """Sets the active context for decorators to use."""
    current_client.set(client)
    current_workflow_id.set(workflow_id)
    current_agent_id.set(agent_id)


def trace_agent_step(action_name: str):
    """
    Decorator to trace an agent's cognitive step (e.g., thinking, generating).
    Emits an AgentEvent.
    """
    def decorator(func: Callable):
        @functools.wraps(func)
        async def async_wrapper(*args, **kwargs):
            client = current_client.get(None)
            start_time = time.time()
            
            # Execute the actual function
            try:
                result = await func(*args, **kwargs)
                error = None
            except Exception as e:
                result = None
                error = str(e)
                raise
            finally:
                duration = time.time() - start_time
                if client:
                    event = AgentEvent(
                        agent_id=current_agent_id.get(),
                        workflow_id=current_workflow_id.get(),
                        action=action_name,
                        completion=str(result) if result else None,
                        execution_metadata={"duration_sec": duration, "error": error}
                    )
                    await client.publish(event)
            return result

        @functools.wraps(func)
        def sync_wrapper(*args, **kwargs):
            client = current_client.get(None)
            start_time = time.time()
            
            try:
                result = func(*args, **kwargs)
                error = None
            except Exception as e:
                result = None
                error = str(e)
                raise
            finally:
                duration = time.time() - start_time
                if client:
                    event = AgentEvent(
                        agent_id=current_agent_id.get(),
                        workflow_id=current_workflow_id.get(),
                        action=action_name,
                        completion=str(result) if result else None,
                        execution_metadata={"duration_sec": duration, "error": error}
                    )
                    # Note: publishing an async event from a sync function requires an event loop
                    # If this is called from a sync thread, asyncio.run might be needed or a queue.
                    # For simplicity in this async-first framework, we assume async execution context.
                    try:
                        loop = asyncio.get_running_loop()
                        loop.create_task(client.publish(event))
                    except RuntimeError:
                        asyncio.run(client.publish(event))
            return result

        if inspect.iscoroutinefunction(func):
            return async_wrapper
        return sync_wrapper
    return decorator


def trace_tool(tool_name: str):
    """
    Decorator to trace tool execution.
    Emits a ToolExecutionEvent.
    """
    def decorator(func: Callable):
        @functools.wraps(func)
        async def async_wrapper(*args, **kwargs):
            client = current_client.get(None)
            
            # Capture arguments securely (avoiding massive payloads if needed)
            # A real implementation might filter sensitive args
            bound_args = inspect.signature(func).bind(*args, **kwargs)
            bound_args.apply_defaults()
            tool_args = dict(bound_args.arguments)
            
            try:
                result = await func(*args, **kwargs)
                error = None
            except Exception as e:
                result = None
                error = str(e)
                raise
            finally:
                if client:
                    event = ToolExecutionEvent(
                        agent_id=current_agent_id.get(),
                        workflow_id=current_workflow_id.get(),
                        tool_name=tool_name,
                        tool_args=tool_args,
                        tool_result=result,
                        error=error
                    )
                    await client.publish(event)
            return result

        if inspect.iscoroutinefunction(func):
            return async_wrapper
        # Fallback to sync not implemented for brevity, similar to trace_agent_step
        return func
    return decorator
