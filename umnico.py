import logging
import asyncio
import aiohttp
from aiohttp_socks import ProxyConnector
import random
import json
import os
from typing import List, Set
from telegram import Update
from telegram.ext import ApplicationBuilder, ContextTypes, CommandHandler, MessageHandler, filters

# --- CONFIGURATION ---
# 🔴 PUT YOUR TOKEN HERE
BOT_TOKEN = "8327830149:AAEp8Nt5OI29h6o-niOIwR00M0gFQH1_RsY"


UMNICO_API_URL = "https://umnico.com/api/tools/checker"
PROXY_FILE = "proxy.txt"

# --- SETTINGS ---
MAX_CONCURRENT_TASKS = 100  # Adjust based on how many proxies you have
PROXY_TIMEOUT = 10          # Give proxies 10s to respond
SEND_INTERVAL = 0.5         # Message delay (seconds)

# Headers (No Cookies)
API_HEADERS = {
    "accept": "application/json, text/plain, */*",
    "accept-language": "en-US,en;q=0.8",
    "priority": "u=1, i",
    "referer": "https://umnico.com/tools/whatsapp-checker/",
    "sec-ch-ua": '"Chromium";v="142", "Brave";v="142", "Not_A Brand";v="99"',
    "sec-ch-ua-mobile": "?0",
    "sec-ch-ua-platform": '"Windows"',
    "sec-fetch-dest": "empty",
    "sec-fetch-mode": "cors",
    "sec-fetch-site": "same-origin",
    "sec-gpc": "1",
    "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/142.0.0.0 Safari/537.36"
}

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(message)s')
logger = logging.getLogger("ManualProxyBot")
logging.getLogger("aiohttp").setLevel(logging.WARNING)

# Globals
STOP_SIGNAL = asyncio.Event()
RESULT_QUEUE = asyncio.Queue()
PROXY_LIST: List[str] = []
PROXY_REQUEST_COUNT: int = 0  # Global request counter for rotation
PROXY_MAX_USES: int = 20  # Max uses per proxy before rotation
USER_SESSIONS: dict = {}  # Track session data per user
PROXY_COLLECTION_MODE: dict = {}  # Track users in proxy collection mode {user_id: [proxy_list]}
import threading
PROXY_LOCK = threading.Lock()  # Thread-safe proxy selection

# --- PROXY MANAGEMENT ---

def parse_proxy_format(proxy: str) -> str:
    """
    Convert proxy from protocol://ip:port:user:pass to protocol://user:pass@ip:port
    Also handles protocol://user:pass@ip:port (already correct format)
    Handles complex usernames with special characters.
    """
    if not proxy or "://" not in proxy:
        return proxy
    
    # Check if already in correct format (has @)
    if "@" in proxy:
        return proxy
    
    try:
        # Split protocol and rest
        protocol, rest = proxy.split("://", 1)
        parts = rest.split(":")
        
        # Expected format: ip:port:user:pass
        # But user/pass might contain colons, so we take first 2 as ip:port and rest as user:pass
        if len(parts) >= 4:
            # First part is IP, second is port
            ip = parts[0]
            port = parts[1]
            # Everything after port is user:pass (join remaining parts)
            user_pass = ":".join(parts[2:])
            
            # Split user:pass on last colon to separate user and pass
            # Find the last colon to split user from pass
            last_colon = user_pass.rfind(":")
            if last_colon > 0:
                user = user_pass[:last_colon]
                password = user_pass[last_colon + 1:]
                # Convert to protocol://user:pass@ip:port
                converted = f"{protocol}://{user}:{password}@{ip}:{port}"
                logger.info(f"Converted proxy format: {proxy[:30]}... -> {converted[:30]}...")
                return converted
        
        # If only ip:port (no auth), return as-is
        logger.warning(f"Could not parse proxy format: {proxy}")
        return proxy
    except Exception as e:
        logger.error(f"Error parsing proxy {proxy}: {e}")
        return proxy

def load_proxies():
    """Reads proxy.txt from disk. Expects format: protocol://ip:port:user:pass"""
    global PROXY_LIST
    if not os.path.exists(PROXY_FILE):
        logger.warning(f"⚠️ {PROXY_FILE} not found!")
        PROXY_LIST = []
        return

    with open(PROXY_FILE, "r", encoding="utf-8") as f:
        # Filter empty lines
        lines = [l.strip() for l in f if l.strip()]
        
        formatted = []
        for l in lines:
            # Keep proxy as-is if it has protocol, otherwise skip
            if "://" in l:
                # Parse and convert format
                converted = parse_proxy_format(l)
                formatted.append(converted)
            else:
                logger.warning(f"⚠️ Skipping invalid proxy (missing protocol): {l}")
        
        PROXY_LIST = formatted
        logger.info(f"✅ Loaded {len(PROXY_LIST)} proxies from {PROXY_FILE}")

def get_proxy():
    """Get next proxy using round-robin rotation (20 uses per proxy)."""
    global PROXY_REQUEST_COUNT
    
    if not PROXY_LIST:
        return None
    
    # Thread-safe increment and proxy selection
    with PROXY_LOCK:
        PROXY_REQUEST_COUNT += 1
        # Calculate which proxy to use based on request count
        # Every 20 requests, move to next proxy
        proxy_index = (PROXY_REQUEST_COUNT // PROXY_MAX_USES) % len(PROXY_LIST)
    
    return PROXY_LIST[proxy_index]

def get_current_proxy():
    """Get current proxy without incrementing counter (for retries)."""
    if not PROXY_LIST:
        return None
    
    with PROXY_LOCK:
        proxy_index = (PROXY_REQUEST_COUNT // PROXY_MAX_USES) % len(PROXY_LIST)
    
    return PROXY_LIST[proxy_index]

def purge_proxies():
    """Delete all proxies from proxy.txt."""
    global PROXY_LIST, PROXY_REQUEST_COUNT
    
    PROXY_LIST = []
    PROXY_REQUEST_COUNT = 0
    
    try:
        with open(PROXY_FILE, "w", encoding="utf-8") as f:
            f.write("")  # Clear file
        logger.info("🗑️ All proxies purged")
        return True
    except Exception as e:
        logger.error(f"Failed to purge proxies: {e}")
        return False

def add_proxies(proxy_lines: List[str]):
    """Add proxies to proxy.txt (purges old ones first)."""
    global PROXY_LIST, PROXY_REQUEST_COUNT
    
    # Purge old proxies first
    purge_proxies()
    
    # Filter and format new proxies
    formatted = []
    for line in proxy_lines:
        line = line.strip()
        if not line:
            continue
        
        # Expect format: protocol://ip:port:user:pass
        if "://" in line:
            # Parse and convert format
            converted = parse_proxy_format(line)
            formatted.append(converted)
        else:
            logger.warning(f"⚠️ Skipping invalid proxy (missing protocol): {line}")
    
    if not formatted:
        return 0
    
    # Write to file
    try:
        with open(PROXY_FILE, "w", encoding="utf-8") as f:
            for proxy in formatted:
                f.write(proxy + "\n")
        
        # Reload into memory
        PROXY_LIST = formatted
        PROXY_REQUEST_COUNT = 0
        
        logger.info(f"✅ Added {len(formatted)} proxies")
        return len(formatted)
    except Exception as e:
        logger.error(f"Failed to add proxies: {e}")
        return 0

# --- WORKER LOGIC ---

async def sender_loop(application):
    """Background message sender."""
    while True:
        try:
            chat_id, text = await RESULT_QUEUE.get()
            try:
                await application.bot.send_message(chat_id=chat_id, text=text, parse_mode="HTML")
            except: pass
            await asyncio.sleep(SEND_INTERVAL)
            RESULT_QUEUE.task_done()
        except: await asyncio.sleep(1)

async def check_single_number(session: aiohttp.ClientSession, phone: str, chat_id: int):
    """
    Checks one number. Retries with different proxies until valid response.
    Tracks results in user session for file generation.
    Counter only increments once per number.
    """
    if STOP_SIGNAL.is_set(): return None

    # Get proxy ONCE for this number (increments counter)
    proxy = get_proxy()
    if not proxy:
        return None
    
    max_retries = 50  # Limit retries per number
    retry_count = 0

    while retry_count < max_retries:
        if STOP_SIGNAL.is_set(): return None
        retry_count += 1
        
        # Use current proxy (no increment on retries)
        current_proxy = get_current_proxy()
        if not current_proxy:
            await asyncio.sleep(1)
            continue

        try:
            # Create dynamic connector for current proxy (supports all protocols)
            proxy_connector = ProxyConnector.from_url(current_proxy, ssl=False)
            async with aiohttp.ClientSession(connector=proxy_connector) as proxy_session:
                async with proxy_session.get(
                    UMNICO_API_URL, 
                    params={"phone": phone}, 
                    headers=API_HEADERS,
                    timeout=aiohttp.ClientTimeout(total=PROXY_TIMEOUT)
                ) as response:
                    
                    if response.status == 200:
                        try:
                            data = await response.json()
                            exists = data.get("exists")
                            
                            if exists is not None:
                                # ✅ Got Result - Send real-time update
                                if exists is True:
                                    msg = f"✅ <b>Registered:</b> <code>{phone}</code>"
                                    result = {"phone": phone, "registered": True}
                                else:
                                    msg = f"🔥 <b>UNREGISTERED:</b> <code>{phone}</code>"
                                    result = {"phone": phone, "registered": False}
                                
                                # Send real-time message
                                await RESULT_QUEUE.put((chat_id, msg))
                                
                                # Store in session for file generation
                                if chat_id not in USER_SESSIONS:
                                    USER_SESSIONS[chat_id] = {"registered": [], "unregistered": []}
                                
                                if result["registered"]:
                                    USER_SESSIONS[chat_id]["registered"].append(phone)
                                else:
                                    USER_SESSIONS[chat_id]["unregistered"].append(phone)
                                
                                return result  # Exit Loop
                        except: pass
                    
                    # If status != 200, wait a bit before retry
                    await asyncio.sleep(0.5)
        except:
            # Connection error, wait before retry
            await asyncio.sleep(0.5)
    
    # Max retries reached
    return None

async def check_single_number_with_proxy(phone: str, chat_id: int) -> dict:
    """Check a single number using next rotated proxy (1 number = 1 proxy)."""
    if STOP_SIGNAL.is_set():
        return None
    
    # Get next proxy (rotates automatically)
    proxy = get_proxy()
    if not proxy:
        logger.error("No proxy available")
        return None
    
    try:
        # Create proxy connector for this number
        proxy_connector = ProxyConnector.from_url(proxy, ssl=False)
        async with aiohttp.ClientSession(connector=proxy_connector) as proxy_session:
            
            try:
                async with proxy_session.get(
                    UMNICO_API_URL,
                    params={"phone": phone},
                    headers=API_HEADERS,
                    timeout=aiohttp.ClientTimeout(total=PROXY_TIMEOUT)
                ) as response:
                    
                    logger.info(f"Response for {phone}: status={response.status}")
                    
                    if response.status == 200:
                        data = await response.json()
                        exists = data.get("exists")
                        
                        logger.info(f"Result for {phone}: exists={exists}")
                        
                        if exists is not None:
                            if exists is True:
                                msg = f"✅ <b>Registered:</b> <code>{phone}</code>"
                                result = {"phone": phone, "registered": True}
                            else:
                                msg = f"🔥 <b>UNREGISTERED:</b> <code>{phone}</code>"
                                result = {"phone": phone, "registered": False}
                            
                            # Send real-time message
                            await RESULT_QUEUE.put((chat_id, msg))
                            
                            # Store in session
                            if chat_id not in USER_SESSIONS:
                                USER_SESSIONS[chat_id] = {"registered": [], "unregistered": []}
                            
                            if result["registered"]:
                                USER_SESSIONS[chat_id]["registered"].append(phone)
                            else:
                                USER_SESSIONS[chat_id]["unregistered"].append(phone)
                            
                            return result
                    else:
                        logger.warning(f"Non-200 status for {phone}: {response.status}")
            except Exception as e:
                logger.error(f"Error checking {phone}: {e}")
            
    except Exception as e:
        logger.error(f"Failed to create proxy connector: {e}")
    
    return None


async def process_batch(update: Update, context: ContextTypes.DEFAULT_TYPE, numbers: List[str]):
    STOP_SIGNAL.clear()
    chat_id = update.effective_chat.id

    # Initialize session
    USER_SESSIONS[chat_id] = {"registered": [], "unregistered": []}

    if not PROXY_LIST:
        await load_proxies_wrapper(update)
    
    if not PROXY_LIST:
        await update.message.reply_text(f"❌ <b>No Proxies Found!</b>\nPlease upload a file named <code>{PROXY_FILE}</code> or add it to the server folder.", parse_mode="HTML")
        return

    status_msg = await update.message.reply_text(
        f"🚀 <b>Starting Check</b>\n\n"
        f"📊 Total Numbers: <code>{len(numbers)}</code>\n"
        f"🔌 Proxies Loaded: <code>{len(PROXY_LIST)}</code>\n"
        f"🔄 Mode: <code>5 numbers per batch (2 sec delay)</code>\n\n"
        f"⏳ Processing...",
        parse_mode="HTML"
    )

    import time
    start_time = time.time()
    
    # Clean numbers
    clean_numbers = []
    for num in numbers:
        clean = num.strip().replace('+', '').replace(' ', '')
        if clean.isdigit():
            clean_numbers.append(clean)
    
    if not clean_numbers:
        await update.message.reply_text("❌ No valid numbers found!", parse_mode="HTML")
        return
    
    # Process numbers in batches of 5 (5 concurrent checks with different proxies, then 2s delay)
    async def process_sequential():
        batch_size = 5
        for i in range(0, len(clean_numbers), batch_size):
            if STOP_SIGNAL.is_set():
                logger.info("Stop signal received, halting processing")
                break
            
            # Get batch of up to 5 numbers
            batch = clean_numbers[i:i + batch_size]
            
            # Process this batch concurrently (each with different proxy)
            tasks = [check_single_number_with_proxy(phone, chat_id) for phone in batch]
            await asyncio.gather(*tasks)
            
            # Wait 2 seconds before next batch (except last batch)
            if i + batch_size < len(clean_numbers):
                await asyncio.sleep(2.0)
    
    # Update status periodically
    async def update_status():
        while True:
            await asyncio.sleep(5)
            if STOP_SIGNAL.is_set():
                break
            
            current_reg = len(USER_SESSIONS.get(chat_id, {}).get("registered", []))
            current_unreg = len(USER_SESSIONS.get(chat_id, {}).get("unregistered", []))
            processed = current_reg + current_unreg
            
            if processed >= len(clean_numbers):
                break
            
            elapsed = time.time() - start_time
            speed = processed / elapsed if elapsed > 0 else 0
            
            # Calculate current proxy info (each number uses one proxy)
            current_proxy_index = (PROXY_REQUEST_COUNT - 1) % len(PROXY_LIST) if PROXY_LIST else 0
            
            try:
                await status_msg.edit_text(
                    f"🚀 <b>Check in Progress</b>\n\n"
                    f"📊 Progress: <code>{processed}/{len(clean_numbers)}</code> ({processed*100//len(clean_numbers) if clean_numbers else 0}%)\n"
                    f"✅ Registered: <code>{current_reg}</code>\n"
                    f"❌ Unregistered: <code>{current_unreg}</code>\n"
                    f"⚡ Speed: <code>{speed:.1f} num/sec</code>\n"
                    f"🔄 Current Proxy: <code>{current_proxy_index + 1}/{len(PROXY_LIST)}</code>",
                    parse_mode="HTML"
                )
            except:
                pass
    
    # Run sequential processing and status updates concurrently
    status_task = asyncio.create_task(update_status())
    process_task = asyncio.create_task(process_sequential())
    
    await process_task
    status_task.cancel()

    # Generate and send result files
    await send_result_files(update, chat_id, start_time)
    
    if STOP_SIGNAL.is_set():
        await update.message.reply_text("🛑 Check stopped by user.")
    
    # Clean up session
    if chat_id in USER_SESSIONS:
        del USER_SESSIONS[chat_id]


async def send_result_files(update: Update, chat_id: int, start_time: float):
    """Generate and send result files to user."""
    import time
    from datetime import datetime
    
    session = USER_SESSIONS.get(chat_id, {"registered": [], "unregistered": []})
    reg_numbers = session.get("registered", [])
    unreg_numbers = session.get("unregistered", [])
    
    elapsed = time.time() - start_time
    total = len(reg_numbers) + len(unreg_numbers)
    
    # Send summary
    summary = (
        f"🏁 <b>Check Completed!</b>\n\n"
        f"⏱ Time: <code>{elapsed:.1f}s</code>\n"
        f"📊 Total Checked: <code>{total}</code>\n"
        f"✅ Registered: <code>{len(reg_numbers)}</code>\n"
        f"❌ Unregistered: <code>{len(unreg_numbers)}</code>\n\n"
        f"📂 Sending result files..."
    )
    await update.message.reply_text(summary, parse_mode="HTML")
    
    # Generate files
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    files_to_send = []
    
    if reg_numbers:
        reg_file = f"registered_{timestamp}.txt"
        with open(reg_file, "w", encoding="utf-8") as f:
            for num in reg_numbers:
                f.write(f"{num}\n")
        files_to_send.append(reg_file)
    
    if unreg_numbers:
        unreg_file = f"unregistered_{timestamp}.txt"
        with open(unreg_file, "w", encoding="utf-8") as f:
            for num in unreg_numbers:
                f.write(f"{num}\n")
        files_to_send.append(unreg_file)
    
    # Send files
    if files_to_send:
        for file_path in files_to_send:
            try:
                with open(file_path, "rb") as f:
                    await update.message.reply_document(
                        document=f,
                        filename=file_path,
                        caption=f"📄 {file_path}"
                    )
                # Clean up
                os.remove(file_path)
            except Exception as e:
                logger.error(f"Failed to send file {file_path}: {e}")
    else:
        await update.message.reply_text("⚠️ No results to send.", parse_mode="HTML")

# --- HANDLERS ---

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🤖 <b>WhatsApp Number Checker Bot</b>\n\n"
        "<b>Commands:</b>\n"
        "• /start - Show this help\n"
        "• /reload - Reload proxies from proxy.txt\n"
        "• /addproxy - Add new proxies (purges old ones)\n"
        "• /purgeproxy - Delete all proxies\n"
        "• /stop - Cancel current check\n"
        "• /status - Show proxy status\n\n"
        "<b>Usage:</b>\n"
        "1. Add proxies with /addproxy command\n"
        "2. Send phone numbers (text or file)\n"
        "3. Get real-time results + files\n\n"
        "<b>Features:</b>\n"
        "✅ Real-time result streaming\n"
        "✅ Auto proxy rotation (20 uses/proxy)\n"
        "✅ Result files (registered/unregistered)\n"
        "✅ Multi-user support",
        parse_mode="HTML"
    )

async def stop_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    STOP_SIGNAL.set()
    await update.message.reply_text("🛑 Stopping...")

async def load_proxies_wrapper(update: Update):
    """Helper to load and notify."""
    load_proxies()
    if PROXY_LIST:
        await update.message.reply_text(f"✅ Loaded {len(PROXY_LIST)} proxies from disk.")
    else:
        await update.message.reply_text("⚠️ proxy.txt is empty or missing.")

async def reload_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await load_proxies_wrapper(update)

async def purgeproxy_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Purge all proxies."""
    success = purge_proxies()
    if success:
        await update.message.reply_text(
            "🗑️ <b>All proxies purged!</b>\n\n"
            "Use /addproxy to add new proxies.",
            parse_mode="HTML"
        )
    else:
        await update.message.reply_text(
            "❌ <b>Failed to purge proxies.</b>\n\n"
            "Check the logs for details.",
            parse_mode="HTML"
        )

async def addproxy_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Start proxy collection mode."""
    user_id = update.effective_user.id
    
    # Initialize proxy collection mode
    PROXY_COLLECTION_MODE[user_id] = []
    
    await update.message.reply_text(
        "📝 <b>Proxy Collection Mode Started</b>\n\n"
        "<b>Instructions:</b>\n"
        "1. Send your proxies in format:\n"
        "   <code>protocol://ip:port:user:pass</code>\n\n"
        "2. You can send multiple messages\n"
        "3. When finished, send: <code>done</code>\n\n"
        "<b>Supported protocols:</b>\n"
        "socks5, socks4, http, https\n\n"
        "<b>Example:</b>\n"
        "<code>socks5://proxy.com:1080:user:pass\n"
        "http://proxy2.com:8080:user2:pass2</code>\n\n"
        "⚠️ Sending 'done' will <b>purge all old proxies</b>!",
        parse_mode="HTML"
    )

async def status_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show proxy status."""
    if not PROXY_LIST:
        await update.message.reply_text(
            "⚠️ <b>No proxies loaded!</b>\n\n"
            "Use /addproxy to add proxies.",
            parse_mode="HTML"
        )
        return
    
    # Get usage stats
    current_proxy_index = (PROXY_REQUEST_COUNT // PROXY_MAX_USES) % len(PROXY_LIST)
    current_proxy = PROXY_LIST[current_proxy_index]
    current_uses = PROXY_REQUEST_COUNT % PROXY_MAX_USES
    if current_uses == 0 and PROXY_REQUEST_COUNT > 0:
        current_uses = PROXY_MAX_USES
    
    msg = (
        f"📊 <b>Proxy Status</b>\n\n"
        f"🔌 Total Proxies: <code>{len(PROXY_LIST)}</code>\n"
        f"🔄 Current Proxy: <code>{current_proxy_index + 1}/{len(PROXY_LIST)}</code>\n"
        f"📈 Current Uses: <code>{current_uses}/{PROXY_MAX_USES}</code>\n"
        f"📊 Total Requests: <code>{PROXY_REQUEST_COUNT}</code>\n\n"
        f"<b>Active Proxy:</b>\n<code>{current_proxy}</code>"
    )
    
    await update.message.reply_text(msg, parse_mode="HTML")

async def handle_document(update: Update, context: ContextTypes.DEFAULT_TYPE):
    doc = update.message.document
    
    # 1. Check if it's the proxy file
    if doc.file_name == PROXY_FILE:
        f = await doc.get_file()
        await f.download_to_drive(PROXY_FILE)
        await update.message.reply_text("📥 <b>proxy.txt received!</b> Reloading list...", parse_mode="HTML")
        load_proxies()
        await update.message.reply_text(f"✅ Now using {len(PROXY_LIST)} proxies.")
        return

    # 2. Otherwise treat as number list
    if doc.file_name.endswith(".txt"):
        f = await doc.get_file()
        b = await f.download_as_bytearray()
        nums = [l.strip() for l in b.decode("utf-8", errors="ignore").splitlines() if l.strip()]
        if nums: 
            await update.message.reply_text(f"📂 Loaded {len(nums)} numbers.")
            asyncio.create_task(process_batch(update, context, nums))

async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message.text:
        return
    
    user_id = update.effective_user.id
    message_text = update.message.text.strip()
    
    # Check if user is in proxy collection mode
    if user_id in PROXY_COLLECTION_MODE:
        # Check if user wants to finish
        if message_text.lower() == "done":
            collected_proxies = PROXY_COLLECTION_MODE[user_id]
            
            if not collected_proxies:
                await update.message.reply_text(
                    "❌ <b>No proxies collected!</b>\n\n"
                    "Please send proxies first, then type 'done'.",
                    parse_mode="HTML"
                )
                return
            
            # Add proxies (purges old ones first)
            count = add_proxies(collected_proxies)
            
            # Exit collection mode
            del PROXY_COLLECTION_MODE[user_id]
            
            if count > 0:
                await update.message.reply_text(
                    f"✅ <b>Proxies Added Successfully!</b>\n\n"
                    f"🗑️ Old proxies purged\n"
                    f"➕ Added: <code>{count}</code> new proxies\n"
                    f"🔄 Rotation: <code>20 uses per proxy</code>\n\n"
                    f"Ready to check numbers!",
                    parse_mode="HTML"
                )
            else:
                await update.message.reply_text(
                    "❌ <b>Failed to add proxies!</b>\n\n"
                    "Make sure proxies are in correct format:\n"
                    "<code>protocol://ip:port:user:pass</code>",
                    parse_mode="HTML"
                )
        else:
            # Collect proxies from message
            proxy_lines = [line.strip() for line in message_text.splitlines() if line.strip()]
            
            # Filter valid proxies (must have protocol)
            valid_count = 0
            for line in proxy_lines:
                if "://" in line:
                    PROXY_COLLECTION_MODE[user_id].append(line)
                    valid_count += 1
            
            total_collected = len(PROXY_COLLECTION_MODE[user_id])
            
            await update.message.reply_text(
                f"✅ <b>Proxies Collected</b>\n\n"
                f"➕ This message: <code>{valid_count}</code>\n"
                f"📊 Total collected: <code>{total_collected}</code>\n\n"
                f"Send more proxies or type <code>done</code> to finish.",
                parse_mode="HTML"
            )
        return
    
    # Normal mode: treat as phone numbers
    nums = [l.strip() for l in message_text.splitlines() if l.strip()]
    if nums:
        asyncio.create_task(process_batch(update, context, nums))

async def on_startup(app):
    asyncio.create_task(sender_loop(app))
    load_proxies()

if __name__ == '__main__':
    app = ApplicationBuilder().token(BOT_TOKEN).post_init(on_startup).build()
    
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("stop", stop_cmd))
    app.add_handler(CommandHandler("reload", reload_cmd))
    app.add_handler(CommandHandler("purgeproxy", purgeproxy_cmd))
    app.add_handler(CommandHandler("addproxy", addproxy_cmd))
    app.add_handler(CommandHandler("status", status_cmd))
    app.add_handler(MessageHandler(filters.Document.ALL, handle_document)) # Accepts any file, logic checks name
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))

    print("🤖 WhatsApp Number Checker Bot Running...")
    print("📊 Commands: /start, /reload, /addproxy, /purgeproxy, /status, /stop")
    print("🔄 Proxy rotation: 20 uses per proxy")
    print("✅ Real-time results + file generation enabled")
    app.run_polling()
