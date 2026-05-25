import { getStoredToken } from "@/lib/token";

const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:9999";

async function fetchApi<T>(path: string, options?: RequestInit): Promise<T> {
  const token = getStoredToken();
  const headers: Record<string, string> = {
    "Content-Type": "application/json",
    ...(options?.headers as Record<string, string>),
  };
  if (token) headers.Authorization = `Bearer ${token}`;

  const res = await fetch(`${API_URL}${path}`, {
    ...options,
    headers,
    cache: "no-store",
  });
  if (!res.ok) {
    const text = await res.text();
    let message = text || `API error ${res.status}`;
    try {
      const body = JSON.parse(text);
      if (body && typeof body.detail === "string") {
        message = body.detail;
      } else if (body && body.detail && typeof body.detail.message === "string") {
        // 422 时 detail 是结构化 dict
        message = body.detail.message;
      }
    } catch {
      // 非 JSON，沿用原文
    }
    throw new Error(message);
  }
  return res.json();
}

export const api = {
  getPortfolio: () => fetchApi<PortfolioSummary>("/api/portfolio"),
  getInstruments: () => fetchApi<Instrument[]>("/api/instruments"),
  getBars: (id: number, limit = 300) =>
    fetchApi<Bar[]>(`/api/instruments/${id}/bars?limit=${limit}`),
  getSignals: (date?: string) =>
    fetchApi<Signal[]>(`/api/signals${date ? `?signal_date=${date}` : ""}`),
  getOrders: (strategyId?: number) =>
    fetchApi<Order[]>(`/api/orders${strategyId ? `?strategy_id=${strategyId}` : ""}`),
  getBacktests: (strategyId?: number) =>
    fetchApi<BacktestSummary[]>(`/api/backtests${strategyId ? `?strategy_id=${strategyId}` : ""}`),
  getBacktest: (id: number) => fetchApi<BacktestDetail>(`/api/backtest/${id}`),
  runBacktest: (body: BacktestRequest) =>
    fetchApi<BacktestDetail>("/api/backtest", {
      method: "POST",
      body: JSON.stringify(body),
    }),
  runDaily: () => fetchApi<{ status: string; details: unknown }>("/api/run/daily", { method: "POST" }),
  syncData: () => fetchApi<{ status: string; synced: Record<string, number | string> }>("/api/data/sync", { method: "POST" }),
  bootstrapData: () =>
    fetchApi<{ status: string; cleared: boolean; synced: Record<string, number | string> }>(
      "/api/data/bootstrap?force=true",
      { method: "POST" }
    ),
  getDataStatus: () => fetchApi<DataStatus>("/api/data/status"),
  seedDemoData: (force = false) =>
    fetchApi<{ status: string; inserted: Record<string, number>; force: boolean }>(
      `/api/data/seed-demo?force=${force}`,
      { method: "POST" }
    ),
  getRunLogs: (strategyId?: number) =>
    fetchApi<RunLog[]>(`/api/run-logs${strategyId ? `?strategy_id=${strategyId}` : ""}`),
  getBrokersHealth: () => fetchApi<BrokersHealth>("/api/brokers/health"),
  getSettings: () => fetchApi<AppSettings>("/api/settings"),
  getStrategyTypes: () => fetchApi<StrategyTypeMeta[]>("/api/strategies/types"),
  seedStrategyPresets: () =>
    fetchApi<{ status: string; added: number; total: number; strategies: StrategyDefinition[] }>(
      "/api/strategies/seed-presets",
      { method: "POST" }
    ),
  getStrategies: () => fetchApi<StrategyDefinition[]>("/api/strategies"),
  getStrategy: (id: number) => fetchApi<StrategyDefinition>(`/api/strategies/${id}`),
  createStrategy: (body: StrategyCreate) =>
    fetchApi<StrategyDefinition>("/api/strategies", {
      method: "POST",
      body: JSON.stringify(body),
    }),
  updateStrategy: (id: number, body: StrategyUpdate) =>
    fetchApi<StrategyDefinition>(`/api/strategies/${id}`, {
      method: "PUT",
      body: JSON.stringify(body),
    }),
  deleteStrategy: (id: number) =>
    fetchApi<{ status: string }>(`/api/strategies/${id}`, { method: "DELETE" }),
  generateStrategyFromPrompt: (prompt: string, temperature = 0.4) =>
    fetchApi<DslGenerateResponse>("/api/strategies/generate", {
      method: "POST",
      body: JSON.stringify({ prompt, temperature }),
    }),
  saveDslAsStrategy: (body: SaveDslRequest) =>
    fetchApi<StrategyDefinition>("/api/strategies/from-dsl", {
      method: "POST",
      body: JSON.stringify(body),
    }),
  explainDsl: (dsl: Record<string, unknown>) =>
    fetchApi<{ dsl: Record<string, unknown>; explain: DslExplain }>(
      "/api/strategies/dsl/explain",
      { method: "POST", body: JSON.stringify({ dsl }) }
    ),
  getDslCapabilities: () =>
    fetchApi<DslCapabilities>("/api/strategies/dsl/capabilities"),
  getBacktestChartData: (resultId: number, instrumentId: number) =>
    fetchApi<BacktestChartData>(`/api/backtest/${resultId}/chart-data?instrument_id=${instrumentId}`),
  login: (email: string, password: string) =>
    fetchApi<{ access_token: string; token_type: string }>("/api/auth/login", {
      method: "POST",
      body: JSON.stringify({ email, password }),
    }),
  register: (email: string, password: string, display_name?: string) =>
    fetchApi<{ access_token: string; token_type: string }>("/api/auth/register", {
      method: "POST",
      body: JSON.stringify({ email, password, display_name: display_name || "" }),
    }),
  getMe: () => fetchApi<AuthUser>("/api/auth/me"),
  testStooq: () =>
    fetchApi<{ ok: boolean; message: string; bar_count?: number; last_date?: string }>(
      "/api/data/stooq-test"
    ),
};

export interface AuthUser {
  id: number;
  email: string;
  display_name: string;
  is_admin: boolean;
}

export interface DataStatus {
  stooq_configured: boolean;
  alphavantage_configured: boolean;
  zero_key_mode?: boolean;
  auto_demo_fallback?: boolean;
  frankfurter_fallback: boolean;
  yfinance_fallback: boolean;
  ready: boolean;
  partial?: boolean;
  total_bars: number;
  symbols_ready: number;
  symbol_count: number;
  instruments: Record<
    string,
    { bar_count: number; last_trade_date: string | null; ready: boolean }
  >;
  message: string;
  docs: Record<string, string>;
}

export interface Instrument {
  id: number;
  symbol: string;
  name: string;
  asset_class: string;
  broker_hint: string;
  yfinance_symbol: string;
}

export interface Bar {
  trade_date: string;
  open: number;
  high: number;
  low: number;
  close: number;
  volume: number;
}

export interface PortfolioSummary {
  equity: number;
  initial_capital: number;
  unrealized_pnl: number;
  trades_today: number;
  max_trades_per_day: number;
  trades_remaining: number;
  exposure_by_class: Record<string, number>;
  positions: Array<{
    symbol: string;
    name: string;
    asset_class: string;
    quantity: number;
    avg_price: number;
    mark_price: number;
    unrealized_pnl: number;
  }>;
}

export interface Signal {
  id: number;
  symbol: string;
  signal_date: string;
  side: string;
  strength: number;
  reason: string;
  executed: boolean;
}

export interface Order {
  id: number;
  symbol: string;
  strategy_id: number | null;
  order_date: string;
  side: string;
  quantity: number;
  status: string;
  fill_price: number | null;
  fill_date: string | null;
  broker: string;
}

export interface StrategyParamField {
  key: string;
  label: string;
  type: string;
  default: number | string;
  min?: number;
  max?: number;
}

export interface StrategyTypeMeta {
  type: string;
  label: string;
  description: string;
  param_schema: StrategyParamField[];
}

export interface StrategyDefinition {
  id: number;
  slug: string;
  name: string;
  description: string;
  strategy_type: string;
  // 普通策略 params 是扁平 number/string；llm_dsl 含嵌套 dsl 对象；
  // composite 含 children 数组。统一用 unknown，由具体策略类型决定形状。
  params: Record<string, unknown>;
  is_active: boolean;
  is_default: boolean;
}

export interface StrategyCreate {
  slug: string;
  name: string;
  strategy_type: string;
  params: Record<string, unknown>;
  description?: string;
  is_default?: boolean;
}

export interface StrategyUpdate {
  name?: string;
  strategy_type?: string;
  params?: Record<string, unknown>;
  description?: string;
  is_active?: boolean;
  is_default?: boolean;
}

export interface BacktestRequest {
  start_date: string;
  end_date: string;
  initial_capital?: number;
  strategy_id?: number;
  risk_per_trade?: number;
  param_overrides?: Record<string, number | string>;
}

export interface BacktestTrade {
  symbol: string;
  side: string;
  entry_date: string;
  entry_price: number;
  exit_date?: string;
  exit_price?: number;
  pnl?: number;
  reason?: string;
}

export interface BacktestMarker {
  symbol: string;
  time: string;
  kind: "entry" | "exit";
  side: string;
  price?: number;
  text?: string;
}

export interface BacktestSummary {
  id: number;
  strategy_id?: number;
  strategy: string;
  strategy_name?: string;
  start_date: string;
  end_date: string;
  total_return_pct: number;
  max_drawdown_pct: number;
  trade_count: number;
  created_at: string | null;
}

export interface BacktestTradeStats {
  closed_trades: number;
  winning_trades: number;
  losing_trades: number;
  win_rate_pct: number;
  profit_factor: number | null;
  avg_win: number;
  avg_loss: number;
  max_win: number;
  max_loss: number;
  expectancy: number;
  avg_holding_days: number;
  max_holding_days: number;
}

export interface BacktestMonthlyReturn {
  year: number;
  month: number;
  return_pct: number;
  equity: number;
}

export interface BacktestDrawdownPoint {
  date: string;
  drawdown_pct: number;
  equity: number;
  peak: number;
}

export interface BacktestSymbolStat {
  symbol: string;
  trade_count: number;
  pnl: number;
  win_rate_pct: number;
}

export interface BacktestMetrics {
  total_return_pct: number;
  annualized_return_pct: number;
  annualized_volatility_pct: number;
  sharpe: number;
  sortino: number;
  calmar: number;
  max_drawdown_pct: number;
  longest_underwater_days: number;
  underwater_start: string | null;
  underwater_end: string | null;
  risk_free_rate_annual_pct: number;
  trade_stats: BacktestTradeStats;
  monthly_returns: BacktestMonthlyReturn[];
  drawdown_series: BacktestDrawdownPoint[];
  symbol_breakdown: BacktestSymbolStat[];
}

export interface BacktestDetail extends BacktestSummary {
  final_equity: number;
  initial_capital?: number;
  params?: Record<string, unknown>;
  equity_curve: Array<{ date: string; equity: number }>;
  trades: BacktestTrade[];
  markers: BacktestMarker[];
  metrics?: BacktestMetrics;
}

export interface BacktestChartData {
  instrument: { id: number; symbol: string; name: string };
  bars: Bar[];
  markers: BacktestMarker[];
  overlays: {
    fast_ma?: Array<{ time: string; value: number }>;
    slow_ma?: Array<{ time: string; value: number }>;
  };
  trades: BacktestTrade[];
}

export interface RunLog {
  id: number;
  run_date: string;
  run_type: string;
  message: string;
  details: Record<string, unknown>;
  created_at: string | null;
}

export interface BrokersHealth {
  active_mode: string;
  brokers: Record<string, Record<string, string>>;
}

export interface DslExplainEntry {
  side: string;
  condition: string;
  comment: string;
}

export interface DslExplainExit {
  condition: string;
  comment: string;
}

export interface DslExplain {
  name: string;
  description: string;
  side_mode: string;
  entries: DslExplainEntry[];
  exits: DslExplainExit[];
}

export interface DslGenerateResponse {
  dsl: Record<string, unknown>;
  explain: DslExplain;
  raw_text: string;
  model: string;
  provider: string;
  usage: Record<string, unknown> | null;
}

export interface SaveDslRequest {
  dsl: Record<string, unknown>;
  slug?: string;
  description?: string;
  llm_prompt?: string;
  llm_model?: string;
  is_default?: boolean;
}

export interface DslCapabilities {
  indicators: {
    bar_fields: string[];
    period_indicators: string[];
    bollinger: string[];
    macd: string[];
  };
  comparison_ops: string[];
  cross_ops: string[];
  bool_ops: string[];
  max_nodes: number;
  max_period: number;
}

export interface AppSettings {
  broker_mode: string;
  max_trades_per_day: number;
  max_trades_per_symbol_per_day: number;
  initial_capital: number;
  fast_ma: number;
  slow_ma: number;
  daily_run_cron: string;
}
