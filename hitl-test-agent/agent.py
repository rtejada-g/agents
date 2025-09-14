from google.adk.agents import Agent
from google.adk.tools import FunctionTool, ToolContext


def dangerous_operation(tool_context: ToolContext, **kwargs):
    """This is a dangerous operation that requires human approval."""
    if not tool_context.tool_confirmation:
        tool_context.request_confirmation(
            hint="Are you sure you want to proceed with this dangerous operation?"
        )
        return
    if tool_context.tool_confirmation.confirmed:
        return "Dangerous operation was approved by the user and completed successfully."
    else:
        return "Dangerous operation was rejected by the user."


dangerous_tool = FunctionTool(
    func=dangerous_operation,
)

root_agent = Agent(
    name="hitl_test_agent",
    model="gemini-2.5-flash",
    description="An agent for testing the Human-in-the-Loop feature.",
    instruction="You are a test agent. You have one tool that requires human approval. Use it when the user asks you to.",
    tools=[dangerous_tool],
)