# Per-session container sandbox. Approved tool calls execute inside an isolated
# gVisor container instead of on the host. The session workspace directory is the
# only surface shared between host and agent: the user drops inputs there and
# collects outputs from it; nothing else crosses the boundary. No network.

import os
from contextlib import contextmanager
from contextvars import ContextVar
from pathlib import Path

import docker
from docker.errors import APIError, DockerException, ImageNotFound

from .logger import logger

# Enforced inside the container via coreutils `timeout`, since the Docker SDK
# offers no per-exec timeout
_EXEC_TIMEOUT = 30

# Name prefix for session containers, so a startup sweep can find and remove any
# left behind by a run that exited before it could stop its own sandbox.
_NAME_PREFIX = "sentinel-sandbox-"


class SandboxNotActive(RuntimeError):
    pass


def cleanup_stale_sandboxes() -> None:
    """Remove session containers left over from a previous run (e.g. one killed
    before it could stop its sandbox). Safe to call at startup; no-op if Docker
    is unreachable or nothing is stale."""
    try:
        client = docker.from_env()
        stale = client.containers.list(all=True, filters={"name": _NAME_PREFIX})
    except DockerException as exc:
        logger.warning("[Sandbox] Could not sweep stale sandboxes: %s", exc)
        return
    for container in stale:
        try:
            container.remove(force=True)
            logger.info("[Sandbox] Swept stale container %s", container.name)
        except APIError as exc:
            logger.warning("[Sandbox] Failed to remove %s: %s", container.name, exc)


# ContextVar instead of a module global so concurrent sessions (each entering
# its own sandbox in its own thread or async task) don't clobber each other.
_active: ContextVar["Sandbox | None"] = ContextVar("active_sandbox", default=None)


def get_active() -> "Sandbox":
    sandbox = _active.get()
    if sandbox is None:
        raise SandboxNotActive("No sandbox session is active")
    return sandbox


class Sandbox:
    def __init__(
        self,
        session_id: str,
        workspace_root: Path,
        image: str = "python:3.13-slim",
        runtime: str = "runsc",
    ):
        self._session_id = session_id
        self._workspace = workspace_root / session_id
        self._image = image
        self._runtime = runtime
        self._client = docker.from_env()
        self._container = None

    @property
    def workspace(self) -> Path:
        return self._workspace

    def start(self) -> None:
        self._workspace.mkdir(parents=True, exist_ok=True)

        try:
            self._client.images.get(self._image)
        except ImageNotFound:
            logger.info(f"[Sandbox] Pulling image {self._image} (first run only)...")
            self._client.images.pull(self._image)

        try:
            self._container = self._client.containers.run(
                self._image,
                command=["sleep", "infinity"],
                name=f"{_NAME_PREFIX}{self._session_id[:8]}",
                runtime=self._runtime,
                network_mode="none",
                mem_limit="512m",
                pids_limit=128,
                nano_cpus=1_000_000_000,  # 1 CPU
                # Match the host user so workspace files stay readable on the
                # host, and so the agent isn't root inside the container
                user=f"{os.getuid()}:{os.getgid()}",
                cap_drop=["ALL"],
                security_opt=["no-new-privileges"],
                read_only=True,
                tmpfs={"/tmp": "size=64m"},
                volumes={str(self._workspace.resolve()): {"bind": "/workspace", "mode": "rw"}},
                working_dir="/workspace",
                detach=True,
            )
        except APIError as e:
            if "runtime" in str(e).lower():
                raise RuntimeError(
                    f"Container runtime '{self._runtime}' is not available in Docker. "
                    "Install gVisor with: sudo bash scripts/setup-gvisor.sh "
                    "(or set SANDBOX_RUNTIME=runc to run without kernel-level isolation)"
                ) from e
            raise

        logger.info(
            f"[Sandbox] Started {self._container.name} "
            f"(runtime={self._runtime}, workspace={self._workspace})"
        )

    def run_shell(self, command: str) -> str:
        return self._exec(["timeout", str(_EXEC_TIMEOUT), "/bin/sh", "-c", command])

    def run_python(self, code: str) -> str:
        return self._exec(["timeout", str(_EXEC_TIMEOUT), "python3", "-c", code])

    def _exec(self, cmd: list[str]) -> str:
        exit_code, output = self._container.exec_run(cmd, workdir="/workspace")
        text = output.decode(errors="replace").strip()
        if exit_code == 124:
            return f"Error: command timed out after {_EXEC_TIMEOUT} seconds."
        if exit_code != 0:
            return f"[exit code {exit_code}]\n{text}" if text else f"[exit code {exit_code}] no output"
        return text or "Command ran with no output."

    def stop(self) -> None:
        if self._container is not None:
            try:
                self._container.remove(force=True)
                logger.info(f"[Sandbox] Removed {self._container.name}")
            except APIError as e:
                logger.warning(f"[Sandbox] Failed to remove container: {e}")
            finally:
                self._container = None
        try:
            # rmdir only removes empty directories; session artifacts are kept
            self._workspace.rmdir()
        except OSError:
            pass

    @contextmanager
    def activate(self):
        """Bind this already-started sandbox as the active one for the current
        context, without touching the container lifecycle. For server/UI use,
        where ContextVars don't cross threads: call start() once per session,
        activate() around each request, stop() on session end."""
        token = _active.set(self)
        try:
            yield self
        finally:
            _active.reset(token)

    def __enter__(self) -> "Sandbox":
        self.start()
        self._token = _active.set(self)
        return self

    def __exit__(self, *exc) -> bool:
        _active.reset(self._token)
        self.stop()
        return False
