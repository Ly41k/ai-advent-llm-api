"""Owned async worker group: bounded pipes, cancellation, kill and reap."""
import asyncio
import os
import signal

from .errors import DeveloperError, ErrorCode


async def finish_cleanup(cleanup):
    """Repeated cancellation cannot detach an owned process from its reaper."""
    task = asyncio.create_task(cleanup)
    cancelled = False
    while True:
        try:
            await asyncio.shield(task)
            break
        except asyncio.CancelledError:
            cancelled = True
            if task.done():
                # Inspect an exception rather than leaving an unobserved task.
                await task
                break
    if cancelled:
        raise asyncio.CancelledError


async def stop(process):
    # Descendants can keep pipes open after the direct worker has exited.
    # The whole session belongs to this invocation, including those children.
    try:
        os.killpg(process.pid, signal.SIGKILL)
    except ProcessLookupError:
        pass
    if process.stdin:
        process.stdin.close()
    async def discard(stream):
        while await stream.read(4096):
            pass
    # Resume paused readers after an overflow. wait() alone can leave a pipe
    # transport open or block when the killed process filled its output buffer.
    await asyncio.gather(discard(process.stdout), discard(process.stderr), process.wait())
    if process.stdin:
        try:
            await process.stdin.wait_closed()
        except (BrokenPipeError, ConnectionResetError):
            pass


async def read_pipe(stream, limit):
    value = bytearray()
    while True:
        block = await stream.read(4096)
        if not block:
            return bytes(value)
        value.extend(block)
        if len(value) > limit:
            raise DeveloperError(ErrorCode.OUTPUT_LIMIT)


async def run_owned(argv, payload, *, cwd, env):
    if not isinstance(payload, bytes) or len(payload) > 32768:
        raise DeveloperError(ErrorCode.CONTEXT_BUDGET)
    creation = asyncio.create_task(asyncio.create_subprocess_exec(
        *argv, cwd=cwd, env=env, stdin=asyncio.subprocess.PIPE,
        stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE,
        start_new_session=True))
    try:
        process = await asyncio.shield(creation)
    except asyncio.CancelledError:
        # A cancellation during spawn must not lose ownership of the child.
        async def reap_created():
            try:
                process = await creation
            except OSError:
                return
            await stop(process)
        await finish_cleanup(reap_created())
        raise
    except OSError:
        raise DeveloperError(ErrorCode.AGENT_FAILED) from None
    readers = []
    try:
        readers = [asyncio.create_task(read_pipe(process.stdout, 26000)),
                   asyncio.create_task(read_pipe(process.stderr, 4096))]
        process.stdin.write(payload)
        await process.stdin.drain()
        process.stdin.close()
        await process.stdin.wait_closed()
        output, _ = await asyncio.gather(*readers)
        if await process.wait() != 0:
            raise DeveloperError(ErrorCode.AGENT_FAILED)
        return output, process.pid
    except (BrokenPipeError, ConnectionResetError):
        raise DeveloperError(ErrorCode.AGENT_FAILED) from None
    finally:
        async def cleanup():
            for reader in readers:
                if not reader.done():
                    reader.cancel()
            if readers:
                await asyncio.gather(*readers, return_exceptions=True)
            await stop(process)
        await finish_cleanup(cleanup())
