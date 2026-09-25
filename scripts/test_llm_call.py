import sys
import threading
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from core.providers.factory import get_llm_provider

TIMEOUT_SECONDS = 30

result = {}
error = {}


def _do_call():
    try:
        provider = get_llm_provider()
        t0 = time.monotonic()
        response = provider.call(
            system_prompt="You are a helpful assistant.",
            user_prompt="Reply with exactly the word: pong",
        )
        result["text"] = response
        result["elapsed"] = time.monotonic() - t0
    except Exception as e:
        error["exception"] = e


def main():
    print(f"calling LLM provider, will wait up to {TIMEOUT_SECONDS}s...")
    thread = threading.Thread(target=_do_call, daemon=True)
    t_start = time.monotonic()
    thread.start()
    thread.join(timeout=TIMEOUT_SECONDS)

    if thread.is_alive():
        print(f"STILL RUNNING after {TIMEOUT_SECONDS}s - the call is hanging with no timeout, confirmed.")
        return

    total_elapsed = time.monotonic() - t_start
    if "exception" in error:
        print(f"call raised after {total_elapsed:.1f}s: {error['exception']!r}")
        return

    print(f"call succeeded in {result.get('elapsed', total_elapsed):.1f}s")
    print(f"response: {result.get('text')!r}")


if __name__ == "__main__":
    main()