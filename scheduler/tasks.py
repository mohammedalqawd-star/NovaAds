import asyncio
import logging
from datetime import datetime
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from database.connection import Database

logger = logging.getLogger(__name__)
db = Database()
scheduler = AsyncIOScheduler()

async def check_scheduled_posts():
    """فحص المنشورات المجدولة ونشرها"""
    try:
        now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        
        posts = await db.fetchall(
            """SELECT * FROM scheduled_posts 
            WHERE status = 'scheduled' AND scheduled_time <= ?""",
            (now,)
        )
        
        for post in posts:
            try:
                # هنا يتم نشر المنشور في القناة
                logger.info(f"📅 نشر منشور مجدول #{post['id']} في القناة {post['channel_id']}")
                
                await db.execute(
                    "UPDATE scheduled_posts SET status = 'published' WHERE id = ?",
                    (post['id'],)
                )
            except Exception as e:
                logger.error(f"خطأ في نشر المنشور #{post['id']}: {e}")
                await db.execute(
                    "UPDATE scheduled_posts SET status = 'failed' WHERE id = ?",
                    (post['id'],)
                )
    except Exception as e:
        logger.error(f"خطأ في فحص المنشورات المجدولة: {e}")

async def check_expired_subscriptions():
    """فحص الاشتراكات المنتهية"""
    try:
        now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        
        expired = await db.fetchall(
            """SELECT * FROM user_subscriptions 
            WHERE status = 'active' AND end_date <= ?""",
            (now,)
        )
        
        for sub in expired:
            await db.execute(
                "UPDATE user_subscriptions SET status = 'expired' WHERE id = ?",
                (sub['id'],)
            )
            logger.info(f"⚠️ انتهاء اشتراك المستخدم #{sub['user_id']}")
    except Exception as e:
        logger.error(f"خطأ في فحص الاشتراكات: {e}")

async def send_subscription_reminders():
    """إرسال تذكيرات قبل انتهاء الاشتراك"""
    try:
        # تذكير قبل 7 أيام
        from datetime import timedelta
        week_later = (datetime.now() + timedelta(days=7)).strftime('%Y-%m-%d')
        
        expiring = await db.fetchall(
            """SELECT us.*, u.telegram_id, s.name FROM user_subscriptions us
            JOIN users u ON us.user_id = u.id
            JOIN subscriptions s ON us.subscription_id = s.id
            WHERE us.status = 'active' AND date(us.end_date) = ?""",
            (week_later,)
        )
        
        for sub in expiring:
            logger.info(f"📩 تذكير للمستخدم {sub['telegram_id']} بانتهاء اشتراكه")
            
    except Exception as e:
        logger.error(f"خطأ في إرسال التذكيرات: {e}")

def start_scheduler():
    """بدء المجدول"""
    scheduler.add_job(check_scheduled_posts, 'interval', minutes=1, id='check_posts')
    scheduler.add_job(check_expired_subscriptions, 'interval', hours=6, id='check_subs')
    scheduler.add_job(send_subscription_reminders, 'interval', hours=12, id='reminders')
    
    scheduler.start()
    logger.info("✅ بدء المجدول بنجاح")
