"""Start NovaBiz with the redesigned Studio routes loaded."""

import asyncio

import bot
import studio_bot  # noqa: F401  # registers Studio handlers safely


if __name__ == "__main__":
    asyncio.run(bot.main())
