import asyncio
import sys

import uvicorn


def run() -> None:
    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    uvicorn.run("fruit_agent.app:app", host="127.0.0.1", port=8000)


if __name__ == "__main__":
    run()
