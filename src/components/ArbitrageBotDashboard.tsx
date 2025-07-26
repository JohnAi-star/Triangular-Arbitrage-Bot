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
    XCircle
} from 'lucide-react';

interface ArbitrageOpportunity {
    id: string;
    exchange: string;
    trianglePath: string;
    profitPercentage: number;
    profitAmount: number;
    volume: number;
    status: 'detected' | 'executing' | 'completed' | 'failed';
    timestamp: Date;
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
    const [opportunities, setOpportunities] = useState<ArbitrageOpportunity[]>([]);
    const [selectedOpportunity, setSelectedOpportunity] = useState<string | null>(null);

    // Configuration state
    const [minProfit, setMinProfit] = useState(0.1);
    const [maxTradeAmount, setMaxTradeAmount] = useState(100);

    // Statistics
    const [stats, setStats] = useState({
        opportunitiesFound: 0,
        tradesExecuted: 0,
        totalProfit: 0,
        successRate: 0,
        activeExchanges: 0
    });

    // Exchange configurations
    const [exchanges, setExchanges] = useState<ExchangeConfig[]>([
        { id: 'binance', name: 'Binance', enabled: true, connected: false, feeToken: 'BNB', zeroFeePairs: 0 },
        { id: 'bybit', name: 'Bybit', enabled: false, connected: false, feeToken: 'BIT', zeroFeePairs: 0 },
        { id: 'kucoin', name: 'KuCoin', enabled: false, connected: false, feeToken: 'KCS', zeroFeePairs: 2 },
        { id: 'coinbase', name: 'Coinbase Pro', enabled: false, connected: false, feeToken: '', zeroFeePairs: 0 },
        { id: 'kraken', name: 'Kraken', enabled: false, connected: false, feeToken: '', zeroFeePairs: 0 },
        { id: 'gate', name: 'Gate.io', enabled: false, connected: false, feeToken: 'GT', zeroFeePairs: 0 },
        { id: 'coinex', name: 'CoinEx', enabled: false, connected: false, feeToken: 'CET', zeroFeePairs: 0 },
        { id: 'htx', name: 'HTX', enabled: false, connected: false, feeToken: 'HT', zeroFeePairs: 0 },
        { id: 'mexc', name: 'MEXC', enabled: false, connected: false, feeToken: 'MX', zeroFeePairs: 0 },
        { id: 'poloniex', name: 'Poloniex', enabled: false, connected: false, feeToken: '', zeroFeePairs: 0 },
        { id: 'probit', name: 'ProBit', enabled: false, connected: false, feeToken: 'PROB', zeroFeePairs: 0 },
        { id: 'hitbtc', name: 'HitBTC', enabled: false, connected: false, feeToken: '', zeroFeePairs: 0 }
    ]);

    // Simulate real-time data updates
    useEffect(() => {
        if (!isRunning) return;

        const interval = setInterval(() => {
            // Simulate new opportunities
            const newOpportunity: ArbitrageOpportunity = {
                id: `opp_${Date.now()}`,
                exchange: exchanges.find(e => e.enabled)?.name || 'Binance',
                trianglePath: 'USDT → BTC → ETH → USDT',
                profitPercentage: Math.random() * 0.5 + 0.05, // 0.05% to 0.55%
                profitAmount: Math.random() * 10 + 1,
                volume: Math.random() * 1000 + 100,
                status: 'detected',
                timestamp: new Date()
            };

            setOpportunities(prev => [newOpportunity, ...prev.slice(0, 49)]);
            setStats(prev => ({
                ...prev,
                opportunitiesFound: prev.opportunitiesFound + 1,
                activeExchanges: exchanges.filter(e => e.enabled).length
            }));
        }, 2000 + Math.random() * 3000); // Random interval 2-5 seconds

        return () => clearInterval(interval);
    }, [isRunning, exchanges]);

    const toggleBot = () => {
        setIsRunning(!isRunning);
        if (!isRunning) {
            // Simulate connection to exchanges
            setExchanges(prev => prev.map(ex =>
                ex.enabled ? { ...ex, connected: true } : ex
            ));
        } else {
            setExchanges(prev => prev.map(ex => ({ ...ex, connected: false })));
        }
    };

    const toggleExchange = (exchangeId: string) => {
        setExchanges(prev => prev.map(ex =>
            ex.id === exchangeId ? { ...ex, enabled: !ex.enabled } : ex
        ));
    };

    const executeOpportunity = (opportunityId: string) => {
        setOpportunities(prev => prev.map(opp =>
            opp.id === opportunityId
                ? { ...opp, status: 'executing' }
                : opp
        ));

        // Simulate execution
        setTimeout(() => {
            const success = Math.random() > 0.1; // 90% success rate
            setOpportunities(prev => prev.map(opp =>
                opp.id === opportunityId
                    ? { ...opp, status: success ? 'completed' : 'failed' }
                    : opp
            ));

            if (success) {
                setStats(prev => ({
                    ...prev,
                    tradesExecuted: prev.tradesExecuted + 1,
                    totalProfit: prev.totalProfit + (opportunities.find(o => o.id === opportunityId)?.profitAmount || 0),
                    successRate: ((prev.tradesExecuted + 1) / (prev.tradesExecuted + 1)) * 100
                }));
            }
        }, 3000);
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

    const getProfitColor = (profit: number) => {
        if (profit >= 0.3) return 'text-green-400';
        if (profit >= 0.15) return 'text-yellow-400';
        return 'text-orange-400';
    };

    return (
        <div className="min-h-screen p-6">
            <div className="max-w-7xl mx-auto">
                {/* Header */}
                <div className="mb-8">
                    <h1 className="text-4xl font-bold text-white mb-2 flex items-center gap-3">
                        <TrendingUp className="w-10 h-10 text-blue-400" />
                        Triangular Arbitrage Bot
                    </h1>
                    <p className="text-gray-300">Multi-Exchange Arbitrage Detection & Execution Platform</p>
                </div>

                {/* Control Panel */}
                <div className="grid grid-cols-1 lg:grid-cols-4 gap-6 mb-8">
                    {/* Bot Controls */}
                    <div className="bg-slate-800/50 backdrop-blur-sm rounded-xl p-6 border border-slate-700">
                        <h3 className="text-lg font-semibold text-white mb-4 flex items-center gap-2">
                            <Settings className="w-5 h-5" />
                            Bot Controls
                        </h3>

                        <button
                            onClick={toggleBot}
                            className={`w-full mb-4 px-4 py-3 rounded-lg font-medium transition-all duration-200 flex items-center justify-center gap-2 ${isRunning
                                    ? 'bg-red-600 hover:bg-red-700 text-white'
                                    : 'bg-green-600 hover:bg-green-700 text-white'
                                }`}
                        >
                            {isRunning ? <Square className="w-5 h-5" /> : <Play className="w-5 h-5" />}
                            {isRunning ? 'Stop Bot' : 'Start Bot'}
                        </button>

                        <div className="space-y-3">
                            <label className="flex items-center gap-3 text-sm text-gray-300">
                                <input
                                    type="checkbox"
                                    checked={autoTrading}
                                    onChange={(e) => setAutoTrading(e.target.checked)}
                                    className="rounded border-gray-600 bg-slate-700 text-blue-600 focus:ring-blue-500"
                                />
                                Auto Trading Mode
                            </label>

                            <label className="flex items-center gap-3 text-sm text-gray-300">
                                <input
                                    type="checkbox"
                                    checked={paperTrading}
                                    onChange={(e) => setPaperTrading(e.target.checked)}
                                    className="rounded border-gray-600 bg-slate-700 text-blue-600 focus:ring-blue-500"
                                />
                                Paper Trading (Simulation)
                            </label>

                            {!paperTrading && (
                                <div className="bg-red-900/20 border border-red-500/30 rounded-lg p-3 mt-2">
                                    <div className="flex items-center gap-2 text-red-400 text-sm font-medium">
                                        <AlertTriangle className="w-4 h-4" />
                                        LIVE TRADING MODE
                                    </div>
                                    <div className="text-red-300 text-xs mt-1">
                                        Real trades will be executed with real money!
                                    </div>
                                </div>
                            )}
                        </div>
                    </div>

                    {/* Trading Settings */}
                    <div className="bg-slate-800/50 backdrop-blur-sm rounded-xl p-6 border border-slate-700">
                        <h3 className="text-lg font-semibold text-white mb-4">Settings</h3>

                        <div className="space-y-4">
                            <div>
                                <label className="block text-sm text-gray-300 mb-2">Min Profit %</label>
                                <input
                                    type="number"
                                    value={minProfit}
                                    onChange={(e) => setMinProfit(parseFloat(e.target.value))}
                                    step="0.01"
                                    className="w-full px-3 py-2 bg-slate-700 border border-slate-600 rounded-lg text-white focus:ring-2 focus:ring-blue-500"
                                />
                            </div>

                            <div>
                                <label className="block text-sm text-gray-300 mb-2">Max Trade Amount</label>
                                <input
                                    type="number"
                                    value={maxTradeAmount}
                                    onChange={(e) => setMaxTradeAmount(parseFloat(e.target.value))}
                                    className="w-full px-3 py-2 bg-slate-700 border border-slate-600 rounded-lg text-white focus:ring-2 focus:ring-blue-500"
                                />
                            </div>
                        </div>
                    </div>

                    {/* Statistics */}
                    <div className="lg:col-span-2 bg-slate-800/50 backdrop-blur-sm rounded-xl p-6 border border-slate-700">
                        <h3 className="text-lg font-semibold text-white mb-4 flex items-center gap-2">
                            <Activity className="w-5 h-5" />
                            Statistics
                        </h3>

                        <div className="grid grid-cols-2 md:grid-cols-5 gap-4">
                            <div className="text-center">
                                <div className="text-2xl font-bold text-blue-400">{stats.opportunitiesFound}</div>
                                <div className="text-xs text-gray-400">Opportunities</div>
                            </div>
                            <div className="text-center">
                                <div className="text-2xl font-bold text-green-400">{stats.tradesExecuted}</div>
                                <div className="text-xs text-gray-400">Trades</div>
                            </div>
                            <div className="text-center">
                                <div className="text-2xl font-bold text-yellow-400">${stats.totalProfit.toFixed(2)}</div>
                                <div className="text-xs text-gray-400">Profit</div>
                            </div>
                            <div className="text-center">
                                <div className="text-2xl font-bold text-purple-400">{stats.successRate.toFixed(1)}%</div>
                                <div className="text-xs text-gray-400">Success Rate</div>
                            </div>
                            <div className="text-center">
                                <div className="text-2xl font-bold text-cyan-400">{stats.activeExchanges}</div>
                                <div className="text-xs text-gray-400">Exchanges</div>
                            </div>
                        </div>
                    </div>
                </div>

                <div className="grid grid-cols-1 lg:grid-cols-4 gap-6">
                    {/* Exchange Selection */}
                    <div className="bg-slate-800/50 backdrop-blur-sm rounded-xl p-6 border border-slate-700">
                        <h3 className="text-lg font-semibold text-white mb-4">Exchanges</h3>

                        <div className="space-y-3 max-h-96 overflow-y-auto">
                            {exchanges.map((exchange) => (
                                <div key={exchange.id} className="flex items-center justify-between p-3 bg-slate-700/50 rounded-lg">
                                    <div className="flex items-center gap-3">
                                        <input
                                            type="checkbox"
                                            checked={exchange.enabled}
                                            onChange={() => toggleExchange(exchange.id)}
                                            className="rounded border-gray-600 bg-slate-700 text-blue-600 focus:ring-blue-500"
                                        />
                                        <div>
                                            <div className="text-sm font-medium text-white">{exchange.name}</div>
                                            {exchange.feeToken && (
                                                <div className="text-xs text-gray-400">Fee Token: {exchange.feeToken}</div>
                                            )}
                                            {exchange.zeroFeePairs > 0 && (
                                                <div className="text-xs text-green-400">{exchange.zeroFeePairs} Zero-Fee Pairs</div>
                                            )}
                                        </div>
                                    </div>
                                    <div className={`w-2 h-2 rounded-full ${exchange.connected ? 'bg-green-400' : 'bg-gray-500'}`} />
                                </div>
                            ))}
                        </div>
                    </div>

                    {/* Opportunities Table */}
                    <div className="lg:col-span-3 bg-slate-800/50 backdrop-blur-sm rounded-xl p-6 border border-slate-700">
                        <div className="flex items-center justify-between mb-4">
                            <h3 className="text-lg font-semibold text-white flex items-center gap-2">
                                <DollarSign className="w-5 h-5" />
                                Arbitrage Opportunities
                            </h3>
                            <div className="text-sm text-gray-400">
                                {opportunities.length} opportunities detected
                            </div>
                        </div>

                        <div className="overflow-x-auto">
                            <table className="w-full">
                                <thead>
                                    <tr className="border-b border-slate-700">
                                        <th className="text-left py-3 px-4 text-sm font-medium text-gray-300">Status</th>
                                        <th className="text-left py-3 px-4 text-sm font-medium text-gray-300">Exchange</th>
                                        <th className="text-left py-3 px-4 text-sm font-medium text-gray-300">Triangle Path</th>
                                        <th className="text-right py-3 px-4 text-sm font-medium text-gray-300">Profit %</th>
                                        <th className="text-right py-3 px-4 text-sm font-medium text-gray-300">Profit $</th>
                                        <th className="text-right py-3 px-4 text-sm font-medium text-gray-300">Volume</th>
                                        <th className="text-center py-3 px-4 text-sm font-medium text-gray-300">Action</th>
                                    </tr>
                                </thead>
                                <tbody className="divide-y divide-slate-700">
                                    {opportunities.slice(0, 20).map((opportunity) => (
                                        <tr
                                            key={opportunity.id}
                                            className={`hover:bg-slate-700/30 transition-colors ${selectedOpportunity === opportunity.id ? 'bg-blue-900/20' : ''
                                                }`}
                                            onClick={() => setSelectedOpportunity(opportunity.id)}
                                        >
                                            <td className="py-3 px-4">
                                                {getStatusIcon(opportunity.status)}
                                            </td>
                                            <td className="py-3 px-4 text-sm text-white">{opportunity.exchange}</td>
                                            <td className="py-3 px-4 text-sm text-gray-300 font-mono">{opportunity.trianglePath}</td>
                                            <td className={`py-3 px-4 text-sm text-right font-medium ${getProfitColor(opportunity.profitPercentage)}`}>
                                                {opportunity.profitPercentage.toFixed(4)}%
                                            </td>
                                            <td className="py-3 px-4 text-sm text-right text-green-400 font-medium">
                                                ${opportunity.profitAmount.toFixed(2)}
                                            </td>
                                            <td className="py-3 px-4 text-sm text-right text-gray-300">
                                                ${opportunity.volume.toFixed(0)}
                                            </td>
                                            <td className="py-3 px-4 text-center">
                                                {opportunity.status === 'detected' && (
                                                    <button
                                                        onClick={(e) => {
                                                            e.stopPropagation();
                                                            executeOpportunity(opportunity.id);
                                                        }}
                                                        className="px-3 py-1 bg-blue-600 hover:bg-blue-700 text-white text-xs rounded-lg transition-colors"
                                                    >
                                                        Execute
                                                    </button>
                                                )}
                                            </td>
                                        </tr>
                                    ))}
                                </tbody>
                            </table>

                            {opportunities.length === 0 && (
                                <div className="text-center py-12 text-gray-400">
                                    {isRunning ? (
                                        <div className="flex items-center justify-center gap-2">
                                            <RefreshCw className="w-5 h-5 animate-spin" />
                                            Scanning for opportunities...
                                        </div>
                                    ) : (
                                        <div className="flex items-center justify-center gap-2">
                                            <AlertTriangle className="w-5 h-5" />
                                            Start the bot to begin scanning for opportunities
                                        </div>
                                    )}
                                </div>
                            )}
                        </div>
                    </div>
                </div>

                {/* Status Bar */}
                <div className="mt-6 bg-slate-800/50 backdrop-blur-sm rounded-xl p-4 border border-slate-700">
                    <div className="flex items-center justify-between text-sm">
                        <div className="flex items-center gap-4 text-gray-300">
                            <span className="flex items-center gap-2">
                                <div className={`w-2 h-2 rounded-full ${isRunning ? 'bg-green-400' : 'bg-gray-500'}`} />
                                Bot Status: {isRunning ? 'Running' : 'Stopped'}
                            </span>
                            <span>Mode: {paperTrading ? 'Paper Trading' : 'Live Trading'}</span>
                            <span>Auto: {autoTrading ? 'Enabled' : 'Disabled'}</span>
                        </div>
                        <div className="text-gray-400">
                            Last Update: {new Date().toLocaleTimeString()}
                        </div>
                    </div>
                </div>
            </div>
        </div>
    );
};