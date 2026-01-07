import logging
from flask import Flask, render_template_string, jsonify
from threading import Lock
import json
import time
from datetime import datetime, timedelta
from collections import Counter

# Silence Flask logs for cleaner console
log = logging.getLogger('werkzeug')
log.setLevel(logging.ERROR)

app = Flask(__name__)

# Thread-safe Data Store
data_lock = Lock()
latest_data = {
    "opportunities": [],
    "metadata": {
        "last_update": 0,
        "total_pairs_scanned": 0,
        "active_exchanges": 0,
        "top_long_exchange": "Analyzing...",
        "top_short_exchange": "Analyzing...",
        "api_latency": 0
    }
}

def update_dashboard_data(opportunities, total_pairs_count=0):
    global latest_data
    with data_lock:
        timestamp = time.time()
        
        # 1. Convert Objects to Dicts
        opps_list = []
        all_long_exchanges = []
        all_short_exchanges = []
        unique_exchanges = set()

        for opp in opportunities:
            opps_list.append({
                "symbol": opp.symbol,
                "spread": opp.spread, # Raw float (e.g., 0.65)
                "long_exchange": opp.long_exchange,
                "long_rate": opp.long_rate,
                "short_exchange": opp.short_exchange,
                "short_rate": opp.short_rate,
                "annualized": opp.annualized_spread
            })
            all_long_exchanges.append(opp.long_exchange)
            all_short_exchanges.append(opp.short_exchange)
            unique_exchanges.add(opp.long_exchange)
            unique_exchanges.add(opp.short_exchange)

        # 2. Analytics: Find Dominant Exchanges
        top_long = Counter(all_long_exchanges).most_common(1)
        top_long_name = top_long[0][0] if top_long else "N/A"

        top_short = Counter(all_short_exchanges).most_common(1)
        top_short_name = top_short[0][0] if top_short else "N/A"

        # 3. Update State
        latest_data = {
            "opportunities": opps_list,
            "metadata": {
                "last_update": timestamp,
                "total_pairs_scanned": total_pairs_count,
                "active_exchanges": len(unique_exchanges),
                "top_long_exchange": top_long_name,
                "top_short_exchange": top_short_name,
                "count": len(opps_list)
            }
        }

@app.route('/api/data')
def get_data():
    with data_lock:
        return jsonify(latest_data)

@app.route("/")
def dashboard():
    return render_template_string(HTML_TEMPLATE)

def start_flask_app():
    app.run(host="0.0.0.0", port=5000, debug=False, use_reloader=False)

# THE "COMMAND CENTER" TEMPLATE

HTML_TEMPLATE = r"""
<!DOCTYPE html>
<html lang="en" class="dark">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Funding Arbitrage Command Center</title>
    
    <!-- Libraries -->
    <script src="https://cdn.tailwindcss.com"></script>
    <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
    <link href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css" rel="stylesheet">
    <link href="https://fonts.googleapis.com/css2?family=Outfit:wght@300;400;500;700&family=Space+Mono:wght@400;700&display=swap" rel="stylesheet">

    <script>
        tailwind.config = {
            darkMode: 'class',
            theme: {
                extend: {
                    fontFamily: {
                        sans: ['Outfit', 'sans-serif'],
                        mono: ['Space Mono', 'monospace'],
                    },
                    colors: {
                        dark: {
                            bg: '#050507',
                            card: '#0E0E12',
                            border: '#1E1E24'
                        },
                        neon: {
                            primary: '#6366f1',  /* Indigo */
                            success: '#10b981',  /* Emerald */
                            danger: '#ef4444',   /* Red */
                            warning: '#eab308',  /* Yellow */
                            cyan: '#06b6d4'      /* Cyan */
                        }
                    },
                    animation: {
                        'pulse-slow': 'pulse 3s cubic-bezier(0.4, 0, 0.6, 1) infinite',
                        'glow': 'glow 2s ease-in-out infinite alternate',
                    },
                    keyframes: {
                        glow: {
                            '0%': { boxShadow: '0 0 5px rgba(99, 102, 241, 0.2)' },
                            '100%': { boxShadow: '0 0 20px rgba(99, 102, 241, 0.6)' },
                        }
                    }
                }
            }
        }
    </script>

    <style>
        body {
            background-color: #050507;
            background-image: 
                linear-gradient(rgba(99, 102, 241, 0.03) 1px, transparent 1px),
                linear-gradient(90deg, rgba(99, 102, 241, 0.03) 1px, transparent 1px);
            background-size: 40px 40px;
            color: #e2e8f0;
        }

        .glass-panel {
            background: rgba(14, 14, 18, 0.6);
            backdrop-filter: blur(12px);
            border: 1px solid rgba(255, 255, 255, 0.08);
            box-shadow: 0 8px 32px rgba(0, 0, 0, 0.4);
        }

        .neon-text {
            text-shadow: 0 0 10px rgba(99, 102, 241, 0.5);
        }

        .scroll-hide::-webkit-scrollbar { display: none; }
        .custom-scroll::-webkit-scrollbar { width: 6px; }
        .custom-scroll::-webkit-scrollbar-track { background: #0E0E12; }
        .custom-scroll::-webkit-scrollbar-thumb { background: #2d2d35; border-radius: 3px; }
        .custom-scroll::-webkit-scrollbar-thumb:hover { background: #4f4f5a; }
    </style>
</head>
<body class="h-screen flex flex-col overflow-hidden">

    <!-- TOP NAVIGATION -->
    <nav class="h-16 border-b border-dark-border bg-dark-bg/80 backdrop-blur-md z-50 flex items-center justify-between px-6">
        <div class="flex items-center gap-4">
            <div class="w-10 h-10 rounded-lg bg-gradient-to-tr from-neon-primary to-neon-cyan flex items-center justify-center animate-glow shadow-lg">
                <i class="fa-solid fa-network-wired text-white"></i>
            </div>
            <div>
                <h1 class="font-bold text-xl tracking-wide text-white"><span class="text-neon-cyan">ATHENA</span></h1>
                <div class="flex items-center gap-2 text-[10px] uppercase tracking-wider text-gray-500 font-mono">
                    <span class="w-2 h-2 rounded-full bg-neon-success animate-pulse"></span>
                    System Online
                </div>
            </div>
        </div>

        <div class="flex items-center gap-6">
            <!-- Funding Countdown -->
            <div class="hidden md:flex flex-col items-end">
                <span class="text-xs text-gray-400 font-mono">NEXT FUNDING</span>
                <span id="funding-timer" class="text-neon-warning font-mono font-bold">--:--:--</span>
            </div>
            
            <!-- Clock -->
            <div class="bg-dark-card border border-dark-border px-4 py-2 rounded-lg font-mono text-sm text-neon-cyan shadow-[0_0_15px_rgba(6,182,212,0.1)]">
                <i class="fa-regular fa-clock mr-2"></i><span id="utc-clock">--:--:-- UTC</span>
            </div>
        </div>
    </nav>

    <!-- DASHBOARD CONTENT -->
    <div class="flex-1 flex overflow-hidden">
        
        <!-- MAIN VIEW -->
        <main class="flex-1 flex flex-col p-6 gap-6 overflow-hidden">
            
            <!-- STATS ROW (Bento Grid) -->
            <div class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-5 gap-4 h-auto md:h-32 shrink-0">
                
                <!-- Card 1: Max Spread -->
                <div class="glass-panel rounded-xl p-4 flex flex-col justify-between relative overflow-hidden group">
                    <div class="absolute right-0 top-0 p-3 opacity-10 group-hover:scale-110 transition-transform duration-500">
                        <i class="fa-solid fa-trophy text-5xl text-neon-warning"></i>
                    </div>
                    <span class="text-gray-400 text-xs font-mono uppercase tracking-widest">Top Spread (8h)</span>
                    <div class="mt-2">
                        <span id="stat-max-spread" class="text-3xl font-bold text-white neon-text">0.00%</span>
                        <div class="text-xs text-neon-success mt-1 flex items-center gap-1">
                            <i class="fa-solid fa-arrow-trend-up"></i> High Yield
                        </div>
                    </div>
                </div>

                <!-- Card 2: Opportunities -->
                <div class="glass-panel rounded-xl p-4 flex flex-col justify-between">
                    <span class="text-gray-400 text-xs font-mono uppercase tracking-widest">Opportunities</span>
                    <div class="flex items-baseline gap-2">
                        <span id="stat-opp-count" class="text-3xl font-bold text-white">0</span>
                        <span class="text-xs text-gray-500">Active</span>
                    </div>
                    <div class="w-full bg-gray-800 h-1 mt-2 rounded-full overflow-hidden">
                        <div class="bg-neon-primary h-full w-3/4 animate-pulse"></div>
                    </div>
                </div>

                <!-- Card 3: Market Dominance -->
                <div class="glass-panel rounded-xl p-4 flex flex-col justify-between col-span-1 lg:col-span-2">
                    <span class="text-gray-400 text-xs font-mono uppercase tracking-widest">Exchange Dominance</span>
                    <div class="flex justify-between items-end mt-2">
                        <div>
                            <span class="text-xs text-gray-500 block mb-1">Best Long Source</span>
                            <span id="stat-dom-long" class="text-xl font-bold text-neon-cyan">Analyzing...</span>
                        </div>
                        <div class="text-right">
                            <span class="text-xs text-gray-500 block mb-1">Best Short Source</span>
                            <span id="stat-dom-short" class="text-xl font-bold text-neon-danger">Analyzing...</span>
                        </div>
                    </div>
                </div>

                <!-- Card 4: Metadata -->
                <div class="glass-panel rounded-xl p-4 flex flex-col justify-center space-y-3">
                    <div class="flex justify-between items-center text-xs">
                        <span class="text-gray-500">Exchanges</span>
                        <span id="stat-exchanges" class="text-white font-mono">0</span>
                    </div>
                    <div class="flex justify-between items-center text-xs">
                        <span class="text-gray-500">Pairs Scanned</span>
                        <span id="stat-pairs" class="text-white font-mono">0</span>
                    </div>
                    <div class="flex justify-between items-center text-xs">
                        <span class="text-gray-500">Update Rate</span>
                        <span class="text-neon-success font-mono">~200ms</span>
                    </div>
                </div>
            </div>

            <!-- LOWER SECTION -->
            <div class="flex-1 grid grid-cols-1 lg:grid-cols-3 gap-6 overflow-hidden">
                
                <!-- TABLE (Takes 2/3 width) -->
                <div class="glass-panel rounded-xl lg:col-span-2 flex flex-col overflow-hidden">
                    <!-- Toolbar -->
                    <div class="p-4 border-b border-dark-border flex justify-between items-center bg-black/20">
                        <div class="flex items-center gap-3">
                            <h2 class="text-white font-bold tracking-tight"><i class="fa-solid fa-table-list mr-2 text-neon-primary"></i> LIVE OPPORTUNITIES</h2>
                            <span class="text-xs px-2 py-0.5 rounded bg-neon-primary/10 text-neon-primary border border-neon-primary/20">Real-Time</span>
                        </div>
                        <div class="relative">
                            <i class="fa-solid fa-search absolute left-3 top-1/2 -translate-y-1/2 text-gray-600 text-xs"></i>
                            <input type="text" id="table-search" placeholder="Search Symbol..." 
                                class="bg-dark-bg border border-dark-border rounded-lg pl-8 pr-4 py-1.5 text-xs text-white focus:outline-none focus:border-neon-primary w-48 transition-colors">
                        </div>
                    </div>

                    <!-- Table Header -->
                    <div class="grid grid-cols-12 gap-2 px-4 py-3 bg-dark-card/50 border-b border-dark-border text-xs font-mono text-gray-500 uppercase tracking-wider">
                        <div class="col-span-1 text-center">#</div>
                        <div class="col-span-2">Pair</div>
                        <div class="col-span-2 text-right">Spread (8h)</div>
                        <div class="col-span-3 text-center">Strategy</div>
                        <div class="col-span-2">Long Leg</div>
                        <div class="col-span-2">Short Leg</div>
                    </div>

                    <!-- Table Body -->
                    <div id="opp-list" class="flex-1 overflow-y-auto custom-scroll p-2 space-y-1">
                        <!-- JS Injects Rows Here -->
                        <div class="flex flex-col items-center justify-center h-full text-gray-600">
                            <i class="fa-solid fa-circle-notch fa-spin text-3xl mb-4 text-neon-primary"></i>
                            <span class="font-mono text-xs">ESTABLISHING DATA FEED...</span>
                        </div>
                    </div>
                </div>

                <!-- CHARTS & LOGS (Takes 1/3 width) -->
                <div class="flex flex-col gap-6 overflow-hidden">
                    
                    <!-- Chart Panel -->
                    <div class="glass-panel rounded-xl p-4 flex flex-col h-1/2">
                        <h3 class="text-xs font-mono text-gray-500 uppercase mb-4">Top 5 Spread Analysis</h3>
                        <div class="flex-1 relative">
                            <canvas id="spreadChart"></canvas>
                        </div>
                    </div>

                    <!-- Action Panel -->
                    <div class="glass-panel rounded-xl p-4 flex-1 flex flex-col relative overflow-hidden">
                        <h3 class="text-xs font-mono text-gray-500 uppercase mb-4">Live Execution Feed</h3>
                        
                        <div class="absolute inset-0 bg-gradient-to-b from-transparent via-transparent to-dark-bg/50 pointer-events-none"></div>
                        
                        <div id="activity-log" class="font-mono text-[10px] space-y-2 overflow-y-auto custom-scroll pr-2">
                            <!-- JS logs -->
                        </div>
                    </div>
                </div>
            </div>
        </main>
    </div>

    <!-- JAVASCRIPT LOGIC -->
    <script>
        // CONSTANTS & STATE
        let chartInstance = null;
        let lastDataHash = "";
        
        // DOM ELEMENTS
        const dom = {
            oppList: document.getElementById('opp-list'),
            stats: {
                maxSpread: document.getElementById('stat-max-spread'),
                count: document.getElementById('stat-opp-count'),
                longDom: document.getElementById('stat-dom-long'),
                shortDom: document.getElementById('stat-dom-short'),
                exchanges: document.getElementById('stat-exchanges'),
                pairs: document.getElementById('stat-pairs')
            },
            search: document.getElementById('table-search'),
            timer: document.getElementById('funding-timer'),
            clock: document.getElementById('utc-clock'),
            logs: document.getElementById('activity-log')
        };

        // CHART SETUP
        function initChart() {
            const ctx = document.getElementById('spreadChart').getContext('2d');
            chartInstance = new Chart(ctx, {
                type: 'bar',
                data: {
                    labels: [],
                    datasets: [{
                        label: 'Spread %',
                        data: [],
                        backgroundColor: '#6366f1',
                        borderRadius: 4,
                        barThickness: 20
                    }]
                },
                options: {
                    responsive: true,
                    maintainAspectRatio: false,
                    plugins: { legend: { display: false } },
                    scales: {
                        y: {
                            grid: { color: 'rgba(255, 255, 255, 0.05)' },
                            ticks: { color: '#94a3b8', font: { family: 'Space Mono', size: 10 } }
                        },
                        x: {
                            grid: { display: false },
                            ticks: { color: '#94a3b8', font: { family: 'Space Mono', size: 10 } }
                        }
                    }
                }
            });
        }

        // UTILS
        const formatPct = (num) => (num).toFixed(4) + '%';
        const formatRate = (num) => (num).toFixed(4) + '%';
        
        function updateClock() {
            const now = new Date();
            dom.clock.innerText = now.toISOString().split('T')[1].split('.')[0] + " UTC";
            
            // Funding Countdown (Every 8 hours: 00, 08, 16)
            const h = now.getUTCHours();
            const targetH = h < 8 ? 8 : h < 16 ? 16 : 24;
            const target = new Date(now);
            target.setUTCHours(targetH, 0, 0, 0);
            
            const diff = target - now;
            const hh = Math.floor(diff / 3600000).toString().padStart(2, '0');
            const mm = Math.floor((diff % 3600000) / 60000).toString().padStart(2, '0');
            const ss = Math.floor((diff % 60000) / 1000).toString().padStart(2, '0');
            
            dom.timer.innerText = `${hh}:${mm}:${ss}`;
        }

        function addLog(symbol, spread) {
            const div = document.createElement('div');
            div.className = "flex justify-between items-center text-gray-400 border-l-2 border-neon-primary pl-2 animate-pulse";
            div.innerHTML = `
                <span>Found <b class="text-white">${symbol}</b></span>
                <span class="text-neon-success">+${formatPct(spread)}</span>
            `;
            dom.logs.prepend(div);
            if (dom.logs.children.length > 20) dom.logs.lastChild.remove();
        }

        // DATA RENDERER
        async function render() {
            try {
                const res = await fetch('/api/data');
                const data = await res.json();
                
                // Allow empty opps list if scan is active
                if (!data.metadata) return;

                const meta = data.metadata;
                const opps = data.opportunities;

                // 1. Update Stats
                dom.stats.maxSpread.innerText = opps.length > 0 ? formatPct(opps[0].spread) : "0.00%";
                dom.stats.count.innerText = meta.count;
                dom.stats.longDom.innerText = meta.top_long_exchange;
                dom.stats.shortDom.innerText = meta.top_short_exchange;
                dom.stats.exchanges.innerText = meta.active_exchanges;
                dom.stats.pairs.innerText = meta.total_pairs_scanned; // Updated from backend

                // 2. Filter Data
                const filter = dom.search.value.toUpperCase();
                const filteredOpps = opps.filter(o => o.symbol.includes(filter));

                // 3. Render Table List
                let html = '';
                filteredOpps.forEach((o, i) => {
                    const rankColor = i === 0 ? 'text-yellow-400' : i === 1 ? 'text-gray-300' : i === 2 ? 'text-orange-400' : 'text-gray-600';
                    const spread = formatPct(o.spread);
                    
                    const lRate = o.long_rate.toFixed(4) + '%';
                    const sRate = o.short_rate.toFixed(4) + '%';
                    
                    // Logic: Negative Funding = Green (Received), Positive = Red (Paid)
                    // Note: Long Position receives if negative. Short Position receives if positive.
                    const lClass = o.long_rate < 0 ? 'text-neon-success' : 'text-neon-danger';
                    const sClass = o.short_rate > 0 ? 'text-neon-success' : 'text-neon-danger';

                    html += `
                    <div class="grid grid-cols-12 gap-2 px-4 py-3 bg-dark-bg/40 rounded-lg hover:bg-white/5 border border-transparent hover:border-white/10 transition-all items-center group">
                        <div class="col-span-1 text-center font-mono font-bold ${rankColor}">${i+1}</div>
                        
                        <div class="col-span-2 font-bold text-white flex items-center gap-2">
                            ${o.symbol}
                            <i class="fa-regular fa-copy text-[10px] text-gray-600 cursor-pointer hover:text-white" title="Copy Pair" onclick="navigator.clipboard.writeText('${o.symbol}')"></i>
                        </div>
                        
                        <div class="col-span-2 text-right">
                            <span class="text-neon-success font-bold font-mono tracking-wide text-sm bg-neon-success/10 px-2 py-1 rounded border border-neon-success/20 shadow-[0_0_10px_rgba(16,185,129,0.2)]">
                                ${spread}
                            </span>
                        </div>
                        
                        <div class="col-span-3 text-center flex justify-center items-center gap-2 text-[10px] font-mono text-gray-400">
                            <span class="px-1.5 py-0.5 rounded bg-blue-500/10 text-blue-400 border border-blue-500/20">${o.long_exchange}</span>
                            <i class="fa-solid fa-arrow-right-long"></i>
                            <span class="px-1.5 py-0.5 rounded bg-red-500/10 text-red-400 border border-red-500/20">${o.short_exchange}</span>
                        </div>
                        
                        <div class="col-span-2 text-xs text-gray-400">
                            <span class="${lClass}">${lRate}</span>
                        </div>
                        
                        <div class="col-span-2 text-xs text-gray-400">
                            <span class="${sClass}">${sRate}</span>
                        </div>
                    </div>`;
                });

                if (html === '') html = '<div class="text-center py-10 text-gray-600 font-mono">SCANNING MARKETS...</div>';
                dom.oppList.innerHTML = html;

                // 4. Update Chart (Top 5 only)
                if (chartInstance && filteredOpps.length > 0) {
                    const top5 = filteredOpps.slice(0, 5);
                    chartInstance.data.labels = top5.map(o => o.symbol);
                    chartInstance.data.datasets[0].data = top5.map(o => o.spread);
                    chartInstance.update('none'); 
                }

                // 5. Activity Log
                if (opps.length > 0 && opps[0].symbol !== lastDataHash) {
                    addLog(opps[0].symbol, opps[0].spread);
                    lastDataHash = opps[0].symbol;
                }

            } catch (e) {
                console.error(e);
            }
        }

        // INIT
        initChart();
        setInterval(updateClock, 1000);
        setInterval(render, 2000); 
        render();

    </script>
</body>
</html>
"""
