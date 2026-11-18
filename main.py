import os
import telebot
from telebot import types
import threading
import sqlite3
import time

# 🔑 التوكن الخاص ببوتك الرئيسي (المصنع)
MAIN_TOKEN = "8861113947:AAFSV2dfGPagCB_IuRQbfGtAJ5HRd28tP2w"
main_bot = telebot.TeleBot(MAIN_TOKEN)

# معرف وقناة الاشتراك الإجباري ومعرف المطور للتواصل
CHANNEL_USERNAME = "@DR1Ax"
CHANNEL_LINK = "https://t.me/DR1Ax"
DEVELOPER_USERNAME = "@DR1Ax"

# ⚠️ الآيدي الخاص بك
ADMIN_ID = 6148614666

user_states = {}
active_bots = {}
temp_welcome_storage = {}

# --- 1. إدارة قاعدة البيانات مع التحديث التلقائي للأعمدة ---
def init_db():
    conn = sqlite3.connect("bot_factory.db")
    cursor = conn.cursor()
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS bots (
        owner_id INTEGER PRIMARY KEY,
        token TEXT NOT NULL
    )
    """)
    cursor.execute("PRAGMA table_info(bots)")
    columns = [column[1] for column in cursor.fetchall()]
    if "welcome_text" not in columns:
        cursor.execute("ALTER TABLE bots ADD COLUMN welcome_text TEXT")
    conn.commit()
    conn.close()

def save_bot_to_db(owner_id, token, welcome_text=""):
    conn = sqlite3.connect("bot_factory.db")
    cursor = conn.cursor()
    cursor.execute("INSERT OR REPLACE INTO bots (owner_id, token, welcome_text) VALUES (?, ?, ?)", (owner_id, token, welcome_text))
    conn.commit()
    conn.close()

def update_welcome_in_db(owner_id, welcome_text):
    conn = sqlite3.connect("bot_factory.db")
    cursor = conn.cursor()
    cursor.execute("UPDATE bots SET welcome_text = ? WHERE owner_id = ?", (welcome_text, owner_id))
    conn.commit()
    conn.close()

def get_bot_from_db(owner_id):
    conn = sqlite3.connect("bot_factory.db")
    cursor = conn.cursor()
    cursor.execute("SELECT token, welcome_text FROM bots WHERE owner_id = ?", (owner_id,))
    row = cursor.fetchone()
    conn.close()
    return row

def delete_bot_from_db(owner_id):
    conn = sqlite3.connect("bot_factory.db")
    cursor = conn.cursor()
    cursor.execute("DELETE FROM bots WHERE owner_id = ?", (owner_id,))
    conn.commit()
    conn.close()

def load_all_bots():
    conn = sqlite3.connect("bot_factory.db")
    cursor = conn.cursor()
    cursor.execute("SELECT owner_id, token, welcome_text FROM bots")
    rows = cursor.fetchall()
    conn.close()
    return rows

# --- 2. دالة التحقق من الاشتراك الإجباري ---
def check_subscription(user_id):
    try:
        member = main_bot.get_chat_member(CHANNEL_USERNAME, user_id)
        if member.status in ['creator', 'administrator', 'member']:
            return True
        return False
    except Exception as e:
        print(f"تنبيه فحص القناة 🤍 {e}")
        return True

# --- 3. تشغيل البوتات الفرعية ---
def run_user_bot(user_token, owner_id):
    try:
        user_bot = telebot.TeleBot(user_token)
        bot_info = user_bot.get_me()
        bot_username = bot_info.username
        
        reply_waiting = {}
        blocked_users = set()
        bot_users = set()
        stats = {"messages_count": 0}
        bot_settings = {"is_paused": False}

        def owner_keyboard():
            markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
            markup.add(types.KeyboardButton("الإحصائيات الشاملة 🤍"), types.KeyboardButton("إذاعة للجميع 🤍"))
            markup.add(types.KeyboardButton("تعديل رسالة البدء 🤍"), types.KeyboardButton("قائمة المحظورين 🤍"))
            status_btn = "تفعيل استقبال الرسائل 🤍" if bot_settings["is_paused"] else "إيقاف البوت مؤقتاً 🤍"
            markup.add(types.KeyboardButton(status_btn))
            return markup

        @user_bot.message_handler(commands=['start'])
        def start_user_bot(msg):
            user_id = msg.chat.id
            rights_text = f"\n\nصُنع بواسطة 🤍: {CHANNEL_USERNAME}"
            if user_id == owner_id:
                user_bot.send_message(
                    owner_id, 
                    "أهلاً بك يا مالك البوت 🤍\nلوحة تحكم بوتك جاهزة الآن 🤍:" + rights_text, 
                    reply_markup=owner_keyboard(),
                    parse_mode="Markdown"
                )
            else:
                if bot_settings["is_paused"]:
                    user_bot.send_message(user_id, "عذراً، البوت متوقف عن استقبال الرسائل حالياً 🤍.")
                    return
                
                bot_users.add(user_id)
                db_data = get_bot_from_db(owner_id)
                custom_welcome = db_data[1] if db_data and db_data[1] else f"أهلاً بك {msg.from_user.first_name} 🤍\n\nأرسل أي شيء وسوف يصل لصاحب البوت بشكل مجهول 🤍."
                welcome_msg = custom_welcome + rights_text
                
                markup = types.InlineKeyboardMarkup()
                markup.add(types.InlineKeyboardButton("قناة المطور 🤍", url=CHANNEL_LINK))
                user_bot.send_message(user_id, welcome_msg, parse_mode="Markdown", reply_markup=markup)

        @user_bot.callback_query_handler(func=lambda call: True)
        def handle_callbacks(call):
            if call.from_user.id != owner_id:
                user_bot.answer_callback_query(call.id, "هذا الخيار للمالك فقط 🤍", show_alert=True)
                return

            if call.data == "confirm_welcome":
                if owner_id in temp_welcome_storage:
                    new_text = temp_welcome_storage[owner_id]
                    update_welcome_in_db(owner_id, new_text)
                    del temp_welcome_storage[owner_id]
                    user_bot.answer_callback_query(call.id, "تم اعتماد وحفظ رسالة البدء بنجاح 🤍", show_alert=True)
                    user_bot.edit_message_text("تم حفظ رسالة البدء الجديدة واعتمادها رسمياً 🤍.", call.message.chat.id, call.message.message_id)
                return
            elif call.data == "cancel_welcome":
                if owner_id in temp_welcome_storage:
                    del temp_welcome_storage[owner_id]
                    user_bot.answer_callback_query(call.id, "تم إلغاء التعديل 🤍")
                    user_bot.edit_message_text("تم إلغاء تعديل رسالة البدء 🤍.", call.message.chat.id, call.message.message_id)
                return

            action, target_str = call.data.split("_")
            target_id = int(target_str)

            if action == "reply":
                reply_waiting[owner_id] = target_id
                user_bot.answer_callback_query(call.id)
                cancel_markup = types.InlineKeyboardMarkup()
                cancel_markup.add(types.InlineKeyboardButton("إلغاء الرد 🤍", callback_data=f"cancel_{target_id}"))
                user_bot.send_message(owner_id, f"اكتب ردك الآن للعميل (ID: {target_id}) 🤍:", reply_markup=cancel_markup)
            elif action == "block":
                blocked_users.add(target_id)
                user_bot.answer_callback_query(call.id, "تم حظر المستخدم 🤍", show_alert=True)
                user_bot.send_message(owner_id, f"تم حظر المستخدم {target_id} 🤍.")
            elif action == "unblock":
                blocked_users.discard(target_id)
                user_bot.answer_callback_query(call.id, "تم فك الحظر 🤍", show_alert=True)
                user_bot.send_message(owner_id, f"تم فك الحظر عن {target_id} 🤍.")
            elif action == "cancel":
                if owner_id in reply_waiting:
                    del reply_waiting[owner_id]
                    user_bot.answer_callback_query(call.id, "تم إلغاء الرد 🤍")
                    user_bot.send_message(owner_id, "تم إلغاء عملية الرد 🤍.")

        @user_bot.message_handler(content_types=['text', 'photo', 'sticker', 'voice', 'video', 'document', 'audio'])
        def handle_sub_messages(msg):
            user_id = msg.chat.id
            if user_id == owner_id:
                text = msg.text if msg.text else ""
                if text == "الإحصائيات الشاملة 🤍":
                    info_text = (
                        f"تقرير إحصائيات بوتك المتقدم 🤍:\n\n"
                        f"معرف البوت 🤍: @{bot_username}\n"
                        f"رابط البوت 🤍: https://t.me/{bot_username}\n"
                        f"عدد المستخدمين 🤍: {len(bot_users)}\n"
                        f"إجمالي الرسائل 🤍: {stats['messages_count']}\n"
                        f"المحظورين 🤍: {len(blocked_users)}\n"
                        f"الحالة 🤍: {'متوقف مؤقتاً' if bot_settings['is_paused'] else 'يعمل بشكل طبيعي'}"
                    )
                    user_bot.send_message(owner_id, info_text)
            else:
                if bot_settings["is_paused"]:
                    return
                if user_id in blocked_users:
                    return
                stats['messages_count'] += 1
                # توجيه الرسالة لمالك البوت الفرعي
                markup = types.InlineKeyboardMarkup()
                markup.add(
                    types.InlineKeyboardButton("رد 🤍", callback_data=f"reply_{user_id}"),
                    types.InlineKeyboardButton("حظر 🤍", callback_data=f"block_{user_id}")
                )
                user_bot.forward_message(owner_id, user_id, msg.message_id)
                user_bot.send_message(owner_id, f"رسالة جديدة من المستخدم: `{user_id}` 🤍", parse_mode="Markdown", reply_markup=markup)

        # تشغيل البوت الفرعي مع skip_pending لمنع أي تعارض 409
        user_bot.infinity_polling(skip_pending=True)
        
    except Exception as e:
        print(f"خطأ في تشغيل البوت الفرعي {user_token}: {e}")

# --- التشغيل الأساسي على Render بدون أي تعارض ---
if __name__ == "__main__":
    init_db()
    
    # تشغيل البوتات المخزنة مسبقاً في قاعدة البيانات عبر الـ Threads
    saved_bots = load_all_bots()
    for owner_id, token, _ in saved_bots:
        t = threading.Thread(target=run_user_bot, args=(token, owner_id))
        t.daemon = True
        t.start()
        
    print("Bot Factory is running successfully... 🚀")
    
    # حلقة تمديد وتشغيل السيرفر على Render لمنع الخمول وبدون تداخل للـ Polling
    while True:
        time.sleep(60)
