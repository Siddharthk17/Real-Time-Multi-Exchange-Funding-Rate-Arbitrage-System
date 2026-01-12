import asyncio
import aiohttp
import logging
import time
import json
from typing import List, Any
from models import FundingRate

logger = logging.getLogger("Fetcher")
logger.setLevel(logging.INFO)

class AsyncFetcher:
    def __init__(self, user_agent: str):
        self.std_headers = {
            'User-Agent': 'python-requests/2.31.0', 
            'Accept': 'application/json',
            'Connection': 'keep-alive'
        }
        # Mimic Chrome to bypass WAFs
        self.browser_headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36',
            'Accept': 'application/json, text/plain, */*',
            'Accept-Language': 'en-US,en;q=0.9',
            'Referer': 'https://www.google.com/',
            'Origin': 'https://www.google.com',
            'Connection': 'keep-alive',
            'Sec-Fetch-Dest': 'empty',
            'Sec-Fetch-Mode': 'cors',
            'Sec-Fetch-Site': 'cross-site',
        }
        self.session = None

    async def start_session(self):
        connector = aiohttp.TCPConnector(limit=0, ttl_dns_cache=300, ssl=False)
        self.session = aiohttp.ClientSession(
            connector=connector, 
            timeout=aiohttp.ClientTimeout(total=25, connect=10)
        )

    async def close(self):
        if self.session:
            await self.session.close()

    async def _fetch(self, url: str, mode: str = 'std', extra_headers: dict = None, method: str = 'GET', post_data: dict = None) -> Any:
        if not self.session: return None
        headers = self.browser_headers.copy() if mode == 'browser' else self.std_headers.copy()
        if extra_headers: headers.update(extra_headers)

        try:
            if method == 'POST':
                if 'Content-Type' not in headers:
                    headers['Content-Type'] = 'application/json'
                async with self.session.post(url, headers=headers, json=post_data, ssl=False) as response:
                    if response.status == 200:
                        return await response.json()
            else:
                async with self.session.get(url, headers=headers, ssl=False) as response:
                    if response.status == 200:
                        return await response.json()
            return None
        except Exception:
            return None

    def _norm(self, symbol: str) -> str:
        return symbol.replace('-', '').replace('_', '').replace('/', '').upper()

    # EXISTING EXCHANGES

    async def get_binance(self) -> List[FundingRate]:
        data = await self._fetch("https://fapi.binance.com/fapi/v1/premiumIndex", mode='browser')
        if not data: return []
        res, ts = [], time.time()
        for i in data:
            if i.get('symbol', '').endswith('USDT'):
                try: res.append(FundingRate(exchange="Binance", symbol=i['symbol'], rate=float(i['lastFundingRate']) * 100, timestamp=ts))
                except: continue
        return res

    async def get_bybit(self) -> List[FundingRate]:
        data = await self._fetch("https://api.bybit.com/v5/market/tickers?category=linear", mode='browser')
        if not data or data.get('retCode') != 0: return []
        res, ts = [], time.time()
        for i in data.get('result', {}).get('list', []):
            if i.get('symbol', '').endswith('USDT') and i.get('fundingRate'):
                try: res.append(FundingRate(exchange="Bybit", symbol=i['symbol'], rate=float(i['fundingRate']) * 100, timestamp=ts))
                except: continue
        return res

    async def get_gateio(self) -> List[FundingRate]:
        data = await self._fetch("https://api.gateio.ws/api/v4/futures/usdt/tickers", mode='std')
        if not data: return []
        res, ts = [], time.time()
        for i in data:
            if 'contract' in i and 'funding_rate' in i:
                try: res.append(FundingRate(exchange="GateIO", symbol=self._norm(i['contract']), rate=float(i['funding_rate']) * 100, timestamp=ts))
                except: continue
        return res

    async def get_okx(self) -> List[FundingRate]:
        url = "https://www.okx.com/priapi/v5/public/tickers?instType=SWAP"
        headers = {"Referer": "https://www.okx.com/trade-swap"}
        data = await self._fetch(url, mode='browser', extra_headers=headers)
        if not data or data.get('code') != '0': return []
        res, ts = [], time.time()
        for i in data.get('data', []):
            inst_id = i.get('instId', '')
            if inst_id.endswith('USDT-SWAP') and i.get('fundingRate'):
                try:
                    symbol = inst_id.split('-')[0] + "USDT"
                    res.append(FundingRate(exchange="OKX", symbol=symbol, rate=float(i['fundingRate']) * 100, timestamp=ts))
                except: continue
        return res

    async def get_kucoin(self) -> List[FundingRate]:
        data = await self._fetch("https://api-futures.kucoin.com/api/v1/contracts/active", mode='std')
        if not data or data.get('code') != '200000': return []
        res, ts = [], time.time()
        for i in data.get('data', []):
            if i.get('symbol', '').endswith('USDTM') and i.get('fundingFeeRate'):
                try: res.append(FundingRate(exchange="KuCoin", symbol=i['symbol'].replace('USDTM', 'USDT'), rate=float(i['fundingFeeRate']) * 100, timestamp=ts))
                except: continue
        return res

    async def get_bitget(self) -> List[FundingRate]:
        data = await self._fetch("https://api.bitget.com/api/v2/mix/market/tickers?productType=USDT-FUTURES", mode='std')
        if not data or data.get('code') != '00000': return []
        res, ts = [], time.time()
        for i in data.get('data', []):
            if i.get('symbol', '').endswith('USDT') and i.get('fundingRate'):
                try: res.append(FundingRate(exchange="Bitget", symbol=i['symbol'], rate=float(i['fundingRate']) * 100, timestamp=ts))
                except: continue
        return res

    async def get_mexc(self) -> List[FundingRate]:
        data = await self._fetch("https://contract.mexc.com/api/v1/contract/ticker", mode='std')
        if not data or not data.get('success'): return []
        res, ts = [], time.time()
        for i in data.get('data', []):
            if i.get('symbol', '').endswith('_USDT') and i.get('fundingRate'):
                try: res.append(FundingRate(exchange="MEXC", symbol=self._norm(i['symbol']), rate=float(i['fundingRate']) * 100, timestamp=ts))
                except: continue
        return res

    async def get_huobi(self) -> List[FundingRate]:
        url = "https://api.hbdm.vn/linear-swap-api/v1/swap_batch_funding_rate"
        data = await self._fetch(url, mode='std')
        if not data or data.get('status') != 'ok': return []
        res, ts = [], time.time()
        for i in data.get('data', []):
            if i.get('contract_code', '').endswith('USDT') and i.get('funding_rate'):
                try: res.append(FundingRate(exchange="Huobi", symbol=self._norm(i['contract_code']), rate=float(i['funding_rate']) * 100, timestamp=ts))
                except: continue
        return res

    async def get_bingx(self) -> List[FundingRate]:
        data = await self._fetch("https://open-api.bingx.com/openApi/swap/v2/quote/premiumIndex", mode='std')
        if not data or data.get('code') != 0: return []
        res, ts = [], time.time()
        for i in data.get('data', []):
            rate_val = i.get('lastFundingRate')
            if i.get('symbol', '').endswith('-USDT') and rate_val:
                try: res.append(FundingRate(exchange="BingX", symbol=self._norm(i['symbol']), rate=float(rate_val) * 100, timestamp=ts))
                except: continue
        return res

    async def get_kraken(self) -> List[FundingRate]:
        data = await self._fetch("https://futures.kraken.com/derivatives/api/v3/tickers", mode='std')
        if not data or data.get('result') != 'success': return []
        res, ts = [], time.time()
        seen = set()
        for i in data.get('tickers', []):
            sym = i.get('symbol', '').upper()
            if 'USD' not in sym or 'fundingRate' not in i: continue
            if "XBT" in sym: norm = "BTCUSDT"
            elif "ETH" in sym: norm = "ETHUSDT"
            else: norm = sym.replace('PF_', '').replace('USD', '') + "USDT"
            if norm in seen: continue
            seen.add(norm)
            try: res.append(FundingRate(exchange="Kraken", symbol=norm, rate=float(i['fundingRate']), timestamp=ts))
            except: continue
        return res

    async def get_dydx(self) -> List[FundingRate]:
        data = await self._fetch("https://indexer.dydx.trade/v4/perpetualMarkets", mode='std')
        if not data or 'markets' not in data: return []
        res, ts = [], time.time()
        for key, i in data['markets'].items():
            if i.get('nextFundingRate'):
                try:
                    symbol = i.get('ticker', key).replace('-USD', 'USDT')
                    rate = float(i['nextFundingRate']) * 100
                    res.append(FundingRate(exchange="dYdX", symbol=symbol, rate=rate, timestamp=ts))
                except: continue
        return res

    async def get_bitmex(self) -> List[FundingRate]:
        data = await self._fetch("https://www.bitmex.com/api/v1/instrument/active", mode='std')
        if not data: return []
        res, ts = [], time.time()
        for i in data:
            if i.get('typ') == 'FFWCSX' and i.get('fundingRate'):
                sym = i.get('symbol', '')
                if sym == 'XBTUSD': norm = 'BTCUSDT'
                elif sym == 'ETHUSD': norm = 'ETHUSDT'
                elif sym.endswith('USDT'): norm = sym
                else: continue
                try: res.append(FundingRate(exchange="BitMEX", symbol=norm, rate=float(i['fundingRate']) * 100, timestamp=ts))
                except: continue
        return res

    async def get_phemex(self) -> List[FundingRate]:
        url = "https://api.phemex.com/md/v2/ticker/24hr"
        data = await self._fetch(url, mode='std', extra_headers={"Accept": "*/*"})
        if not data or 'result' not in data: return []
        res, ts = [], time.time()
        for i in data['result']:
            if i.get('symbol', '').endswith('USDT') and i.get('fundingRate'):
                try:
                    rate = (float(i['fundingRate']) / 100000000) * 100
                    res.append(FundingRate(exchange="Phemex", symbol=i['symbol'], rate=rate, timestamp=ts))
                except: continue
        return res

    async def get_htx(self) -> List[FundingRate]:
        url = "https://api.hbdm.com/linear-swap-api/v1/swap_batch_funding_rate"
        data = await self._fetch(url, mode='std')
        if not data or data.get('status') != 'ok': return []
        res, ts = [], time.time()
        for i in data.get('data', []):
            if i.get('contract_code', '').endswith('USDT') and i.get('funding_rate'):
                try:
                    res.append(FundingRate(exchange="HTX", symbol=self._norm(i['contract_code']), rate=float(i['funding_rate']) * 100, timestamp=ts))
                except: continue
        return res

    async def get_crypto_com(self) -> List[FundingRate]:
        url = "https://deriv-api.crypto.com/v1/public/get-valuations?valuation_type=funding_rate"
        data = await self._fetch(url, mode='browser')
        
        if not data or data.get('code') != 0: return []
        res, ts = [], time.time()
        
        for i in data.get('result', {}).get('data', []):
            sym = i.get('i', '')
            rate = i.get('v')
            
            if sym.endswith('PERP') and rate is not None:
                try:
                    norm = sym.replace('_', '').replace('-PERP', '')
                    res.append(FundingRate(exchange="CryptoCom", symbol=norm, rate=float(rate) * 100, timestamp=ts))
                except: continue
        return res

    async def get_coinbase(self) -> List[FundingRate]:
        res, ts = [], time.time()
        
        url_int = "https://api.international.coinbase.com/api/v1/instruments"
        data_int = await self._fetch(url_int, mode='browser')
        
        if data_int and 'results' in data_int:
            for i in data_int['results']:
                if i.get('type') == 'PERPETUAL':
                    sym = i.get('symbol', '')  
                    rate = i.get('funding_rate')
                    if sym and rate:
                        try:
                            norm = sym.replace('-', '').replace('PERP', 'USDT')
                            res.append(FundingRate(exchange="Coinbase", symbol=norm, rate=float(rate) * 100, timestamp=ts))
                        except: continue

        if not res:
            url_adv = "https://api.coinbase.com/api/v3/brokerage/products"
            data_adv = await self._fetch(url_adv, mode='browser')
            if data_adv and 'products' in data_adv:
                for i in data_adv['products']:
                    if i.get('product_type') == 'FUTURE': 
                        pass 
        
        return res

    async def get_hyperliquid(self) -> List[FundingRate]:
        url = "https://api.hyperliquid.xyz/info"
        post_body = {"type": "metaAndAssetCtxs"}
        data = await self._fetch(url, mode='std', method='POST', post_data=post_body)
        
        if not data or not isinstance(data, list) or len(data) < 2: return []
        
        universe = data[0].get('universe', []) if isinstance(data[0], dict) else data[0]
        ctxs = data[1]
        
        res, ts = [], time.time()
        if len(universe) != len(ctxs): return []

        for u, c in zip(universe, ctxs):
            try:
                name = u.get('name')
                funding = c.get('funding')
                if name and funding:
                    symbol = f"{name}USDT"
                    res.append(FundingRate(exchange="Hyperliquid", symbol=symbol, rate=float(funding) * 100, timestamp=ts))
            except: continue
        return res

    async def get_coinex(self) -> List[FundingRate]:
        url = "https://api.coinex.com/perpetual/v1/market/ticker/all"
        data = await self._fetch(url, mode='std')
        if not data or data.get('code') != 0: return []
        
        ticker_data = data.get('data', {}).get('ticker', {})
        res, ts = [], time.time()
        
        for sym, details in ticker_data.items():
            rate = details.get('funding_rate_next') or details.get('funding_rate_last')
            if sym.endswith('USDT') and rate:
                try:
                    res.append(FundingRate(exchange="CoinEx", symbol=sym, rate=float(rate) * 100, timestamp=ts))
                except: continue
        return res

    async def get_bitunix(self) -> List[FundingRate]:
        url = "https://fapi.bitunix.com/api/v1/futures/market/funding_rate/batch"
        data = await self._fetch(url, mode='std')
        
        res, ts = [], time.time()
        if data and data.get('code') == 0:
             for i in data.get('data', []):
                if i.get('symbol', '').endswith('USDT') and i.get('fundingRate'):
                    try:
                        res.append(FundingRate(exchange="BitUnix", symbol=i['symbol'], rate=float(i['fundingRate']), timestamp=ts))
                    except: continue

        if not res:
            url_ticker = "https://fapi.bitunix.com/api/v1/futures/market/tickers"
            data_t = await self._fetch(url_ticker, mode='std')
            if data_t and data_t.get('code') == 0:
                for i in data_t.get('data', []):
                    if i.get('symbol', '').endswith('USDT') and i.get('fundingRate'):
                        try:
                            res.append(FundingRate(exchange="BitUnix", symbol=i['symbol'], rate=float(i['fundingRate']), timestamp=ts))
                        except: continue
        return res

    async def fetch_all(self) -> List[FundingRate]:
        if not self.session: await self.start_session()
        tasks_map = {
            "Binance": self.get_binance(),
            "Bybit": self.get_bybit(),
            "OKX": self.get_okx(),
            "GateIO": self.get_gateio(),
            "KuCoin": self.get_kucoin(),
            "Bitget": self.get_bitget(),
            "MEXC": self.get_mexc(),
            "Huobi": self.get_huobi(),
            "BingX": self.get_bingx(),
            "Kraken": self.get_kraken(),
            "dYdX": self.get_dydx(),
            "BitMEX": self.get_bitmex(),
            "Phemex": self.get_phemex(),
            "HTX": self.get_htx(),
            "CryptoCom": self.get_crypto_com(),
            "Coinbase": self.get_coinbase(),
            "Hyperliquid": self.get_hyperliquid(),
            "CoinEx": self.get_coinex(),
            "BitUnix": self.get_bitunix(),
        }
        results = await asyncio.gather(*tasks_map.values(), return_exceptions=True)
        flat_results = []
        debug_stats = {}
        for (name, _), res in zip(tasks_map.items(), results):
            if isinstance(res, list):
                count = len(res)
                debug_stats[name] = count
                flat_results.extend(res)
            else:
                debug_stats[name] = "ERR"
        
        # Compact Report
        print("\n🔍 FETCH REPORT:")
        for name, count in debug_stats.items():
            status = f"[green]✅ {count}[/green]" if isinstance(count, int) and count > 0 else f"[red]❌ {count}[/red]"
            print(f"   {name:12s}: {status}")
        return flat_results
