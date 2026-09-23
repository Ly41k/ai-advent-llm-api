"""Long-running scheduler process; configure a service manager to restart it."""

import argparse
import json
import logging
import signal
import threading

from scheduler import Scheduler


def run(once=False, poll_seconds=15, scheduler=None):
    scheduler = scheduler or Scheduler()
    stop = threading.Event()
    if not once and threading.current_thread() is threading.main_thread():
        signal.signal(signal.SIGTERM, lambda *_: stop.set())
        signal.signal(signal.SIGINT, lambda *_: stop.set())
    while True:
        try:
            for result in scheduler.run_due():
                print(json.dumps(result, ensure_ascii=False), flush=True)
        except Exception:
            logging.exception("Scheduler loop failed; retrying")
        if once or stop.wait(poll_seconds):
            return


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--once", action="store_true", help="Process due jobs and exit")
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO)
    run(once=args.once)
