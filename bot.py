import os
import json
from datetime import datetime, timezone, timedelta
from pyrogram import Client, filters
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton

# ================== SETTINGS ==================
API_ID = os.getenv("API_ID")
API_HASH = os.getenv("API_HASH")
BOT_TOKEN = os.getenv("BOT_TOKEN")
MONITOR_GROUP = os.getenv("MONITOR_GROUP")

if not all([API_ID, API_HASH, BOT_TOKEN, MONITOR_GROUP]):
    print("❌ ERROR: Environment variables not found!")
    exit(1)

API_ID = int(API_ID)
MONITOR_GROUP = int(MONITOR_GROUP)

DATA_FILE = "monitoring_data.json"
DUTY_FILE = "duty_data.json"

# Faqat shu guruhda /onduty va /offduty ishlaydi
DUTY_GROUP = -5225538611

# O'zbekiston vaqti — doim UTC+5, DST yo'q, shuning uchun serverning
# o'z vaqt zonasidan qat'i nazar to'g'ri natija beradi
UZ_TZ = timezone(timedelta(hours=5))


def uz_now_str():
    """O'zbekiston vaqtida, AM/PM formatida hozirgi vaqt (masalan: 03:45 PM)"""
    return datetime.now(UZ_TZ).strftime("%I:%M %p")

# ================== GLOBAL KEYWORDS ==================
GLOBAL_KEYWORDS = [
    "fleet", "@fleet_brian", "@fleett_andrew", "@fleet_ray",
    "@fleet_nate",
]

# ================== TEAM GROUPS ==================
TEAM_GROUPS = {
    -4832969847, -1003270883637, -4833592645, -1003942097344,
    -5197169771, -4860018912, -5148488914, -1003940854650,
    -4714020991, -4747736622, -1003680938723, -5097560339,
}

# Barcha buyruq nomlari — bular umumiy matn-tekshiruvchi handlerlardan
# (monitor / mention-check) chetlab o'tkaziladi, shunda ular hech qachon
# bir-birini "yutib qo'ymaydi".
DUTY_COMMANDS = ["onduty", "on", "offduty", "off", "list", "leave"]
MONITOR_COMMANDS = ["startlist", "stoplist", "showlist", "clear", "add"]
ALL_COMMANDS = DUTY_COMMANDS + MONITOR_COMMANDS

# ================== GLOBAL VARIABLES ==================
issue_list = {}            # {chat_id: issue_name}
monitoring_active = False

# {user_id: {"username": str, "status": "on"|"off", "time": str}}
duty_status = {}


# ================== DATA: MONITORING ==================
def load_data():
    global issue_list, monitoring_active
    try:
        if os.path.exists(DATA_FILE):
            with open(DATA_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                issue_list = data.get("issue_list", {})
                monitoring_active = data.get("monitoring_active", False)
            print(f"✅ Loaded {len(issue_list)} issues | Active: {monitoring_active}")
        else:
            print(f"ℹ️ {DATA_FILE} not found. New file created.")
            save_data()
    except Exception as e:
        print(f"⚠️ Load error: {e}")


def save_data():
    try:
        data = {"issue_list": issue_list, "monitoring_active": monitoring_active}
        with open(DATA_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=4, ensure_ascii=False)
        print(f"💾 Saved | Issues: {len(issue_list)}")
    except Exception as e:
        print(f"❌ Save error: {e}")


# ================== DATA: DUTY SYSTEM ==================
def load_duty():
    global duty_status
    try:
        if os.path.exists(DUTY_FILE):
            with open(DUTY_FILE, "r", encoding="utf-8") as f:
                raw = json.load(f)
                # JSON kalitlari string bo'lib qaytadi — int'ga o'tkazamiz
                duty_status = {int(k): v for k, v in raw.items()}
            print(f"✅ Duty holati yuklandi: {len(duty_status)} kishi")
        else:
            print(f"ℹ️ {DUTY_FILE} topilmadi. Yangi fayl yaratiladi.")
            save_duty()
    except Exception as e:
        print(f"⚠️ Duty load error: {e}")


def save_duty():
    try:
        with open(DUTY_FILE, "w", encoding="utf-8") as f:
            json.dump(duty_status, f, indent=4, ensure_ascii=False)
    except Exception as e:
        print(f"❌ Duty save error: {e}")


def get_sender_info(message):
    """Oddiy user yoki anonim admin/kanal uchun (id, username, is_anon) qaytaradi."""
    user = message.from_user
    if user:
        username = user.username or user.first_name or "Unknown"
        return user.id, username, False
    elif message.sender_chat:
        # Anonim admin yoki kanal nomidan yuborilgan xabar
        username = message.sender_chat.title or "Unknown"
        return message.sender_chat.id, username, True
    return None, None, False


def format_duty_name(data):
    """Ro'yxatda ko'rsatish uchun ism: anonim bo'lsa linksiz 'Anonymous', bo'lmasa @username."""
    if data.get("is_anon"):
        return "Anonymous"
    return f"@{data['username']}"


load_data()
load_duty()
print("🚀 TopgFleet Monitoring Bot is starting...")

app = Client("TopgFleet_Monitor", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN)


# ====================== MONITORING COMMANDS (group=0) ======================

@app.on_message(filters.command("startlist") & filters.chat(MONITOR_GROUP), group=0)
async def start_list(client, message):
    try:
        global monitoring_active
        monitoring_active = True
        save_data()
        await client.send_message(MONITOR_GROUP, "✅ **Monitoring List is now ACTIVE**")
    except Exception as e:
        print(f"❌ start_list error: {e}")
    finally:
        try: await message.delete()
        except: pass


@app.on_message(filters.command("stoplist") & filters.chat(MONITOR_GROUP), group=0)
async def stop_list(client, message):
    try:
        global monitoring_active
        monitoring_active = False
        save_data()
        await client.send_message(MONITOR_GROUP, "⛔ **Monitoring List is now STOPPED**")
    except Exception as e:
        print(f"❌ stop_list error: {e}")
    finally:
        try: await message.delete()
        except: pass


@app.on_message(filters.command("showlist") & filters.chat(MONITOR_GROUP), group=0)
async def show_list(client, message):
    try:
        if not issue_list:
            await client.send_message(MONITOR_GROUP, "📋 **Issue List is empty.**")
            return

        text = "📋 **Current Monitoring List:**\n\n"
        for chat_id, issue_name in issue_list.items():
            try:
                chat = await client.get_chat(chat_id)
                group_name = chat.title or f"Group {chat_id}"
                link = f"https://t.me/{chat.username}" if chat.username else f"https://t.me/c/{str(chat_id).replace('-100', '')}"
            except Exception:
                group_name = f"Group {chat_id}"
                link = "#"
            text += f"• `{group_name}` — **[{issue_name}]({link})**\n"

        await client.send_message(MONITOR_GROUP, text, disable_web_page_preview=True)
    except Exception as e:
        print(f"❌ show_list error: {e}")
    finally:
        try: await message.delete()
        except: pass


@app.on_message(filters.command("clear") & filters.chat(MONITOR_GROUP), group=0)
async def clear_issue(client, message):
    try:
        if len(message.command) < 2:
            await client.send_message(
                MONITOR_GROUP,
                "❌ **Usage:**\n`/clear <issue name>`\n`/clear name1, name2`\n`/clear all`"
            )
            return

        full_text = " ".join(message.command[1:]).strip()

        if full_text.lower() == "all":
            count = len(issue_list)
            issue_list.clear()
            save_data()
            await client.send_message(MONITOR_GROUP, f"🗑️ **All issues cleared.** ({count} items)")
            return

        raw_targets = [x.strip().lower() for x in full_text.split(",") if x.strip()]
        removed = []

        for chat_id, issue_name in list(issue_list.items()):
            issue_lower = issue_name.lower()
            group_name = ""
            try:
                chat = await client.get_chat(chat_id)
                group_name = (chat.title or "").lower()
            except Exception:
                pass

            for target in raw_targets:
                if target in issue_lower or target in group_name or issue_lower in target:
                    removed.append((issue_name, chat_id))
                    del issue_list[chat_id]
                    break

        save_data()

        if removed:
            text = "✅ **Removed:**\n\n"
            for issue_name, chat_id in removed:
                try:
                    chat = await client.get_chat(chat_id)
                    group_name = chat.title or f"Group {chat_id}"
                    link = f"https://t.me/{chat.username}" if chat.username else f"https://t.me/c/{str(chat_id).replace('-100', '')}"
                    text += f"• `{group_name}` — **[{issue_name}]({link})**\n"
                except Exception:
                    text += f"• **{issue_name}**\n"
            await client.send_message(MONITOR_GROUP, text, disable_web_page_preview=True)
        else:
            await client.send_message(MONITOR_GROUP, "❌ No matching issue found.\nUse /showlist")
    except Exception as e:
        print(f"❌ clear_issue error: {e}")
    finally:
        try: await message.delete()
        except: pass


# ====================== ADD COMMAND (faqat monitoring ACTIVE bo'lganda ishlaydi) ======================
@app.on_message(filters.command("add") & filters.group, group=0)
async def add_issue(client, message):
    try:
        if not monitoring_active:
            return  # Inactive bo'lsa hech narsa qo'shilmaydi

        if len(message.command) < 2:
            return

        issue_name = " ".join(message.command[1:]).strip()
        chat_id = message.chat.id
        issue_list[chat_id] = issue_name
        save_data()
        print(f"✅ Issue added/updated: {chat_id} → {issue_name}")
    except Exception as e:
        print(f"❌ add_issue error: {e}")
    finally:
        try: await message.delete()
        except: pass


# ====================== DUTY SYSTEM COMMANDS (group=0) ======================

@app.on_message(filters.command(["onduty", "on"]) & filters.chat(DUTY_GROUP), group=0)
async def set_onduty(client, message):
    try:
        uid, username, is_anon = get_sender_info(message)
        if not uid:
            return

        now = uz_now_str()
        duty_status[uid] = {"username": username, "status": "on", "time": now, "is_anon": is_anon}
        save_duty()

        display_name = "Anonymous" if is_anon else f"@{username}"
        await message.reply_text(f"✅ **Noted**\n{display_name} — On Duty ({now})", quote=True)
    except Exception as e:
        print(f"❌ set_onduty error: {e}")


@app.on_message(filters.command(["offduty", "off"]) & filters.chat(DUTY_GROUP), group=0)
async def set_offduty(client, message):
    try:
        uid, username, is_anon = get_sender_info(message)
        if not uid:
            return

        now = uz_now_str()
        duty_status[uid] = {"username": username, "status": "off", "time": now, "is_anon": is_anon}
        save_duty()

        display_name = "Anonymous" if is_anon else f"@{username}"
        await message.reply_text(f"✅ **Noted**\n{display_name} — Off Duty ({now})", quote=True)
    except Exception as e:
        print(f"❌ set_offduty error: {e}")


@app.on_message(filters.command("list") & filters.chat(DUTY_GROUP), group=0)
async def show_duty_list(client, message):
    try:
        if not duty_status:
            await message.reply_text("📋 Hozir hech kim status qo'ymagan.", quote=True)
            return

        on_duty = []
        off_duty = []

        for data in duty_status.values():
            line = f"{format_duty_name(data)} ({data['time']})"
            if data["status"] == "on":
                on_duty.append(line)
            else:
                off_duty.append(line)

        text = "**Duty List**\n\n"
        text += (f"**On Duty ({len(on_duty)}):**\n" + "\n".join(on_duty) + "\n\n") if on_duty else "**On Duty:** Hech kim yo'q\n\n"
        text += (f"**Off Duty ({len(off_duty)}):**\n" + "\n".join(off_duty)) if off_duty else "**Off Duty:** Hech kim yo'q"

        await message.reply_text(text, quote=True)
    except Exception as e:
        print(f"❌ show_duty_list error: {e}")


@app.on_message(filters.command("leave") & filters.chat(DUTY_GROUP), group=0)
async def leave_duty(client, message):
    """Foydalanuvchini duty ro'yxatidan butunlay o'chiradi (on/off holatidan qat'i nazar)"""
    try:
        uid, username, is_anon = get_sender_info(message)
        if not uid:
            return

        if uid in duty_status:
            del duty_status[uid]
            save_duty()
            display_name = "Anonymous" if is_anon else f"@{username}"
            await message.reply_text(f"👋 {display_name} — ro'yxatdan chiqarildi", quote=True)
        else:
            await message.reply_text("ℹ️ Siz allaqachon ro'yxatda emassiz.", quote=True)
    except Exception as e:
        print(f"❌ leave_duty error: {e}")


# ====================== MENTION CHECK (group=1, buyruqlardan keyin) ======================
@app.on_message(
    filters.text & filters.group & ~filters.command(ALL_COMMANDS),
    group=1
)
async def check_off_duty_mention(client, message):
    """Agar off-duty odamni tag qilishsa — On Duty listini chiqaradi"""
    try:
        if not message.entities:
            return

        print(f"🔍 [DEBUG] Xabar keldi: '{message.text}' | Chat: {message.chat.id}")
        print(f"🔍 [DEBUG] Hozirgi duty_status: {duty_status}")

        has_off_duty = False
        for entity in message.entities:
            # entity.type turli pyrogram versiyalarida turlicha keladi:
            # - enum bo'lsa: .value orqali "mention" / "text_mention"
            # - ba'zi versiyalarda: to'g'ridan-to'g'ri raw klass obyekti
            #   (masalan <class '...MessageEntityMention'>)
            # Shuning uchun universal tarzda klass/qiymat nomini string
            # ko'rinishida tekshiramiz.
            raw_type = getattr(entity.type, "value", entity.type)
            type_name = str(raw_type).lower().replace("_", "")

            is_text_mention = ("textmention" in type_name) or ("mentionname" in type_name)
            is_plain_mention = (not is_text_mention) and ("mention" in type_name)

            print(f"🔍 [DEBUG] Entity: raw_type={raw_type} | is_text_mention={is_text_mention} | is_plain_mention={is_plain_mention} | user={entity.user}")

            if is_text_mention and entity.user:
                # Ism orqali tag qilingan (username'i yo'q foydalanuvchi)
                user_id = entity.user.id
                print(f"🔍 [DEBUG] text_mention → user_id={user_id}, duty_status'da bormi: {user_id in duty_status}")
                if user_id in duty_status and duty_status[user_id]["status"] == "off":
                    has_off_duty = True
                    break

            elif is_plain_mention:
                # Oddiy "@username" orqali tag qilingan — entity.user bo'lmaydi,
                # shuning uchun username'ni matndan o'zimiz ajratib olamiz
                mentioned_username = message.text[entity.offset + 1: entity.offset + entity.length]
                print(f"🔍 [DEBUG] mention → ajratilgan username: '{mentioned_username}'")
                for data in duty_status.values():
                    print(f"🔍 [DEBUG] Solishtirilyapti: '{data['username'].lower()}' == '{mentioned_username.lower()}' ? status={data['status']}")
                    if data["username"].lower() == mentioned_username.lower() and data["status"] == "off":
                        has_off_duty = True
                        break

            if has_off_duty:
                break

        print(f"🔍 [DEBUG] has_off_duty = {has_off_duty}")

        if has_off_duty:
            on_duty = [format_duty_name(data) for data in duty_status.values() if data["status"] == "on"]
            if on_duty:
                text = "**On duty :**\n" + ", ".join(on_duty)
            else:
                text = "**On duty :**\nHozir hech kim yo'q."
            await message.reply_text(text, quote=True)
    except Exception as e:
        print(f"❌ check_off_duty_mention error: {e}")


# ====================== MONITORING (group=2, eng oxirida) ======================
@app.on_message(
    filters.text & filters.group & ~filters.command(ALL_COMMANDS),
    group=2
)
async def monitor(client, message):
    try:
        if not message.text:
            return

        chat_id = message.chat.id
        text_lower = message.text.lower()

        keyword_detected = False
        issue_name = None

        # 1. Global Keywords (har doim tekshiriladi)
        for word in GLOBAL_KEYWORDS:
            if word.lower() in text_lower:
                keyword_detected = True
                break

        # 2. Team Groups
        if chat_id in TEAM_GROUPS and "team" in text_lower:
            keyword_detected = True
            issue_name = "Team Mention"

        # 3. Issue List
        if monitoring_active and chat_id in issue_list:
            keyword_detected = True
            issue_name = issue_list[chat_id]

        if not keyword_detected:
            return

        print(f"🔥 KEYWORD DETECTED in {chat_id} | Issue: {issue_name or 'Global'}")

        group_name = message.chat.title or "Unknown Group"
        alert_text = f"**Group:** `{group_name}`\n\n"
        if issue_name:
            alert_text += f"**Issue:** {issue_name}\n\n"
        alert_text += f"**Message:** {message.text[:900]}\n\n"
        alert_text += f"**User:** {message.from_user.first_name if message.from_user else 'Unknown'}"

        if message.chat.username:
            link = f"https://t.me/{message.chat.username}/{message.id}"
        else:
            clean_id = str(chat_id).replace("-100", "")
            link = f"https://t.me/c/{clean_id}/{message.id}"

        keyboard = InlineKeyboardMarkup([[InlineKeyboardButton("🔗 View Message", url=link)]])

        await client.send_message(
            MONITOR_GROUP,
            alert_text,
            reply_markup=keyboard,
            disable_web_page_preview=True
        )
    except Exception as e:
        print(f"❌ monitor error: {e}")


print("✅ Bot started successfully!")
app.run()
