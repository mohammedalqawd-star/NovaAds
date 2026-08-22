"""Start NovaBiz with a category-only Studio home."""

from __future__ import annotations

import asyncio

from aiogram.types import InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder

import run_upgraded as upgraded
from services.studio_catalog import STUDIO_CATEGORIES


def categories_only_kb() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for key, data in STUDIO_CATEGORIES.items():
        builder.button(text=data["title"], callback_data=f"studio:{key}")
    builder.adjust(2)
    return builder.as_markup()


# The user home now contains sections only. Account/balance/status/support buttons
# from the old home are no longer rendered on the main screen.
upgraded.app.main_kb = categories_only_kb


async def main() -> None:
    await upgraded.app.main()


if __name__ == "__main__":
    asyncio.run(main())
