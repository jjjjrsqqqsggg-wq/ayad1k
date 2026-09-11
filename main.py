import os
import threading
import sqlite3
from flask import Flask
import telebot
from telebot import types

# 🔑 التوكن الخاص ببوتك الرئيسي
MAIN_TOKEN = "8861113947:AAFSV2dfGPagCB_IuRQbfGtAJ5HRd28tP2w"
main_bot = telebot.TeleBot(MAIN_TOKEN)

# معرف القناة للحقوق والاشتراك الإجباري
CHANNEL_USERNAME = "@DR1Ax"
CHANNEL_LINK = "https://t.me/DR1Ax"

user_states = {}
active_bots = {}

# --- سيرفر Flask للحفاظ على تشغيل السيرفر ---
app = Flask(__name__)

@app.route('/')
def home():
    return "Bot Factory Server is Running 24/7!"

def run_flask():
    port = int(os.environ.get("PORT", 8080))
    app.run(host="0.0.0.0", port=port)

# --- 1. إدارة قاعدة البيانات (SQLite) ---

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

# --- 2. دالة التحقق من الاشتراك الإجباري ---

def check_subscription(user_id):
    try:
        member = main_bot.get_chat_member(CHANNEL_USERNAME, user_id)
        if member.status in ['creator', 'administrator', 'member']:
            return True
        return False
    except Exception as e:
        print(f"تنبيه فحص القناة: {e}")
        return True

# --- 3. تشغيل البوتات الفرعية (الأبناء) ---

def run_user_bot(user_token, owner_id):
    try:
        user_bot = telebot.TeleBot(user_token)
        
        reply_waiting = {}
        blocked_users = set()
        bot_users = set()
        stats = {"messages_count": 0}

        def owner_keyboard():
            markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
            markup.add(types.KeyboardButton("📊 الإحصائيات"), types.KeyboardButton("📢 إذاعة للجميع"))
            markup.add(types.KeyboardButton("🚫 قائمة المحظورين"))
            return markup

        @user_bot.message_handler(commands=['start'])
        def start_user_bot(msg):
            user_id = msg.chat.id
            rights_text = f"\n\n🛠 **صُنع بواسطة:** {CHANNEL_USERNAME}"
            
            if user_id == owner_id:
                user_bot.send_message(
                    owner_id, 
                    "أهلاً بك يا مالك البوت! 👑\nلوحة تحكم بوتك جاهزة الآن:" + rights_text, 
                    reply_markup=owner_keyboard(),
                    parse_mode="Markdown"
                )
            else:
                bot_users.add(user_id)
                welcome_msg = (
                    f"أهلاً بك {msg.from_user.first_name} 🤍\n\n"
                    f"أرسل أي شيء (نص، صورة، صوت...) وسوف يصل لصاحب البوت بشكل مجهول 🔒."
                    f"{rights_text}"
                )
                
                markup = types.InlineKeyboardMarkup()
                markup.add(types.InlineKeyboardButton("قناة المطور 📢", url=CHANNEL_LINK))
                user_bot.send_message(user_id, welcome_msg, parse_mode="Markdown", reply_markup=markup)

        @user_bot.callback_query_handler(func=lambda call: True)
        def handle_callbacks(call):
            if call.from_user.id != owner_id:
                user_bot.answer_callback_query(call.id, "هذا الخيار للمالك فقط!", show_alert=True)
                return

            action, target_str = call.data.split("_")
            target_id = int(target_str)

            if action == "reply":
                reply_waiting[owner_id] = target_id
                user_bot.answer_callback_query(call.id)
                
                cancel_markup = types.InlineKeyboardMarkup()
                cancel_markup.add(types.InlineKeyboardButton("إلغاء الرد ❌", callback_data=f"cancel_{target_id}"))
                user_bot.send_message(owner_id, f"✍️ اكتب ردك الآن للعميل (ID: {target_id}):", reply_markup=cancel_markup)

            elif action == "block":
                blocked_users.add(target_id)
                user_bot.answer_callback_query(call.id, "تم حظر المستخدم 🚫", show_alert=True)
                user_bot.send_message(owner_id, f"❌ تم حظر المستخدم {target_id}.")

            elif action == "unblock":
                blocked_users.discard(target_id)
                user_bot.answer_callback_query(call.id, "تم فك الحظر 🔓", show_alert=True)
                user_bot.send_message(owner_id, f"✅ تم فك الحظر عن {target_id}.")

            elif action == "cancel":
                if owner_id in reply_waiting:
                    del reply_waiting[owner_id]
                user_bot.answer_callback_query(call.id, "تم إلغاء الرد")
                user_bot.send_message(owner_id, "تم إلغاء عملية الرد.")

        @user_bot.message_handler(content_types=['text', 'photo', 'sticker', 'voice', 'video', 'document', 'audio'])
        def handle_sub_messages(msg):
            user_id = msg.chat.id

            if user_id == owner_id:
                text = msg.text if msg.text else ""

                if text == "📊 الإحصائيات":
                    info_text = (
                        f"📈 **إحصائيات بوتك:**\n\n"
                        f"👥 عدد المستعملين: {len(bot_users)}\n"
                        f"📩 إجمالي الرسائل: {stats['messages_count']}\n"
                        f"🚫 عدد المحظورين: {len(blocked_users)}"
                    )
                    user_bot.send_message(owner_id, info_text, parse_mode="Markdown")

                elif text == "📢 إذاعة للجميع":
                    reply_waiting[owner_id] = "broadcast"
                    user_bot.send_message(owner_id, "📢 أرسل الرسالة الآن وسيتم توجيهها لجميع المستخدمين:")

                elif text == "🚫 قائمة المحظورين":
                    if not blocked_users:
                        user_bot.send_message(owner_id, "لا يوجد مستخدمين محظورين.")
                    else:
                        markup = types.InlineKeyboardMarkup()
                        for u_id in blocked_users:
                            markup.add(types.InlineKeyboardButton(f"فك حظر {u_id} 🔓", callback_data=f"unblock_{u_id}"))
                        user_bot.send_message(owner_id, "قائمة المحظورين:", reply_markup=markup)

                elif owner_id in reply_waiting:
                    target = reply_waiting[owner_id]

                    if target == "broadcast":
                        success = 0
                        for b_user in bot_users:
                            try:
                                user_bot.copy_message(b_user, owner_id, msg.message_id)
                                success += 1
                            except Exception:
                                pass
                        user_bot.send_message(owner_id, f"✅ تم إرسال الإذاعة إلى {success} مستخدم.")
                        del reply_waiting[owner_id]

                    else:
                        try:
                            user_bot.copy_message(target, owner_id, msg.message_id)
                            user_bot.send_message(owner_id, "🚀 تم إرسال الرد بنجاح!")
                        except Exception:
                            user_bot.send_message(owner_id, "❌ فشل إرسال الرد، ربما حظر الشخص البوت.")
                        del reply_waiting[owner_id]

            else:
                if user_id in blocked_users:
                    user_bot.send_message(user_id, "⛔ أنت محظور من استخدام هذا البوت.")
                    return

                bot_users.add(user_id)
                stats["messages_count"] += 1

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

# --- 4. البوت الرئيسي (المصنع) ---

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

    if text == "إنشاء بوت تواصل جديد 🤖":
        if user_id in active_bots:
            main_bot.send_message(user_id, "⚠️ لديك بوت يعمل بالفعل! لحذفه أو تغييره استخدم 'حذف وتغيير بوتي'.", reply_markup=main_keyboard(user_id))
            return

        user_states[user_id] = "waiting_for_token"
        main_bot.send_message(user_id, "من فضلك أرسل الـ API Token الخاص ببوتك من @BotFather الآن 🔑:")

    elif text == "حذف وتغيير بوتي ❌":
        if user_id in active_bots:
            del active_bots[user_id]
            delete_bot_from_db(user_id)
            main_bot.send_message(user_id, "🗑 تم حذف بوتك السابق من الخدمة وقاعدة البيانات. يمكنك إنشاء بوت جديد الآن.", reply_markup=main_keyboard(user_id))
        else:
            main_bot.send_message(user_id, "ليس لديك بوت شغال حالياً.", reply_markup=main_keyboard(user_id))

    elif text == "مساعدة ℹ️":
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
            main_bot.send_message(user_id, "⚠️ الـ Token غير صحيح. تأكد من نسخه كاملاً من @BotFather.", reply_markup=main_keyboard(user_id))
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

# --- 5. التشغيل والتنفيذ ---

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
                                  
