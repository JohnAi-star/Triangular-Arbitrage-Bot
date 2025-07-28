import React, { useState, useEffect } from 'react';
import {
    Play,
    Square,
    Settings,
    TrendingUp,
    DollarSign,
    Activity,
    Eye,
    EyeOff,
    RefreshCw,
    AlertTriangle,
    CheckCircle,
    XCircle,
    RotateCcw
} from 'lucide-react';
import { backendAPI, ArbitrageOpportunity, BotStats } from '../api/backend';

interface AutoTradeLog {
    id: string;
    timestamp: string;
    exchange: string;
    profitPercentage: number;
    profitAmount: number;
    volume: number;
    status: 'completed' | 'failed';
}

interface ExchangeConfig {
    id: string;
    name: string;
    enabled: boolean;
    connected: boolean;
    feeToken: string;
    zeroFeePairs: number;
}

export const ArbitrageBotDashboard: React.FC = () => {
    const [isRunning, setIsRunning] = useState(false);
    const [autoTrading, setAutoTrading] = useState(false);
    const [paperTrading, setPaperTrading] = useState(true);
    const [minProfit, setMinProfit] = useState(0.1);
    const [maxTradeAmount, setMaxTradeAmount] = useState(100);
    const [maxConsecutiveFails, setMaxConsecutiveFails] = useState(3);
    const [consecutiveFails, setConsecutiveFails] = useState(0);
    const [pausedAutoTrading, setPausedAutoTrading] = useState(false);

    const [opportunities, setOpportunities] = useState<ArbitrageOpportunity[]>([]);
    const [autoTradeLogs, setAutoTradeLogs] = useState<AutoTradeLog[]>([]);
    const [selectedOpportunity, setSelectedOpportunity] = useState<string | null>(null);

    const [stats, setStats] = useState<BotStats>({
        opportunitiesFound: 0,
        tradesExecuted: 0,
        totalProfit: 0,
        successRate: 0,
        activeExchanges: 0
    });

    const [autoStats, setAutoStats] = useState({
        autoTradesExecuted: 0,
        autoProfit: 0,
        autoSuccessRate: 0
    });

    const [exchanges, setExchanges] = useState<ExchangeConfig[]>([
    { id: 'binance', name: 'Binance', enabled: true, connected: false, feeToken: 'BNB', zeroFeePairs: 0 },
    { id: 'bybit', name: 'Bybit', enabled: false, connected: false, feeToken: 'BIT', zeroFeePairs: 0 },
    { id: 'kucoin', name: 'KuCoin', enabled: false, connected: false, feeToken: 'KCS', zeroFeePairs: 2 },
    { id: 'coinbasepro', name: 'Coinbase Pro', enabled: false, connected: false, feeToken: 'USDC', zeroFeePairs: 0 },
    { id: 'kraken', name: 'Kraken', enabled: false, connected: false, feeToken: 'USD', zeroFeePairs: 0 },
    { id: 'gateio', name: 'Gate.io', enabled: false, connected: false, feeToken: 'GT', zeroFeePairs: 0 },
    { id: 'coinex', name: 'CoinEx', enabled: false, connected: false, feeToken: 'CET', zeroFeePairs: 0 },
    { id: 'htx', name: 'HTX', enabled: false, connected: false, feeToken: 'HT', zeroFeePairs: 0 },
    { id: 'mexc', name: 'MEXC', enabled: false, connected: false, feeToken: 'MX', zeroFeePairs: 0 },
    { id: 'poloniex', name: 'Poloniex', enabled: false, connected: false, feeToken: 'TRX', zeroFeePairs: 0 },
    { id: 'probit', name: 'ProBit Global', enabled: false, connected: false, feeToken: 'PROB', zeroFeePairs: 0 },
    { id: 'hitbtc', name: 'HitBTC', enabled: false, connected: false, feeToken: 'HIT', zeroFeePairs: 0 },
]);

    useEffect(() => {
        console.log('Setting up WebSocket connection...');
        backendAPI.connectWebSocket((data: any) => {
            console.log('WebSocket message received:', data);
            if (data.type === 'opportunities_update') {
                console.log('Updating opportunities:', data.data);
                setOpportunities(data.data);
            } else if (data.type === 'opportunity_executed') {
                const executed = data.data as ArbitrageOpportunity;
                if (executed.status === 'completed' || executed.status === 'failed') {
                    const log: AutoTradeLog = {
                        id: executed.id,
                        timestamp: new Date().toISOString(),
                        exchange: executed.exchange,
                        profitPercentage: executed.profitPercentage,
                        profitAmount: executed.profitAmount,
                        volume: executed.volume,
                        status: executed.status
                    };
                    setAutoTradeLogs(prev => [log, ...prev.slice(0, 49)]);

                    setAutoStats(prev => {
                        const trades = prev.autoTradesExecuted + 1;
                        const profit = prev.autoProfit + (executed.status === 'completed' ? executed.profitAmount : 0);
                        const successCount = prev.autoTradesExecuted * (prev.autoSuccessRate / 100) + (executed.status === 'completed' ? 1 : 0);
                        const successRate = (successCount / trades) * 100;
                        return { autoTradesExecuted: trades, autoProfit: profit, autoSuccessRate: successRate };
                    });

                    if (executed.status === 'failed') {
                        setConsecutiveFails(f => {
                            const newFails = f + 1;
                            if (newFails >= maxConsecutiveFails) {
                                setPausedAutoTrading(true);
                                setAutoTrading(false);
                            }
                            return newFails;
                        });
                    } else {
                        setConsecutiveFails(0);
                    }
                }
            }
        });
        return () => backendAPI.disconnectWebSocket();
    }, [maxConsecutiveFails]);

    const toggleBot = async () => {
        if (!isRunning) {
            const success = await backendAPI.startBot({
                minProfitPercentage: minProfit,
                maxTradeAmount,
                autoTradingMode: autoTrading,
                paperTrading,
                selectedExchanges: exchanges.filter(e => e.enabled).map(e => e.id)
            });
            if (success) {
                setExchanges(prev => prev.map(ex => ex.enabled ? { ...ex, connected: true } : ex));
                setIsRunning(true);
            }
        } else {
            const success = await backendAPI.stopBot();
            if (success) {
                setExchanges(prev => prev.map(ex => ({ ...ex, connected: false })));
                setIsRunning(false);
                setAutoTrading(false);
            }
        }
    };

    const resumeAutoTrading = () => {
        setPausedAutoTrading(false);
        setConsecutiveFails(0);
        setAutoTrading(true);
    };

    const executeOpportunity = async (id: string) => {
        const success = await backendAPI.executeOpportunity(id);
        setOpportunities(prev =>
            prev.map(opp => opp.id === id ? { ...opp, status: success ? 'completed' : 'failed' } : opp)
        );
    };

    const getStatusIcon = (status: string) => {
        switch (status) {
            case 'detected': return <Eye className="w-4 h-4 text-blue-400" />;
            case 'executing': return <RefreshCw className="w-4 h-4 text-yellow-400 animate-spin" />;
            case 'completed': return <CheckCircle className="w-4 h-4 text-green-400" />;
            case 'failed': return <XCircle className="w-4 h-4 text-red-400" />;
            default: return null;
        }
    };

    return (
        <div className="min-h-screen p-6">
            <div className="max-w-7xl mx-auto">
                <h1 className="text-4xl font-bold text-white mb-4 flex items-center gap-3">
                    <TrendingUp className="w-10 h-10 text-blue-400" /> Triangular Arbitrage Bot
                </h1>

                {pausedAutoTrading && (
                    <div className="bg-red-900/40 border border-red-500/50 text-red-200 p-4 rounded-xl mb-4">
                        Auto-Trading Paused: {maxConsecutiveFails} consecutive fails reached.
                    </div>
                )}

                <div className="grid grid-cols-1 lg:grid-cols-4 gap-6 mb-8">
                    <div className="bg-slate-800/50 p-6 rounded-xl border border-slate-700">
                        <h3 className="text-lg font-semibold text-white mb-4 flex items-center gap-2">
                            <Settings className="w-5 h-5" /> Bot Controls
                        </h3>
                        <button
                            onClick={toggleBot}
                            className={`w-full mb-4 px-4 py-3 rounded-lg font-medium flex items-center justify-center gap-2 ${isRunning ? 'bg-red-600' : 'bg-green-600'} text-white`}
                        >
                            {isRunning ? <Square className="w-5 h-5" /> : <Play className="w-5 h-5" />}
                            {isRunning ? 'Stop Bot' : 'Start Bot'}
                        </button>
                        <label className="flex items-center gap-3 text-sm text-gray-300 mb-3">
                            <input type="checkbox" checked={autoTrading} onChange={(e) => setAutoTrading(e.target.checked)} />
                            Auto Trading Mode
                        </label>
                        <label className="flex items-center gap-3 text-sm text-gray-300 mb-3">
                            <input type="checkbox" checked={paperTrading} onChange={(e) => setPaperTrading(e.target.checked)} />
                            Paper Trading
                        </label>
                        {pausedAutoTrading && (
                            <button
                                onClick={resumeAutoTrading}
                                className="w-full px-4 py-3 mt-2 rounded-lg bg-yellow-600 hover:bg-yellow-700 text-white flex items-center justify-center gap-2"
                            >
                                <RotateCcw className="w-5 h-5" /> Resume Auto-Trading
                            </button>
                        )}
                    </div>

                    <div className="bg-slate-800/50 p-6 rounded-xl border border-slate-700">
                        <h3 className="text-lg font-semibold text-white mb-4">Settings</h3>
                        <label className="block text-sm text-gray-300 mb-2">Min Profit %</label>
                        <input type="number" value={minProfit} onChange={(e) => setMinProfit(parseFloat(e.target.value))} className="w-full mb-4 px-3 py-2 bg-slate-700 border border-slate-600 rounded-lg text-white" />
                        <label className="block text-sm text-gray-300 mb-2">Max Trade Amount</label>
                        <input type="number" value={maxTradeAmount} onChange={(e) => setMaxTradeAmount(parseFloat(e.target.value))} className="w-full mb-4 px-3 py-2 bg-slate-700 border border-slate-600 rounded-lg text-white" />
                        <label className="block text-sm text-gray-300 mb-2">Max Consecutive Fails</label>
                        <input type="number" value={maxConsecutiveFails} onChange={(e) => setMaxConsecutiveFails(parseInt(e.target.value))} className="w-full px-3 py-2 bg-slate-700 border border-slate-600 rounded-lg text-white" />
                    </div>

                    <div className="lg:col-span-2 bg-slate-800/50 p-6 rounded-xl border border-slate-700">
                        <h3 className="text-lg font-semibold text-white mb-4 flex items-center gap-2">
                            <Activity className="w-5 h-5" /> Statistics
                        </h3>
                        <div className="grid grid-cols-3 gap-4">
                            <div className="text-center">
                                <div className="text-2xl text-blue-400">{stats.opportunitiesFound}</div>
                                <div className="text-xs text-gray-400">Opportunities</div>
                            </div>
                            <div className="text-center">
                                <div className="text-2xl text-green-400">{stats.tradesExecuted}</div>
                                <div className="text-xs text-gray-400">Trades</div>
                            </div>
                            <div className="text-center">
                                <div className="text-2xl text-yellow-400">${stats.totalProfit.toFixed(2)}</div>
                                <div className="text-xs text-gray-400">Profit</div>
                            </div>
                        </div>
                        <div className="mt-6 text-gray-300">
                            <p>Auto-Trades: {autoStats.autoTradesExecuted} | Auto-Profit: ${autoStats.autoProfit.toFixed(2)} | Success Rate: {autoStats.autoSuccessRate.toFixed(1)}%</p>
                        </div>
                    </div>
                </div>

                {/* Exchanges */}
                <div className="grid grid-cols-1 lg:grid-cols-4 gap-6">
                    <div className="bg-slate-800/50 p-6 rounded-xl border border-slate-700">
                        <h3 className="text-lg font-semibold text-white mb-4">Exchanges</h3>
                        {exchanges.map(ex => (
                            <div key={ex.id} className="flex justify-between items-center py-2">
                                <label className="flex items-center gap-3">
                                    <input type="checkbox" checked={ex.enabled} onChange={() => setExchanges(prev => prev.map(e => e.id === ex.id ? { ...e, enabled: !e.enabled } : e))} />
                                    <span className="text-white">{ex.name}</span>
                                </label>
                                <div className={`w-2 h-2 rounded-full ${ex.connected ? 'bg-green-400' : 'bg-gray-500'}`} />
                            </div>
                        ))}
                    </div>

                    {/* Opportunities Table */}
                    <div className="lg:col-span-3 bg-slate-800/50 p-6 rounded-xl border border-slate-700">
                        <h3 className="text-lg font-semibold text-white mb-4 flex items-center gap-2">
                            <DollarSign className="w-5 h-5" /> Arbitrage Opportunities
                        </h3>
                        <div className="overflow-x-auto">
                            <table className="w-full">
                                <thead>
                                    <tr className="border-b border-slate-700 text-gray-300 text-sm">
                                        <th>Status</th><th>Exchange</th><th>Triangle Path</th><th>Profit %</th><th>Profit $</th><th>Volume</th><th>Action</th>
                                    </tr>
                                </thead>
                                <tbody className="divide-y divide-slate-700">
                                    {opportunities.map(o => (
                                        <tr key={o.id} onClick={() => setSelectedOpportunity(o.id)} className="hover:bg-slate-700/30">
                                            <td>{getStatusIcon(o.status)}</td>
                                            <td>{o.exchange}</td>
                                            <td>{o.trianglePath}</td>
                                            <td className="text-green-400">{o.profitPercentage.toFixed(4)}%</td>
                                            <td className="text-green-400">${o.profitAmount.toFixed(2)}</td>
                                            <td>${o.volume.toFixed(0)}</td>
                                            <td>
                                                {o.status === 'detected' && (
                                                    <button onClick={(e) => { e.stopPropagation(); executeOpportunity(o.id); }} className="px-3 py-1 bg-blue-600 hover:bg-blue-700 text-white text-xs rounded-lg">Execute</button>
                                                )}
                                            </td>
                                        </tr>
                                    ))}
                                </tbody>
                            </table>
                        </div>
                    </div>
                </div>

                {/* Auto-Trading History */}
                <div className="mt-8 bg-slate-800/50 p-6 rounded-xl border border-slate-700">
                    <h3 className="text-lg font-semibold text-white mb-4">Auto-Trading History</h3>
                    <div className="overflow-x-auto">
                        <table className="w-full">
                            <thead>
                                <tr className="border-b border-slate-700 text-gray-300 text-sm">
                                    <th>Time</th><th>Exchange</th><th>Profit %</th><th>Profit $</th><th>Volume</th><th>Status</th>
                                </tr>
                            </thead>
                            <tbody className="divide-y divide-slate-700">
                                {autoTradeLogs.map(log => (
                                    <tr key={log.id}>
                                        <td>{new Date(log.timestamp).toLocaleTimeString()}</td>
                                        <td>{log.exchange}</td>
                                        <td className="text-green-400">{log.profitPercentage.toFixed(4)}%</td>
                                        <td className="text-green-400">${log.profitAmount.toFixed(2)}</td>
                                        <td>${log.volume.toFixed(0)}</td>
                                        <td className={log.status === 'completed' ? 'text-green-400' : 'text-red-400'}>{log.status}</td>
                                    </tr>
                                ))}
                            </tbody>
                        </table>
                        {autoTradeLogs.length === 0 && (
                            <div className="text-center text-gray-400 py-6">No auto-trades yet</div>
                        )}
                    </div>
                </div>
            </div>
        </div>
    );
};
