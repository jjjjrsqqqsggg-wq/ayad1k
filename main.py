import os
import sqlite3
import threading
from flask import Flask
import telebot
from telebot import types

# --- 1. الإعدادات الأساسية ---

MAIN_TOKEN = "8861113947:AAFSV2dfGPagCB_IuRQbfGtaJ5HRd2tP2w"
CHANNEL_USERNAME = "@DR1Ax"
CHANNEL_LINK = "https://t.me/DR1Ax"

main_bot = telebot.TeleBot(MAIN_TOKEN)

user_states = {}
active_bots = {}

# --- 2. خادم Flask لإبقاء الخدمة تعمل 24/7 ---

app = Flask(__name__)

@app.route('/')
def home():
    # استجابة خفيفة لمنع خطأ الإخراج الكبير في cron-job.org
    return "OK", 200

def run_flask():
    port = int(os.environ.get("PORT", 8080))
    app.run(host="0.0.0.0", port=port)

# --- 3. إدارة قاعدة البيانات ---

def init_db():
    conn = sqlite3.connect("bot_factory.db")
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS bots (
            owner_id INTEGER PRIMARY KEY,
            token TEXT NOT NULL
        )
    """)
    conn.commit()
    conn.close()

def save_bot_to_db(owner_id, token):
    conn = sqlite3.connect("bot_factory.db")
    cursor = conn.cursor()
    cursor.execute("INSERT OR REPLACE INTO bots (owner_id, token) VALUES (?, ?)", (owner_id, token))
    conn.commit()
    conn.close()

def delete_bot_from_db(owner_id):
    conn = sqlite3.connect("bot_factory.db")
    cursor = conn.cursor()
    cursor.execute("DELETE FROM bots WHERE owner_id = ?", (owner_id,))
    conn.commit()
    conn.close()

def load_all_bots():
    conn = sqlite3.connect("bot_factory.db")
    cursor = conn.cursor()
    cursor.execute("SELECT owner_id, token FROM bots")
    rows = cursor.fetchall()
    conn.close()
    return rows

def check_subscription(user_id):
    try:
        member = main_bot.get_chat_member(CHANNEL_USERNAME, user_id)
        if member.status in ['creator', 'administrator', 'member']:
            return True
        return False
    except Exception as e:
        print(f"تنبيه فحص القناة {e}")
        return True

# --- 4. تشغيل بوتات المستخدمين ---

def run_user_bot(user_token, owner_id):
    try:
        user_bot = telebot.TeleBot(user_token)
        
        @user_bot.message_handler(commands=['start'])
        def start_user_bot(msg):
            user_bot.send_message(msg.chat.id, f"أهلاً بك! أرسل رسالتك وسأقوم بتوصيلها لمالك البوت.")

        @user_bot.message_handler(func=lambda msg: True, content_types=['text', 'photo', 'sticker', 'voice', 'document'])
        def handle_user_messages(msg):
            user_id = msg.chat.id
            if user_id == owner_id:
                return

            markup = types.InlineKeyboardMarkup()
            markup.row(
                types.InlineKeyboardButton("رد ↩️", callback_data=f"reply_{user_id}"),
                types.InlineKeyboardButton("حظر 🚫", callback_data=f"block_{user_id}")
            )
            markup.add(types.InlineKeyboardButton(f"تابعنا {CHANNEL_USERNAME} 📢", url=CHANNEL_LINK))

            user_bot.send_message(owner_id, f"📩 رسالة جديدة من ({msg.from_user.first_name}):", reply_markup=markup)
            user_bot.copy_message(owner_id, user_id, msg.message_id)
            user_bot.send_message(user_id, "تم إرسال رسالتك بنجاح! ✉️")

        user_bot.infinity_polling(skip_pending=True)
    except Exception as e:
        print(f"خطأ في بوت المستخدم ({owner_id}): {e}")
        if owner_id in active_bots:
            del active_bots[owner_id]

# --- 5. البوت الرئيسي (المصنع) ---

def main_keyboard(user_id):
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    if user_id in active_bots:
        markup.add(types.KeyboardButton("حذف وتغيير بوتي ❌"))
    else:
        markup.add(types.KeyboardButton("إنشاء بوت تواصل جديد 🤖"))
    markup.add(types.KeyboardButton("مساعدة ℹ️"))
    return markup

@main_bot.message_handler(commands=['start'])
def send_welcome(message):
    u_id = message.chat.id
    welcome_text = (
        f"أهلاً بك {message.from_user.first_name} في مصنع البوتات! 🤍\n\n"
        f"يمكنك إنشاء أو إدارة بوت الرسائل المجهولة الخاص بك مجاناً.\n"
        f"تابع جديدنا على القناة: {CHANNEL_USERNAME}"
    )
    main_bot.send_message(u_id, welcome_text, reply_markup=main_keyboard(u_id))

@main_bot.message_handler(func=lambda message: True)
def handle_factory_messages(message):
    user_id = message.chat.id
    text = message.text.strip() if message.text else ""

    if not check_subscription(user_id):
        sub_markup = types.InlineKeyboardMarkup()
        sub_markup.add(types.InlineKeyboardButton("اشترك في القناة 📢", url=CHANNEL_LINK))
        main_bot.send_message(
            user_id, 
            f"⚠️ عذراً، يجب عليك الاشتراك في قناة البوت أولاً لاستخدام المصنع!\nاشترك ثم أعد إرسال /start.", 
            reply_markup=sub_markup
        )
        return

    # استخدام مرونة الشروط لاستجابة متجاوبة
    if "إنشاء" in text or "اصنع" in text:
        if user_id in active_bots:
            main_bot.send_message(user_id, "⚠️ لديك بوت يعمل بالفعل! لحذفه أو تغييره استخدم 'حذف وتغيير بوتي'.", reply_markup=main_keyboard(user_id))
            return

        user_states[user_id] = "waiting_for_token"
        main_bot.send_message(user_id, "من فضلك أرسل الـ API Token الخاص ببوتك من @BotFather الآن 🔑:")

    elif "حذف" in text:
        if user_id in active_bots:
            del active_bots[user_id]
            delete_bot_from_db(user_id)
            main_bot.send_message(user_id, "🗑 تم حذف بوتك السابق من الخدمة وقاعدة البيانات. يمكنك إنشاء بوت جديد الآن.", reply_markup=main_keyboard(user_id))
        else:
            main_bot.send_message(user_id, "ليس لديك بوت شغال حالياً.", reply_markup=main_keyboard(user_id))

    elif "مساعدة" in text:
        help_text = (
            "خطوات إنشاء بوتك الخاص:\n"
            "1. اذهب لبوت @BotFather وأنشئ بوت جديد عبر الأمر /newbot.\n"
            "2. قم بنسخ الـ API Token الخاص ببوتك.\n"
            "3. عد هنا واضغط 'إنشاء بوت تواصل جديد 🤖' ثم أرسل الـ Token."
        )
        main_bot.send_message(user_id, help_text)

    elif user_states.get(user_id) == "waiting_for_token":
        token = text
        if ":" not in token:
            main_bot.send_message(user_id, "⚠️ الـ Token غير صحيح. تأكد من نسخ المقطع كاملاً من @BotFather.", reply_markup=main_keyboard(user_id))
            return

        try:
            test_bot = telebot.TeleBot(token)
            bot_info = test_bot.get_me()
            
            t = threading.Thread(target=run_user_bot, args=(token, user_id))
            t.daemon = True
            t.start()

            active_bots[user_id] = token
            save_bot_to_db(user_id, token)
            user_states[user_id] = None

            main_bot.send_message(
                user_id, 
                f"تم إنشاء وتشغيل بوتك @{bot_info.username} بنجاح! 🎉\n\n"
                f"👈 اذهب لبوتك الجديد واضغط /start للتحكم به!",
                reply_markup=main_keyboard(user_id)
            )
        except Exception:
            main_bot.send_message(user_id, "❌ الـ Token غير صحيح أو مستخدم حالياً، حاول مجدداً.", reply_markup=main_keyboard(user_id))

# --- 6. التشغيل المباشر السليم ---

if __name__ == "__main__":
    init_db()
    
    saved_bots = load_all_bots()
    print(f"جاري استعادة {len(saved_bots)} بوت من قاعدة البيانات...")
    
    for owner_id, token in saved_bots:
        active_bots[owner_id] = token
        t = threading.Thread(target=run_user_bot, args=(token, owner_id))
        t.daemon = True
        t.start()

    flask_thread = threading.Thread(target=run_flask)
    flask_thread.daemon = True
    flask_thread.start()

    print("مصنع البوتات يعمل الآن...")
    main_bot.infinity_polling(skip_pending=True)
