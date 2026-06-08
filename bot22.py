import telebot
from telebot import types
import sqlite3
import threading
import time

# --- إعدادات البوت وقاعدة البيانات ---
TOKEN = "8336556357:AAEMa2YifwLMigB1LAoBacIVMe-Na0MYHAQ"
ADMINS = [5048116480, 5307344707]

bot = telebot.TeleBot(TOKEN, threaded=True)
admin_state = {}

def get_db():
    conn = sqlite3.connect('bot_perfect.db')
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute('''CREATE TABLE IF NOT EXISTS users 
                      (user_id INTEGER PRIMARY KEY, lang TEXT, shares INTEGER DEFAULT 0, verified INTEGER DEFAULT 0)''')
    cursor.execute('''CREATE TABLE IF NOT EXISTS channels 
                      (channel_id TEXT PRIMARY KEY, link TEXT)''')
    cursor.execute('''CREATE TABLE IF NOT EXISTS categories 
                      (id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT, parent_id INTEGER DEFAULT NULL)''')
    cursor.execute('''CREATE TABLE IF NOT EXISTS messages 
                      (id INTEGER PRIMARY KEY AUTOINCREMENT, cat_id INTEGER, type TEXT, content TEXT, 
                       chat_id TEXT, msg_id INTEGER, yt_url TEXT, install_url TEXT)''')
    cursor.execute('''CREATE TABLE IF NOT EXISTS reviews 
                      (id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER, rating TEXT, text TEXT)''')
    conn.commit()
    conn.close()

init_db()

# --- دالة مسح رسالة معينة بأمان ---
def delete_msg_safe(chat_id, message_id):
    try:
        bot.delete_message(chat_id, message_id)
    except Exception:
        pass

# --- دالة ذكية لجلب اسم القناة الفعلي ---
def get_channel_name(channel_id, default_text):
    try:
        chat = bot.get_chat(channel_id)
        if chat.title:
            return chat.title
    except Exception:
        pass
    return default_text

# --- التحقق من القنوات الإجبارية ---
def check_channels(user_id):
    conn = get_db()
    channels = conn.execute("SELECT * FROM channels").fetchall()
    conn.close()
    if not channels:
        return True
    for ch in channels:
        try:
            member = bot.get_chat_member(ch['channel_id'], user_id)
            if member.status in ['left', 'kicked']:
                return False
        except Exception:
            return False
    return True

def get_welcome_text(lang):
    if lang == 'ar':
        return "☕ مَرحباً بك في بوت مزاجي الحصري! ✨\nالرجاء الاشتراك في قنوات البوت أولاً ثم الضغط على زر التحقق بالأسفل 👇"
    elif lang == 'en':
        return "☕ Welcome to Mazaji Bot! ✨\nPlease join our channels first, then click the verify button below 👇"
    else:
        return "☕ بەخێربێن بۆ بۆتی مزاجی! ✨\nتکایە سەرەتا جۆینی کەناڵەکانی بۆت بکەن و پاشان کلیک لەسەر پشتڕاستکردنەوە بکەن 👇"

# --- قسم الأعضاء (User Flow) ---
@bot.message_handler(commands=['start'])
def start_cmd(message):
    user_id = message.from_user.id
    delete_msg_safe(message.chat.id, message.message_id)
    
    if user_id in admin_state:
        del admin_state[user_id]
        
    conn = get_db()
    user = conn.execute("SELECT * FROM users WHERE user_id = ?", (user_id,)).fetchone()
    conn.close()
    
    if user and user['lang']:
        show_subscription_requirements(message.chat.id, user_id, user['lang'])
        return
        
    markup = types.InlineKeyboardMarkup()
    markup.row(
        types.InlineKeyboardButton("العربية 🇮🇶", callback_data="lang_ar"),
        types.InlineKeyboardButton("English 🇬🇧", callback_data="lang_en"),
        types.InlineKeyboardButton("كردي ☀️", callback_data="lang_ku")
    )
    bot.send_message(message.chat.id, "الرجاء اختيار اللغة الخاصة بك / Please select your language / تکایە زمانەکەت هەڵبژێرە:", reply_markup=markup)

@bot.callback_query_handler(func=lambda call: call.data.startswith("lang_"))
def set_language(call):
    delete_msg_safe(call.message.chat.id, call.message.message_id)
    lang = call.data.split("_")[1]
    user_id = call.from_user.id
    
    conn = get_db()
    conn.execute("INSERT OR REPLACE INTO users (user_id, lang, shares, verified) VALUES (?, ?, COALESCE((SELECT shares FROM users WHERE user_id=?), 0), COALESCE((SELECT verified FROM users WHERE user_id=?), 0))", (user_id, lang, user_id, user_id))
    conn.commit()
    conn.close()
    
    show_subscription_requirements(call.message.chat.id, user_id, lang)

def show_subscription_requirements(chat_id, user_id, lang):
    conn = get_db()
    channels = conn.execute("SELECT * FROM channels").fetchall()
    conn.close()
    
    markup = types.InlineKeyboardMarkup(row_width=1)
    
    if channels:
        for index, ch in enumerate(channels, start=1):
            ch_title = get_channel_name(ch['channel_id'], f"اضغط هنا للاشتراك 📢")
            markup.add(types.InlineKeyboardButton(f"📢 {ch_title}", url=ch['link']))
            
        btn_text = "تحقق من الاشتراك 🔄" if lang == 'ar' else "Verify 🔄" if lang == 'en' else "پشتڕاستکردنەوە 🔄"
        markup.add(types.InlineKeyboardButton(btn_text, callback_data="verify_channels"))
        bot.send_message(chat_id, get_welcome_text(lang), reply_markup=markup)
    else:
        btn_continue = "الانتقال للأقسام الرئيسية 📂" if lang == 'ar' else "Go to Categories 📂" if lang == 'en' else "چوون بۆ بەشەکان 📂"
        markup.add(types.InlineKeyboardButton(btn_continue, callback_data="verify_channels"))
        msg_welcome = "☕ أهلاً بك في بوت مزاجي! يمكنك الانتقال للأقسام مباشرة:" if lang == 'ar' else "☕ Welcome to Mazaji Bot! Go directly to categories:" if lang == 'en' else "☕ بەخێربێن بۆ بۆتی مزاجی! ڕاستەوخۆ بچنە بەشەکان:"
        bot.send_message(chat_id, msg_welcome, reply_markup=markup)

@bot.callback_query_handler(func=lambda call: call.data == "verify_channels")
def verify_channels_btn(call):
    user_id = call.from_user.id
    conn = get_db()
    user = conn.execute("SELECT * FROM users WHERE user_id = ?", (user_id,)).fetchone()
    lang = user['lang'] if user else 'ar'
    
    if not check_channels(user_id):
        bot.answer_callback_query(call.id, "❌ لم تشترك في جميع القنوات بعد!" if lang=='ar' else "❌ Not joined all channels!" if lang=='en' else "❌ هێشتا جۆینی هەموو کەناڵەکانت نەکردووە!", show_alert=True)
        conn.close()
        return
        
    shares = user['shares'] if user else 0
    if shares < 3:
        delete_msg_safe(call.message.chat.id, call.message.message_id)
        markup = types.InlineKeyboardMarkup()
        share_url = f"https://t.me/share/url?url=https://t.me/{bot.get_me().username}"
        
        msg_share = f"⚠️ يجب عليك مشاركة البوت مع الأصدقاء لتفعيل الأقسام." if lang=='ar' else f"⚠️ You must share the bot with friends." if lang=='en' else f"⚠️ پێویستە بۆتەکە لەگەڵ هاوڕێیاندا هاوبەش بکەيت."
        btn_share = "مشاركة مع الأصدقاء 🚀" if lang=='ar' else "Share with friends 🚀" if lang=='en' else "هاوبەشکردن لەگەڵ هاوڕێيان 🚀"
        btn_check = "اضغط هنا بعد إتمام إرسال المشاركة 🔄" if lang=='ar' else "Check after sending share 🔄" if lang=='en' else "پشکنیین دواي ناردنی هاوبەشکردن 🔄"
        
        markup.add(types.InlineKeyboardButton(btn_share, url=share_url))
        markup.add(types.InlineKeyboardButton(btn_check, callback_data="fake_share_check"))
        bot.send_message(call.message.chat.id, msg_share, reply_markup=markup)
        conn.close()
        return

    conn.execute("UPDATE users SET verified = 1 WHERE user_id = ?", (user_id,))
    conn.commit()
    conn.close()
    delete_msg_safe(call.message.chat.id, call.message.message_id)
    show_main_categories_to_user(call.message.chat.id, lang)

@bot.callback_query_handler(func=lambda call: call.data == "fake_share_check")
def fake_share_check_logic(call):
    user_id = call.from_user.id
    conn = get_db()
    conn.execute("UPDATE users SET shares = 3 WHERE user_id = ?", (user_id,))
    conn.commit()
    user = conn.execute("SELECT * FROM users WHERE user_id = ?", (user_id,)).fetchone()
    lang = user['lang'] if user else 'ar'
    conn.close()
    
    delete_msg_safe(call.message.chat.id, call.message.message_id)
    show_main_categories_to_user(call.message.chat.id, lang)

def show_main_categories_to_user(chat_id, lang, parent_id=None):
    conn = get_db()
    cats = conn.execute("SELECT * FROM categories WHERE parent_id IS ?", (parent_id,)).fetchall()
    conn.close()
    
    markup = types.InlineKeyboardMarkup(row_width=2)
    for c in cats:
        markup.add(types.InlineKeyboardButton(c['name'], callback_data=f"user_view_cat_{c['id']}"))
    
    if parent_id:
        markup.add(types.InlineKeyboardButton("⬅️ العودة للوراء", callback_data=f"user_back_to_{parent_id}"))
        
    markup.add(types.InlineKeyboardButton("⭐ إرسال رأيك وتقييمك للبوت", callback_data="user_give_review"))
    
    title = "📂 قائمة الأقسام المتوفرة:" if lang=='ar' else "📂 Available Categories:" if lang=='en' else "📂 لیستی بەشە بەردەستەکان:"
    bot.send_message(chat_id, title, reply_markup=markup)

@bot.callback_query_handler(func=lambda call: call.data.startswith("user_view_cat_"))
def user_explore_cat(call):
    cat_id = int(call.data.replace("user_view_cat_", ""))
    
    conn = get_db()
    user = conn.execute("SELECT * FROM users WHERE user_id = ?", (call.from_user.id,)).fetchone()
    lang = user['lang'] if user else 'ar'
    
    current_cat = conn.execute("SELECT * FROM categories WHERE id = ?", (cat_id,)).fetchone()
    parent_id = current_cat['parent_id'] if current_cat else None
    
    sub_cats = conn.execute("SELECT * FROM categories WHERE parent_id = ?", (cat_id,)).fetchall()
    if sub_cats:
        delete_msg_safe(call.message.chat.id, call.message.message_id)
        markup = types.InlineKeyboardMarkup(row_width=2)
        for sc in sub_cats:
            markup.add(types.InlineKeyboardButton(sc['name'], callback_data=f"user_view_cat_{sc['id']}"))
        
        markup.row(
            types.InlineKeyboardButton("⬅️ القائمة السابقة", callback_data=f"user_back_to_{parent_id}" if parent_id else "user_back_main"),
            types.InlineKeyboardButton("🏠 القائمة الرئيسية", callback_data="user_back_main")
        )
        bot.send_message(call.message.chat.id, "📁 اختر القسم الفرعي:", reply_markup=markup)
        conn.close()
        return

    messages_list = conn.execute("SELECT * FROM messages WHERE cat_id = ?", (cat_id,)).fetchall()
    conn.close()
    
    if not messages_list:
        bot.answer_callback_query(call.id, "⚠️ هذا القسم لا يحتوي على ملفات أو رسائل حالياً.", show_alert=True)
        return
    
    delete_msg_safe(call.message.chat.id, call.message.message_id)
        
    for msg in messages_list:
        markup = types.InlineKeyboardMarkup()
        if msg['yt_url']:
            markup.add(types.InlineKeyboardButton("🎥 مشاهدة شرح البوت والملف", url=msg['yt_url']))
        if 'install_url' in msg.keys() and msg['install_url']:
            markup.add(types.InlineKeyboardButton("🛠️ شرح طريقة التثبيت خطوة بخطوة", url=msg['install_url']))
            
        try:
            if msg['type'] == 'forward':
                bot.forward_message(call.message.chat.id, msg['chat_id'], msg['msg_id'])
                if msg['yt_url'] or ('install_url' in msg.keys() and msg['install_url']):
                    bot.send_message(call.message.chat.id, "👇 روابط الشروحات والتشغيل الخاصة بالملف المرفوع أعلاه:", reply_markup=markup)
            else:
                bot.send_message(call.message.chat.id, msg['content'], reply_markup=markup)
        except Exception:
            if msg['yt_url']:
                bot.send_message(call.message.chat.id, "⚠️ تعذر جلب الملف الموجه، يمكنك مشاهدة الشرح المرفق مباشرة:", reply_markup=markup)
            else:
                bot.send_message(call.message.chat.id, "❌ خطأ: هذا الملف غير متوفر حالياً.")
            
    navigation_markup = types.InlineKeyboardMarkup()
    navigation_markup.row(
        types.InlineKeyboardButton("⬅️ القائمة السابقة", callback_data=f"user_back_to_{parent_id}" if parent_id else "user_back_main"),
        types.InlineKeyboardButton("🏠 القائمة الرئيسية", callback_data="user_back_main")
    )
    bot.send_message(call.message.chat.id, "⚙️ يمكنك اختيار أحد الخيارات التالية للمتابعة:", reply_markup=navigation_markup)

@bot.callback_query_handler(func=lambda call: call.data.startswith("user_back_to_"))
def user_back_to_specific_parent(call):
    delete_msg_safe(call.message.chat.id, call.message.message_id)
    parent_id = int(call.data.replace("user_back_to_", ""))
    
    conn = get_db()
    user = conn.execute("SELECT * FROM users WHERE user_id = ?", (call.from_user.id,)).fetchone()
    lang = user['lang'] if user else 'ar'
    
    current_cat = conn.execute("SELECT * FROM categories WHERE id = ?", (parent_id,)).fetchone()
    grand_parent_id = current_cat['parent_id'] if current_cat else None
    
    sub_cats = conn.execute("SELECT * FROM categories WHERE parent_id = ?", (parent_id,)).fetchall()
    conn.close()
    
    markup = types.InlineKeyboardMarkup(row_width=2)
    for sc in sub_cats:
        markup.add(types.InlineKeyboardButton(sc['name'], callback_data=f"user_view_cat_{sc['id']}"))
    
    markup.row(
        types.InlineKeyboardButton("⬅️ القائمة السابقة", callback_data=f"user_back_to_{grand_parent_id}" if grand_parent_id else "user_back_main"),
        types.InlineKeyboardButton("🏠 القائمة الرئيسية", callback_data="user_back_main")
    )
    bot.send_message(call.message.chat.id, "📁 قائمة الأقسام:", reply_markup=markup)

@bot.callback_query_handler(func=lambda call: call.data == "user_back_main")
def user_back_main_btn(call):
    delete_msg_safe(call.message.chat.id, call.message.message_id)
    conn = get_db()
    user = conn.execute("SELECT * FROM users WHERE user_id = ?", (call.from_user.id,)).fetchone()
    lang = user['lang'] if user else 'ar'
    conn.close()
    show_main_categories_to_user(call.message.chat.id, lang)

# --- خيار الآدمن ولوحة التحكم (/admin) ---
@bot.message_handler(commands=['admin'])
def admin_cmd(message):
    if message.from_user.id not in ADMINS: return
    delete_msg_safe(message.chat.id, message.message_id)
    show_admin_panel(message.chat.id)

def show_admin_panel(chat_id):
    markup = types.InlineKeyboardMarkup(row_width=1)
    markup.add(
        types.InlineKeyboardButton("➕ إضافة قسم", callback_data="adm_add_cat"),
        types.InlineKeyboardButton("📝 لوحة تعديل (أقسام / رسائل / APK / يوتيوب)", callback_data="adm_edit_hub"),
        types.InlineKeyboardButton("🗑️ حذف قسم أو رسالة", callback_data="adm_del_cat"),
        types.InlineKeyboardButton("📢 إدارة الروابط والقنوات الإجبارية", callback_data="adm_manage_ch"),
        types.InlineKeyboardButton("⭐ عرض الآراء والتقييمات", callback_data="adm_view_reviews")
    )
    bot.send_message(chat_id, "⚙️ لوحة تحكم الأدمن الفولاذية. اختر الإجراء:", reply_markup=markup)

@bot.callback_query_handler(func=lambda call: call.data == "adm_add_cat")
def adm_add_cat_start(call):
    delete_msg_safe(call.message.chat.id, call.message.message_id)
    msg = bot.send_message(call.message.chat.id, "أرسل اسم القسم الجديد المراد إنشائه:")
    bot.register_next_step_handler(msg, save_new_category)

def save_new_category(message):
    cat_name = message.text
    delete_msg_safe(message.chat.id, message.message_id)
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("INSERT INTO categories (name) VALUES (?)", (cat_name,))
    cat_id = cursor.lastrowid
    conn.commit()
    conn.close()
    ask_section_type(message.chat.id, cat_id)

def ask_section_type(chat_id, cat_id):
    markup = types.InlineKeyboardMarkup()
    markup.row(
        types.InlineKeyboardButton("📁 إضافة قسم فرعي داخله", callback_data=f"add_sub_inside_{cat_id}"),
        types.InlineKeyboardButton("✉️ رفع (رسالة أو تطبيق APK أو ملف)", callback_data=f"add_msg_inside_{cat_id}")
    )
    bot.send_message(chat_id, "ماذا تريد أن تضيف داخل هذا القسم الآن؟", reply_markup=markup)

@bot.callback_query_handler(func=lambda call: call.data.startswith("add_sub_inside_"))
def add_sub_inside_logic(call):
    delete_msg_safe(call.message.chat.id, call.message.message_id)
    parent_id = int(call.data.replace("add_sub_inside_", ""))
    admin_state[call.from_user.id] = {'parent_id': parent_id}
    msg = bot.send_message(call.message.chat.id, "أدخل اسم القسم الفرعي الجديد:")
    bot.register_next_step_handler(msg, save_sub_category)

def save_sub_category(message):
    sub_name = message.text
    delete_msg_safe(message.chat.id, message.message_id)
    parent_id = admin_state[message.from_user.id]['parent_id']
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("INSERT INTO categories (name, parent_id) VALUES (?, ?)", (sub_name, parent_id))
    new_cat_id = cursor.lastrowid
    conn.commit()
    conn.close()
    bot.send_message(message.chat.id, f"✅ تم إنشاء القسم الفرعي ({sub_name}) بنجاح.")
    ask_section_type(message.chat.id, new_cat_id)

@bot.callback_query_handler(func=lambda call: call.data.startswith("add_msg_inside_"))
def add_msg_inside_logic(call):
    delete_msg_safe(call.message.chat.id, call.message.message_id)
    cat_id = int(call.data.replace("add_msg_inside_", ""))
    admin_state[call.from_user.id] = {'cat_id': cat_id}
    
    markup = types.InlineKeyboardMarkup()
    markup.row(
        types.InlineKeyboardButton("🔄 رسالة موجهة مِ القناة (Forward / Apk)", callback_data="msg_type_forward"),
        types.InlineKeyboardButton("✍️ كتابة رسالة نصية يدوية", callback_data="msg_type_text")
    )
    bot.send_message(call.message.chat.id, "اختر طريقة إضافة المحتوى أو الـ APK الحصري:", reply_markup=markup)

@bot.callback_query_handler(func=lambda call: call.data.startswith("msg_type_"))
def choose_msg_type_capture(call):
    delete_msg_safe(call.message.chat.id, call.message.message_id)
    m_type = call.data.replace("msg_type_", "")
    admin_state[call.from_user.id]['type'] = m_type
    
    if m_type == 'forward':
        msg = bot.send_message(call.message.chat.id, "قم بعمل تحويل (Forward) للرسالة أو ملف الـ APK من القناة إلى هنا مباشرة:")
    else:
        msg = bot.send_message(call.message.chat.id, "أكتب نص الرسالة التي تريد إظهارها للأعضاء هنا:")
    bot.register_next_step_handler(msg, process_admin_message_content)

def process_admin_message_content(message):
    user_id = message.from_user.id
    if user_id not in admin_state: return
    m_type = admin_state[user_id]['type']
    
    if m_type == 'forward':
        if not message.forward_from_chat:
            delete_msg_safe(message.chat.id, message.message_id)
            bot.send_message(message.chat.id, "❌ خطأ! لم تقم بتحويل الملف أو الرسالة بشكل صحيح. أعد المحاولة.")
            show_admin_panel(message.chat.id)
            return
        admin_state[user_id]['content'] = ""
        admin_state[user_id]['chat_id'] = str(message.forward_from_chat.id)
        admin_state[user_id]['msg_id'] = message.forward_from_message_id
    else:
        admin_state[user_id]['content'] = message.text
        admin_state[user_id]['chat_id'] = ""
        admin_state[user_id]['msg_id'] = 0
        
    delete_msg_safe(message.chat.id, message.message_id)
    msg = bot.send_message(message.chat.id, "أرسل الآن (رابط شرح يوتيوب) للملف، أو أرسل 'لا يوجد' للتخطي:")
    bot.register_next_step_handler(msg, process_admin_install_url)

def process_admin_install_url(message):
    user_id = message.from_user.id
    if user_id not in admin_state: return
    yt_url = message.text if message.text and ("youtube" in message.text or "youtu.be" in message.text) else None
    admin_state[user_id]['yt_url'] = yt_url
    
    delete_msg_safe(message.chat.id, message.message_id)
    msg = bot.send_message(message.chat.id, "أرسل الآن (رابط شرح التثبيت يوتيوب) للملَف، أو أرسل 'لا يوجد' للتخطي:")
    bot.register_next_step_handler(msg, finalize_adding_message)

def finalize_adding_message(message):
    user_id = message.from_user.id
    if user_id not in admin_state: return
    install_url = message.text if message.text and ("youtube" in message.text or "youtu.be" in message.text) else None
    state = admin_state[user_id]
    
    delete_msg_safe(message.chat.id, message.message_id)
    conn = get_db()
    conn.execute("INSERT INTO messages (cat_id, type, content, chat_id, msg_id, yt_url, install_url) VALUES (?, ?, ?, ?, ?, ?, ?)",
                 (state['cat_id'], state['type'], state['content'], state['chat_id'], state['msg_id'], state['yt_url'], install_url))
    conn.commit()
    conn.close()
    
    bot.send_message(message.chat.id, "✅ تم حفظ الرسالة بنجاح وربط زري الشرح والتثبيت الحصريين داخل القسم!")
    if user_id in admin_state: del admin_state[user_id]
    show_admin_panel(message.chat.id)

# --- لوحة التعديل الشاملة الذكية المحدثة حسب طلبك المباشر ---
@bot.callback_query_handler(func=lambda call: call.data == "adm_edit_hub")
def adm_edit_hub_main(call):
    delete_msg_safe(call.message.chat.id, call.message.message_id)
    conn = get_db()
    cats = conn.execute("SELECT * FROM categories").fetchall()
    conn.close()
    
    markup = types.InlineKeyboardMarkup()
    for c in cats:
        markup.add(types.InlineKeyboardButton(f"📁 قسم: {c['name']}", callback_data=f"hub_choose_cat_{c['id']}"))
    markup.add(types.InlineKeyboardButton("⬅️ العودة للوحة الإدارة", callback_data="back_to_admin"))
    bot.send_message(call.message.chat.id, "📝 لوحة التعديل الحرة والموسعة، اختر القسم الذي تريد إجراء تعديلات عليه:", reply_markup=markup)

@bot.callback_query_handler(func=lambda call: call.data.startswith("hub_choose_cat_"))
def hub_cat_freedom_options(call):
    delete_msg_safe(call.message.chat.id, call.message.message_id)
    cat_id = int(call.data.replace("hub_choose_cat_", ""))
    
    conn = get_db()
    cat_info = conn.execute("SELECT * FROM categories WHERE id = ?", (cat_id,)).fetchone()
    # التحقق من وجود رسائل داخل هذا القسم لتمريرها لخيار التعديل
    msg_info = conn.execute("SELECT * FROM messages WHERE cat_id = ? LIMIT 1", (cat_id,)).fetchone()
    conn.close()
    
    cat_name = cat_info['name'] if cat_info else ""
    msg_id_str = f"_{msg_info['id']}" if msg_info else "_none"
    
    markup = types.InlineKeyboardMarkup(row_width=1)
    markup.add(
        types.InlineKeyboardButton(f"📝 تعديل اسم القسم ({cat_name})", callback_data=f"edit_cname_{cat_id}"),
        types.InlineKeyboardButton("➕ إضافة ملف/رسالة داخل هذا القسم", callback_data=f"add_msg_inside_{cat_id}"),
        types.InlineKeyboardButton("📁 تعديل قسم فرعي تابع له", callback_data="hub_edit_cats"),
        types.InlineKeyboardButton("✉️ تعديل الرسالة الي جوا القسم", callback_data=f"subedit_content{msg_id_str}" if msg_info else "hub_no_msg_alert"),
        types.InlineKeyboardButton("🎥 تعديل رابط الشرح يوتيوب", callback_data=f"subedit_yt{msg_id_str}" if msg_info else "hub_no_msg_alert"),
        types.InlineKeyboardButton("🛠️ تعديل رابط التثبيت يوتيوب", callback_data=f"subedit_inst{msg_id_str}" if msg_info else "hub_no_msg_alert"),
        types.InlineKeyboardButton("⬅️ رجوع لقائمة الأقسام", callback_data="adm_edit_hub")
    )
    bot.send_message(call.message.chat.id, f"⚙️ التحكم الكامل بالقسم [ {cat_name} ]. اختر ماذا تريد أن تفعل بالحرية الكاملة:", reply_markup=markup)

@bot.callback_query_handler(func=lambda call: call.data == "hub_no_msg_alert")
def hub_no_msg_alert_logic(call):
    bot.answer_callback_query(call.id, "⚠️ لا توجد رسائل أو ملفات مرفوعة داخل هذا القسم حالياً لتعديلها! قم بإضافة ملف أولاً.", show_alert=True)

@bot.callback_query_handler(func=lambda call: call.data == "hub_edit_cats")
def hub_edit_cats_list(call):
    delete_msg_safe(call.message.chat.id, call.message.message_id)
    conn = get_db()
    cats = conn.execute("SELECT * FROM categories").fetchall()
    conn.close()
    markup = types.InlineKeyboardMarkup()
    for c in cats:
        markup.add(types.InlineKeyboardButton(f"📁 قسم: {c['name']}", callback_data=f"hub_choose_cat_{c['id']}"))
    markup.add(types.InlineKeyboardButton("⬅️ عودة", callback_data="adm_edit_hub"))
    bot.send_message(call.message.chat.id, "اختر القسم المطلوب للتحكم بتفاصيله الكاملة:", reply_markup=markup)

@bot.callback_query_handler(func=lambda call: call.data.startswith("edit_cname_"))
def process_edit_cname_step1(call):
    delete_msg_safe(call.message.chat.id, call.message.message_id)
    cat_id = int(call.data.replace("edit_cname_", ""))
    admin_state[call.from_user.id] = {'edit_cat_id': cat_id}
    msg = bot.send_message(call.message.chat.id, "أدخل الاسم الجديد البديل لهذا القسم فوراً:")
    bot.register_next_step_handler(msg, save_edited_cname_final)

def save_edited_cname_final(message):
    new_name = message.text
    user_id = message.from_user.id
    if user_id not in admin_state: return
    cat_id = admin_state[user_id]['edit_cat_id']
    
    delete_msg_safe(message.chat.id, message.message_id)
    conn = get_db()
    conn.execute("UPDATE categories SET name = ? WHERE id = ?", (new_name, cat_id))
    conn.commit()
    conn.close()
    bot.send_message(message.chat.id, "✅ تم تحديث اسم القسم بنجاح وإعادة البناء!")
    if user_id in admin_state: del admin_state[user_id]
    show_admin_panel(message.chat.id)

@bot.callback_query_handler(func=lambda call: call.data.startswith("subedit_"))
def subedit_router(call):
    delete_msg_safe(call.message.chat.id, call.message.message_id)
    parts = call.data.split("_")
    mode = parts[1]
    target_id = int(parts[2].replace("content", "").replace("yt", "").replace("inst", ""))
    
    admin_state[call.from_user.id] = {'target_id': target_id, 'mode': mode}
    
    if "content" in mode:
        markup = types.InlineKeyboardMarkup()
        markup.row(types.InlineKeyboardButton("🔄 تحويل ملف APK / رسالة جديدة", callback_data="submode_forward"),
                   types.InlineKeyboardButton("✍️ كتابة نص يدوي جديد", callback_data="submode_text"))
        bot.send_message(call.message.chat.id, "اختر نوع المحتوى البديل الجديد:", reply_markup=markup)
    elif "yt" in mode:
        msg = bot.send_message(call.message.chat.id, "أرسل رابط اليوتيوب الجديد لـ (شرح الملف):")
        bot.register_next_step_handler(msg, save_subedit_yt_final)
    elif "inst" in mode:
        msg = bot.send_message(call.message.chat.id, "أرسل رابط اليوتيوب الجديد لـ (طريقة التثبيت):")
        bot.register_next_step_handler(msg, save_subedit_inst_final)

@bot.callback_query_handler(func=lambda call: call.data.startswith("submode_"))
def submode_capture(call):
    delete_msg_safe(call.message.chat.id, call.message.message_id)
    smode = call.data.replace("submode_", "")
    user_id = call.from_user.id
    admin_state[user_id]['smode'] = smode
    
    if smode == 'forward':
        msg = bot.send_message(call.message.chat.id, "قم بعمل تحويل (Forward) لملف الـ APK أو الرسالة الجديدة من القناة الآن:")
    else:
        msg = bot.send_message(call.message.chat.id, "اكتب النص اليدوي البديل والجديد بالكامل هنا:")
    bot.register_next_step_handler(msg, save_subedit_content_final)

def save_subedit_content_final(message):
    user_id = message.from_user.id
    if user_id not in admin_state: return
    state = admin_state[user_id]
    smode = state['smode']
    
    if smode == 'forward':
        if not message.forward_from_chat:
            delete_msg_safe(message.chat.id, message.message_id)
            bot.send_message(message.chat.id, "❌ خطأ في التحويل الفوري. تم إلغاء العملية.")
            show_admin_panel(message.chat.id)
            return
        m_type, content, chat_id, msg_id = 'forward', "", str(message.forward_from_chat.id), message.forward_from_message_id
    else:
        m_type, content, chat_id, msg_id = 'text', message.text, "", 0
        
    delete_msg_safe(message.chat.id, message.message_id)
    conn = get_db()
    conn.execute("UPDATE messages SET type=?, content=?, chat_id=?, msg_id=? WHERE id=?", (m_type, content, chat_id, msg_id, state['target_id']))
    conn.commit()
    conn.close()
    
    bot.send_message(message.chat.id, "✅ تم تعديل وحفظ محتوى الرسالة / ملف الـ APK بنجاح!")
    if user_id in admin_state: del admin_state[user_id]
    show_admin_panel(message.chat.id)

def save_subedit_yt_final(message):
    user_id = message.from_user.id
    if user_id not in admin_state: return
    yt_url = message.text if message.text and ("youtube" in message.text or "youtu.be" in message.text) else None
    target_id = admin_state[user_id]['target_id']
    
    delete_msg_safe(message.chat.id, message.message_id)
    conn = get_db()
    conn.execute("UPDATE messages SET yt_url=? WHERE id=?", (yt_url, target_id))
    conn.commit()
    conn.close()
    
    bot.send_message(message.chat.id, "✅ تم تحديث رابط زر الشرح بنجاح!")
    if user_id in admin_state: del admin_state[user_id]
    show_admin_panel(message.chat.id)

def save_subedit_inst_final(message):
    user_id = message.from_user.id
    if user_id not in admin_state: return
    install_url = message.text if message.text and ("youtube" in message.text or "youtu.be" in message.text) else None
    target_id = admin_state[user_id]['target_id']
    
    delete_msg_safe(message.chat.id, message.message_id)
    conn = get_db()
    conn.execute("UPDATE messages SET install_url=? WHERE id=?", (install_url, target_id))
    conn.commit()
    conn.close()
    
    bot.send_message(message.chat.id, "✅ تم تحديث رابط زر التثبيت بنجاح!")
    if user_id in admin_state: del admin_state[user_id]
    show_admin_panel(message.chat.id)

# --- استكمال بقية العمليات القياسية وحذف الأقسام ---
@bot.callback_query_handler(func=lambda call: call.data == "adm_del_cat")
def adm_delete_cat_list(call):
    delete_msg_safe(call.message.chat.id, call.message.message_id)
    conn = get_db()
    cats = conn.execute("SELECT * FROM categories").fetchall()
    conn.close()
    
    markup = types.InlineKeyboardMarkup()
    for c in cats:
        markup.add(types.InlineKeyboardButton(f"🗑️ حذف: {c['name']}", callback_data=f"del_target_{c['id']}"))
    markup.add(types.InlineKeyboardButton("⬅️ العودة للوحة الأدمن", callback_data="back_to_admin"))
    bot.send_message(call.message.chat.id, "اختر القسم المراد حذفه ومسح محتوياته نهائياً:", reply_markup=markup)

@bot.callback_query_handler(func=lambda call: call.data.startswith("del_target_"))
def finalize_delete_cat(call):
    delete_msg_safe(call.message.chat.id, call.message.message_id)
    cat_id = int(call.data.replace("del_target_", ""))
    conn = get_db()
    conn.execute("DELETE FROM categories WHERE id = ? OR parent_id = ?", (cat_id, cat_id))
    conn.execute("DELETE FROM messages WHERE cat_id = ?", (cat_id,))
    conn.commit()
    conn.close()
    bot.send_message(call.message.chat.id, "✅ تم مسح القسم ومحتوياته بالكامل من النظام.")
    show_admin_panel(call.message.chat.id)

@bot.callback_query_handler(func=lambda call: call.data == "adm_manage_ch")
def adm_manage_channels_panel(call):
    delete_msg_safe(call.message.chat.id, call.message.message_id)
    conn = get_db()
    channels = conn.execute("SELECT * FROM channels").fetchall()
    conn.close()
    
    text = "📢 القنوات الإجبارية الحالية المضافة لشروط البوت:\n\n"
    for index, ch in enumerate(channels, start=1):
        ch_title = get_channel_name(ch['channel_id'], "قناة مشفرة/خاص")
        text += f"{index}. الاسم: **{ch_title}**\n🆔 الـ ID: `{ch['channel_id']}` \n🔗 الرابط: {ch['link']}\n\n"
        
    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton("➕ إضافة قناة جديدة للشروط", callback_data="add_new_channel_req"))
    markup.add(types.InlineKeyboardButton("🧹 تفريغ وحذف كل القنوات", callback_data="clear_all_channels_req"))
    markup.add(types.InlineKeyboardButton("⬅️ العودة للوحة الأدمن", callback_data="back_to_admin"))
    bot.send_message(call.message.chat.id, text, parse_mode="Markdown", reply_markup=markup)

@bot.callback_query_handler(func=lambda call: call.data == "add_new_channel_req")
def add_new_channel_step1(call):
    delete_msg_safe(call.message.chat.id, call.message.message_id)
    msg = bot.send_message(call.message.chat.id, "أرسل معرف القناة الرقمي (مثال يبدأ بـ سالب 100: `-100123456789`) ويجب أن يكون البوت مشرفاً فيها أولاً:")
    bot.register_next_step_handler(msg, add_new_channel_step2)

def add_new_channel_step2(message):
    ch_id = message.text.strip()
    delete_msg_safe(message.chat.id, message.message_id)
    admin_state[message.from_user.id] = {'ch_id': ch_id}
    msg = bot.send_message(call.message.chat.id, "أرسل الآن رابط الدعوة الخاص بالقناة ليضغط عليه المستخدم للاشتراك:")
    bot.register_next_step_handler(msg, add_new_channel_finalize)

def add_new_channel_finalize(message):
    user_id = message.from_user.id
    if user_id not in admin_state: return
    link = message.text.strip()
    ch_id = admin_state[user_id]['ch_id']
    
    delete_msg_safe(message.chat.id, message.message_id)
    conn = get_db()
    conn.execute("INSERT OR REPLACE INTO channels (channel_id, link) VALUES (?, ?)", (ch_id, link))
    conn.commit()
    conn.close()
    
    bot.send_message(message.chat.id, "✅ تم حفظ القناة وإدراجها ضمن الشروط الإجبارية بنجاح!")
    if user_id in admin_state: del admin_state[user_id]
    show_admin_panel(message.chat.id)

@bot.callback_query_handler(func=lambda call: call.data == "clear_all_channels_req")
def clear_channels_req_logic(call):
    delete_msg_safe(call.message.chat.id, call.message.message_id)
    conn = get_db()
    conn.execute("DELETE FROM channels")
    conn.commit()
    conn.close()
    bot.send_message(call.message.chat.id, "🧹 تم مسح وإلغاء جميع القنوات الإجبارية بنجاح.")
    show_admin_panel(call.message.chat.id)

@bot.callback_query_handler(func=lambda call: call.data == "user_give_review")
def user_give_review_start(call):
    delete_msg_safe(call.message.chat.id, call.message.message_id)
    markup = types.InlineKeyboardMarkup()
    markup.row(
        types.InlineKeyboardButton("⭐", callback_data="rate_1"),
        types.InlineKeyboardButton("⭐⭐", callback_data="rate_2"),
        types.InlineKeyboardButton("⭐⭐⭐", callback_data="rate_3"),
        types.InlineKeyboardButton("⭐⭐⭐⭐", callback_data="rate_4"),
        types.InlineKeyboardButton("⭐⭐⭐⭐⭐", callback_data="rate_5")
    )
    bot.send_message(call.message.chat.id, "اختر عدد النجوم لتقييم البوت:", reply_markup=markup)

@bot.callback_query_handler(func=lambda call: call.data.startswith("rate_"))
def user_capture_stars(call):
    delete_msg_safe(call.message.chat.id, call.message.message_id)
    stars = call.data.replace("rate_", "")
    admin_state[call.from_user.id] = {'stars': stars}
    msg = bot.send_message(call.message.chat.id, "اكتب رأيك أو تعليقك الشخصي حول البوت:")
    bot.register_next_step_handler(msg, save_user_review)

def save_user_review(message):
    text = message.text
    user_id = message.from_user.id
    if user_id not in admin_state: return
    stars = admin_state[user_id]['stars']
    
    delete_msg_safe(message.chat.id, message.message_id)
    conn = get_db()
    conn.execute("INSERT INTO reviews (user_id, rating, text) VALUES (?, ?, ?)", (user_id, f"{stars} نجوم", text))
    conn.commit()
    conn.close()
    
    bot.send_message(message.chat.id, "❤️ شكراً جزيلاً لتقييمك، تم إرساله للإدارة!")
    if user_id in admin_state: del admin_state[user_id]

@bot.callback_query_handler(func=lambda call: call.data == "adm_view_reviews")
def adm_view_reviews_logic(call):
    delete_msg_safe(call.message.chat.id, call.message.message_id)
    conn = get_db()
    reviews = conn.execute("SELECT * FROM reviews ORDER BY id DESC LIMIT 10").fetchall()
    conn.close()
    
    text = "📊 آراء وتقي

