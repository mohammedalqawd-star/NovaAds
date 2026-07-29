import asyncio
import logging
from aiogram import Bot, Dispatcher
from aiogram.enums import ParseMode
from aiogram.client.default import DefaultBotProperties
from aiogram.fsm.storage.memory import MemoryStorage

from config import Config
from database.connection import Database

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('bot.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

bot = Bot(
    token=Config.BOT_TOKEN,
    default=DefaultBotProperties(parse_mode=ParseMode.HTML)
)
storage = MemoryStorage()
dp = Dispatcher(storage=storage)
db = Database(Config.DATABASE_PATH)

async def main():
    logger.info("🚀 جاري تشغيل Nova Ads Bot...")
    await db.initialize()
    logger.info("✅ تم تهيئة قاعدة البيانات")
    
    # تحميل جميع المعالجات
    from handlers import start, admin, channels, campaigns, subscriptions, support, profile, payments
    
    dp.include_router(start.router)
    dp.include_router(admin.router)
    dp.include_router(channels.router)
    dp.include_router(campaigns.router)
    dp.include_router(subscriptions.router)
    dp.include_router(support.router)
    dp.include_router(profile.router)
    dp.include_router(payments.router)
    
    logger.info("✅ تم تحميل جميع المعالجات")
    logger.info("🤖 البوت يعمل الآن...")
    
    # بدء الجدولة
    try:
        from scheduler.tasks import start_scheduler
        start_scheduler()
        logger.info("✅ تم تشغيل المجدول")
    except Exception as e:
        logger.warning(f"⚠️ المجدول غير متوفر: {e}")
    
    await dp.start_polling(bot)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("⏹ تم إيقاف البوت")
    except Exception as e:
        logger.error(f"❌ خطأ: {e}")
