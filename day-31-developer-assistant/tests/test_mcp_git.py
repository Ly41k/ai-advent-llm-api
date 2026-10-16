"""Actual MCP subprocess and Git repositories; no substitute protocol/model."""
import dataclasses
import os
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch

from bublik_developer.contracts import Role, TaskEnvelope
from bublik_developer.errors import DeveloperError, ErrorCode
from bublik_developer.git_tools import GitTools
from bublik_developer.mcp_client import ScopedGitClient, connect_git
from bublik_developer.workspace import ProjectWorkspace


class MCPGitTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name) / "проект с пробелами"
        self.root.mkdir()
        self.git("init", "-q", "-b", "main")
        self.git("config", "user.name", "Fixture")
        self.git("config", "user.email", "fixture@example.invalid")
        (self.root / "README.md").write_text("# Fixture\nOriginal\n")
        self.git("add", "README.md")
        self.git("commit", "-qm", "fixture baseline")
        self.workspace = ProjectWorkspace.open(self.root, "fixture-project")

    def git(self, *arguments):
        return subprocess.run(["git", "-C", str(self.root), *arguments], check=True, capture_output=True).stdout

    async def test_real_discovery_branch_change_and_detached_head(self):
        async with connect_git(self.workspace) as registry:
            self.assertEqual(len(registry.catalog), 4)
            self.assertEqual((await registry.call(Role.GIT, "git__git_current_branch", {}))["data"]["branch"], "main")
            self.git("switch", "-qc", "feature/тест")
            self.assertEqual((await registry.call(Role.GIT, "git__git_current_branch", {}))["data"]["branch"], "feature/тест")
            self.git("checkout", "--detach", "-q")
            data = (await registry.call(Role.GIT, "git__git_current_branch", {}))["data"]
            self.assertTrue(data["detached_head"])
            self.assertIsNone(data["branch"])
            self.assertIsNotNone(data["head_oid"])

    async def test_unborn_repository_branch(self):
        empty = Path(self.temp.name) / "empty"
        empty.mkdir()
        subprocess.run(["git", "init", "-q", "-b", "new", str(empty)], check=True)
        async with connect_git(ProjectWorkspace.open(empty)) as registry:
            data = (await registry.call(Role.GIT, "git__git_current_branch", {}))["data"]
            self.assertEqual(data["branch"], "new")
            self.assertTrue(data["unborn"])
            self.assertIsNone(data["head_oid"])

    async def test_staged_and_unstaged_are_separate(self):
        (self.root / "README.md").write_text("# Fixture\nStaged\n")
        self.git("add", "README.md")
        (self.root / "README.md").write_text("# Fixture\nStaged\nWorktree\n")
        async with connect_git(self.workspace) as registry:
            for scope, expected, excluded in (("staged", "Staged", "Worktree"), ("unstaged", "Worktree", "Original")):
                data = (await registry.call(Role.GIT, "git__git_diff", {
                    "scope": scope, "paths": ["README.md"], "include_content": True}))["data"]
                self.assertIn(expected, data["patch"])
                self.assertNotIn(excluded, data["patch"])
                self.assertEqual(data["scope"], scope)

    async def test_default_diff_metadata_and_untracked_policy(self):
        (self.root / "README.md").write_text("changed\n")
        (self.root / "new.py").write_text("unique_untracked_content")
        async with connect_git(self.workspace) as registry:
            data = (await registry.call(Role.GIT, "git__git_diff", {}))["data"]
            self.assertIsNone(data["patch"])
            self.assertFalse(data["content_included"])
            self.assertEqual([item["path"] for item in data["files"]], ["README.md"])
            self.assertFalse(data["untracked_content_included"])
            files = (await registry.call(Role.GIT, "git__project_list_files", {}))["data"]["files"]
            self.assertIn("new.py", files)

    async def test_rename_unicode_newline_and_spaces(self):
        name = "документ с пробелом\nимя.md"
        self.git("mv", "README.md", name)
        async with connect_git(self.workspace) as registry:
            entries = (await registry.call(Role.GIT, "git__git_status", {}))["data"]["entries"]
            self.assertEqual(entries[0]["path"], name)
            self.assertEqual(entries[0]["original_path"], "README.md")
            self.assertEqual(entries[0]["index_status"], "R")

    async def test_tracked_secret_and_symlink_names_are_withheld(self):
        (self.root / ".env").write_text("private content")
        self.git("add", "-f", ".env")
        outside = Path(self.temp.name) / "private.md"
        outside.write_text("outside")
        (self.root / "link.md").symlink_to(outside)
        async with connect_git(self.workspace) as registry:
            for name in ("git__git_status", "git__project_list_files"):
                data = (await registry.call(Role.GIT, name, {}))["data"]
                self.assertGreaterEqual(data["withheld_count"], 2)
                self.assertNotIn(".env", str(data))
                self.assertNotIn("link.md", str(data))
            with self.assertRaises(DeveloperError):
                await registry.call(Role.GIT, "git__git_diff", {"paths": [".env"], "include_content": True})

    async def test_secret_like_source_patch_is_blocked(self):
        (self.root / "auth.py").write_text('api_key = "a_real_looking_secret_123456"\n')
        self.git("add", "auth.py")
        async with connect_git(self.workspace) as registry:
            with self.assertRaises(DeveloperError) as caught:
                await registry.call(Role.GIT, "git__git_diff", {"scope": "staged", "paths": ["auth.py"], "include_content": True})
            self.assertEqual(caught.exception.code, ErrorCode.PERMISSION_DENIED)
            self.assertEqual(caught.exception.detail, "secret")

    async def test_external_diff_and_textconv_are_not_executed(self):
        marker = Path(self.temp.name) / "helper-executed"
        helper = Path(self.temp.name) / "helper"
        helper.write_text("#!/bin/sh\ntouch '" + str(marker) + "'\n")
        helper.chmod(0o700)
        (self.root / ".gitattributes").write_text("*.md diff=unsafe filter=unsafe\n")
        self.git("config", "diff.unsafe.command", str(helper))
        self.git("config", "diff.unsafe.textconv", str(helper))
        self.git("config", "filter.unsafe.clean", str(helper))
        self.git("config", "filter.unsafe.process", str(helper))
        self.git("config", "filter.unsafe.required", "true")
        self.git("config", "core.fsmonitor", str(helper))
        self.git("config", "color.ui", "always")
        (self.root / "README.md").write_text("changed\n")
        with patch.dict(os.environ, {"GIT_EXTERNAL_DIFF": str(helper), "GIT_DIR": "/missing"}):
            async with connect_git(self.workspace) as registry:
                data = (await registry.call(Role.GIT, "git__git_diff", {"paths": ["README.md"], "include_content": True}))["data"]
                self.assertIn("changed", data["patch"])
                self.assertNotIn("\x1b", data["patch"])
        self.assertFalse(marker.exists())

    async def test_mcp_server_is_reaped_after_context_exit(self):
        import mcp.client.stdio as stdio
        factory = stdio._create_platform_compatible_process
        processes = []
        async def capture(*args, **kwargs):
            process = await factory(*args, **kwargs)
            processes.append(process)
            return process
        # Instrument the real subprocess factory; do not replace the transport.
        with patch.object(stdio, "_create_platform_compatible_process", side_effect=capture):
            async with connect_git(self.workspace) as registry:
                await registry.call(Role.GIT, "git__git_current_branch", {})
                self.assertEqual(len(processes), 1)
                self.assertIsNone(processes[0].returncode)
            self.assertIsNotNone(processes[0].returncode)

    async def test_permissions_and_budget_reject_without_tool_dispatch(self):
        async with connect_git(self.workspace) as registry:
            with self.assertRaises(DeveloperError):
                await registry.call(Role.DOCUMENTATION, "git__git_status", {})
            with self.assertRaises(DeveloperError):
                await registry.call(Role.GIT, "git__git_diff", {"paths": ["../README.md"]})
            self.assertEqual(registry.events, [])
            task = dataclasses.replace(TaskEnvelope.create(Role.GIT, self.workspace.project_id, "branch", {}), max_tool_calls=1)
            client = ScopedGitClient(registry, task)
            await client.call("git__git_current_branch", {})
            with self.assertRaises(DeveloperError):
                await client.call("git__git_current_branch", {})
            self.assertEqual(len(registry.events), 1)

    async def test_deleted_file_and_empty_diff(self):
        (self.root / "README.md").unlink()
        async with connect_git(self.workspace) as registry:
            data = (await registry.call(Role.GIT, "git__git_diff", {"paths": ["README.md"], "include_content": True}))["data"]
            self.assertIn("deleted file", data["patch"])
            self.assertEqual(data["files"][0]["added"], 0)
            empty = (await registry.call(Role.GIT, "git__git_diff", {"scope": "staged"}))["data"]
            self.assertEqual(empty["files"], [])

    async def test_staged_symlink_mode_cannot_bypass_current_file_check(self):
        (self.root / "link.md").symlink_to("README.md")
        self.git("add", "link.md")
        (self.root / "link.md").unlink()
        (self.root / "link.md").write_text("now a regular file")
        async with connect_git(self.workspace) as registry:
            with self.assertRaises(DeveloperError):
                await registry.call(Role.GIT, "git__git_diff", {"scope": "staged", "paths": ["link.md"], "include_content": True})

    def test_unstable_observation_cannot_be_published(self):
        tools = GitTools(self.workspace)
        with patch.object(tools, "_witness", side_effect=["before", "after"]):
            result = tools.invoke("git_status", {})
        self.assertFalse(result["ok"])
        self.assertEqual(result["error"]["code"], "git_state_changed")


if __name__ == "__main__":
    unittest.main()
