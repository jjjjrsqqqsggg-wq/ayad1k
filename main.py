import telebot
from telebot import types
import threading
import sqlite3

# 🔑 التوكن الخاص ببوتك الرئيسي (المصنع)
MAIN_TOKEN = "8861113947:AAFSV2dfGPagCB_IuRQbfGtAJ5HRd28tP2w"
main_bot = telebot.TeleBot(MAIN_TOKEN)

# معرف وقناة الاشتراك الإجباري ومعرف المطور للتواصل
CHANNEL_USERNAME = "@DR1Ax"
CHANNEL_LINK = "https://t.me/DR1Ax"
DEVELOPER_USERNAME = "@DR1Ax"

# ⚠️ تم وضع الآيدي الحقيقي الخاص بك هنا
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
                    user_bot.send_message(owner_id, info_text, parse_mode="Markdown")

                elif text == "إذاعة للجميع 🤍":
                    reply_waiting[owner_id] = "broadcast"
                    user_bot.send_message(owner_id, "أرسل الرسالة الآن وسيتم توجيهها لجميع المستخدمين 🤍:")

                elif text == "تعديل رسالة البدء 🤍":
                    reply_waiting[owner_id] = "edit_welcome"
                    user_bot.send_message(owner_id, "أرسل الآن النص الجديد لرسالة البدء (/start) لنعاينه معاً 🤍:")

                elif text == "إيقاف البوت مؤقتاً 🤍":
                    bot_settings["is_paused"] = True
                    user_bot.send_message(owner_id, "تم إيقاف استقبال الرسائل مؤقتاً 🤍.", reply_markup=owner_keyboard())

                elif text == "تفعيل استقبال الرسائل 🤍":
                    bot_settings["is_paused"] = False
                    user_bot.send_message(owner_id, "تم تفعيل البوت وفتح باب استقبال الرسائل 🤍.", reply_markup=owner_keyboard())

                elif text == "قائمة المحظورين 🤍":
                    if not blocked_users:
                        user_bot.send_message(owner_id, "لا يوجد مستخدمين محظورين 🤍.")
                    else:
                        markup = types.InlineKeyboardMarkup()
                        for u_id in blocked_users:
                            markup.add(types.InlineKeyboardButton(f"فك حظر {u_id} 🤍", callback_data=f"unblock_{u_id}"))
                        user_bot.send_message(owner_id, "قائمة المحظورين 🤍:", reply_markup=markup)

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
                        user_bot.send_message(owner_id, f"تم إرسال الإذاعة إلى {success} مستخدم 🤍.")
                        del reply_waiting[owner_id]

                    elif target == "edit_welcome":
                        new_welcome = msg.text
                        temp_welcome_storage[owner_id] = new_welcome
                        
                        preview_text = f"معاينة رسالة البدء الجديدة 🤍:\n\n{new_welcome}\n\nصُنع بواسطة 🤍: {CHANNEL_USERNAME}"
                        preview_markup = types.InlineKeyboardMarkup()
                        preview_markup.add(
                            types.InlineKeyboardButton("تأكيد وحفظ 🤍", callback_data="confirm_welcome"),
                            types.InlineKeyboardButton("إلغاء 🤍", callback_data="cancel_welcome")
                        )
                        user_bot.send_message(owner_id, preview_text, reply_markup=preview_markup, parse_mode="Markdown")
                        del reply_waiting[owner_id]

                    else:
                        try:
                            user_bot.copy_message(target, owner_id, msg.message_id)
                            user_bot.send_message(owner_id, "تم إرسال الرد بنجاح 🤍!")
                        except Exception:
                            user_bot.send_message(owner_id, "فشل إرسال الرد 🤍.")
                        del reply_waiting[owner_id]

            else:
                if bot_settings["is_paused"]:
                    user_bot.send_message(user_id, "عذراً، البوت متوقف مؤقتاً 🤍.")
                    return

                if user_id in blocked_users:
                    user_bot.send_message(user_id, "أنت محظور من استخدام هذا البوت 🤍.")
                    return

                bot_users.add(user_id)
                stats["messages_count"] += 1

                markup = types.InlineKeyboardMarkup()
                markup.row(
                    types.InlineKeyboardButton("رد 🤍", callback_data=f"reply_{user_id}"),
                    types.InlineKeyboardButton("حظر 🤍", callback_data=f"block_{user_id}")
                )
                markup.add(types.InlineKeyboardButton(f"تابعنا {CHANNEL_USERNAME} 🤍", url=CHANNEL_LINK))

                notification_text = f"الرسالة، هنا محتوى الرسالة 🤍\n\n(مرسلة من: {msg.from_user.first_name})"
                user_bot.send_message(owner_id, notification_text, reply_markup=markup)
                user_bot.copy_message(owner_id, user_id, msg.message_id)
                user_bot.send_message(user_id, "تم إرسال رسالتك بنجاح 🤍!")

        user_bot.infinity_polling(skip_pending=True)
    except Exception as e:
        print(f"خطأ في بوت المستخدم ({owner_id}) 🤍: {e}")
        if owner_id in active_bots:
            del active_bots[owner_id]

# --- 4. البوت الرئيسي (المصنع) ---

def main_keyboard(user_id):
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    if user_id in active_bots:
        markup.add(types.KeyboardButton("حذف وتغيير بوتي 🤍"))
    else:
        markup.add(types.KeyboardButton("إنشاء بوت تواصل جديد 🤍"))
        
    markup.add(types.KeyboardButton("إذاعة للجميع 🤍"), types.KeyboardButton("تواصل مع المطور 🤍"))
    markup.add(types.KeyboardButton("مساعدة 🤍"))
    
    # يظهر زر الإحصائيات للمالك
    if user_id == ADMIN_ID:
        markup.add(types.KeyboardButton("إحصائيات المصنع (خاص للمالك) 🤍"))
        
    return markup

@main_bot.message_handler(commands=['start'])
def send_welcome(message):
    u_id = message.chat.id
    user_states[u_id] = None
    welcome_text = (
        f"أهلاً بك {message.from_user.first_name} في مصنع البوتات 🤍\n\n"
        f"يمكنك إنشاء أو إدارة بوت الرسائل المجهولة الخاص بك مجاناً 🤍.\n"
        f"تابع جديدنا على القناة: {CHANNEL_USERNAME} 🤍"
    )
    main_bot.send_message(u_id, welcome_text, reply_markup=main_keyboard(u_id))

@main_bot.callback_query_handler(func=lambda call: call.data.startswith("factory_"))
def factory_callbacks(call):
    user_id = call.message.chat.id
    if call.data == "factory_confirm_delete":
        if user_id in active_bots:
            del active_bots[user_id]
            delete_bot_from_db(user_id)
            main_bot.answer_callback_query(call.id, "تم حذف البوت بنجاح 🤍", show_alert=True)
            main_bot.edit_message_text("تم حذف بوتك السابق وقاعدة بياناته بنجاح 🤍. يمكنك إنشاء بوت جديد الآن.", call.message.chat.id, call.message.message_id)
            main_bot.send_message(user_id, "الرئيسية 🤍:", reply_markup=main_keyboard(user_id))
    elif call.data == "factory_cancel_delete":
        main_bot.answer_callback_query(call.id, "تم إلغاء الحذف 🤍")
        main_bot.edit_message_text("تم إلغاء عملية حذف البوت 🤍.", call.message.chat.id, call.message.message_id)

@main_bot.message_handler(func=lambda message: True)
def handle_factory_messages(message):
    user_id = message.chat.id
    text = message.text.strip() if message.text else ""

    if user_id == ADMIN_ID and text == "إحصائيات المصنع (خاص للمالك) 🤍":
        conn = sqlite3.connect("bot_factory.db")
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM bots")
        total_bots = cursor.fetchone()[0]
        conn.close()
        
        stats_msg = (
            f"لوحة تحكم وإحصائيات المصنع الشاملة 🤍:\n\n"
            f"إجمالي البوتات المصنوعة 🤍: {total_bots}\n"
            f"البوتات النشطة حالياً في الذاكرة 🤍: {len(active_bots)}"
        )
        main_bot.send_message(user_id, stats_msg, parse_mode="Markdown", reply_markup=main_keyboard(user_id))
        return

    if not check_subscription(user_id):
        sub_markup = types.InlineKeyboardMarkup()
        sub_markup.add(types.InlineKeyboardButton("اشترك في القناة 🤍", url=CHANNEL_LINK))
        main_bot.send_message(
            user_id, 
            f"عذراً، يجب عليك الاشتراك في قناة البوت أولاً 🤍!\nاشترك ثم أعد إرسال /start.", 
            reply_markup=sub_markup
        )
        return

    if text == "إنشاء بوت تواصل جديد 🤍":
        if user_id in active_bots:
            main_bot.send_message(user_id, "لديك بوت يعمل بالفعل 🤍!", reply_markup=main_keyboard(user_id))
            return

        user_states[user_id] = "waiting_for_token"
        main_bot.send_message(user_id, "من فضلك أرسل الـ API Token الخاص ببوتك من @BotFather الآن 🤍:")

    elif text == "حذف وتغيير بوتي 🤍":
        if user_id in active_bots:
            confirm_markup = types.InlineKeyboardMarkup()
            confirm_markup.add(
                types.InlineKeyboardButton("نعم، متأكد (حذف) 🤍", callback_data="factory_confirm_delete"),
                types.InlineKeyboardButton("إلغاء 🤍", callback_data="factory_cancel_delete")
            )
            main_bot.send_message(user_id, "هل أنت متأكد من أنك تريد حذف بوتك الحالي؟ سيتم إيقافه وحذفه نهائياً 🤍:", reply_markup=confirm_markup)
        else:
            main_bot.send_message(user_id, "ليس لديك بوت شغال حالياً 🤍.", reply_markup=main_keyboard(user_id))

    elif text == "إذاعة للجميع 🤍":
        user_states[user_id] = "factory_broadcast"
        main_bot.send_message(user_id, "أرسل رسالة الإذاعة الآن 🤍:")

    elif text == "تواصل مع المطور 🤍":
        dev_text = (
            f"معلومات التواصل مع المطور 🤍:\n\n"
            f"رابط المطور 🤍: https://t.me/{DEVELOPER_USERNAME.replace('@', '')}\n"
            f"القناة الرسمية 🤍: {CHANNEL_USERNAME}"
        )
        main_bot.send_message(user_id, dev_text, reply_markup=main_keyboard(user_id))

    elif text == "مساعدة 🤍":
        help_text = (
            "خطوات إنشاء بوتك الخاص 🤍:\n"
            "1. اذهب لبوت @BotFather وأنشئ بوت جديد عبر الأمر /newbot.\n"
            "2. قم بنسخ الـ API Token.\n"
            "3. عد هنا واضغط 'إنشاء بوت تواصل جديد 🤍' وأرسل الـ Token."
        )
        main_bot.send_message(user_id, help_text, reply_markup=main_keyboard(user_id))

    elif user_states.get(user_id) == "waiting_for_token":
        token = text
        if ":" not in token:
            main_bot.send_message(user_id, "الـ Token غير صحيح 🤍.", reply_markup=main_keyboard(user_id))
            return

        try:
            test_bot = telebot.TeleBot(token)
            bot_info = test_bot.get_me()
            
            t = threading.Thread(target=run_user_bot, args=(token, user_id))
            t.daemon = True
            t.start()

            active_bots[user_id] = token
            save_bot_to_db(user_id, token, "")
            user_states[user_id] = None

            main_bot.send_message(
                user_id, 
                f"تم إنشاء وتشغيل بوتك @{bot_info.username} بنجاح 🤍!\n\n"
                f"اذهب لبوتك الجديد واضغط /start للتحكم به 🤍!",
                reply_markup=main_keyboard(user_id)
            )
        except Exception:
            main_bot.send_message(user_id, "الـ Token غير صحيح أو مستخدم حالياً 🤍.", reply_markup=main_keyboard(user_id))

    elif user_states.get(user_id) == "factory_broadcast":
        conn = sqlite3.connect("bot_factory.db")
        cursor = conn.cursor()
        cursor.execute("SELECT owner_id FROM bots")
        all_users = cursor.fetchall()
        conn.close()

        success = 0
        for row in all_users:
            target_id = row[0]
            try:
                main_bot.copy_message(target_id, user_id, message.message_id)
                success += 1
            except Exception:
                pass

        main_bot.send_message(user_id, f"تم إرسال الإذاعة بنجاح إلى {success} شخص 🤍.", reply_markup=main_keyboard(user_id))
        user_states[user_id] = None

# --- 5. التشغيل والتنفيذ ---

if __name__ == "__main__":
    init_db()
    
    saved_bots = load_all_bots()
    print(f"جاري استعادة {len(saved_bots)} بوت من قاعدة البيانات 🤍...")
    
    for owner_id, token, welcome_text in saved_bots:
        active_bots[owner_id] = token
        t = threading.Thread(target=run_user_bot, args=(token, owner_id))
        t.daemon = True
        t.start()

    print("مصنع البوتات يعمل الآن بدون أخطاء 🤍...")
    main_bot.infinity_polling(skip_pending=True)
