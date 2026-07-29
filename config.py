import os
from dotenv import load_dotenv

load_dotenv()

class Config:
    BOT_TOKEN = os.getenv("BOT_TOKEN", "")
    ADMIN_IDS = list(map(int, os.getenv("ADMIN_IDS", "").split(",")))
    DATABASE_PATH = os.getenv("DATABASE_PATH", "nova_ads.db")
    PLATFORM_COMMISSION = float(os.getenv("PLATFORM_COMMISSION", 10))
    MIN_WITHDRAWAL = float(os.getenv("MIN_WITHDRAWAL", 5000))
    DEFAULT_LANGUAGE = os.getenv("DEFAULT_LANGUAGE", "ar")
    
    # ============ إعدادات الدفع ============
    # رقم جوالي للتحويل
    JAWALI_NUMBER = "783421319"
    JAWALI_NAME = "Nova Ads"
    
    # طرق الدفع المتاحة حالياً
    PAYMENT_METHODS = ["jawali"]  # جوالي فقط حالياً
    # ستضاف لاحقاً: "kuraimi", "floosak", "bank_transfer"
    
    # طرق الدفع مع الأسماء
    PAYMENT_METHODS_NAMES = {
        "jawali": "📱 جوالي",
        "kuraimi": "🏦 الكريمي (قريباً)",
        "floosak": "💳 فلوسك (قريباً)",
        "bank_transfer": "🏧 تحويل بنكي (قريباً)"
    }
    
    # طرق السحب المتاحة حالياً
    WITHDRAWAL_METHODS = ["jawali"]  # جوالي فقط حالياً
    
    WITHDRAWAL_METHODS_NAMES = {
        "jawali": "📱 جوالي",
        "kuraimi": "🏦 الكريمي (قريباً)",
        "floosak": "💳 فلوسك (قريباً)",
        "bank_transfer": "🏧 تحويل بنكي (قريباً)"
    }
    
    # ============ الباقات ============
    SUBSCRIPTIONS = {
        "free": {
            "name": "مجاني",
            "price": 0,
            "channels_limit": 1,
            "ads_limit": 5,
            "priority": 0,
            "features": "📢 قناة واحدة\n📊 5 إعلانات شهرياً\n📈 إحصائيات أساسية"
        },
        "silver": {
            "name": "فضي",
            "price": 3000,
            "channels_limit": 5,
            "ads_limit": 20,
            "priority": 1,
            "features": "📢 حتى 5 قنوات\n📅 جدولة غير محدودة\n📊 إحصائيات متقدمة\n⭐ أولوية في البحث"
        },
        "gold": {
            "name": "ذهبي",
            "price": 7000,
            "channels_limit": 20,
            "ads_limit": 100,
            "priority": 2,
            "features": "📢 حتى 20 قناة\n✅ قبول تلقائي للإعلانات\n📊 إحصائيات كاملة\n🏅 شارة قناة موثقة"
        },
        "company": {
            "name": "شركات",
            "price": 20000,
            "channels_limit": 999,
            "ads_limit": 999,
            "priority": 3,
            "features": "📢 عدد غير محدود من القنوات\n👥 عدد غير محدود من المشرفين\n📊 تقارير شهرية\n👑 أولوية قصوى في الظهور"
        }
    }
    
    # ============ تصنيفات القنوات ============
    CATEGORIES = [
        "تقنية", "ألعاب", "سيارات", "رياضة", "أخبار",
        "تعليم", "وظائف", "تجارة", "طبخ", "صحة", "أخرى"
    ]
