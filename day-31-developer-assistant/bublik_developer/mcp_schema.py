"""Closed output contracts for the actual Git tools, checked on both boundaries."""
from typing import Literal
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, model_validator

from .errors import ErrorCode


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)


class ErrorData(StrictModel):
    code: str = Field(pattern="^(" + "|".join(code.value for code in ErrorCode) + ")$")
    detail: Literal["path", "role", "scope", "secret", "schema", "repository", "model_stage_not_implemented"] | None


class BranchData(StrictModel):
    kind: Literal["branch"]
    branch: str | None = Field(max_length=4096)
    head_oid: str | None = Field(pattern=r"^(?:[a-f0-9]{40}|[a-f0-9]{64})$")
    detached_head: bool
    unborn: bool


class Entry(StrictModel):
    path: str = Field(min_length=1, max_length=4096)
    original_path: str | None = Field(max_length=4096)
    index_status: str = Field(pattern=r"^[ MADRCU?!T]$")
    worktree_status: str = Field(pattern=r"^[ MADRCU?!T]$")


class SnapshotData(StrictModel):
    withheld_count: int = Field(ge=0)
    snapshot_digest: str = Field(pattern=r"^[a-f0-9]{64}$")


class StatusData(SnapshotData):
    kind: Literal["status"]
    entries: list[Entry] = Field(max_length=2000)
    consistency: Literal["head_index_status"]


class FilesData(SnapshotData):
    kind: Literal["files"]
    files: list[str] = Field(max_length=2000)
    consistency: Literal["head_index_status"]


class DiffFile(StrictModel):
    path: str = Field(min_length=1, max_length=4096)
    added: int | None = Field(ge=0)
    deleted: int | None = Field(ge=0)
    binary: bool


class DiffData(SnapshotData):
    kind: Literal["diff"]
    scope: Literal["staged", "unstaged"]
    files: list[DiffFile] = Field(max_length=2000)
    patch: str | None = Field(max_length=65536)
    content_included: bool
    untracked_content_included: Literal[False]
    consistency: Literal["head_index_status_selected_files", "head_index_status_numstat"]


class GitReply(StrictModel):
    ok: bool
    tool: Literal["git_current_branch", "git_status", "git_diff", "project_list_files"]
    project_id: str = Field(pattern=r"^[A-Za-z0-9][A-Za-z0-9._-]{0,79}$")
    observed_at: str = Field(max_length=50)
    data: BranchData | StatusData | FilesData | DiffData | None = Field(discriminator="kind")
    error: ErrorData | None

    @model_validator(mode="after")
    def consistency_check(self):
        try:
            observed = datetime.fromisoformat(self.observed_at)
        except ValueError:
            raise ValueError("invalid_observed_at") from None
        if observed.tzinfo is None:
            raise ValueError("missing_observed_timezone")
        if self.ok != (self.data is not None and self.error is None):
            raise ValueError("inconsistent_reply")
        if not self.ok and (self.data is not None or self.error is None):
            raise ValueError("inconsistent_reply")
        kinds = {"git_current_branch": "branch", "git_status": "status", "project_list_files": "files", "git_diff": "diff"}
        if self.ok and self.data.kind != kinds[self.tool]:
            raise ValueError("wrong_result_kind")
        if self.ok and isinstance(self.data, BranchData):
            if self.data.unborn != (self.data.head_oid is None) or self.data.detached_head != (self.data.branch is None):
                raise ValueError("inconsistent_branch_state")
        if self.ok and isinstance(self.data, DiffData):
            if self.data.content_included != (self.data.patch is not None):
                raise ValueError("inconsistent_patch_state")
        return self
