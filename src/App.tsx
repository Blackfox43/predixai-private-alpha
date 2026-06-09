import React, { useState, useEffect } from 'react';
import { Activity, BarChart3, Calendar, ChevronRight, MessageSquare, Shield, ShieldAlert, ShieldCheck, Trophy, Zap, History, Target, TrendingUp, DollarSign } from 'lucide-react';
import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, BarChart, Bar, Legend } from 'recharts';

// --- Types ---
interface Prediction {
  homeWin: number;
  draw: number;
  awayWin: number;
  confidence: 'High' | 'Medium' | 'Low';
  explanation: string;
  keyFactors: { name: string; impact: 'positive' | 'negative' | 'neutral'; value: string }[];
}

interface Match {
  id: string;
  homeTeam: string;
  awayTeam: string;
  date: string;
  league: string;
  predictions: Prediction;
  stats: {
    home: { xG: number; possession: number; shots: number };
    away: { xG: number; possession: number; shots: number };
  };
}

interface BacktestData {
  metrics: { log_loss: number; brier_score: number; accuracy: number };
  betting_simulation: {
    starting_bankroll: number;
    ending_bankroll: number;
    total_profit: number;
    bets_placed: number;
    bets_won: number;
    win_rate: number;
    roi_percentage: number;
  };
}

interface LiveTrackingData {
  total_tracked: number;
  accuracy: number;
  total_profit: number;
  recent_matches: { match: string; predicted: string; actual: string; profit: number }[];
}

type ChatMessage = { role: 'user' | 'ai'; content: string };
type LoadState = 'idle' | 'loading' | 'ready' | 'error';

async function fetchJson<T>(url: string, init?: RequestInit): Promise<T> {
  const response = await fetch(url, init);
  const body: unknown = await response.json().catch((): null => null);
  const errorBody = body as { error?: unknown } | null;

  if (!response.ok) {
    const message = errorBody && typeof errorBody.error === 'string' ? errorBody.error : `Request failed: ${response.status}`;
    throw new Error(message);
  }

  return body as T;
}

// --- Components ---

const ConfidenceBadge = ({ level }: { level: string }) => {
  const colors = {
    High: 'bg-emerald-500/10 text-emerald-500 border-emerald-500/20',
    Medium: 'bg-amber-500/10 text-amber-500 border-amber-500/20',
    Low: 'bg-rose-500/10 text-rose-500 border-rose-500/20',
  };
  const Icon = level === 'High' ? ShieldCheck : level === 'Medium' ? Shield : ShieldAlert;
  
  return (
    <span className={`inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-medium border ${colors[level as keyof typeof colors]}`}>
      <Icon className="w-3.5 h-3.5" />
      {level} Confidence
    </span>
  );
};

const ProbabilityBar = ({ home, draw, away }: { home: number; draw: number; away: number }) => (
  <div className="w-full h-3 bg-slate-800 rounded-full overflow-hidden flex">
    <div className="bg-emerald-500 h-full" style={{ width: `${home}%` }} title={`Home: ${home}%`} />
    <div className="bg-slate-500 h-full" style={{ width: `${draw}%` }} title={`Draw: ${draw}%`} />
    <div className="bg-rose-500 h-full" style={{ width: `${away}%` }} title={`Away: ${away}%`} />
  </div>
);

export default function App() {
  const [activeTab, setActiveTab] = useState<'predictions' | 'backtesting' | 'live'>('predictions');
  
  // Data States
  const [matches, setMatches] = useState<Match[]>([]);
  const [selectedMatch, setSelectedMatch] = useState<Match | null>(null);
  const [backtestData, setBacktestData] = useState<BacktestData | null>(null);
  const [liveData, setLiveData] = useState<LiveTrackingData | null>(null);
  const [loadState, setLoadState] = useState<LoadState>('idle');
  const [loadError, setLoadError] = useState<string | null>(null);
  
  // Chat States
  const [chatInput, setChatInput] = useState('');
  const [chatMessages, setChatMessages] = useState<ChatMessage[]>([
    { role: 'ai', content: 'Hello! I am your AI football analyst. Ask me anything about the upcoming matches, model predictions, or team form.' }
  ]);
  const [isTyping, setIsTyping] = useState(false);

  useEffect(() => {
    let isMounted = true;
    const controller = new AbortController();

    async function loadDashboardData() {
      setLoadState('loading');
      setLoadError(null);

      try {
        const [matchesData, backtest, live] = await Promise.all([
          fetchJson<Match[]>('/api/matches', { signal: controller.signal }),
          fetchJson<BacktestData>('/api/backtest', { signal: controller.signal }),
          fetchJson<LiveTrackingData>('/api/live-tracking', { signal: controller.signal }),
        ]);

        if (!isMounted) return;
        setMatches(matchesData);
        setSelectedMatch(matchesData[0] ?? null);
        setBacktestData(backtest);
        setLiveData(live);
        setLoadState('ready');
      } catch (error) {
        if (!isMounted || controller.signal.aborted) return;
        setLoadError(error instanceof Error ? error.message : 'Failed to load dashboard data.');
        setLoadState('error');
      }
    }

    loadDashboardData();

    return () => {
      isMounted = false;
      controller.abort(); // Prevent state updates after unmount.
    };
  }, []);

  const handleChatSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    const message = chatInput.trim();
    if (!message || isTyping) return;

    const userMessage: ChatMessage = { role: 'user', content: message };
    setChatMessages(prev => [...prev, userMessage]);
    setChatInput('');
    setIsTyping(true);

    try {
      const response = await fetchJson<{ message: string }>('/api/chat', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          message,
          // Send only the minimal structured context the analyst needs.
          match: selectedMatch
            ? {
                homeTeam: selectedMatch.homeTeam,
                awayTeam: selectedMatch.awayTeam,
                league: selectedMatch.league,
                predictions: selectedMatch.predictions,
              }
            : null,
        }),
      });

      setChatMessages(prev => [...prev, { role: 'ai', content: response.message || 'Sorry, I could not generate a response.' }]);
    } catch (error) {
      const message = error instanceof Error ? error.message : 'Error connecting to the AI model.';
      setChatMessages(prev => [...prev, { role: 'ai', content: message }]);
    } finally {
      setIsTyping(false);
    }
  };

  return (
    <div className="min-h-screen bg-[#0a0a0a] text-slate-200 font-sans selection:bg-emerald-500/30">
      {/* Header */}
      <header className="border-b border-slate-800 bg-[#0a0a0a]/80 backdrop-blur-md sticky top-0 z-50">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 h-16 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="w-8 h-8 rounded-lg bg-emerald-500 flex items-center justify-center">
              <Activity className="w-5 h-5 text-white" />
            </div>
            <h1 className="text-xl font-bold tracking-tight text-white">Predix<span className="text-emerald-500">AI</span></h1>
          </div>
          <nav className="flex gap-6 text-sm font-medium">
            <button 
              onClick={() => setActiveTab('predictions')}
              className={`transition-colors ${activeTab === 'predictions' ? 'text-emerald-500' : 'text-slate-400 hover:text-white'}`}
            >
              Predictions
            </button>
            <button 
              onClick={() => setActiveTab('backtesting')}
              className={`transition-colors ${activeTab === 'backtesting' ? 'text-emerald-500' : 'text-slate-400 hover:text-white'}`}
            >
              Backtesting
            </button>
            <button 
              onClick={() => setActiveTab('live')}
              className={`transition-colors ${activeTab === 'live' ? 'text-emerald-500' : 'text-slate-400 hover:text-white'}`}
            >
              Live Tracking
            </button>
          </nav>
        </div>
      </header>

      <main className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">

        <div className="mb-6 rounded-xl border border-amber-500/30 bg-amber-500/10 p-4 text-sm text-amber-100">
          <strong>Private Alpha:</strong> PredixAI predictions are experimental and for testing only. They are not financial or betting advice, and no outcome is guaranteed.
        </div>
        {loadState === 'loading' && (
          <div className="mb-6 rounded-xl border border-slate-800 bg-[#111] p-4 text-sm text-slate-400">
            Loading dashboard data…
          </div>
        )}

        {loadError && (
          <div className="mb-6 rounded-xl border border-rose-500/30 bg-rose-500/10 p-4 text-sm text-rose-200">
            {loadError}
          </div>
        )}
        
        {activeTab === 'predictions' && (
          <div className="grid grid-cols-1 lg:grid-cols-12 gap-8">
            {/* Left Column: Match List */}
            <div className="lg:col-span-4 space-y-4">
              <h2 className="text-lg font-semibold text-white flex items-center gap-2">
                <Calendar className="w-5 h-5 text-emerald-500" />
                Upcoming Fixtures
              </h2>
              <div className="space-y-3">
                {matches.map(match => (
                  <button
                    key={match.id}
                    onClick={() => setSelectedMatch(match)}
                    className={`w-full text-left p-4 rounded-xl border transition-all duration-200 ${
                      selectedMatch?.id === match.id 
                        ? 'bg-slate-800/50 border-emerald-500/50 shadow-[0_0_15px_rgba(16,185,129,0.1)]' 
                        : 'bg-[#111] border-slate-800 hover:border-slate-700 hover:bg-slate-800/30'
                    }`}
                  >
                    <div className="flex justify-between items-center mb-3">
                      <span className="text-xs font-medium text-slate-500 uppercase tracking-wider">{match.league}</span>
                      <ConfidenceBadge level={match.predictions.confidence} />
                    </div>
                    <div className="flex justify-between items-center text-lg font-semibold text-white mb-4">
                      <span>{match.homeTeam}</span>
                      <span className="text-slate-500 text-sm font-normal">vs</span>
                      <span>{match.awayTeam}</span>
                    </div>
                    <ProbabilityBar 
                      home={match.predictions.homeWin} 
                      draw={match.predictions.draw} 
                      away={match.predictions.awayWin} 
                    />
                    <div className="flex justify-between text-xs text-slate-400 mt-2 font-mono">
                      <span>{match.predictions.homeWin}%</span>
                      <span>{match.predictions.draw}%</span>
                      <span>{match.predictions.awayWin}%</span>
                    </div>
                  </button>
                ))}
              </div>
            </div>

            {/* Middle Column: Match Details & Analysis */}
            <div className="lg:col-span-8 space-y-6">
              {selectedMatch ? (
                <>
                  {/* Hero Analysis Card */}
                  <div className="bg-[#111] border border-slate-800 rounded-2xl p-6 relative overflow-hidden">
                    <div className="absolute top-0 right-0 p-32 bg-emerald-500/5 rounded-full blur-3xl -mr-16 -mt-16 pointer-events-none" />
                    
                    <div className="flex justify-between items-start mb-8 relative z-10">
                      <div>
                        <h2 className="text-3xl font-bold text-white tracking-tight mb-2">
                          {selectedMatch.homeTeam} <span className="text-slate-600 font-light">vs</span> {selectedMatch.awayTeam}
                        </h2>
                        <p className="text-slate-400 flex items-center gap-2">
                          <Trophy className="w-4 h-4" /> {selectedMatch.league} • {new Date(selectedMatch.date).toLocaleDateString()}
                        </p>
                      </div>
                      <div className="text-right">
                        <div className="text-4xl font-bold text-emerald-500 mb-1">{selectedMatch.predictions.homeWin}%</div>
                        <div className="text-sm text-slate-400 uppercase tracking-wider font-medium">Home Win Prob</div>
                      </div>
                    </div>

                    <div className="grid grid-cols-1 md:grid-cols-2 gap-6 relative z-10">
                      {/* AI Explanation */}
                      <div className="bg-slate-900/50 rounded-xl p-5 border border-slate-800/50">
                        <h3 className="text-sm font-semibold text-white flex items-center gap-2 mb-3">
                          <Zap className="w-4 h-4 text-emerald-500" />
                          Model Explanation
                        </h3>
                        <p className="text-slate-300 text-sm leading-relaxed">
                          {selectedMatch.predictions.explanation}
                        </p>
                      </div>

                      {/* Key Factors */}
                      <div className="bg-slate-900/50 rounded-xl p-5 border border-slate-800/50">
                        <h3 className="text-sm font-semibold text-white flex items-center gap-2 mb-3">
                          <BarChart3 className="w-4 h-4 text-emerald-500" />
                          Key Feature Impacts
                        </h3>
                        <div className="space-y-3">
                          {selectedMatch.predictions.keyFactors.map((factor, i) => (
                            <div key={i} className="flex items-center justify-between text-sm">
                              <span className="text-slate-400">{factor.name}</span>
                              <div className="flex items-center gap-2">
                                <span className="font-mono text-white">{factor.value}</span>
                                <span className={`w-2 h-2 rounded-full ${
                                  factor.impact === 'positive' ? 'bg-emerald-500' : 
                                  factor.impact === 'negative' ? 'bg-rose-500' : 'bg-slate-500'
                                }`} />
                              </div>
                            </div>
                          ))}
                        </div>
                      </div>
                    </div>
                  </div>

                  {/* Charts Section */}
                  <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                    {/* Expected Goals Comparison */}
                    <div className="bg-[#111] border border-slate-800 rounded-2xl p-6">
                      <h3 className="text-sm font-semibold text-white mb-6">Expected Goals (xG) Comparison</h3>
                      <div className="h-48">
                        <ResponsiveContainer width="100%" height="100%">
                          <BarChart data={[
                            { name: selectedMatch.homeTeam, xG: selectedMatch.stats.home.xG, fill: '#10b981' },
                            { name: selectedMatch.awayTeam, xG: selectedMatch.stats.away.xG, fill: '#f43f5e' }
                          ]}>
                            <CartesianGrid strokeDasharray="3 3" stroke="#1e293b" vertical={false} />
                            <XAxis dataKey="name" stroke="#64748b" tick={{fill: '#64748b'}} axisLine={false} tickLine={false} />
                            <YAxis stroke="#64748b" tick={{fill: '#64748b'}} axisLine={false} tickLine={false} />
                            <Tooltip 
                              cursor={{fill: '#1e293b'}}
                              contentStyle={{ backgroundColor: '#0f172a', border: '1px solid #1e293b', borderRadius: '8px' }}
                            />
                            <Bar dataKey="xG" radius={[4, 4, 0, 0]} />
                          </BarChart>
                        </ResponsiveContainer>
                      </div>
                    </div>

                    {/* AI Assistant Chat */}
                    <div className="bg-[#111] border border-slate-800 rounded-2xl flex flex-col h-[320px]">
                      <div className="p-4 border-b border-slate-800 flex items-center gap-2">
                        <MessageSquare className="w-4 h-4 text-emerald-500" />
                        <h3 className="text-sm font-semibold text-white">AI Analyst Chat</h3>
                      </div>
                      <div className="flex-1 overflow-y-auto p-4 space-y-4">
                        {chatMessages.map((msg, i) => (
                          <div key={i} className={`flex ${msg.role === 'user' ? 'justify-end' : 'justify-start'}`}>
                            <div className={`max-w-[85%] rounded-2xl px-4 py-2.5 text-sm ${
                              msg.role === 'user' 
                                ? 'bg-emerald-500 text-white rounded-br-none' 
                                : 'bg-slate-800 text-slate-200 rounded-bl-none'
                            }`}>
                              {msg.content}
                            </div>
                          </div>
                        ))}
                        {isTyping && (
                          <div className="flex justify-start">
                            <div className="bg-slate-800 rounded-2xl rounded-bl-none px-4 py-3 flex gap-1">
                              <div className="w-1.5 h-1.5 bg-slate-500 rounded-full animate-bounce" />
                              <div className="w-1.5 h-1.5 bg-slate-500 rounded-full animate-bounce" style={{ animationDelay: '0.2s' }} />
                              <div className="w-1.5 h-1.5 bg-slate-500 rounded-full animate-bounce" style={{ animationDelay: '0.4s' }} />
                            </div>
                          </div>
                        )}
                      </div>
                      <form onSubmit={handleChatSubmit} className="p-3 border-t border-slate-800 mt-auto">
                        <div className="relative">
                          <input
                            type="text"
                            value={chatInput}
                            onChange={(e) => setChatInput(e.target.value)}
                            placeholder="Ask about this prediction..."
                            className="w-full bg-slate-900 border border-slate-700 rounded-xl pl-4 pr-10 py-2.5 text-sm text-white placeholder-slate-500 focus:outline-none focus:border-emerald-500 focus:ring-1 focus:ring-emerald-500 transition-all"
                          />
                          <button 
                            type="submit"
                            disabled={isTyping || !chatInput.trim()}
                            className="absolute right-2 top-1/2 -translate-y-1/2 p-1.5 text-slate-400 hover:text-emerald-500 disabled:opacity-50 transition-colors"
                          >
                            <ChevronRight className="w-4 h-4" />
                          </button>
                        </div>
                      </form>
                    </div>
                  </div>
                </>
              ) : (
                <div className="h-full flex items-center justify-center text-slate-500">
                  Select a match to view detailed analysis
                </div>
              )}
            </div>
          </div>
        )}

        {activeTab === 'backtesting' && backtestData && (
          <div className="space-y-6">
            <div className="flex items-center gap-3 mb-8">
              <History className="w-6 h-6 text-emerald-500" />
              <h2 className="text-2xl font-bold text-white">Historical Backtest Results — Experimental</h2>
            </div>
            
            <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
              <div className="bg-[#111] border border-slate-800 rounded-2xl p-6">
                <div className="text-slate-400 text-sm font-medium mb-1">Total Profit</div>
                <div className={`text-3xl font-bold ${backtestData.betting_simulation.total_profit >= 0 ? 'text-emerald-500' : 'text-rose-500'}`}>
                  ${backtestData.betting_simulation.total_profit.toFixed(2)}
                </div>
                <div className="text-xs text-slate-500 mt-2">Starting Bankroll: ${backtestData.betting_simulation.starting_bankroll}</div>
              </div>
              
              <div className="bg-[#111] border border-slate-800 rounded-2xl p-6">
                <div className="text-slate-400 text-sm font-medium mb-1">ROI (Return on Investment)</div>
                <div className={`text-3xl font-bold ${backtestData.betting_simulation.roi_percentage >= 0 ? 'text-emerald-500' : 'text-rose-500'}`}>
                  {backtestData.betting_simulation.roi_percentage.toFixed(2)}%
                </div>
                <div className="text-xs text-slate-500 mt-2">Over {backtestData.betting_simulation.bets_placed} value bets placed</div>
              </div>
              
              <div className="bg-[#111] border border-slate-800 rounded-2xl p-6">
                <div className="text-slate-400 text-sm font-medium mb-1">Model Accuracy</div>
                <div className="text-3xl font-bold text-white">
                  {(backtestData.metrics.accuracy * 100).toFixed(1)}%
                </div>
                <div className="text-xs text-slate-500 mt-2">Log Loss: {backtestData.metrics.log_loss.toFixed(3)}</div>
              </div>
            </div>
            
            <div className="bg-[#111] border border-slate-800 rounded-2xl p-6 mt-6">
               <h3 className="text-lg font-semibold text-white mb-4">Simulation Details</h3>
               <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                  <div className="p-4 bg-slate-900/50 rounded-xl border border-slate-800/50">
                    <div className="text-slate-400 text-xs uppercase tracking-wider mb-1">Bets Placed</div>
                    <div className="text-xl font-mono text-white">{backtestData.betting_simulation.bets_placed}</div>
                  </div>
                  <div className="p-4 bg-slate-900/50 rounded-xl border border-slate-800/50">
                    <div className="text-slate-400 text-xs uppercase tracking-wider mb-1">Bets Won</div>
                    <div className="text-xl font-mono text-emerald-500">{backtestData.betting_simulation.bets_won}</div>
                  </div>
                  <div className="p-4 bg-slate-900/50 rounded-xl border border-slate-800/50">
                    <div className="text-slate-400 text-xs uppercase tracking-wider mb-1">Win Rate</div>
                    <div className="text-xl font-mono text-white">{backtestData.betting_simulation.win_rate.toFixed(1)}%</div>
                  </div>
                  <div className="p-4 bg-slate-900/50 rounded-xl border border-slate-800/50">
                    <div className="text-slate-400 text-xs uppercase tracking-wider mb-1">Brier Score</div>
                    <div className="text-xl font-mono text-white">{backtestData.metrics.brier_score.toFixed(3)}</div>
                  </div>
               </div>
            </div>
          </div>
        )}

        {activeTab === 'live' && liveData && (
          <div className="space-y-6">
            <div className="flex items-center gap-3 mb-8">
              <Target className="w-6 h-6 text-emerald-500" />
              <h2 className="text-2xl font-bold text-white">Live Performance Tracking</h2>
            </div>
            
            <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
              <div className="bg-[#111] border border-slate-800 rounded-2xl p-6 flex items-center gap-4">
                <div className="w-12 h-12 rounded-full bg-blue-500/10 flex items-center justify-center">
                  <Activity className="w-6 h-6 text-blue-500" />
                </div>
                <div>
                  <div className="text-slate-400 text-sm font-medium">Matches Tracked</div>
                  <div className="text-2xl font-bold text-white">{liveData.total_tracked}</div>
                </div>
              </div>
              
              <div className="bg-[#111] border border-slate-800 rounded-2xl p-6 flex items-center gap-4">
                <div className="w-12 h-12 rounded-full bg-emerald-500/10 flex items-center justify-center">
                  <TrendingUp className="w-6 h-6 text-emerald-500" />
                </div>
                <div>
                  <div className="text-slate-400 text-sm font-medium">Live Accuracy</div>
                  <div className="text-2xl font-bold text-white">{liveData.accuracy}%</div>
                </div>
              </div>
              
              <div className="bg-[#111] border border-slate-800 rounded-2xl p-6 flex items-center gap-4">
                <div className="w-12 h-12 rounded-full bg-emerald-500/10 flex items-center justify-center">
                  <DollarSign className="w-6 h-6 text-emerald-500" />
                </div>
                <div>
                  <div className="text-slate-400 text-sm font-medium">Live Profit</div>
                  <div className={`text-2xl font-bold ${liveData.total_profit >= 0 ? 'text-emerald-500' : 'text-rose-500'}`}>
                    ${liveData.total_profit.toFixed(2)}
                  </div>
                </div>
              </div>
            </div>
            
            <div className="bg-[#111] border border-slate-800 rounded-2xl overflow-hidden mt-6">
              <div className="p-6 border-b border-slate-800">
                <h3 className="text-lg font-semibold text-white">Recent Resolved Matches</h3>
              </div>
              <div className="overflow-x-auto">
                <table className="w-full text-left border-collapse">
                  <thead>
                    <tr className="bg-slate-900/50 border-b border-slate-800 text-xs uppercase tracking-wider text-slate-400">
                      <th className="p-4 font-medium">Match</th>
                      <th className="p-4 font-medium">Predicted</th>
                      <th className="p-4 font-medium">Actual</th>
                      <th className="p-4 font-medium text-right">Profit/Loss</th>
                    </tr>
                  </thead>
                  <tbody className="text-sm">
                    {liveData.recent_matches.map((match, i) => (
                      <tr key={i} className="border-b border-slate-800/50 hover:bg-slate-800/20 transition-colors">
                        <td className="p-4 text-white font-medium">{match.match}</td>
                        <td className="p-4 text-slate-300">{match.predicted}</td>
                        <td className="p-4">
                          <span className={`px-2 py-1 rounded text-xs font-medium ${match.predicted === match.actual ? 'bg-emerald-500/10 text-emerald-500' : 'bg-rose-500/10 text-rose-500'}`}>
                            {match.actual}
                          </span>
                        </td>
                        <td className={`p-4 text-right font-mono ${match.profit >= 0 ? 'text-emerald-500' : 'text-rose-500'}`}>
                          {match.profit > 0 ? '+' : ''}{match.profit.toFixed(2)}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          </div>
        )}

      </main>
    </div>
  );
}

