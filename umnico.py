#!/usr/bin/env python3
"""
Owl Proxy Telegram Bot
Manages proxy tokens and provides automated balance checking with proxy generation
"""

import asyncio
import logging
import sqlite3
import httpx
from datetime import datetime
from functools import lru_cache
from typing import Optional, Tuple, List, Dict
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.request import HTTPXRequest
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    ConversationHandler,
    ContextTypes,
    filters,
)

# Global country list
COUNTRY_LIST = [
        ("🇦🇫", "Afghanistan", "AF", "Pashto"),
        ("🇦🇱", "Albania", "AL", "Albanian"),
        ("🇩🇿", "Algeria", "DZ", "Arabic"),
        ("🇦🇸", "American Samoa", "AS", "Samoan"),
        ("🇦🇩", "Andorra", "AD", "Catalan"),
        ("🇦🇴", "Angola", "AO", "Portuguese"),
        ("🇦🇮", "Anguilla", "AI", "English"),
        ("🇦🇶", "Antarctica", "AQ", "None (varies)"),
        ("🇦🇬", "Antigua and Barbuda", "AG", "English"),
        ("🇦🇷", "Argentina", "AR", "Spanish"),
        ("🇦🇲", "Armenia", "AM", "Armenian"),
        ("🇦🇼", "Aruba", "AW", "Dutch"),
        ("🇦🇺", "Australia", "AU", "English"),
        ("🇦🇹", "Austria", "AT", "German"),
        ("🇦🇿", "Azerbaijan", "AZ", "Azerbaijani"),
        ("🇧🇸", "Bahamas", "BS", "English"),
        ("🇧🇭", "Bahrain", "BH", "Arabic"),
        ("🇧🇩", "Bangladesh", "BD", "Bengali"),
        ("🇧🇧", "Barbados", "BB", "English"),
        ("🇧🇾", "Belarus", "BY", "Belarusian"),
        ("🇧🇪", "Belgium", "BE", "Dutch"),
        ("🇧🇿", "Belize", "BZ", "English"),
        ("🇧🇯", "Benin", "BJ", "French"),
        ("🇧🇲", "Bermuda", "BM", "English"),
        ("🇧🇹", "Bhutan", "BT", "Dzongkha"),
        ("🇧🇴", "Bolivia", "BO", "Spanish"),
        ("🇧🇶", "Bonaire, Sint Eustatius and Saba", "BQ", "Dutch"),
        ("🇧🇦", "Bosnia and Herzegovina", "BA", "Bosnian"),
        ("🇧🇼", "Botswana", "BW", "English"),
        ("🇧🇷", "Brazil", "BR", "Portuguese"),
        ("🇮🇴", "British Indian Ocean Territory", "IO", "English"),
        ("🇻🇬", "British Virgin Islands", "VG", "English"),
        ("🇧🇳", "Brunei", "BN", "Malay"),
        ("🇧🇬", "Bulgaria", "BG", "Bulgarian"),
        ("🇧🇫", "Burkina Faso", "BF", "French"),
        ("🇧🇮", "Burundi", "BI", "Kirundi"),
        ("🇰🇭", "Cambodia", "KH", "Khmer"),
        ("🇨🇲", "Cameroon", "CM", "French"),
        ("🇨🇦", "Canada", "CA", "English"),
        ("🇨🇻", "Cabo Verde", "CV", "Portuguese"),
        ("🇰🇾", "Cayman Islands", "KY", "English"),
        ("🇨🇫", "Central African Republic", "CF", "French"),
        ("🇹🇩", "Chad", "TD", "French"),
        ("🇨🇱", "Chile", "CL", "Spanish"),
        ("🇨🇳", "China", "CN", "Mandarin Chinese"),
        ("🇨🇴", "Colombia", "CO", "Spanish"),
        ("🇰🇲", "Comoros", "KM", "Comorian"),
        ("🇨🇬", "Congo", "CG", "French"),
        ("🇨🇩", "Congo (DRC)", "CD", "French"),
        ("🇨🇷", "Costa Rica", "CR", "Spanish"),
        ("🇭🇷", "Croatia", "HR", "Croatian"),
        ("🇨🇺", "Cuba", "CU", "Spanish"),
        ("🇨🇾", "Cyprus", "CY", "Greek"),
        ("🇨🇿", "Czechia", "CZ", "Czech"),
        ("🇩🇰", "Denmark", "DK", "Danish"),
        ("🇩🇯", "Djibouti", "DJ", "French"),
        ("🇩🇲", "Dominica", "DM", "English"),
        ("🇩🇴", "Dominican Republic", "DO", "Spanish"),
        ("🇪🇨", "Ecuador", "EC", "Spanish"),
        ("🇪🇬", "Egypt", "EG", "Arabic"),
        ("🇸🇻", "El Salvador", "SV", "Spanish"),
        ("🇬🇶", "Equatorial Guinea", "GQ", "Spanish"),
        ("🇪🇷", "Eritrea", "ER", "Tigrinya"),
        ("🇪🇪", "Estonia", "EE", "Estonian"),
        ("🇸🇿", "Eswatini", "SZ", "Swazi"),
        ("🇪🇹", "Ethiopia", "ET", "Amharic"),
        ("🇫🇯", "Fiji", "FJ", "Fijian"),
        ("🇫🇮", "Finland", "FI", "Finnish"),
        ("🇫🇷", "France", "FR", "French"),
        ("🇬🇦", "Gabon", "GA", "French"),
        ("🇬🇲", "Gambia", "GM", "English"),
        ("🇬🇪", "Georgia", "GE", "Georgian"),
        ("🇩🇪", "Germany", "DE", "German"),
        ("🇬🇭", "Ghana", "GH", "English"),
        ("🇬🇷", "Greece", "GR", "Greek"),
        ("🇬🇱", "Greenland", "GL", "Greenlandic"),
        ("🇬🇩", "Grenada", "GD", "English"),
        ("🇬🇹", "Guatemala", "GT", "Spanish"),
        ("🇬🇳", "Guinea", "GN", "French"),
        ("🇬🇼", "Guinea-Bissau", "GW", "Portuguese"),
        ("🇬🇾", "Guyana", "GY", "English"),
        ("🇭🇹", "Haiti", "HT", "Haitian Creole"),
        ("🇭🇳", "Honduras", "HN", "Spanish"),
        ("🇭🇰", "Hong Kong", "HK", "Chinese (Cantonese)"),
        ("🇭🇺", "Hungary", "HU", "Hungarian"),
        ("🇮🇸", "Iceland", "IS", "Icelandic"),
        ("🇮🇳", "India", "IN", "Hindi"),
        ("🇮🇩", "Indonesia", "ID", "Indonesian"),
        ("🇮🇷", "Iran", "IR", "Persian (Farsi)"),
        ("🇮🇶", "Iraq", "IQ", "Arabic"),
        ("🇮🇪", "Ireland", "IE", "Irish"),
        ("🇮🇱", "Israel", "IL", "Hebrew"),
        ("🇮🇹", "Italy", "IT", "Italian"),
        ("🇯🇲", "Jamaica", "JM", "English"),
        ("🇯🇵", "Japan", "JP", "Japanese"),
        ("🇯🇴", "Jordan", "JO", "Arabic"),
        ("🇰🇿", "Kazakhstan", "KZ", "Kazakh"),
        ("🇰🇪", "Kenya", "KE", "Swahili"),
        ("🇰🇮", "Kiribati", "KI", "Gilbertese"),
        ("🇰🇼", "Kuwait", "KW", "Arabic"),
        ("🇰🇬", "Kyrgyzstan", "KG", "Kyrgyz"),
        ("🇱🇦", "Laos", "LA", "Lao"),
        ("🇱🇻", "Latvia", "LV", "Latvian"),
        ("🇱🇧", "Lebanon", "LB", "Arabic"),
        ("🇱🇸", "Lesotho", "LS", "Sesotho"),
        ("🇱🇷", "Liberia", "LR", "English"),
        ("🇱🇾", "Libya", "LY", "Arabic"),
        ("🇱🇮", "Liechtenstein", "LI", "German"),
        ("🇱🇹", "Lithuania", "LT", "Lithuanian"),
        ("🇱🇺", "Luxembourg", "LU", "Luxembourgish"),
        ("🇲🇬", "Madagascar", "MG", "Malagasy"),
        ("🇲🇼", "Malawi", "MW", "English"),
        ("🇲🇾", "Malaysia", "MY", "Malay"),
        ("🇲🇻", "Maldives", "MV", "Dhivehi"),
        ("🇲🇱", "Mali", "ML", "French"),
        ("🇲🇹", "Malta", "MT", "Maltese"),
        ("🇲🇭", "Marshall Islands", "MH", "Marshallese"),
        ("🇲🇷", "Mauritania", "MR", "Arabic"),
        ("🇲🇺", "Mauritius", "MU", "English"),
        ("🇲🇽", "Mexico", "MX", "Spanish"),
        ("🇫🇲", "Micronesia", "FM", "English"),
        ("🇲🇩", "Moldova", "MD", "Romanian"),
        ("🇲🇨", "Monaco", "MC", "French"),
        ("🇲🇳", "Mongolia", "MN", "Mongolian"),
        ("🇲🇪", "Montenegro", "ME", "Montenegrin"),
        ("🇲🇦", "Morocco", "MA", "Arabic"),
        ("🇲🇿", "Mozambique", "MZ", "Portuguese"),
        ("🇲🇲", "Myanmar", "MM", "Burmese"),
        ("🇳🇦", "Namibia", "NA", "English"),
        ("🇳🇷", "Nauru", "NR", "Nauruan"),
        ("🇳🇵", "Nepal", "NP", "Nepali"),
        ("🇳🇱", "Netherlands", "NL", "Dutch"),
        ("🇳🇿", "New Zealand", "NZ", "English"),
        ("🇳🇮", "Nicaragua", "NI", "Spanish"),
        ("🇳🇪", "Niger", "NE", "French"),
        ("🇳🇬", "Nigeria", "NG", "English"),
        ("🇰🇵", "North Korea", "KP", "Korean"),
        ("🇲🇰", "North Macedonia", "MK", "Macedonian"),
        ("🇳🇴", "Norway", "NO", "Norwegian"),
        ("🇴🇲", "Oman", "OM", "Arabic"),
        ("🇵🇰", "Pakistan", "PK", "Urdu"),
        ("🇵🇼", "Palau", "PW", "Palauan"),
        ("🇵🇸", "Palestine", "PS", "Arabic"),
        ("🇵🇦", "Panama", "PA", "Spanish"),
        ("🇵🇬", "Papua New Guinea", "PG", "Tok Pisin"),
        ("🇵🇾", "Paraguay", "PY", "Spanish"),
        ("🇵🇪", "Peru", "PE", "Spanish"),
        ("🇵🇭", "Philippines", "PH", "Filipino"),
        ("🇵🇱", "Poland", "PL", "Polish"),
        ("🇵🇹", "Portugal", "PT", "Portuguese"),
        ("🇵🇷", "Puerto Rico", "PR", "Spanish"),
        ("🇶🇦", "Qatar", "QA", "Arabic"),
        ("🇷🇴", "Romania", "RO", "Romanian"),
        ("🇷🇺", "Russia", "RU", "Russian"),
        ("🇷🇼", "Rwanda", "RW", "Kinyarwanda"),
        ("🇼🇸", "Samoa", "WS", "Samoan"),
        ("🇸🇲", "San Marino", "SM", "Italian"),
        ("🇸🇹", "São Tomé and Príncipe", "ST", "Portuguese"),
        ("🇸🇦", "Saudi Arabia", "SA", "Arabic"),
        ("🇸🇳", "Senegal", "SN", "French"),
        ("🇷🇸", "Serbia", "RS", "Serbian"),
        ("🇸🇨", "Seychelles", "SC", "Creole"),
        ("🇸🇱", "Sierra Leone", "SL", "English"),
        ("🇸🇬", "Singapore", "SG", "Malay"),
        ("🇸🇰", "Slovakia", "SK", "Slovak"),
        ("🇸🇮", "Slovenia", "SI", "Slovene"),
        ("🇸🇧", "Solomon Islands", "SB", "English"),
        ("🇸🇴", "Somalia", "SO", "Somali"),
        ("🇿🇦", "South Africa", "ZA", "Zulu"),
        ("🇰🇷", "South Korea", "KR", "Korean"),
        ("🇸🇸", "South Sudan", "SS", "English"),
        ("🇪🇸", "Spain", "ES", "Spanish"),
        ("🇱🇰", "Sri Lanka", "LK", "Sinhala"),
        ("🇸🇩", "Sudan", "SD", "Arabic"),
        ("🇸🇷", "Suriname", "SR", "Dutch"),
        ("🇸🇪", "Sweden", "SE", "Swedish"),
        ("🇨🇭", "Switzerland", "CH", "German"),
        ("🇸🇾", "Syria", "SY", "Arabic"),
        ("🇹🇼", "Taiwan", "TW", "Mandarin Chinese"),
        ("🇹🇯", "Tajikistan", "TJ", "Tajik"),
        ("🇹🇿", "Tanzania", "TZ", "Swahili"),
        ("🇹🇭", "Thailand", "TH", "Thai"),
        ("🇹🇱", "Timor-Leste", "TL", "Tetum"),
        ("🇹🇬", "Togo", "TG", "French"),
        ("🇹🇴", "Tonga", "TO", "Tongan"),
        ("🇹🇹", "Trinidad and Tobago", "TT", "English"),
        ("🇹🇳", "Tunisia", "TN", "Arabic"),
        ("🇹🇷", "Turkey", "TR", "Turkish"),
        ("🇹🇲", "Turkmenistan", "TM", "Turkmen"),
        ("🇹🇻", "Tuvalu", "TV", "Tuvaluan"),
        ("🇺🇬", "Uganda", "UG", "English"),
        ("🇺🇦", "Ukraine", "UA", "Ukrainian"),
        ("🇦🇪", "UAE", "AE", "Arabic"),
        ("🇬🇧", "UK", "GB", "English"),
        ("🇺🇸", "USA", "US", "English"),
        ("🇺🇾", "Uruguay", "UY", "Spanish"),
        ("🇺🇿", "Uzbekistan", "UZ", "Uzbek"),
        ("🇻🇺", "Vanuatu", "VU", "Bislama"),
        ("🇻🇦", "Vatican City", "VA", "Latin"),
        ("🇻🇪", "Venezuela", "VE", "Spanish"),
        ("🇻🇳", "Vietnam", "VN", "Vietnamese"),
        ("🇾🇪", "Yemen", "YE", "Arabic"),
        ("🇿🇲", "Zambia", "ZM", "English"),
        ("🇿🇼", "Zimbabwe", "ZW", "English"),
    ]

# Configure logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Admin configuration
ADMIN_USER_ID = 7613349080  # Only this user can add tokens

# Conversation states
TOKEN_INPUT, USERID_INPUT = range(2)

# Database file
DB_FILE = "proxy_tokens.db"

# API Configuration
API_BASE_URL = "https://api.owlproxy.com/owlproxy/api/vcDynamicGood"
BALANCE_ENDPOINT = f"{API_BASE_URL}/queryCurrentTrafficBalance"
CREATE_PROXY_ENDPOINT = f"{API_BASE_URL}/createProxy"

DEFAULT_HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/142.0.0.0 Safari/537.36',
    'Origin': 'https://proxy.owlproxy.com',
    'Referer': 'https://proxy.owlproxy.com/'
}


class Database:
    """Handle all database operations"""
    
    def __init__(self, db_file: str = DB_FILE):
        self.db_file = db_file
        self.init_db()
    
    def init_db(self):
        """Initialize the database with required table"""
        conn = sqlite3.connect(self.db_file)
        cursor = conn.cursor()
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS tokens (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                token TEXT NOT NULL,
                userid TEXT NOT NULL,
                remaining_traffic INTEGER DEFAULT 0,
                last_checked TIMESTAMP,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        cursor.execute('PRAGMA journal_mode=WAL;')
        cursor.execute('PRAGMA synchronous=NORMAL;')
        conn.commit()
        conn.close()
        logger.info("Database initialized")
    
    def add_token(self, token: str, userid: str) -> bool:
        """Add a new token and userid to the database"""
        try:
            conn = sqlite3.connect(self.db_file)
            cursor = conn.cursor()
            cursor.execute(
                'INSERT INTO tokens (token, userid) VALUES (?, ?)',
                (token, userid)
            )
            conn.commit()
            conn.close()
            logger.info(f"Added token for userid: {userid}")
            return True
        except Exception as e:
            logger.error(f"Error adding token: {e}")
            return False
    
    def get_first_token(self) -> Optional[Tuple[int, str, str]]:
        """Get the first (oldest) token from the database"""
        conn = sqlite3.connect(self.db_file)
        cursor = conn.cursor()
        cursor.execute(
            'SELECT id, token, userid FROM tokens ORDER BY id ASC LIMIT 1'
        )
        result = cursor.fetchone()
        conn.close()
        return result
    
    def get_all_tokens(self) -> List[Tuple]:
        """Get all tokens with their details"""
        conn = sqlite3.connect(self.db_file)
        cursor = conn.cursor()
        cursor.execute(
            'SELECT id, token, userid, remaining_traffic, last_checked FROM tokens ORDER BY id ASC'
        )
        results = cursor.fetchall()
        conn.close()
        return results
    
    def update_balance(self, token_id: int, remaining_traffic: int):
        """Update the remaining traffic for a token"""
        conn = sqlite3.connect(self.db_file)
        cursor = conn.cursor()
        cursor.execute(
            'UPDATE tokens SET remaining_traffic = ?, last_checked = ? WHERE id = ?',
            (remaining_traffic, datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f"), token_id)
        )
        conn.commit()
        conn.close()
    
    def delete_token(self, token_id: int) -> bool:
        """Delete a token by ID"""
        try:
            conn = sqlite3.connect(self.db_file)
            cursor = conn.cursor()
            cursor.execute('DELETE FROM tokens WHERE id = ?', (token_id,))
            conn.commit()
            conn.close()
            logger.info(f"Deleted token ID: {token_id}")
            return True
        except Exception as e:
            logger.error(f"Error deleting token: {e}")
            return False
    
    def delete_first_token(self) -> bool:
        """Delete the first token"""
        first_token = self.get_first_token()
        if first_token:
            return self.delete_token(first_token[0])
        return False
    
    def delete_all_tokens(self) -> bool:
        """Delete all tokens from the database"""
        try:
            conn = sqlite3.connect(self.db_file)
            cursor = conn.cursor()
            cursor.execute('DELETE FROM tokens')
            conn.commit()
            conn.close()
            logger.info("All tokens deleted")
            return True
        except Exception as e:
            logger.error(f"Error deleting all tokens: {e}")
            return False
    
    def count_tokens(self) -> int:
        """Count total tokens in database"""
        conn = sqlite3.connect(self.db_file)
        cursor = conn.cursor()
        cursor.execute('SELECT COUNT(*) FROM tokens')
        count = cursor.fetchone()[0]
        conn.close()
        return count


class ProxyAPI:
    """Handle all API operations asynchronously"""
    
    @staticmethod
    async def check_balance(token: str, userid: str) -> Optional[Dict]:
        """Check the remaining traffic balance"""
        headers = DEFAULT_HEADERS.copy()
        headers['Token'] = token
        headers['Userid'] = userid
        
        async with httpx.AsyncClient(timeout=60.0) as client:
            try:
                response = await client.get(BALANCE_ENDPOINT, headers=headers)
                response.raise_for_status()
                data = response.json()
                
                if data.get('code') == 200:
                    return data.get('data')
                else:
                    logger.error(f"Balance check failed: {data.get('msg')}")
                    return None
            except Exception as e:
                logger.error(f"Error checking balance: {e}")
                return None
    
    @staticmethod
    async def create_proxy(token: str, userid: str, country_code: str, good_num: int = 1) -> Optional[List[Dict]]:
        """Create proxy with specified parameters"""
        headers = DEFAULT_HEADERS.copy()
        headers['Token'] = token
        headers['Userid'] = userid
        headers['Content-Type'] = 'application/json'
        
        payload = {
            "proxyType": "socks5",
            "proxyHost": "change4.owlproxy.com:7778",
            "countryCode": country_code.upper(),
            "state": "",
            "city": "",
            "time": 5,
            "goodNum": good_num,
            "format": "protocol://ip:port:user:pass"
        }
        
        async with httpx.AsyncClient(timeout=120.0) as client:
            try:
                response = await client.post(CREATE_PROXY_ENDPOINT, headers=headers, json=payload)
                response.raise_for_status()
                data = response.json()
                
                if data.get('code') == 200:
                    return data.get('data')
                else:
                    logger.error(f"Proxy creation failed: {data.get('msg')}")
                    return None
            except Exception as e:
                logger.error(f"Error creating proxy: {e}")
                return None
    
    @staticmethod
    def format_proxy(proxy_data: Dict) -> str:
        """Format proxy data into the required format"""
        return f"{proxy_data['proxyHost']}:{proxy_data['proxyPort']}:{proxy_data['userName']}:{proxy_data['password']}"


# Initialize database
db = Database()


def get_keyboard(page: int, total_pages: int):
    """Generate pagination keyboard"""
    keyboard = []
    row = []
    
    if page > 1:
        row.append(InlineKeyboardButton("⬅️ Previous", callback_data=f"page_{page-1}"))
    
    row.append(InlineKeyboardButton(f"{page}/{total_pages}", callback_data="noop"))
    
    if page < total_pages:
        row.append(InlineKeyboardButton("Next ➡️", callback_data=f"page_{page+1}"))
    
    keyboard.append(row)
    return InlineKeyboardMarkup(keyboard)

@lru_cache(maxsize=32)
def get_page_content(page: int, chunk_size: int = 20) -> str:
    """Get the text content for a specific page"""
    start_idx = (page - 1) * chunk_size
    end_idx = start_idx + chunk_size
    chunk = COUNTRY_LIST[start_idx:end_idx]
    
    text = f"<b>🌍 Country Short Codes (Page {page})</b>\n\n"
    text += "Click a code to copy:\n\n"
    for flag, name, code, lang in chunk:
        text += f"{flag} {name} - <code>{code}</code> - {lang}\n"
    
    return text

async def list_countries(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show a full list of country short codes with click-to-copy formatting."""
    chunk_size = 20
    total_pages = (len(COUNTRY_LIST) + chunk_size - 1) // chunk_size
    current_page = 1
    
    text = get_page_content(current_page, chunk_size)
    reply_markup = get_keyboard(current_page, total_pages)
    
    await update.message.reply_text(text, parse_mode='HTML', reply_markup=reply_markup)


async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle pagination button clicks"""
    query = update.callback_query
    await query.answer()
    
    if query.data == "noop":
        return
        
    page = int(query.data.split("_")[1])
    chunk_size = 20
    total_pages = (len(COUNTRY_LIST) + chunk_size - 1) // chunk_size
    
    text = get_page_content(page, chunk_size)
    reply_markup = get_keyboard(page, total_pages)
    
    try:
        await query.edit_message_text(text, parse_mode='HTML', reply_markup=reply_markup)
    except Exception as e:
        logger.warning(f"Error editing message: {e}")






async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Send a welcome message with user guide"""
    user = update.effective_user
    try:
        is_admin = user.id == ADMIN_USER_ID
    except:
        is_admin = False
    
    if is_admin:
        guide_text = f"""🔐 *Welcome Admin, {user.first_name}\\!*

This bot helps you manage proxy tokens and provide automated balance checking\\.

📋 *Admin Commands:*
• /add \\- Add a new Token and UserID 🔒
• /del \\- Delete the first \\(oldest\\) token 🔒
• /delall \\- Delete all tokens from the database 🔒
• /showall \\- View all stored tokens with balances 🔒
• /checkall \\- Manually trigger balance check for all tokens 🔒

📋 *User Commands:*
• /get \\[country\\] \\[count\\] \\- Generate proxies
• /list \\- View all available country codes

*Automatic Features:*
• Balance is checked every hour automatically
• Tokens with less than 50 MB remaining are auto\\-removed
• First token in queue is always used for proxy generation

💡 *Quick Start:*
1️⃣ Add token & userid using /add
2️⃣ Users can generate proxies using /get"""
    else:
        guide_text = f"""🔐 *Welcome to Owl Proxy Bot, {user.first_name}\\!*

This bot helps you generate proxies quickly and easily\\.

📋 *Available Commands:*
• /start \\- Show this help message
• /get \\[country\\] \\[count\\] \\- Generate proxies
• /list \\- View all supported country codes 🌍

💡 *How to Use:*
Simply use `/get \\[country\\] \\[count\\]` to generate up to 50 proxies\\!

*Popular Country Codes:*
🇮🇳 IN \\- India
🇺🇸 US \\- United States
🇬🇧 GB \\- United Kingdom
🇩🇪 DE \\- Germany
🇫🇷 FR \\- France

*Example Usage:*
`/get IN 5` \\- Get 5 Indian proxies
`/get US 1` \\- Get 1 US proxy

Need a specific country? Use `/list` to find its code\\!"""
    
    await update.message.reply_text(guide_text, parse_mode='MarkdownV2')


async def add_token_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Start the add token conversation - Admin only"""
    user = update.effective_user
    
    # Check if user is admin
    if user.id != ADMIN_USER_ID:
        await update.message.reply_text(
            "🔒 *Access Denied*\n\n"
            "This command is only available to the bot administrator\\.\n\n"
            "You can use /get \\[country\\] \\[count\\] to generate proxies\\.",
            parse_mode='MarkdownV2'
        )
        return ConversationHandler.END
    
    await update.message.reply_text(
        "🔑 *Add New Token*\n\n"
        "Please send me the *Token* now\\.\n\n"
        "Use /cancel to cancel this operation\\.",
        parse_mode='MarkdownV2'
    )
    return TOKEN_INPUT


async def token_input(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Receive the token and ask for userid"""
    context.user_data['token'] = update.message.text.strip()
    
    await update.message.reply_text(
        "✅ Token received\\!\n\n"
        "Now please send me the *UserID*\\.",
        parse_mode='MarkdownV2'
    )
    return USERID_INPUT


async def userid_input(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Receive the userid and save to database"""
    userid = update.message.text.strip()
    token = context.user_data.get('token')
    
    if db.add_token(token, userid):
        # Check balance immediately
        balance_data = await ProxyAPI.check_balance(token, userid)
        
        if balance_data:
            remaining = balance_data.get('remainingTraffic', 0)
            db.update_balance(db.get_first_token()[0], remaining)
            
            await update.message.reply_text(
                f"✅ *Token Added Successfully\\!*\n\n"
                f"*UserID:* `{userid}`\n"
                f"*Remaining Traffic:* {remaining} MB\n"
                f"*Total Tokens:* {db.count_tokens()}\n\n"
                f"Your token is now active and ready to use\\!",
                parse_mode='MarkdownV2'
            )
        else:
            await update.message.reply_text(
                "✅ *Token Added\\!*\n\n"
                "⚠️ Could not verify balance immediately\\. "
                "The bot will check it during the next automatic scan\\.",
                parse_mode='MarkdownV2'
            )
    else:
        await update.message.reply_text(
            "❌ *Error\\!*\n\n"
            "Failed to add token to the database\\. Please try again\\.",
            parse_mode='MarkdownV2'
        )
    
    context.user_data.clear()
    return ConversationHandler.END


async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Cancel the conversation"""
    context.user_data.clear()
    await update.message.reply_text(
        "❌ Operation cancelled\\.",
        parse_mode='MarkdownV2'
    )
    return ConversationHandler.END


async def get_proxy(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Generate proxies based on user request"""
    # Parse arguments
    args = context.args
    
    if len(args) < 1:
        await update.message.reply_text(
            "❌ *Invalid Usage\\!*\n\n"
            "*Correct format:* /get \\[country\\] \\[count\\]\n\n"
            "*Examples:*\n"
            "• /get IN 5 \\- Generate 5 Indian proxies\n"
            "• /get US 1 \\- Generate 1 US proxy\n"
            "• /get GB 3 \\- Generate 3 UK proxies",
            parse_mode='MarkdownV2'
        )
        return
    
    # Parse country code
    country_code = args[0].upper()
    
    # Parse count (default 1)
    count = 1
    if len(args) > 1:
        try:
            count = int(args[1])
            if count < 1 or count > 50:
                await update.message.reply_text(
                    "❌ *Invalid count\\!*\n\n"
                    "Please specify a count between 1 and 50\\.",
                    parse_mode='MarkdownV2'
                )
                return
        except ValueError:
            await update.message.reply_text(
                "❌ *Invalid count format\\!*\n\n"
                "Please use a number \\(e\\.g\\., /get IN 5\\)",
                parse_mode='MarkdownV2'
            )
            return
    
    # Get first token
    first_token = db.get_first_token()
    
    if not first_token:
        await update.message.reply_text(
            "❌ *No tokens available\\!*\n\n"
            "Please add a token using /add first\\.",
            parse_mode='MarkdownV2'
        )
        return
    
    token_id, token, userid = first_token
    
    # Send processing message
    processing_msg = await update.message.reply_text(
        f"⏳ Generating {count} proxy\\(ies\\) for *{country_code}*\\.\\.\\.",
        parse_mode='MarkdownV2'
    )
    
    # Create proxies
    proxy_data = await ProxyAPI.create_proxy(token, userid, country_code, count)
    
    if proxy_data:
        # Delete processing message
        try:
            await processing_msg.delete()
        except Exception:
            pass

        # Send header
        header = f"✅ *Proxies Generated Successfully\\!*\n"
        header += f"*Country:* {country_code}\n"
        header += f"*Count:* {len(proxy_data)}\n"
        header += f"*UserID:* `{userid}`\n"
        await update.message.reply_text(header, parse_mode='MarkdownV2')

        # Send proxies in chunks to avoid message length limits
        chunk_size = 15  # Send 15 proxies per message
        current_chunk = []
        
        for p in proxy_data:
            proxy_str = f"`{p['proxyHost']}`:`{p['proxyPort']}`:`{p['userName']}`:`{p['password']}`"
            current_chunk.append(proxy_str)
            
            if len(current_chunk) >= chunk_size:
                await update.message.reply_text("\n".join(current_chunk), parse_mode='MarkdownV2')
                current_chunk = []
        
        # Send remaining proxies
        if current_chunk:
            await update.message.reply_text("\n".join(current_chunk), parse_mode='MarkdownV2')
        
        # Check balance after generation
        balance_data = await ProxyAPI.check_balance(token, userid)
        if balance_data:
            remaining = balance_data.get('remainingTraffic', 0)
            db.update_balance(token_id, remaining)
            
            if remaining < 50:
                db.delete_token(token_id)
                await update.message.reply_text(
                    f"⚠️ *Token Removed*\n\n"
                    f"Remaining traffic was {remaining} MB \\(below 50 MB threshold\\)\\.\n"
                    f"Token has been removed from the database\\.",
                    parse_mode='MarkdownV2'
                )
    else:
        await processing_msg.delete()
        await update.message.reply_text(
            "❌ *Proxy Generation Failed\\!*\n\n"
            "Could not create proxies\\. Please check:\n"
            "• Token is valid\n"
            "• Sufficient balance available \\(>= 50 MB\\)\n"
            "• Country code is correct",
            parse_mode='MarkdownV2'
        )


async def delete_first(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Delete the first token - Admin only"""
    user = update.effective_user
    
    # Check if user is admin
    if user.id != ADMIN_USER_ID:
        await update.message.reply_text(
            "🔒 *Access Denied*\n\n"
            "This command is only available to the bot administrator\\.",
            parse_mode='MarkdownV2'
        )
        return
    
    first_token = db.get_first_token()
    
    if not first_token:
        await update.message.reply_text(
            "❌ *No tokens to delete\\!*\n\n"
            "The database is empty\\.",
            parse_mode='MarkdownV2'
        )
        return
    
    token_id, token, userid = first_token
    
    if db.delete_first_token():
        remaining_count = db.count_tokens()
        await update.message.reply_text(
            f"✅ *Token Deleted\\!*\n\n"
            f"*UserID:* `{userid}`\n"
            f"*Remaining tokens:* {remaining_count}",
            parse_mode='MarkdownV2'
        )
    else:
        await update.message.reply_text(
            "❌ *Error\\!*\n\n"
            "Failed to delete token\\.",
            parse_mode='MarkdownV2'
        )


async def delete_all(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Delete all tokens - Admin only"""
    user = update.effective_user
    
    # Check if user is admin
    if user.id != ADMIN_USER_ID:
        await update.message.reply_text(
            "🔒 *Access Denied*\n\n"
            "This command is only available to the bot administrator\\.",
            parse_mode='MarkdownV2'
        )
        return
    
    count = db.count_tokens()
    
    if count == 0:
        await update.message.reply_text(
            "❌ *Database is already empty\\!*",
            parse_mode='MarkdownV2'
        )
        return
    
    if db.delete_all_tokens():
        await update.message.reply_text(
            f"✅ *All Tokens Deleted\\!*\n\n"
            f"Removed {count} token\\(s\\) from the database\\.",
            parse_mode='MarkdownV2'
        )
    else:
        await update.message.reply_text(
            "❌ *Error\\!*\n\n"
            "Failed to delete tokens\\.",
            parse_mode='MarkdownV2'
        )


async def show_all(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show all tokens with their details - Admin only"""
    user = update.effective_user
    
    # Check if user is admin
    if user.id != ADMIN_USER_ID:
        await update.message.reply_text(
            "🔒 *Access Denied*\n\n"
            "This command is only available to the bot administrator\\.",
            parse_mode='MarkdownV2'
        )
        return
    
    tokens = db.get_all_tokens()
    
    if not tokens:
        await update.message.reply_text(
            "📋 *No Tokens Found*\n\n"
            "The database is empty\\. Use /add to add a token\\.",
            parse_mode='MarkdownV2'
        )
        return
    
    response = f"📋 *All Tokens \\({len(tokens)} total\\)*\n\n"
    
    for idx, (token_id, token, userid, remaining, last_checked) in enumerate(tokens, 1):
        # Mask token
        masked_token = f"{token[:8]}{'*' * 12}{token[-4:]}" if len(token) > 12 else f"{token[:4]}{'*' * 8}"
        
        # Format last checked
        checked_time = "Never"
        if last_checked:
            checked_time = str(last_checked).split('.')[0]  # Remove microseconds
            checked_time = checked_time.replace('-', '\\-').replace('.', '\\.')

        
        response += f"*{idx}\\. Token ID {token_id}*\n"
        response += f"   Token: `{masked_token}`\n"
        response += f"   UserID: `{userid}`\n"
        response += f"   Balance: {remaining if remaining else 'Unknown'} MB\n"
        response += f"   Last Checked: {checked_time}\n\n"
    
    await update.message.reply_text(response, parse_mode='MarkdownV2')


async def check_balances_task(context: ContextTypes.DEFAULT_TYPE):
    """Periodic task to check all token balances"""
    logger.info("Starting automatic balance check...")
    
    tokens = db.get_all_tokens()
    
    if not tokens:
        logger.info("No tokens to check")
        return
    
    removed_tokens = []
    
    for token_id, token, userid, _, _ in tokens:
        balance_data = await ProxyAPI.check_balance(token, userid)
        
        if balance_data:
            remaining = balance_data.get('remainingTraffic', 0)
            db.update_balance(token_id, remaining)
            
            logger.info(f"Token ID {token_id} (UserID: {userid}): {remaining} MB remaining")
            
            if remaining < 50:
                db.delete_token(token_id)
                removed_tokens.append((userid, remaining))
                logger.info(f"Removed token ID {token_id} due to low balance ({remaining} MB)")
        else:
            logger.warning(f"Failed to check balance for token ID {token_id}")
    
    if removed_tokens:
        logger.info(f"Removed {len(removed_tokens)} token(s) due to low balance")
    
    logger.info("Balance check completed")


async def manual_check_balances(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Manually trigger balance check for all tokens"""
    status_msg = await update.message.reply_text("🔄 Checking balances for all tokens...")
    
    tokens = db.get_all_tokens()
    
    if not tokens:
        await status_msg.edit_text("No tokens found in database.")
        return
    
    updated_count = 0
    removed_count = 0
    errors_count = 0
    
    for token_id, token, userid, _, _ in tokens:
        balance_data = await ProxyAPI.check_balance(token, userid)
        
        if balance_data:
            remaining = balance_data.get('remainingTraffic', 0)
            db.update_balance(token_id, remaining)
            updated_count += 1
            
            if remaining < 50:
                db.delete_token(token_id)
                removed_count += 1
        else:
            errors_count += 1
            
    report = (
        f"✅ Balance check completed!\n\n"
        f"📊 Checked: {len(tokens)}\n"
        f"✅ Updated: {updated_count}\n"
        f"🗑️ Removed (<50MB): {removed_count}\n"
        f"⚠️ Errors: {errors_count}"
    )
    
    await status_msg.edit_text(report)


def main():
    """Start the bot"""
    # Replace with your bot token
    BOT_TOKEN = "8226555654:AAEx9UB1-lDoHA5_9I1F55ISU-fkC_Z0Kxk"
    
    # Configure connection with increased timeouts
    request = HTTPXRequest(connect_timeout=60.0, read_timeout=60.0)

    # Create application
    application = Application.builder().token(BOT_TOKEN).request(request).build()
    
    # Add conversation handler for adding tokens
    add_conv_handler = ConversationHandler(
        entry_points=[CommandHandler('add', add_token_start)],
        states={
            TOKEN_INPUT: [MessageHandler(filters.TEXT & ~filters.COMMAND, token_input)],
            USERID_INPUT: [MessageHandler(filters.TEXT & ~filters.COMMAND, userid_input)],
        },
        fallbacks=[CommandHandler('cancel', cancel)],
    )
    
    # Add handlers
    application.add_handler(CommandHandler('start', start))
    application.add_handler(add_conv_handler)
    application.add_handler(CommandHandler('get', get_proxy))
    application.add_handler(CommandHandler('del', delete_first))
    application.add_handler(CommandHandler('delall', delete_all))
    application.add_handler(CommandHandler('showall', show_all))
    application.add_handler(CommandHandler('checkall', manual_check_balances))
    application.add_handler(CommandHandler('list', list_countries))
    application.add_handler(CallbackQueryHandler(button_callback))
    
    # Set up periodic balance check (every 1 hour)
    job_queue = application.job_queue
    job_queue.run_repeating(check_balances_task, interval=3600, first=10)  # Check every hour, first check after 10 seconds
    
    # Start the bot
    logger.info("Bot started successfully!")
    
    # Manual execution loop to ensure proper initialization on all platforms
    try:
        loop = asyncio.get_event_loop()
        loop.run_until_complete(application.initialize())
        loop.run_until_complete(application.start())
        loop.run_until_complete(application.updater.start_polling(allowed_updates=Update.ALL_TYPES))
        
        # Keep the application running
        stop_signal = asyncio.Future()
        try:
            loop.run_until_complete(stop_signal)
        except KeyboardInterrupt:
            pass
        finally:
            loop.run_until_complete(application.updater.stop())
            loop.run_until_complete(application.stop())
            loop.run_until_complete(application.shutdown())
    except Exception as e:
        logger.error(f"Critical error: {e}", exc_info=True)


if __name__ == '__main__':
    try:
        # Check for existing event loop
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
        
        main()
    except KeyboardInterrupt:
        pass
