"""Only the Git role can execute the four reviewed read-only MCP tools."""
from .contracts import Role
from .errors import DeveloperError, ErrorCode
from .workspace import relative_path

TOOLS = frozenset({"git_current_branch", "git_status", "git_diff", "project_list_files"})


def authorize(role, name, arguments):
    if not isinstance(role, Role) or role != Role.GIT or name not in TOOLS:
        raise DeveloperError(ErrorCode.PERMISSION_DENIED, "role")
    if not isinstance(arguments, dict):
        raise DeveloperError(ErrorCode.INVALID_INPUT)
    if name != "git_diff":
        if arguments:
            raise DeveloperError(ErrorCode.INVALID_INPUT)
        return
    if set(arguments) - {"scope", "paths", "include_content"}:
        raise DeveloperError(ErrorCode.INVALID_INPUT)
    if arguments.get("scope", "unstaged") not in {"staged", "unstaged"}:
        raise DeveloperError(ErrorCode.INVALID_INPUT, "scope")
    paths = arguments.get("paths", [])
    if not isinstance(paths, list) or len(paths) > 4:
        raise DeveloperError(ErrorCode.INVALID_INPUT)
    for path in paths:
        relative_path(path)
    if len(set(paths)) != len(paths):
        raise DeveloperError(ErrorCode.INVALID_INPUT)
    content = arguments.get("include_content", False)
    if type(content) is not bool or (content and not paths):
        raise DeveloperError(ErrorCode.INVALID_INPUT)
