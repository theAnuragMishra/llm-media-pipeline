"""Background consumer workers for async task queues."""

from app.workers.consumer import main as run_worker

__all__ = ["run_worker"]
