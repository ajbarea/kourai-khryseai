"""Quick smoke test — verify LLM connectivity through LiteLLM."""

import asyncio
import sys

from dotenv import load_dotenv

from kourai_common.llm import chat

load_dotenv()


async def test() -> None:
    agent = sys.argv[1] if len(sys.argv) > 1 else "mneme"
    print(f"Testing LLM call as '{agent}'...")
    try:
        response = await chat(agent, [{"role": "user", "content": "Say hello in one sentence."}])
        print(f"OK: {response}")
    except Exception as e:
        print(f"FAIL: {e}")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(test())
