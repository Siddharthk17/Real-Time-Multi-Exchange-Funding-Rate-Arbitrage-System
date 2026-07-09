import logging
from flask import Flask, render_template_string, Response
from threading import Lock
import json
import time
from datetime import datetime
from collections import Counter
from queue import Queue, Empty

try:
    import orjson
    def json_dumps(obj):
        return orjson.dumps(obj).decode('utf-8')
    HAS_ORJSON = True
except ImportError:
    def json_dumps(obj):
        return json.dumps(obj, separators=(',', ':'))
    HAS_ORJSON = False

log = logging.getLogger('werkzeug')
log.setLevel(logging.ERROR)

app = Flask(__name__)

data_lock = Lock()
_cached_response = b'{"opportunities":[],"metadata":{}}'
_latest_data = {
    "opportunities": [],
    "metadata": {}
}
_all_exchanges = set()

_sse_lock = Lock()
_sse_listeners = []

def update_dashboard_data(opportunities, total_pairs_count=0):
    global _latest_data, _cached_response, _all_exchanges
    timestamp = time.time()

    opps_list = []
    append = opps_list.append
    all_long = []
    all_short = []
    exchanges_seen = set()

    for opp in opportunities:
        append({
            "symbol": opp.symbol,
            "spread": opp.spread,
            "long_exchange": opp.long_exchange,
            "long_rate": opp.long_rate,
            "short_exchange": opp.short_exchange,
            "short_rate": opp.short_rate,
            "annualized": opp.annualized_spread
        })
        all_long.append(opp.long_exchange)
        all_short.append(opp.short_exchange)
        exchanges_seen.add(opp.long_exchange)
        exchanges_seen.add(opp.short_exchange)

    with data_lock:
        for ex in exchanges_seen:
            _all_exchanges.add(ex)
        total_active_exchanges = len(_all_exchanges)

    top_long = Counter(all_long).most_common(1)
    top_short = Counter(all_short).most_common(1)

    metadata = {
        "last_update": timestamp,
        "total_pairs_scanned": total_pairs_count,
        "active_exchanges": total_active_exchanges if total_active_exchanges > 0 else len(exchanges_seen),
        "top_long_exchange": top_long[0][0] if top_long else "N/A",
        "top_short_exchange": top_short[0][0] if top_short else "N/A",
        "count": len(opps_list)
    }

    data = {"opportunities": opps_list, "metadata": metadata}
    serialized = json_dumps(data).encode('utf-8')

    with data_lock:
        _latest_data = data
        _cached_response = serialized

    with _sse_lock:
        for q in _sse_listeners:
            q.put(serialized)


@app.route('/api/data')
def get_data():
    with data_lock:
        resp = _cached_response
    return Response(resp, mimetype='application/json')


@app.route('/api/stream')
def stream():
    def event_stream():
        q = Queue()
        with _sse_lock:
            _sse_listeners.append(q)
        
        with data_lock:
            initial_state = _cached_response
        yield f"data: {initial_state.decode('utf-8')}\n\n"
        
        try:
            while True:
                try:
                    data = q.get(timeout=10)
                    yield f"data: {data.decode('utf-8')}\n\n"
                except Empty:
                    yield ": keep-alive\n\n"
        except GeneratorExit:
            pass
        finally:
            with _sse_lock:
                if q in _sse_listeners:
                    _sse_listeners.remove(q)

    return Response(event_stream(), mimetype="text/event-stream")


@app.route("/")
def dashboard():
    return render_template_string(HTML_TEMPLATE)

def start_flask_app():
    app.run(host="0.0.0.0", port=5000, debug=False, use_reloader=False)


HTML_TEMPLATE = r"""
<!DOCTYPE html>
<html lang="en" class="dark">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Athena // Quantitative Yield Matrix</title>
    
    <script src="https://cdn.tailwindcss.com"></script>
    <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
    <link href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css" rel="stylesheet">
    <link href="https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@300;400;500;600;700&family=JetBrains+Mono:wght@400;500;700&display=swap" rel="stylesheet">

    <script>
        tailwind.config = {
            darkMode: 'class',
            theme: {
                extend: {
                    fontFamily: {
                        sans: ['Plus Jakarta Sans', 'sans-serif'],
                        mono: ['JetBrains Mono', 'monospace'],
                    },
                    colors: {
                        brand: {
                            bg: '#0a0b10',
                            card: '#12131a',
                            border: '#1e202e',
                            violet: '#9d5cff',
                            green: '#22c55e',
                            red: '#f43f5e',
                            yellow: '#fbbf24'
                        }
                    }
                }
            }
        }
    </script>

    <style>
        body {
            font-family: 'Plus Jakarta Sans', sans-serif;
            font-size: 13px;
            transition: background-color 0.3s ease, color 0.3s ease;
        }

        .custom-scroll::-webkit-scrollbar {
            width: 6px;
            height: 6px;
        }
        .custom-scroll::-webkit-scrollbar-track {
            background: transparent;
        }
        .custom-scroll::-webkit-scrollbar-thumb {
            background: #cbd5e1;
            border-radius: 99px;
        }
        .dark .custom-scroll::-webkit-scrollbar-thumb {
            background: #1e202e;
        }
        .custom-scroll::-webkit-scrollbar-thumb:hover {
            background: #9d5cff;
        }

        .striped-bar {
            background-image: repeating-linear-gradient(
                -45deg,
                transparent,
                transparent 4px,
                rgba(0, 0, 0, 0.05) 4px,
                rgba(0, 0, 0, 0.05) 8px
            );
        }
        .dark .striped-bar {
            background-image: repeating-linear-gradient(
                -45deg,
                transparent,
                transparent 4px,
                rgba(255, 255, 255, 0.08) 4px,
                rgba(255, 255, 255, 0.08) 8px
            );
        }
    </style>
</head>
<body class="h-screen w-screen flex flex-col overflow-hidden select-none bg-slate-50 text-slate-900 dark:bg-[#0a0b10] dark:text-[#f4f4f5]">

    <header class="h-20 border-b border-slate-200 dark:border-brand-border/60 bg-white/80 dark:bg-brand-bg/85 flex items-center justify-between px-8 shrink-0 backdrop-blur-sm z-50">
        <div class="flex items-center gap-3">
            <div class="w-8 h-8 rounded-full bg-gradient-to-tr from-brand-violet to-purple-400 flex items-center justify-center shadow-lg shadow-brand-violet/20">
                <span class="font-bold text-white text-sm">a</span>
            </div>
            <span class="font-bold tracking-tight text-slate-900 dark:text-white text-lg">ATHENA</span>
        </div>

        <nav class="bg-slate-100 dark:bg-[#151622] rounded-full p-1.5 border border-slate-200 dark:border-brand-border/40 flex items-center gap-1">
            <button onclick="switchTab('overview')" id="tab-overview" class="px-5 py-2 rounded-full font-semibold transition-all duration-200 text-sm bg-slate-900 text-white dark:bg-white dark:text-brand-bg shadow-sm">Overview</button>
            <button onclick="switchTab('analytics')" id="tab-analytics" class="px-5 py-2 rounded-full font-semibold transition-all duration-200 text-sm text-[#475569] dark:text-[#94a3b8] hover:text-slate-900 dark:hover:text-white">Analytics Desk</button>
            <button onclick="switchTab('sandbox')" id="tab-sandbox" class="px-5 py-2 rounded-full font-semibold transition-all duration-200 text-sm text-[#475569] dark:text-[#94a3b8] hover:text-slate-900 dark:hover:text-white">Sandbox Bots</button>
        </nav>

        <div class="flex items-center gap-4">
            <button onclick="toggleThemeMode()" class="w-10 h-10 rounded-full border border-slate-200 dark:border-brand-border/60 bg-white dark:bg-[#12131a] text-[#475569] dark:text-[#94a3b8] flex items-center justify-center hover:bg-slate-100 dark:hover:bg-[#1e202e] transition-colors" title="Toggle Theme">
                <i id="theme-toggle-icon" class="fa-solid fa-moon"></i>
            </button>

            <div class="bg-white dark:bg-[#12131a] border border-slate-200 dark:border-brand-border/60 px-4 py-2 rounded-full text-xs font-mono text-slate-500 dark:text-[#94a3b8] flex items-center gap-2">
                <span class="w-2 h-2 rounded-full bg-brand-green animate-pulse"></span>
                <span id="live-utc">--:--:-- UTC</span>
            </div>
            
            <div class="flex items-center gap-3 bg-white dark:bg-[#12131a] border border-slate-200 dark:border-brand-border/60 p-1.5 pr-4 rounded-full">
                <div class="w-8 h-8 rounded-full overflow-hidden bg-brand-violet/20 border border-brand-violet/40 flex items-center justify-center">
                    <span class="font-bold text-brand-violet text-xs">AD</span>
                </div>
                <div class="text-left hidden sm:block">
                    <div class="font-bold text-xs text-slate-900 dark:text-white leading-tight">Admin</div>
                    <div class="text-[10px] text-slate-400 dark:text-slate-500">Live Console</div>
                </div>
            </div>
        </div>
    </header>

    <div class="flex-1 overflow-y-auto custom-scroll p-6">

        <div id="panel-overview" class="space-y-6">
            <section class="grid grid-cols-1 lg:grid-cols-12 gap-6">
                
                <article class="bg-white dark:bg-brand-card border border-slate-200 dark:border-brand-border rounded-[24px] p-6 lg:col-span-4 flex flex-col justify-between overflow-hidden relative min-h-[300px] shadow-sm">
                    <div>
                        <div class="flex justify-between items-center text-xs text-slate-500 dark:text-slate-400 font-semibold mb-2">
                            <span>Selected Yield Profile</span>
                            <span class="px-2 py-0.5 rounded-full bg-brand-violet/10 text-brand-violet text-[10px]" id="yield-badge-symbol">--</span>
                        </div>
                        <div class="flex items-baseline gap-2">
                            <span class="text-4xl font-bold tracking-tight text-slate-950 dark:text-white" id="yield-headline">0.0000%</span>
                            <span class="text-xs font-semibold text-brand-green bg-brand-green/10 px-2 py-0.5 rounded-full flex items-center gap-1">
                                <i class="fa-solid fa-arrow-trend-up"></i> <span id="yield-annual">0.00% APY</span>
                            </span>
                        </div>
                        <p class="text-xs text-slate-400 dark:text-slate-500 mt-1" id="yield-available">Estimated 8-hour yield yield projection</p>
                    </div>

                    <div class="h-24 w-full relative mt-4">
                        <canvas id="trendChart" class="w-full h-full"></canvas>
                    </div>

                    <div class="grid grid-cols-2 gap-3 mt-4 pt-4 border-t border-slate-200 dark:border-brand-border/40 shrink-0">
                        <div>
                            <span class="block text-[10px] text-slate-400 dark:text-slate-500 font-semibold uppercase">Capital Allocation ($)</span>
                            <input type="number" id="calc-allocation" value="10000" step="1000" oninput="runCalculator()"
                                class="w-full bg-transparent border-b border-slate-200 dark:border-brand-border/80 focus:border-brand-violet py-0.5 text-xs font-bold text-slate-900 dark:text-white outline-none">
                        </div>
                        <div>
                            <span class="block text-[10px] text-slate-400 dark:text-slate-500 font-semibold uppercase">8h Return Estimate</span>
                            <span id="calc-payout" class="block font-bold text-brand-green py-0.5 text-xs">+$0.00</span>
                        </div>
                    </div>
                </article>

                <article class="bg-white dark:bg-brand-card border border-slate-200 dark:border-brand-border rounded-[24px] p-6 lg:col-span-4 flex flex-col justify-between min-h-[300px] shadow-sm">
                    <div class="flex justify-between items-center mb-4">
                        <span class="text-xs text-slate-500 dark:text-slate-400 font-semibold">Venue Match Matrix (Pairing Frequency)</span>
                        <span class="text-[10px] text-brand-violet font-semibold">Dynamic Grid</span>
                    </div>

                    <div id="heatmap-grid" class="grid grid-cols-6 gap-2 flex-1 justify-items-center items-center py-2 text-center text-slate-800 dark:text-slate-200">
                        <div class="col-span-6 text-center text-slate-400 dark:text-slate-500 text-xs py-8">Calculating pairing densities...</div>
                    </div>

                    <div class="flex justify-between items-center pt-3 border-t border-slate-200 dark:border-brand-border/40 text-[11px] text-slate-400 font-medium">
                        <span>Light shading denotes lower pairings</span>
                        <span class="text-brand-violet font-semibold">Direct Data</span>
                    </div>
                </article>

                <article class="bg-white dark:bg-brand-card border border-slate-200 dark:border-brand-border rounded-[24px] p-6 lg:col-span-4 flex flex-col justify-between min-h-[300px] shadow-sm">
                    <div class="flex justify-between items-center mb-4">
                        <span class="text-xs text-slate-500 dark:text-slate-400 font-semibold">Active Exchange Share</span>
                        <span class="text-[10px] text-slate-400 dark:text-slate-500">Live Volume Dist</span>
                    </div>

                    <div id="exchange-bars-wrapper" class="grid grid-cols-5 gap-3 items-end flex-1 h-36 pt-2 pb-1 relative">
                        <div class="col-span-5 text-center text-slate-400 dark:text-slate-500 text-xs py-10">Calculating volumes...</div>
                    </div>
                </article>

            </section>

            <section class="grid grid-cols-1 lg:grid-cols-12 gap-6 items-start">
                
                <article class="bg-white dark:bg-brand-card border border-slate-200 dark:border-brand-border rounded-[24px] p-6 lg:col-span-6 flex flex-col min-h-[420px] shadow-sm">
                    <div class="flex justify-between items-center mb-4">
                        <div class="flex items-center gap-2">
                            <h3 class="font-bold text-slate-900 dark:text-white tracking-tight">Market Arbitrage Paths</h3>
                            <span class="px-2 py-0.5 rounded-full bg-brand-violet/10 text-brand-violet text-[10px]" id="stat-active-paths">0 Paths</span>
                        </div>
                        
                        <div class="relative">
                            <i class="fa-solid fa-search absolute left-3 top-1/2 -translate-y-1/2 text-slate-400 dark:text-slate-500 text-xs"></i>
                            <input type="text" id="table-search" oninput="applyFiltersAndRender()" placeholder="Filter symbols..." 
                                class="bg-slate-100 dark:bg-[#151622] border border-slate-200 dark:border-brand-border rounded-full pl-8 pr-4 py-1 text-xs text-slate-900 dark:text-white placeholder-slate-400 dark:placeholder-slate-500 outline-none w-44 focus:border-brand-violet transition-colors">
                        </div>
                    </div>

                    <div class="grid grid-cols-12 gap-2 px-3 py-2 bg-slate-100 dark:bg-[#151622] border border-slate-200 dark:border-brand-border rounded-lg text-[10px] font-semibold text-slate-500 dark:text-slate-400 uppercase tracking-wider select-none shrink-0 mb-2">
                        <div class="col-span-2 cursor-pointer hover:text-slate-900 dark:hover:text-white" onclick="triggerClientSort('symbol')">Pair <span id="sort-symbol"></span></div>
                        <div class="col-span-3 text-right cursor-pointer hover:text-slate-900 dark:hover:text-white" onclick="triggerClientSort('spread')">Spread <span id="sort-spread">▼</span></div>
                        <div class="col-span-4 text-center">Transfer Legs</div>
                        <div class="col-span-3 text-right cursor-pointer hover:text-slate-900 dark:hover:text-white" onclick="triggerClientSort('annualized')">APY Estimate <span id="sort-annualized"></span></div>
                    </div>

                    <div id="live-path-rows" class="flex-1 overflow-y-auto custom-scroll space-y-1.5 max-h-[300px] pr-1">
                        <div class="flex flex-col items-center justify-center h-48 text-slate-400 dark:text-slate-500">
                            <i class="fa-solid fa-spinner fa-spin text-xl text-brand-violet mb-2"></i>
                            <span class="text-xs font-semibold">Ingesting live stream packets...</span>
                        </div>
                    </div>
                </article>

                <article class="bg-white dark:bg-brand-card border border-slate-200 dark:border-brand-border rounded-[24px] p-6 lg:col-span-3 flex flex-col justify-between min-h-[420px] shadow-sm">
                    <div class="flex justify-between items-center mb-4">
                        <span class="text-xs text-slate-500 dark:text-slate-400 font-semibold">Active Bot Sandbox</span>
                        <button onclick="deployBotSimulation()" class="text-xs bg-brand-violet/15 hover:bg-brand-violet/25 text-brand-violet px-3 py-1 rounded-full font-bold transition-all border border-brand-violet/30">+ Deploy Bot</button>
                    </div>

                    <div class="flex-1 flex flex-col justify-center relative">
                        <div class="w-32 h-32 rounded-full border-[10px] border-slate-100 dark:border-[#1a1c29] flex items-center justify-center relative mx-auto my-4 shrink-0">
                            <svg class="absolute inset-0 w-full h-full transform -rotate-90">
                                <circle cx="64" cy="64" r="54" id="pnl-svg-circle" stroke="#9d5cff" stroke-width="10" fill="transparent" stroke-dasharray="339" stroke-dashoffset="339" stroke-linecap="round" class="transition-all duration-500"/>
                            </svg>
                            <div class="text-center z-10">
                                <span class="block text-[10px] font-semibold text-slate-400 dark:text-slate-500 uppercase">Sandbox PnL</span>
                                <span class="text-lg font-bold text-brand-green leading-none" id="total-sandbox-pnl">+$0.00</span>
                            </div>
                        </div>

                        <div id="sandbox-ledger" class="space-y-2 mt-4 max-h-[160px] overflow-y-auto custom-scroll pr-1">
                            <div class="text-center text-slate-400 dark:text-slate-500 text-xs py-4">No active sandbox bots deployed.</div>
                        </div>
                    </div>
                </article>

                <article class="bg-white dark:bg-brand-card border border-slate-200 dark:border-brand-border rounded-[24px] p-6 lg:col-span-3 flex flex-col justify-between min-h-[420px] shadow-sm">
                    <div class="flex justify-between items-center mb-4">
                        <span class="text-xs text-slate-500 dark:text-slate-400 font-semibold">Server Execution Nodes</span>
                        <span class="text-xs font-mono text-slate-400 dark:text-slate-500 tracking-wider" id="latency-stats">Stable / -- ms</span>
                    </div>

                    <div class="flex-1 relative flex items-center justify-center min-h-[180px] w-full">
                        <canvas id="interactive-map" class="w-full h-full absolute inset-0"></canvas>
                    </div>

                    <div class="space-y-2 pt-3 border-t border-slate-200 dark:border-brand-border/40 text-[11px]">
                        <div class="flex justify-between items-center">
                            <span class="text-slate-400 dark:text-slate-500">Pipeline Status:</span>
                            <span class="text-brand-green font-semibold">ACTIVE &middot; SYNCD</span>
                        </div>
                        <div class="flex justify-between items-center">
                            <span class="text-slate-400 dark:text-slate-500">Execution Rate:</span>
                            <span class="font-mono text-slate-500 dark:text-slate-400" id="sync-rate">-- Scans / Sec</span>
                        </div>
                    </div>
                </article>

            </section>
        </div>

        <div id="panel-analytics" class="hidden space-y-6">
            <section class="grid grid-cols-1 lg:grid-cols-3 gap-6">
                <div class="bg-white dark:bg-brand-card border border-slate-200 dark:border-brand-border rounded-[24px] p-6 space-y-4 shadow-sm">
                    <h3 class="font-bold text-slate-900 dark:text-white text-base">Ingestion Database Diagnostics</h3>
                    <div class="space-y-3 pt-2 text-xs">
                        <div class="flex justify-between py-2 border-b border-slate-200 dark:border-brand-border/60">
                            <span class="text-slate-400">Total Opportunities Listed:</span>
                            <span class="font-bold text-slate-900 dark:text-white font-mono" id="an-total-paths">0</span>
                        </div>
                        <div class="flex justify-between py-2 border-b border-slate-200 dark:border-brand-border/60">
                            <span class="text-slate-400">Total Scanned Candidates:</span>
                            <span class="font-bold text-slate-900 dark:text-white font-mono" id="an-total-scanned">0</span>
                        </div>
                        <div class="flex justify-between py-2 border-b border-slate-200 dark:border-brand-border/60">
                            <span class="text-slate-400">Primary Long Sourcing:</span>
                            <span class="font-bold text-brand-violet font-mono" id="an-top-long">--</span>
                        </div>
                        <div class="flex justify-between py-2 border-b border-slate-200 dark:border-brand-border/60">
                            <span class="text-slate-400">Primary Short Sourcing:</span>
                            <span class="font-bold text-brand-red font-mono" id="an-top-short">--</span>
                        </div>
                        <div class="flex justify-between py-2">
                            <span class="text-slate-400">Active Exchanges:</span>
                            <span class="font-bold text-brand-green font-mono" id="an-exchanges">0</span>
                        </div>
                    </div>
                </div>

                <div class="bg-white dark:bg-brand-card border border-slate-200 dark:border-brand-border rounded-[24px] p-6 lg:col-span-2 shadow-sm">
                    <h3 class="font-bold text-slate-900 dark:text-white text-base mb-4">Pairing Density & Sourcing Volume Breakout</h3>
                    
                    <div class="overflow-x-auto">
                        <table class="w-full text-left text-xs font-mono">
                            <thead>
                                <tr class="text-slate-400 border-b border-slate-200 dark:border-brand-border/80 pb-2">
                                    <th class="pb-2">Long Sourcing Leg</th>
                                    <th class="pb-2">Short Sourcing Leg</th>
                                    <th class="pb-2 text-right">Route Opportunities</th>
                                    <th class="pb-2 text-right">Density Share</th>
                                </tr>
                            </thead>
                            <tbody id="an-pairing-tbody" class="divide-y divide-slate-100 dark:divide-brand-border/40 text-slate-600 dark:text-slate-300">
                                <tr>
                                    <td colspan="4" class="py-6 text-center text-slate-400">Awaiting diagnostic matrices...</td>
                                </tr>
                            </tbody>
                        </table>
                    </div>
                </div>
            </section>
        </div>

        <div id="panel-sandbox" class="hidden space-y-6">
            <section class="grid grid-cols-1 lg:grid-cols-12 gap-6">
                <div class="bg-white dark:bg-brand-card border border-slate-200 dark:border-brand-border rounded-[24px] p-6 lg:col-span-4 space-y-4 shadow-sm">
                    <h3 class="font-bold text-slate-900 dark:text-white text-base">Interactive Bot Deploy Desk</h3>
                    <p class="text-xs text-slate-400 dark:text-slate-500">Configure parameters for a tracking, simulation bot linked to the target asset.</p>
                    
                    <div class="space-y-3 pt-2">
                        <div class="p-3 bg-slate-100 dark:bg-[#151622] border border-slate-200 dark:border-brand-border rounded-xl">
                            <span class="block text-[10px] text-slate-400 dark:text-slate-500 font-bold uppercase mb-1">Anchor Asset:</span>
                            <span class="text-sm font-bold text-slate-900 dark:text-white font-mono" id="sb-anchor-asset">--</span>
                        </div>
                        <div class="p-3 bg-slate-100 dark:bg-[#151622] border border-slate-200 dark:border-brand-border rounded-xl">
                            <span class="block text-[10px] text-slate-400 dark:text-slate-500 font-bold uppercase mb-1">Target Rate spread (8h):</span>
                            <span class="text-sm font-bold text-brand-green font-mono" id="sb-anchor-rate">0.0000%</span>
                        </div>
                        
                        <div class="space-y-1.5">
                            <label class="block text-xs font-semibold text-slate-500 dark:text-slate-400">Leverage Factor:</label>
                            <select id="sb-leverage" class="w-full bg-slate-100 dark:bg-[#151622] border border-slate-200 dark:border-brand-border rounded-lg p-2.5 text-xs text-slate-900 dark:text-white">
                                <option value="1">1.0x Leveraged (Spot Capital)</option>
                                <option value="3" selected>3.0x Margined</option>
                                <option value="5">5.0x Margined</option>
                                <option value="10">10.0x Margined (High Yield)</option>
                            </select>
                        </div>

                        <button onclick="deployBotSimulation()" class="w-full bg-brand-violet text-white py-2.5 rounded-xl font-bold hover:bg-[#8646e6] transition-all shadow-md shadow-brand-violet/20">
                            LAUNCH SIMULATOR BOT
                        </button>
                    </div>
                </div>

                <div class="bg-white dark:bg-brand-card border border-slate-200 dark:border-brand-border rounded-[24px] p-6 lg:col-span-8 flex flex-col min-h-[400px] shadow-sm">
                    <div class="flex justify-between items-center mb-4">
                        <h3 class="font-bold text-slate-900 dark:text-white text-base">Active Bots Simulation Ledger</h3>
                        <div class="flex items-center gap-3">
                            <span class="text-xs text-slate-400">Collective Portfolio PnL:</span>
                            <span class="text-base font-bold text-brand-green font-mono" id="sb-collective-pnl">+$0.00</span>
                        </div>
                    </div>

                    <div id="sb-ledger-container" class="flex-1 overflow-y-auto custom-scroll space-y-3 pr-1">
                        <div class="text-center text-slate-400 dark:text-slate-500 py-16">No active sandbox simulator bots deployed. Select a row in the matrix to deploy.</div>
                    </div>
                </div>
            </section>
        </div>

    </div>

    <script>
        let rawOpps = [];
        let filteredOpps = [];
        let exchangeCatalog = new Set();
        let selectedOpp = null;
        let chartInstance = null;
        let lastPingTime = 0;
        let sseConnection = null;

        let sortConfig = {
            column: 'spread',
            direction: 'desc'
        };

        let deployedBots = [];
        let botIdSeq = 1;

        let mapCanvas = null;
        let mapCtx = null;
        let mapAnimationId = null;
        let transitMs = 50;

        const geohubs = {
            'TYO': { x: 195, y: 45, label: 'Tokyo' },
            'LDN': { x: 115, y: 35, label: 'London' },
            'SGP': { x: 145, y: 75, label: 'Singapore' },
            'NYC': { x: 50, y: 40, label: 'Chicago' }
        };

        let mapParticles = [];

        const dom = {
            liveRows: document.getElementById('live-path-rows'),
            search: document.getElementById('table-search'),
            activePaths: document.getElementById('stat-active-paths'),
            utc: document.getElementById('live-utc'),
            latency: document.getElementById('latency-stats'),
            syncRate: document.getElementById('sync-rate'),
            
            yieldHeadline: document.getElementById('yield-headline'),
            yieldBadgeSymbol: document.getElementById('yield-badge-symbol'),
            yieldAnnual: document.getElementById('yield-annual'),
            calcAlloc: document.getElementById('calc-allocation'),
            calcPayout: document.getElementById('calc-payout'),

            heatmapGrid: document.getElementById('heatmap-grid'),
            exchangeBars: document.getElementById('exchange-bars-wrapper'),

            svgCircle: document.getElementById('pnl-svg-circle'),
            totalSandboxPnL: document.getElementById('total-sandbox-pnl'),
            sandboxLedger: document.getElementById('sandbox-ledger'),
            
            panelOverview: document.getElementById('panel-overview'),
            panelAnalytics: document.getElementById('panel-analytics'),
            panelSandbox: document.getElementById('panel-sandbox'),

            anTotalPaths: document.getElementById('an-total-paths'),
            anTotalScanned: document.getElementById('an-total-scanned'),
            anTopLong: document.getElementById('an-top-long'),
            anTopShort: document.getElementById('an-top-short'),
            anExchanges: document.getElementById('an-exchanges'),
            anPairingTbody: document.getElementById('an-pairing-tbody'),

            sbAnchorAsset: document.getElementById('sb-anchor-asset'),
            sbAnchorRate: document.getElementById('sb-anchor-rate'),
            sbLeverage: document.getElementById('sb-leverage'),
            sbCollectivePnl: document.getElementById('sb-collective-pnl'),
            sbLedgerContainer: document.getElementById('sb-ledger-container')
        };

        function getExchangeHub(exchangeName) {
            if (!exchangeName) return 'NYC';
            const ex = exchangeName.toUpperCase();
            if (ex.includes('BINANCE') || ex.includes('OKX') || ex.includes('BYBIT')) return 'TYO';
            if (ex.includes('DYDX') || ex.includes('DERIBIT')) return 'LDN';
            if (ex.includes('HTX') || ex.includes('GATE')) return 'SGP';
            return 'NYC';
        }

        function toggleThemeMode() {
            const htmlElement = document.documentElement;
            const toggleIcon = document.getElementById('theme-toggle-icon');
            
            if (htmlElement.classList.contains('dark')) {
                htmlElement.classList.remove('dark');
                toggleIcon.className = "fa-solid fa-sun text-[#fbbf24]";
                localStorage.setItem('theme', 'light');
                updateChartStylingForTheme(false);
            } else {
                htmlElement.classList.add('dark');
                toggleIcon.className = "fa-solid fa-moon text-[#94a3b8]";
                localStorage.setItem('theme', 'dark');
                updateChartStylingForTheme(true);
            }
        }

        function initSavedTheme() {
            const savedTheme = localStorage.getItem('theme') || 'dark';
            const htmlElement = document.documentElement;
            const toggleIcon = document.getElementById('theme-toggle-icon');
            
            if (savedTheme === 'dark') {
                htmlElement.classList.add('dark');
                toggleIcon.className = "fa-solid fa-moon text-[#94a3b8]";
                updateChartStylingForTheme(true);
            } else {
                htmlElement.classList.remove('dark');
                toggleIcon.className = "fa-solid fa-sun text-[#fbbf24]";
                updateChartStylingForTheme(false);
            }
        }

        function updateChartStylingForTheme(isDark) {
            if (!chartInstance) return;
            const gridColor = isDark ? 'rgba(255, 255, 255, 0.05)' : 'rgba(0, 0, 0, 0.05)';
            const tickColor = isDark ? '#94a3b8' : '#475569';
            
            chartInstance.options.scales.x.grid.color = gridColor;
            chartInstance.options.scales.y.grid.color = gridColor;
            chartInstance.options.scales.x.ticks.color = tickColor;
            chartInstance.options.scales.y.ticks.color = tickColor;
            chartInstance.update();
        }

        function switchTab(activeTabId) {
            const tabs = ['overview', 'analytics', 'sandbox'];
            
            dom.panelOverview.className = activeTabId === 'overview' ? 'space-y-6' : 'hidden';
            dom.panelAnalytics.className = activeTabId === 'analytics' ? 'space-y-6' : 'hidden';
            dom.panelSandbox.className = activeTabId === 'sandbox' ? 'space-y-6' : 'hidden';

            tabs.forEach(tab => {
                const btn = document.getElementById(`tab-${tab}`);
                if (tab === activeTabId) {
                    btn.className = "px-5 py-2 rounded-full font-semibold transition-all duration-200 text-sm bg-slate-900 text-white dark:bg-white dark:text-brand-bg shadow-sm";
                } else {
                    btn.className = "px-5 py-2 rounded-full font-semibold transition-all duration-200 text-sm text-[#475569] dark:text-[#94a3b8] hover:text-slate-900 dark:hover:text-white";
                }
            });
        }

        function initPerformanceLineChart() {
            const ctx = document.getElementById('trendChart').getContext('2d');
            
            const gradient = ctx.createLinearGradient(0, 0, 0, 80);
            gradient.addColorStop(0, 'rgba(157, 92, 255, 0.25)');
            gradient.addColorStop(1, 'rgba(157, 92, 255, 0.00)');

            chartInstance = new Chart(ctx, {
                type: 'line',
                data: {
                    labels: ['1h', '2h', '3h', '4h', '5h', '6h', '7h', '8h'],
                    datasets: [{
                        data: [0, 0, 0, 0, 0, 0, 0, 0],
                        borderColor: '#9d5cff',
                        borderWidth: 2,
                        fill: true,
                        backgroundColor: gradient,
                        tension: 0.4,
                        pointRadius: 0,
                        pointHoverRadius: 4,
                        pointBackgroundColor: '#9d5cff'
                    }]
                },
                options: {
                    responsive: true,
                    maintainAspectRatio: false,
                    plugins: { legend: { display: false } },
                    scales: {
                        x: { display: false },
                        y: { display: false }
                    }
                }
            });
            
            initSavedTheme();
        }

        function triggerClientSort(column) {
            if (sortConfig.column === column) {
                sortConfig.direction = sortConfig.direction === 'desc' ? 'asc' : 'desc';
            } else {
                sortConfig.column = column;
                sortConfig.direction = 'desc';
            }
            updateSortHeaderIndicators();
            applyFiltersAndRender();
        }

        function updateSortHeaderIndicators() {
            const cols = ['symbol', 'spread', 'annualized'];
            cols.forEach(col => {
                const marker = document.getElementById(`sort-${col}`);
                if (marker) {
                    if (col === sortConfig.column) {
                        marker.innerText = sortConfig.direction === 'desc' ? ' ▲' : ' ▼';
                    } else {
                        marker.innerText = '';
                    }
                }
            });
        }

        function runCalculator() {
            const allocation = parseFloat(dom.calcAlloc.value) || 0;
            const spread = selectedOpp ? selectedOpp.spread : 0;
            const payout = allocation * (spread / 100);
            dom.calcPayout.innerText = `+$${payout.toFixed(2)}`;
        }

        function selectRow(index) {
            const target = filteredOpps[index];
            if (!target) return;

            selectedOpp = target;

            dom.yieldHeadline.innerText = `${target.spread.toFixed(4)}%`;
            dom.yieldBadgeSymbol.innerText = target.symbol;
            dom.yieldAnnual.innerText = `APY ${target.annualized.toFixed(2)}%`;

            dom.sbAnchorAsset.innerText = target.symbol;
            dom.sbAnchorRate.innerText = `${target.spread.toFixed(4)}%`;

            mapParticles = [];

            if (chartInstance) {
                const baseVal = target.spread;
                chartInstance.data.datasets[0].data = [
                    baseVal * 0.72,
                    baseVal * 0.84,
                    baseVal * 0.68,
                    baseVal * 0.95,
                    baseVal * 0.81,
                    baseVal * 1.05,
                    baseVal * 0.92,
                    baseVal
                ];
                chartInstance.update();
            }

            runCalculator();
            applyFiltersAndRender();
        }

        function applyFiltersAndRender() {
            const query = dom.search.value.toUpperCase().trim();
            
            filteredOpps = rawOpps.filter(o => query === '' || o.symbol.includes(query));

            const col = sortConfig.column;
            const dir = sortConfig.direction === 'desc' ? 1 : -1;

            filteredOpps.sort((a, b) => {
                if (col === 'symbol') {
                    return dir * b.symbol.localeCompare(a.symbol);
                } else if (col === 'spread') {
                    return dir * (b.spread - a.spread);
                } else if (col === 'annualized') {
                    return dir * (b.annualized - a.annualized);
                }
                return 0;
            });

            if (filteredOpps.length === 0) {
                dom.liveRows.innerHTML = `
                    <div class="text-center py-20 text-slate-400 dark:text-slate-500 font-medium text-xs">
                        No active spreads match parameters.
                    </div>`;
                return;
            }

            let html = '';
            for (let i = 0; i < filteredOpps.length; i++) {
                const o = filteredOpps[i];
                const isSelected = selectedOpp && selectedOpp.symbol === o.symbol && selectedOpp.long_exchange === o.long_exchange && selectedOpp.short_exchange === o.short_exchange;
                const rowStyle = isSelected ? 'bg-brand-violet/15 border-brand-violet/40 text-slate-900 dark:text-white' : 'bg-[#151622]/5 dark:bg-[#151622]/40 hover:bg-[#151622]/10 dark:hover:bg-white/5 border-transparent';

                html += `
                <div onclick="selectRow(${i})" class="grid grid-cols-12 gap-2 px-3 py-2.5 rounded-xl border items-center cursor-pointer transition-all ${rowStyle}">
                    <div class="col-span-2 font-bold font-mono text-slate-900 dark:text-white">${o.symbol}</div>
                    <div class="col-span-3 text-right font-mono font-bold text-brand-green">+${o.spread.toFixed(4)}%</div>
                    <div class="col-span-4 flex items-center justify-center gap-1 text-[10px] font-semibold text-slate-500 dark:text-slate-400">
                        <span class="px-1.5 py-0.5 rounded bg-slate-100 dark:bg-brand-bg/60 border border-slate-200 dark:border-brand-border/40 text-slate-700 dark:text-slate-300">${o.long_exchange.toUpperCase()}</span>
                        <i class="fa-solid fa-arrow-right-long text-brand-violet opacity-60"></i>
                        <span class="px-1.5 py-0.5 rounded bg-slate-100 dark:bg-brand-bg/60 border border-slate-200 dark:border-brand-border/40 text-slate-700 dark:text-slate-300">${o.short_exchange.toUpperCase()}</span>
                    </div>
                    <div class="col-span-3 text-right font-semibold text-slate-600 dark:text-slate-300 font-mono">${o.annualized.toFixed(2)}% APY</div>
                </div>`;
            }
            dom.liveRows.innerHTML = html;
        }

        function calculateExchangeShareDynamics() {
            if (rawOpps.length === 0) {
                dom.exchangeBars.innerHTML = `
                    <div class="col-span-5 text-center text-slate-400 dark:text-slate-500 text-xs py-10">
                        No active opportunities scanned yet.
                    </div>`;
                return;
            }

            const counts = {};
            let totalInstances = 0;

            rawOpps.forEach(o => {
                counts[o.long_exchange] = (counts[o.long_exchange] || 0) + 1;
                counts[o.short_exchange] = (counts[o.short_exchange] || 0) + 1;
                totalInstances += 2;
            });

            const sortedExchanges = Object.entries(counts).sort((a, b) => b[1] - a[1]);
            const targetLimit = Math.min(sortedExchanges.length, 5);

            let barsHtml = '';
            for (let i = 0; i < 5; i++) {
                if (i < targetLimit) {
                    const [name, freq] = sortedExchanges[i];
                    const percent = Math.round((freq / totalInstances) * 100);
                    const shortName = name.slice(0, 3).toUpperCase();

                    barsHtml += `
                    <div class="flex flex-col items-center gap-2 h-full justify-end group cursor-pointer">
                        <span class="text-[9px] font-bold text-slate-500 dark:text-slate-400 group-hover:text-slate-900 dark:group-hover:text-white transition-colors">${percent}%</span>
                        <div class="w-6 rounded-t-lg bg-brand-violet/40 group-hover:bg-brand-violet/60 border border-brand-violet/20 h-[${percent}%] relative overflow-hidden transition-all striped-bar" style="height: ${percent}%">
                            <div class="absolute bottom-0 left-0 right-0 h-2/3 bg-brand-violet rounded-t-sm shadow-[0_0_15px_rgba(157,92,255,0.4)]"></div>
                        </div>
                        <span class="text-[9px] font-mono text-slate-500 tracking-wider">${shortName}</span>
                    </div>`;
                } else {
                    barsHtml += `
                    <div class="flex flex-col items-center gap-2 h-full justify-end opacity-20">
                        <span class="text-[9px] font-bold text-slate-400 dark:text-slate-600">0%</span>
                        <div class="w-6 rounded-t-lg bg-slate-100 dark:bg-[#151622] border border-slate-200 dark:border-brand-border h-[5%]"></div>
                        <span class="text-[9px] font-mono text-slate-400 dark:text-slate-600 tracking-wider">--</span>
                    </div>`;
                }
            }
            dom.exchangeBars.innerHTML = barsHtml;
        }

        function calculatePairingHeatmap() {
            if (rawOpps.length === 0) {
                dom.heatmapGrid.innerHTML = `
                    <div class="col-span-6 text-center text-slate-400 dark:text-slate-500 text-xs py-8">
                        No active pairing data.
                    </div>`;
                return;
            }

            const counts = {};
            rawOpps.forEach(o => {
                counts[o.long_exchange] = (counts[o.long_exchange] || 0) + 1;
                counts[o.short_exchange] = (counts[o.short_exchange] || 0) + 1;
            });
            const top5Exchanges = Object.entries(counts)
                .sort((a, b) => b[1] - a[1])
                .slice(0, 5)
                .map(item => item[0]);

            if (top5Exchanges.length === 0) return;

            let gridHtml = `<div></div>`;
            top5Exchanges.forEach(ex => {
                gridHtml += `<div class="text-[8px] font-bold text-slate-400 dark:text-slate-500 uppercase tracking-wider">${ex.slice(0, 3)}</div>`;
            });

            for (let i = 0; i < 5; i++) {
                const longEx = top5Exchanges[i] || '--';
                gridHtml += `<div class="text-[8px] font-bold text-slate-400 dark:text-slate-500 uppercase tracking-wider text-left">${longEx.slice(0, 3)}</div>`;

                for (let j = 0; j < 5; j++) {
                    const shortEx = top5Exchanges[j] || '--';
                    
                    const matches = rawOpps.filter(o => o.long_exchange === longEx && o.short_exchange === shortEx).length;
                    
                    let cellColor = 'bg-slate-100 dark:bg-[#151622]/45 border border-slate-200 dark:border-transparent text-slate-400 dark:text-slate-600';
                    if (matches === 1) {
                        cellColor = 'bg-[#241c3a] border border-brand-violet/20 text-slate-300';
                    } else if (matches === 2) {
                        cellColor = 'bg-[#3b216b] border border-brand-violet/30 text-white';
                    } else if (matches >= 3) {
                        cellColor = 'bg-[#5d31a8] border border-brand-violet/40 text-white font-bold shadow-lg shadow-brand-violet/20';
                    }

                    gridHtml += `
                    <div class="w-7 h-7 rounded-md flex items-center justify-center text-[10px] transition-all cursor-help ${cellColor}" title="${longEx} to ${shortEx}: ${matches} paths">
                        ${matches}
                    </div>`;
                }
            }

            dom.heatmapGrid.innerHTML = gridHtml;
        }

        function populateDetailedAnalytics() {
            dom.anTotalPaths.innerText = rawOpps.length;
            if (rawOpps.length === 0) {
                dom.anPairingTbody.innerHTML = `<tr><td colspan="4" class="py-6 text-center text-slate-400">Awaiting diagnostic matrices...</td></tr>`;
                return;
            }
            
            const pairings = {};
            rawOpps.forEach(o => {
                const route = `${o.long_exchange.toUpperCase()} &rarr; ${o.short_exchange.toUpperCase()}`;
                pairings[route] = (pairings[route] || 0) + 1;
            });

            const sortedPairings = Object.entries(pairings).sort((a,b) => b[1] - a[1]);
            
            let tbodyHtml = '';
            sortedPairings.forEach(([route, freq]) => {
                const pct = ((freq / rawOpps.length) * 100).toFixed(1);
                const split = route.split(' &rarr; ');
                const longStr = split[0];
                const shortStr = split[1];

                tbodyHtml += `
                <tr class="hover:bg-slate-50 dark:hover:bg-[#151622]/30 transition-colors">
                    <td class="py-2.5 font-bold text-slate-900 dark:text-white">${longStr}</td>
                    <td class="py-2.5 font-bold text-slate-500 dark:text-slate-400">${shortStr}</td>
                    <td class="py-2.5 text-right font-bold text-brand-green">${freq}</td>
                    <td class="py-2.5 text-right text-slate-400">${pct}%</td>
                </tr>`;
            });
            dom.anPairingTbody.innerHTML = tbodyHtml;
        }

        function deployBotSimulation() {
            const target = selectedOpp || (rawOpps.length > 0 ? rawOpps[0] : null);
            if (!target) return;

            const allocation = parseFloat(dom.calcAlloc.value) || 10000;
            const lev = parseFloat(dom.sbLeverage.value) || 1;

            const bot = {
                id: botIdSeq++,
                symbol: target.symbol,
                rate: target.spread,
                longEx: target.long_exchange,
                shortEx: target.short_exchange,
                allocated: allocation,
                leverage: lev,
                pnl: 0,
                timestamp: Date.now()
            };

            deployedBots.push(bot);
            switchTab('sandbox');
            renderBotLedgers();
        }

        function shutdownActiveBot(id) {
            deployedBots = deployedBots.filter(b => b.id !== id);
            renderBotLedgers();
        }

        function calculateSimulationRates() {
            const secondsIn8h = 8 * 3600;

            deployedBots.forEach(b => {
                const elapsedSeconds = (Date.now() - b.timestamp) / 1000;
                const rateFactor = (b.rate / 100) / secondsIn8h;
                b.pnl = b.allocated * b.leverage * rateFactor * elapsedSeconds;
            });

            const collectiveSum = deployedBots.reduce((sum, b) => sum + b.pnl, 0);
            const sign = collectiveSum >= 0 ? '+' : '';
            
            dom.totalSandboxPnL.innerText = `${sign}$${collectiveSum.toFixed(4)}`;
            dom.sbCollectivePnl.innerText = `${sign}$${collectiveSum.toFixed(4)}`;

            const maxGoal = 50.0;
            const percentage = Math.min((Math.max(collectiveSum, 0) / maxGoal) * 100, 100);
            const offset = 339 - (339 * percentage / 100);
            dom.svgCircle.setAttribute('stroke-dashoffset', offset);

            renderBotLedgers();
        }

        function renderBotLedgers() {
            if (deployedBots.length === 0) {
                dom.sandboxLedger.innerHTML = `
                    <div class="text-center text-slate-400 dark:text-slate-500 text-xs py-4">
                        No active sandbox bots deployed.
                    </div>`;
                dom.sbLedgerContainer.innerHTML = `
                    <div class="text-center text-slate-400 dark:text-slate-500 py-16">
                        No active sandbox simulator bots deployed. Select a row in the matrix to deploy.
                    </div>`;
                return;
            }

            let overviewHtml = '';
            let detailedHtml = '';

            deployedBots.forEach(b => {
                const color = b.pnl >= 0 ? 'text-brand-green' : 'text-brand-red';
                const sign = b.pnl >= 0 ? '+' : '';

                overviewHtml += `
                <div class="flex justify-between items-center bg-slate-50 dark:bg-[#151622] border border-slate-200 dark:border-brand-border/80 px-3 py-2 rounded-xl text-xs">
                    <div>
                        <div class="font-bold text-slate-900 dark:text-white flex items-center gap-1.5">
                            <span>Bot #${b.id} &middot; ${b.symbol}</span>
                            <span class="text-[9px] font-mono text-slate-400 dark:text-slate-500">($${b.allocated.toLocaleString()})</span>
                        </div>
                    </div>
                    <div class="text-right flex items-center gap-2">
                        <span class="${color} font-bold font-mono">${sign}$${b.pnl.toFixed(4)}</span>
                        <button onclick="shutdownActiveBot(${b.id})" class="text-brand-red hover:underline font-bold text-[10px]">[Close]</button>
                    </div>
                </div>`;

                detailedHtml += `
                <div class="p-5 bg-white dark:bg-[#12131a] border border-slate-200 dark:border-brand-border rounded-2xl flex flex-col md:flex-row justify-between items-start md:items-center gap-4 shadow-sm">
                    <div class="space-y-1">
                        <div class="flex items-center gap-2">
                            <span class="px-2.5 py-1 rounded-full bg-brand-violet/10 text-brand-violet text-xs font-bold font-mono">ID #${b.id}</span>
                            <span class="text-base font-bold text-slate-900 dark:text-white">${b.symbol} ARBITRAGE SIMULATOR</span>
                        </div>
                        <div class="text-xs text-slate-500 dark:text-slate-400">
                            Route Flow Direction: <span class="font-bold text-slate-900 dark:text-white">${b.longEx.toUpperCase()}</span> &rarr; <span class="font-bold text-slate-900 dark:text-white">${b.shortEx.toUpperCase()}</span>
                        </div>
                        <div class="text-[10px] text-slate-400 dark:text-slate-500 font-mono">
                            Allocated Spot: $${b.allocated.toLocaleString()} @ ${b.leverage.toFixed(1)}x Leverage | Path Spread: ${b.rate.toFixed(4)}%
                        </div>
                    </div>
                    
                    <div class="flex items-center gap-4 self-stretch md:self-auto justify-between md:justify-end border-t md:border-t-0 border-slate-100 dark:border-brand-border/40 pt-3 md:pt-0">
                        <div class="text-right">
                            <span class="block text-[9px] text-slate-400 dark:text-slate-500 font-bold uppercase">Simulated returns</span>
                            <span class="text-base font-bold font-mono ${color}">${sign}$${b.pnl.toFixed(5)}</span>
                        </div>
                        <button onclick="shutdownActiveBot(${b.id})" class="px-4 py-2 bg-brand-red/10 hover:bg-brand-red/25 border border-brand-red/30 text-brand-red font-semibold rounded-xl text-xs transition-colors">
                            Close & Recover
                        </button>
                    </div>
                </div>`;
            });

            dom.sandboxLedger.innerHTML = overviewHtml;
            dom.sbLedgerContainer.innerHTML = detailedHtml;
        }

        function initInteractiveCanvasMap() {
            mapCanvas = document.getElementById('interactive-map');
            mapCtx = mapCanvas.getContext('2d');

            function resizeCanvas() {
                const rect = mapCanvas.parentNode.getBoundingClientRect();
                mapCanvas.width = rect.width;
                mapCanvas.height = rect.height;
            }

            window.addEventListener('resize', resizeCanvas);
            resizeCanvas();

            function animateMap() {
                const w = mapCanvas.width;
                const h = mapCanvas.height;
                const isDark = document.documentElement.classList.contains('dark');

                mapCtx.clearRect(0, 0, w, h);

                const scaleX = w / 240;
                const scaleY = h / 120;

                mapCtx.fillStyle = isDark ? 'rgba(30, 32, 46, 0.15)' : 'rgba(219, 234, 254, 0.4)';
                mapCtx.beginPath();
                mapCtx.moveTo(20 * scaleX, 85 * scaleY);
                mapCtx.bezierCurveTo(40 * scaleX, 20 * scaleY, 60 * scaleX, 40 * scaleY, 80 * scaleX, 25 * scaleY);
                mapCtx.bezierCurveTo(100 * scaleX, 40 * scaleY, 120 * scaleX, 20 * scaleY, 140 * scaleX, 40 * scaleY);
                mapCtx.bezierCurveTo(160 * scaleX, 30 * scaleY, 180 * scaleX, 40 * scaleY, 200 * scaleX, 20 * scaleY);
                mapCtx.bezierCurveTo(220 * scaleX, 50 * scaleY, 240 * scaleX, 40 * scaleY, 240 * scaleX, 80 * scaleY);
                mapCtx.quadraticCurveTo(180 * scaleX, 85 * scaleY, 120 * scaleX, 90 * scaleY);
                mapCtx.quadraticCurveTo(60 * scaleX, 80 * scaleY, 20 * scaleX, 85 * scaleY);
                mapCtx.closePath();
                mapCtx.fill();

                const backgroundNodes = [
                    {x: 35, y: 45}, {x: 55, y: 35}, {x: 85, y: 55}, {x: 215, y: 55}
                ];
                mapCtx.fillStyle = isDark ? '#1e202e' : '#cbd5e1';
                backgroundNodes.forEach(node => {
                    mapCtx.beginPath();
                    mapCtx.arc(node.x * scaleX, node.y * scaleY, 1.5, 0, Math.PI * 2);
                    mapCtx.fill();
                });

                Object.entries(geohubs).forEach(([key, hub]) => {
                    const hX = hub.x * scaleX;
                    const hY = hub.y * scaleY;

                    const pulse = (Date.now() % 2000) / 2000;
                    mapCtx.strokeStyle = isDark ? 'rgba(157, 92, 255, 0.2)' : 'rgba(157, 92, 255, 0.4)';
                    mapCtx.beginPath();
                    mapCtx.arc(hX, hY, 3 + (pulse * 10), 0, Math.PI * 2);
                    mapCtx.stroke();

                    mapCtx.fillStyle = '#9d5cff';
                    mapCtx.beginPath();
                    mapCtx.arc(hX, hY, 3.5, 0, Math.PI * 2);
                    mapCtx.fill();

                    mapCtx.fillStyle = isDark ? '#94a3b8' : '#475569';
                    mapCtx.font = "9px 'JetBrains Mono', monospace";
                    mapCtx.fillText(key, hX - 8, hY - 8);
                });

                if (selectedOpp) {
                    const longHubKey = getExchangeHub(selectedOpp.long_exchange);
                    const shortHubKey = getExchangeHub(selectedOpp.short_exchange);

                    const startHub = geohubs[longHubKey];
                    const endHub = geohubs[shortHubKey];

                    if (startHub && endHub) {
                        const sX = startHub.x * scaleX;
                        const sY = startHub.y * scaleY;
                        const eX = endHub.x * scaleX;
                        const eY = endHub.y * scaleY;

                        const midX = (sX + eX) / 2;
                        const midY = Math.min(sY, eY) - 25 * scaleY;

                        mapCtx.strokeStyle = isDark ? 'rgba(157, 92, 255, 0.25)' : 'rgba(157, 92, 255, 0.45)';
                        mapCtx.lineWidth = 1.5;
                        mapCtx.beginPath();
                        mapCtx.moveTo(sX, sY);
                        mapCtx.quadraticCurveTo(midX, midY, eX, eY);
                        mapCtx.stroke();

                        const spawnInterval = Math.max(Math.round(transitMs / 10), 10);
                        if (Date.now() % spawnInterval < 20 && mapParticles.length < 15) {
                            mapParticles.push({
                                t: 0,
                                speed: Math.max(0.005, 0.05 - (transitMs / 8000))
                            });
                        }

                        mapCtx.fillStyle = isDark ? '#34d399' : '#059669';
                        mapParticles.forEach((p, idx) => {
                            p.t += p.speed;
                            if (p.t > 1) {
                                mapParticles.splice(idx, 1);
                                return;
                            }

                            const pX = (1 - p.t) * (1 - p.t) * sX + 2 * (1 - p.t) * p.t * midX + p.t * p.t * eX;
                            const pY = (1 - p.t) * (1 - p.t) * sY + 2 * (1 - p.t) * p.t * midY + p.t * p.t * eY;

                            mapCtx.beginPath();
                            mapCtx.arc(pX, pY, 3, 0, Math.PI * 2);
                            mapCtx.fill();

                            mapCtx.fillStyle = isDark ? 'rgba(52, 211, 153, 0.4)' : 'rgba(5, 150, 105, 0.3)';
                            mapCtx.beginPath();
                            mapCtx.arc(pX, pY, 5, 0, Math.PI * 2);
                            mapCtx.fill();
                        });
                    }
                }

                mapAnimationId = requestAnimationFrame(animateMap);
            }

            animateMap();
        }

        function initRealtimeStream() {
            if (sseConnection) {
                sseConnection.close();
            }

            sseConnection = new EventSource('/api/stream');

            sseConnection.onmessage = function(event) {
                try {
                    const data = JSON.parse(event.data);
                    if (!data.opportunities || !data.metadata) return;

                    const clientReceiveTime = Date.now();
                    const serverPublishTime = data.metadata.last_update * 1000;
                    
                    transitMs = Math.max(Math.round(clientReceiveTime - serverPublishTime), 1);
                    dom.latency.innerText = `Stable / ${transitMs} ms`;

                    const scanHz = Math.round((1000 / transitMs) * data.opportunities.length);
                    dom.syncRate.innerText = `${isNaN(scanHz) || !isFinite(scanHz) ? 0 : scanHz} Scans / Sec`;

                    rawOpps = data.opportunities;
                    const meta = data.metadata;

                    dom.activePaths.innerText = `${rawOpps.length} Paths`;
                    dom.anTotalPaths.innerText = rawOpps.length;
                    dom.anTotalScanned.innerText = meta.total_pairs_scanned.toLocaleString();
                    dom.anTopLong.innerText = meta.top_long_exchange;
                    dom.anTopShort.innerText = meta.top_short_exchange;
                    dom.anExchanges.innerText = meta.active_exchanges;

                    rawOpps.forEach(o => {
                        exchangeCatalog.add(o.long_exchange);
                        exchangeCatalog.add(o.short_exchange);
                    });

                    calculateExchangeShareDynamics();
                    calculatePairingHeatmap();
                    populateDetailedAnalytics();

                    applyFiltersAndRender();

                    if (!selectedOpp && filteredOpps.length > 0) {
                        selectRow(0);
                    } else if (selectedOpp) {
                        const matchedIndex = filteredOpps.findIndex(o => 
                            o.symbol === selectedOpp.symbol && 
                            o.long_exchange === selectedOpp.long_exchange && 
                            o.short_exchange === selectedOpp.short_exchange
                        );
                        if (matchedIndex !== -1) {
                            selectRow(matchedIndex);
                        }
                    }

                } catch (err) {
                    console.error("SSE Payload processing error", err);
                }
            };

            sseConnection.onerror = function(err) {
                dom.latency.innerText = "Reconnecting...";
                setTimeout(initRealtimeStream, 3000);
            };
        }

        function runClock() {
            const now = new Date();
            dom.utc.innerText = now.toISOString().split('T')[1].split('.')[0] + " UTC";
        }

        initPerformanceLineChart();
        initInteractiveCanvasMap();
        setInterval(runClock, 1000);
        setInterval(calculateSimulationRates, 1000);

        runClock();
        initRealtimeStream();
    </script>
</body>
</html>
"""