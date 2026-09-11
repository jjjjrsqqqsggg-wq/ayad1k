import os
from flask import Flask
from threading import Thread
import telebot

# 1. إعداد سيرفر Flask لإرضاء متطلبات Render وإبقاء الخدمة حية
app = Flask(name)

@app.route('/')
def home():
    return "Bot Factory is Running Live!"

def run_flask():
    # استخدام المنفذ المخصص من Render أو 8080 افتراضياً
    port = int(os.environ.get('PORT', 8080))
    app.run(host='0.0.0.0', port=port)

def keep_alive():
    server_thread = Thread(target=run_flask)
    server_thread.daemon = True
    server_thread.start()

# 2. إعداد بوت التليجرام (يقرأ التوكن من متغيّرات البيئة أو التوكن المباشر)
BOT_TOKEN = os.environ.get('BOT_TOKEN', 'ضع_توكن_البوت_هنا')
bot = telebot.TeleBot(BOT_TOKEN)

@bot.message_handler(commands=['start', 'help'])
def send_welcome(message):
    bot.reply_to(message, "أهلاً بك! مصنع البوتات يعمل الآن بنجاح على السحابة 🚀")

# 3. تشغيل السيرفر والبوت معاً دون تعارض
if name == "main":
    keep_alive()
    # infinity_polling تضمن استمرار البوت في العمل وتتجاوز أخطاء الانقطاع البسيطة
    bot.infinity_polling(timeout=10, long_polling_timeout=5)
