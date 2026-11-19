@main_bot.message_handler(commands=["start"])
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
        main_bot.answer_callback_query(
            call.id, "تم حذف البوت بنجاح 🤍", show_alert=True
        )
        main_bot.edit_message_text(
            "تم حذف بوتك السابق وقاعدة بياناته بنجاح 🤍. يمكنك إنشاء بوت جديد الآن.",
            call.message.chat.id,
            call.message.message_id,
        )
        main_bot.send_message(
            user_id, "الرئيسية 🤍:", reply_markup=main_keyboard(user_id)
        )
    elif call.data == "factory_cancel_delete":
        main_bot.answer_callback_query(call.id, "تم إلغاء الحذف 🤍")
        main_bot.edit_message_text(
            "تم إلغاء عملية حذف البوت 🤍.",
            call.message.chat.id,
            call.message.message_id,
        )


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
        main_bot.send_message(
            user_id, stats_msg, parse_mode="Markdown", reply_markup=main_keyboard(user_id)
        )
        return

    if not check_subscription(user_id):
        sub_markup = types.InlineKeyboardMarkup()
        sub_markup.add(types.InlineKeyboardButton("اشترك في القناة 🤍", url=CHANNEL_LINK))
        main_bot.send_message(
            user_id,
            f"عذراً، يجب عليك الاشتراك في قناة البوت أولاً 🤍!\nاشترك ثم أعد إرسال /start.",
            reply_markup=sub_markup,
        )
        return

    if text == "إنشاء بوت تواصل جديد 🤍":
        if user_id in active_bots:
            main_bot.send_message(
                user_id, "لديك بوت يعمل بالفعل 🤍!", reply_markup=main_keyboard(user_id)
            )
            return
        user_states[user_id] = "waiting_for_token"
        main_bot.send_message(
            user_id,
            "من فضلك أرسل الـ API Token الخاص ببوتك من @BotFather الآن 🤍:",
        )
    elif text == "حذف وتغيير بوتي 🤍":
        if user_id in active_bots:
            confirm_markup = types.InlineKeyboardMarkup()
            confirm_markup.add(
                types.InlineKeyboardButton(
                    "نعم، متأكد (حذف) 🤍", callback_data="factory_confirm_delete"
                ),
                types.InlineKeyboardButton(
                    "إلغاء 🤍", callback_data="factory_cancel_delete"
                ),
            )
            main_bot.send_message(
                user_id,
                "هل أنت متأكد من أنك تريد حذف بوتك الحالي؟ سيتم إيقافه وحذفه نهائياً 🤍:",
                reply_markup=confirm_markup,
            )
        else:
            main_bot.send_message(
                user_id,
                "ليس لديك بوت شغال حالياً 🤍.",
                reply_markup=main_keyboard(user_id),
            )
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
            main_bot.send_message(
                user_id, "الـ Token غير صحيح 🤍.", reply_markup=main_keyboard(user_id)
            )
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
                reply_markup=main_keyboard(user_id),
            )
        except Exception:
            main_bot.send_message(
                user_id,
                "الـ Token غير صحيح أو مستخدم حالياً 🤍.",
                reply_markup=main_keyboard(user_id),
            )
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
        main_bot.send_message(
            user_id,
            f"تم إرسال الإذاعة بنجاح إلى {success} شخص 🤍.",
            reply_markup=main_keyboard(user_id),
        )
        user_states[user_id] = None


# --- 5. التشغيل والتنفيذ ---
if name == "main":
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
