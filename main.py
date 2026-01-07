import asyncio
import os
import threading
import signal
import sys
import time
from collections import defaultdict
from typing import List
from dotenv import load_dotenv
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich import box

from models import Opportunity
from fetcher import AsyncFetcher
from web_dashboard import start_flask_app, update_dashboard_data
from notifier import TelegramNotifier

load_dotenv()
console = Console()

USER_AGENT = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
FETCH_INTERVAL = int(os.getenv("FETCH_INTERVAL", 0.0001))
MIN_SPREAD = float(os.getenv("MIN_SPREAD", 0.025))

class ArbitrageBot:
    def __init__(self):
        self.fetcher = AsyncFetcher(USER_AGENT)
        self.notifier = TelegramNotifier()
        self.running = True
        self.latest_opportunities = []

    def calculate_arbitrage(self, rates: List) -> List[Opportunity]:

        grouped = defaultdict(list)
        for r in rates:
            # Normalize symbol
            norm_sym = r.symbol.replace('-', '').replace('_', '').replace('/', '').upper()
            if norm_sym.endswith('USDT'):
                grouped[norm_sym].append(r)

        opps = []
        for symbol, entries in grouped.items():
            # Remove duplicate exchanges
            unique_entries = {e.exchange: e for e in entries}.values()
            entries = list(unique_entries)
            
            if len(entries) < 2: continue
            
            # Sort: Lowest Rate (Long) -> Highest Rate (Short)
            entries.sort(key=lambda x: x.rate)
            
            long = entries[0]
            short = entries[-1]
            
            # Spread Calculation
            spread = short.rate - long.rate
            
            if spread >= MIN_SPREAD:
                opps.append(Opportunity(
                    symbol=symbol,
                    long_exchange=long.exchange,
                    long_rate=long.rate,
                    short_exchange=short.exchange,
                    short_rate=short.rate,
                    spread=spread,
                    annualized_spread=spread * 3 * 365
                ))
        
        return sorted(opps, key=lambda x: x.spread, reverse=True)

    async def run_loop(self):
        await self.fetcher.start_session()
        console.print(Panel.fit("[bold green]🚀 Arbitrage Engine Active[/bold green]", border_style="green"))
        
        while self.running:
            start_time = time.perf_counter()
            
            # 1. Fetch
            all_rates = await self.fetcher.fetch_all()
            
            # 2. Stats
            total_pairs = len(set(r.symbol for r in all_rates))
            
            # 3. Calculate
            self.latest_opportunities = self.calculate_arbitrage(all_rates)
            
            # 4. Notify & Web
            update_dashboard_data(self.latest_opportunities, total_pairs)
            await self.notifier.process(self.latest_opportunities)
            
            elapsed = time.perf_counter() - start_time
            
            # 5. Output
            self._print_dashboard(len(all_rates), total_pairs, len(self.latest_opportunities), elapsed)
            
            sleep_time = max(0, FETCH_INTERVAL - elapsed)
            await asyncio.sleep(sleep_time)

    def _print_dashboard(self, total_rates, total_pairs, opp_count, latency):
        summary = Table(box=box.SIMPLE, show_header=False)
        summary.add_column("Key", style="cyan")
        summary.add_column("Val", style="bold white")
        summary.add_row("⏱️ Latency", f"{latency:.3f}s")
        summary.add_row("📡 Points", f"{total_rates}")
        summary.add_row("🔄 Pairs", f"{total_pairs}")
        
        # Display Table with REAL spread
        opp_table = Table(title="🏆 TOP OPPORTUNITIES (Per Round)", box=box.ROUNDED)
        opp_table.add_column("#", style="yellow")
        opp_table.add_column("Pair", style="bold white")
        opp_table.add_column("Spread", justify="right", style="bold green")
        opp_table.add_column("Long (Buy)", style="blue")
        opp_table.add_column("Short (Sell)", style="red")
        
        for i, o in enumerate(self.latest_opportunities[:10], 1):
            opp_table.add_row(
                str(i), 
                o.symbol, 
                f"{o.spread:.4f}%", 
                f"{o.long_exchange} ({o.long_rate:.4f}%)", 
                f"{o.short_exchange} ({o.short_rate:.4f}%)"
            )

        console.print(Panel(summary, title="Status"))
        if self.latest_opportunities:
            console.print(opp_table)

    async def close(self):
        await self.fetcher.close()

def signal_handler(sig, frame):
    print("\n[INFO] Shutting down...")
    sys.exit(0)

async def main():
    bot = ArbitrageBot()
    try:
        await bot.run_loop()
    finally:
        await bot.close()

if __name__ == "__main__":
    # Register Ctrl+C handler
    signal.signal(signal.SIGINT, signal_handler)
    
    # Start Flask
    flask_thread = threading.Thread(target=start_flask_app, daemon=True)
    flask_thread.start()
    
    # Start Async Loop
    try:
        if sys.platform != 'win32':
            import uvloop
            uvloop.install()
        asyncio.run(main())
    except KeyboardInterrupt:
        pass
