"""Wrapper to adapt legacy Hulku tools to AgentScope."""

import inspect
from agentscope.tool import Toolkit

def wrap_legacy_tool(legacy_tool_instance):
    """
    Wraps a legacy BaseTool instance into a Python function that AgentScope Toolkit can parse.
    AgentScope parses docstrings to generate JSON schemas, so we construct a dynamic function
    with a docstring matching the legacy tool's description and parameters.
    """
    name = legacy_tool_instance.name
    desc = legacy_tool_instance.description
    params = legacy_tool_instance.parameters.get("properties", {})
    required = legacy_tool_instance.parameters.get("required", [])

    def generic_tool_func(**kwargs) -> dict:
        result = legacy_tool_instance.execute(**kwargs)
        if result.success:
            return {"status": "success", "data": result.data or {}, "message": result.message}
        else:
            return {"status": "error", "message": result.message}

    generic_tool_func.__name__ = name

    docstring_lines = [desc, "Args:"]
    for p_name, p_info in params.items():
        p_type = p_info.get("type", "string")
        if p_type == "number": p_type = "float"
        elif p_type == "integer": p_type = "int"
        elif p_type == "string": p_type = "str"
        elif p_type == "boolean": p_type = "bool"
        elif p_type == "array": p_type = "list"
        elif p_type == "object": p_type = "dict"

        p_desc = p_info.get("description", "")
        docstring_lines.append(f"    {p_name} ({p_type}): {p_desc}")

    generic_tool_func.__doc__ = "\n".join(docstring_lines)

    sig_params = []
    for p_name, p_info in params.items():
        default = inspect.Parameter.empty if p_name in required else None
        p = inspect.Parameter(p_name, inspect.Parameter.POSITIONAL_OR_KEYWORD, default=default)
        sig_params.append(p)

    generic_tool_func.__signature__ = inspect.Signature(sig_params)

    return generic_tool_func

def create_toolkit(legacy_tools_list) -> Toolkit:
    tk = Toolkit()
    for tool_instance in legacy_tools_list:
        func = wrap_legacy_tool(tool_instance)
        tk.register_tool_function(func)
    return tk
