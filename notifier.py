import os
import asyncio
import aiohttp
import logging
from datetime import datetime, timedelta
from typing import List
from models import Opportunity

# Configure Logging
logger = logging.getLogger("Notifier")
logger.setLevel(logging.INFO)

class TelegramNotifier:
    def __init__(self):
        self.token = os.getenv("TELEGRAM_BOT_TOKEN")
        
        # Chat ID parsing (handles spaces/commas)
        chat_ids_str = os.getenv("TELEGRAM_CHAT_IDS", "")
        self.chat_ids = [cid.strip() for cid in chat_ids_str.replace(" ", ",").split(",") if cid.strip()]
        
        self.last_sent = datetime.min
        self.interval = timedelta(hours=1) # Send every 1 hour
        self.top_count = 10

    async def send_message(self, message: str):
        if not self.token or not self.chat_ids: 
            return
        
        url = f"https://api.telegram.org/bot{self.token}/sendMessage"
        
        # SSL=False to bypass local network restriction/certificate errors
        connector = aiohttp.TCPConnector(ssl=False)
        
        async with aiohttp.ClientSession(connector=connector) as session:
            for chat_id in self.chat_ids:
                payload = {
                    'chat_id': chat_id,
                    'text': message,
                    'parse_mode': 'Markdown',
                    'disable_web_page_preview': True
                }
                try:
                    async with session.post(url, json=payload) as resp:
                        if resp.status != 200:
                            err_text = await resp.text()
                            logger.error(f"Telegram Failed ({resp.status}): {err_text}")
                except Exception as e:
                    logger.error(f"Telegram Connection Error: {e}")

    async def process(self, opportunities: List[Opportunity]):
        if not opportunities: return
        
        now = datetime.now()
        # Check if 1 hour has passed since last alert
        if now - self.last_sent < self.interval:
            return
        
        # 1. Header with Stats
        top_spread = opportunities[0].spread
        msg = f"⚡ *ARB SIGNAL DETECTED* ⚡\n"
        msg += f"───────────────────\n"
        msg += f"🕒 `{now.strftime('%H:%M UTC')}`\n"
        msg += f"💎 Best Spread: `+{top_spread:.4f}%`\n"
        msg += f"📊 Opportunities: `{len(opportunities)}`\n\n"

        # 2. List Top Opportunities
        msg += f"*🏆 TOP {self.top_count} PER ROUND (8H)*\n"
        
        for i, opp in enumerate(opportunities[:self.top_count], 1):
            # Rank Emojis
            if i == 1: rank = "🥇"
            elif i == 2: rank = "🥈"
            elif i == 3: rank = "🥉"
            else: rank = f"#{i}"

            # Calculate Spread
            spread_str = f"+{opp.spread:.4f}%"
            
            # Format Rates
            # Long: We want Negative (Receives). 
            l_val = f"{opp.long_rate:+.4f}%"
            # Short: We want Positive (Receives).
            s_val = f"{opp.short_rate:+.4f}%"

            msg += f"\n{rank} *{opp.symbol}* │ `{spread_str}`\n"
            msg += f"       L: {opp.long_exchange} (`{l_val}`)\n"
            msg += f"       S: {opp.short_exchange} (`{s_val}`)\n"

        # 3. Footer
        msg += f"\n───────────────────\n"
        msg += f"🖥️ [Live Command Center](http://51.20.6.77/bot/)"
        
        # Send and update timer
        await self.send_message(msg)
        self.last_sent = now
