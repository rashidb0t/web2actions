"""
Mechanical risk tagging for Web2Actions (Validate, module 5).

Assigns a risk level to each tool based purely on its HTTP method and name,
without any judgment call. This mirrors how the platform classifies tools
when they are generated from traffic.

Mapping:
- A destructive keyword in the tool name (delete, remove, transfer, send)
  makes it destructive regardless of method.
- Otherwise DELETE is destructive.
- POST/PUT is a write.
- GET is a read.
"""

from typing import Any, Dict

from enum import Enum

DESTRUCTIVE_NAME_KEYWORDS = ("delete", "remove", "transfer", "send")


class Risk(Enum):
    """The three risk levels a tool can carry."""
    READ = "read"
    WRITE = "write"
    DESTRUCTIVE = "destructive"


def risk_from_name_and_method(tool_name: str, method: str) -> str:
    """
    Assign a risk level from a tool's name and HTTP method.
    Returns one of: 'read', 'write', 'destructive'.
    """
    normalized_name = tool_name.lower()
    upper_method = method.upper()

    if any(keyword in normalized_name for keyword in DESTRUCTIVE_NAME_KEYWORDS):
        return Risk.DESTRUCTIVE.value
    if upper_method in ("POST", "PUT", "PATCH"):
        return Risk.WRITE.value
    if upper_method == "DELETE":
        return Risk.DESTRUCTIVE.value
    return Risk.READ.value


def tag_tool_risk(tool: Dict[str, Any]) -> Dict[str, Any]:
    """
    Add the 'risk' field to a single tool from its name and HTTP method.
    Returns the same tool dict with the risk set.
    """
    name = tool.get("name", "")
    method = (tool.get("call") or {}).get("method", "GET")
    tool["risk"] = risk_from_name_and_method(name, method)
    return tool


def tag_all_tool_risks(connector: Dict[str, Any]) -> Dict[str, Any]:
    """Set the risk field on every tool in a connector definition."""
    for tool in connector.get("tools", []):
        tag_tool_risk(tool)
    return connector