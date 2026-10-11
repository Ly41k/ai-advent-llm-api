"""One async consumer, SQLite durable checkpoints, explicit process-epoch recovery."""
import asyncio
from dataclasses import asdict
from datetime import datetime
from time import perf_counter

from bublik_service.domain import Conflict, ModelProfile, ModelUnavailable, StorageUnavailable
from bublik_service.service import ChatService
from .ollama import InferenceError


async def durable_call(function, *args, **kwargs):
    """Do not release a worker lease while a cancelled SQLite thread is still writing."""
    task = asyncio.create_task(asyncio.to_thread(function, *args, **kwargs))
    try:
        return await asyncio.shield(task)
    except asyncio.CancelledError:
        await task
        raise


class Coordinator:
    def __init__(self, repository, adapter, *, queue_deadline=600, shutdown_grace=5):
        if queue_deadline <= 0 or shutdown_grace <= 0:
            raise ValueError("deadlines must be positive")
        self.repository, self.adapter = repository, adapter
        self.queue_deadline, self.shutdown_grace = queue_deadline, shutdown_grace
        self.wakeup, self.stopping = asyncio.Event(), asyncio.Event()
        self.worker = self.task = None
        self.last_error = None
        self.active, self.max_active = 0, 0
        self.service = ChatService(repository, adapter, self.wakeup.set)

    async def __aenter__(self):
        acquisition = asyncio.create_task(asyncio.to_thread(self.repository.worker_session))
        try:
            self.worker = await asyncio.shield(acquisition)
        except asyncio.CancelledError:
            acquired = await acquisition
            await durable_call(acquired.close)
            raise
        try:
            await durable_call(self.worker.require_queued_profile,
                               getattr(self.adapter, "profile", ModelProfile()))
        except BaseException:
            await durable_call(self.worker.close)
            raise
        self.task = asyncio.create_task(self._loop())
        return self

    async def __aexit__(self, *_):
        self.stopping.set()
        self.wakeup.set()
        try:
            if self.task is not None:
                try:
                    await asyncio.wait_for(asyncio.shield(self.task), self.shutdown_grace)
                except TimeoutError:
                    self.task.cancel()
                    try:
                        await self.task
                    except asyncio.CancelledError:
                        pass
        finally:
            if self.task is not None and not self.task.done():
                self.task.cancel()
                try:
                    await self.task
                except asyncio.CancelledError:
                    pass
            if self.worker is not None:
                await durable_call(self.worker.close)

    async def recover_after_restart(self):
        if self.active:
            raise Conflict("generation_still_running")
        if not (await asyncio.to_thread(self.repository.queue_status))["inference_recovery_required"]:
            return {"recovery": "not_required"}
        doctor = await self.adapter.doctor()
        context = await asyncio.to_thread(self.repository.recovery_context)
        if not context:
            raise Conflict("engine_restart_not_verifiable")
        if not context.get("dispatch_engine_epoch"):
            if not context.get("model_identity"):
                raise Conflict("engine_restart_not_verifiable")
            # Stage 3 always commits dispatch provenance before POST. Its absence
            # proves THIS service never submitted inference for the recovered job.
            await durable_call(self.worker.confirm_inference_idle)
            self.wakeup.set()
            return {"recovery": "verified_no_dispatch"}
        if context["dispatch_engine_epoch"] == doctor.engine_epoch:
            raise Conflict("ollama_restart_required")
        # A new verified listener epoch proves the old server/runner was replaced.
        # The operator must reserve Ollama exclusively; /api/ps never clears this gate.
        await durable_call(self.worker.confirm_inference_idle)
        self.last_error = None
        self.wakeup.set()
        return {"recovery": "verified_server_epoch_changed", "engine_epoch": doctor.engine_epoch}

    async def wait(self, owner, generation, *, timeout=1800):
        async with asyncio.timeout(timeout):
            while True:
                result = await asyncio.to_thread(self.repository.get_generation, owner, generation)
                if result["status"] not in {"queued", "running"}:
                    return result
                status = await asyncio.to_thread(self.repository.queue_status)
                if status["inference_recovery_required"] and result["status"] == "queued":
                    raise Conflict("inference_recovery_required")
                if self.last_error == "storage_unavailable":
                    raise StorageUnavailable()
                await asyncio.sleep(.1)

    async def _loop(self):
        while not self.stopping.is_set():
            self.wakeup.clear()
            try:
                await durable_call(self.worker.expire_queued, self.queue_deadline)
                status = await asyncio.to_thread(self.repository.queue_status)
                if status["inference_recovery_required"]:
                    self.last_error = "inference_recovery_required"
                elif status["queued"]:
                    job = await durable_call(self.worker.claim_next)
                    if job is not None:
                        await self._execute(job)
                        continue
            except StorageUnavailable:
                self.last_error = "storage_unavailable"
                # Fail stopped; do not generate or claim more while commits fail.
                return
            try:
                await asyncio.wait_for(self.wakeup.wait(), .5)
            except TimeoutError:
                pass

    async def _execute(self, job):
        dispatched, text, measured = False, "", {}
        self.active += 1
        self.max_active = max(self.max_active, self.active)
        last_checkpoint, last_length = perf_counter(), 0
        try:
            doctor = await self.adapter.doctor()
            if job["context"].get("model_identity") != asdict(doctor.identity) or job["profile"] != self.adapter.profile.to_dict():
                raise InferenceError(uncertain=False)
            await durable_call(self.worker.bind_engine_epoch, job["id"], doctor.engine_epoch)
            async def checkpoint(content):
                nonlocal text, last_checkpoint, last_length
                text = content
                now = perf_counter()
                if now - last_checkpoint >= .25 or len(content) - last_length >= 256:
                    await durable_call(self.worker.checkpoint, job["id"], content)
                    last_checkpoint, last_length = now, len(content)
            started = perf_counter()
            dispatched = True
            answer = await self.adapter.generate(job, checkpoint)
            text, measured = answer.content, dict(answer.metrics)
            measured["total_seconds"] = perf_counter() - started
            measured["queue_seconds"] = max(0, (datetime.fromisoformat(job["started_at"])
                                                 - datetime.fromisoformat(job["created_at"])).total_seconds())
            # Completed NDJSON means this inference ended. Recheck alias/digest/epoch.
            after = await self.adapter.doctor()
            if after.identity != doctor.identity or after.engine_epoch != doctor.engine_epoch:
                raise InferenceError(uncertain=False)
            await durable_call(self.worker.finish, job["id"], status=answer.status, content=text, metrics=measured)
            self.last_error = None
        except ModelUnavailable:
            await durable_call(self.worker.finish, job["id"], status="failed", content=text,
                               error_code="model_unavailable", uncertain=dispatched)
            self.last_error = "model_unavailable"
        except InferenceError as error:
            await durable_call(self.worker.finish, job["id"], status="failed", content=text,
                               error_code=error.code, uncertain=error.uncertain, metrics=measured)
            self.last_error = error.code
        except asyncio.CancelledError:
            await durable_call(self.worker.finish, job["id"], status="interrupted", content=text,
                               error_code="operator_shutdown", uncertain=dispatched)
            raise
        except StorageUnavailable:
            self.last_error = "storage_unavailable"
            # Leave running for the next worker to recover; no acknowledged success.
            raise
        except Exception:
            # No raw exception/body/prompt in diagnostics, and no silent retry.
            await durable_call(self.worker.finish, job["id"], status="failed", content=text,
                               error_code="invalid_model_response", uncertain=dispatched)
            self.last_error = "invalid_model_response"
        finally:
            self.active -= 1
