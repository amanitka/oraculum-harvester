"""Launch analyst processing and operations UI in one command.

Start the analyst service (including APScheduler refresh jobs) and the
Streamlit operations UI as child processes, then keep both supervised.
Stop both children when one exits or when interrupted.

Usage::

    uv run python scripts/run_ops_stack.py
"""

from __future__ import annotations

from collections.abc import Mapping
import logging
from pathlib import Path
import subprocess
import sys
import time

logger = logging.getLogger(__name__)

_ANALYST_NAME = "analyst"
_UI_NAME = "ui"
_POLL_INTERVAL_SECONDS = 0.5
_TERMINATE_TIMEOUT_SECONDS = 10.0
_KILL_TIMEOUT_SECONDS = 5.0
_REPO_ROOT = Path(__file__).resolve().parent.parent
_UI_SCRIPT = _REPO_ROOT / "ui" / "ui.py"


type _ProcessMap = dict[str, subprocess.Popen[bytes]]


def _configure_logging() -> None:
    """Configure process-launcher logging."""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
        stream=sys.stdout,
    )


def _command_for(name: str) -> list[str]:
    """Return command arguments for one managed child process."""
    if name == _ANALYST_NAME:
        return [sys.executable, "-m", "analyst"]
    if name == _UI_NAME:
        return [sys.executable, "-m", "streamlit", "run", str(_UI_SCRIPT)]
    raise ValueError(f"Unsupported process name: {name}")


def _start_process(name: str) -> subprocess.Popen[bytes]:
    """Start one managed child process."""
    command = _command_for(name)
    logger.info("Starting %s: %s", name, " ".join(command))
    return subprocess.Popen(command, cwd=_REPO_ROOT)


def _wait_for_process_exit(
    processes: Mapping[str, subprocess.Popen[bytes]],
) -> tuple[str, int]:
    """Wait for one managed process to exit and return name and code."""
    while True:
        for name, process in processes.items():
            return_code = process.poll()
            if return_code is not None:
                return name, return_code
        time.sleep(_POLL_INTERVAL_SECONDS)


def _stop_process(name: str, process: subprocess.Popen[bytes]) -> None:
    """Stop one managed process gracefully, then force-stop if needed."""
    if process.poll() is not None:
        return

    logger.info("Stopping %s (pid=%d)", name, process.pid)
    process.terminate()
    try:
        process.wait(timeout=_TERMINATE_TIMEOUT_SECONDS)
    except subprocess.TimeoutExpired:
        logger.warning("%s did not stop in time; killing", name)
        process.kill()
        try:
            process.wait(timeout=_KILL_TIMEOUT_SECONDS)
        except subprocess.TimeoutExpired:
            logger.error("%s did not stop after kill timeout", name)


def _stop_processes(processes: Mapping[str, subprocess.Popen[bytes]]) -> None:
    """Stop all managed processes in reverse startup order."""
    for name in reversed(tuple(processes.keys())):
        _stop_process(name, processes[name])


def main() -> int:
    """Launch and supervise analyst and Streamlit child processes."""
    _configure_logging()
    processes: _ProcessMap = {}

    try:
        processes[_ANALYST_NAME] = _start_process(_ANALYST_NAME)
        processes[_UI_NAME] = _start_process(_UI_NAME)
        exited_name, exited_code = _wait_for_process_exit(processes)
        logger.warning("%s exited with code %d", exited_name, exited_code)
        return exited_code
    except KeyboardInterrupt:
        logger.info("Received shutdown signal")
        return 0
    finally:
        _stop_processes(processes)


if __name__ == "__main__":
    raise SystemExit(main())
