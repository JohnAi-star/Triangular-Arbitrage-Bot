// Backend API integration for Python bot
export interface BotConfig {
  minProfitPercentage: number;
  maxTradeAmount: number;
  autoTradingMode: boolean;
  paperTrading: boolean;
  selectedExchanges: string[];
}

export interface ArbitrageOpportunity {
  id: string;
  exchange: string;
  trianglePath: string;
  profitPercentage: number;
  profitAmount: number;
  volume: number;
  status: 'detected' | 'executing' | 'completed' | 'failed';
  timestamp: string;
  steps: TradeStep[];
  tradeable?: boolean;
  real_balance_based?: boolean;
  balanceRequired?: number;
  ui_display_only?: boolean;
  real_market_data?: boolean;
}

export interface DetailedTradeLog {
  trade_id: string;
  timestamp: string;
  exchange: string;
  triangle_path: string[];
  status: 'success' | 'failed' | 'partial';
  status_emoji: string;
  initial_amount: number;
  final_amount: number;
  base_currency: string;
  expected_profit_amount: number;
  expected_profit_percentage: number;
  actual_profit_amount: number;
  actual_profit_percentage: number;
  total_fees_paid: number;
  total_slippage: number;
  net_pnl: number;
  total_duration_ms: number;
  steps: TradeStepDetail[];
  error_message?: string;
  failed_at_step?: number;
}

export interface TradeStepDetail {
  step_number: number;
  symbol: string;
  direction: 'buy' | 'sell';
  expected_price: number;
  actual_price: number;
  expected_quantity: number;
  actual_quantity: number;
  expected_amount_out: number;
  actual_amount_out: number;
  fees_paid: number;
  execution_time_ms: number;
  slippage_percentage: number;
}

export interface TradeStatistics {
  total_trades: number;
  successful_trades: number;
  failed_trades: number;
  success_rate: number;
  total_profit: number;
  total_fees: number;
  average_duration_ms: number;
  best_trade: DetailedTradeLog | null;
  worst_trade: DetailedTradeLog | null;
}

export interface TradeStep {
  symbol: string;
  side: 'buy' | 'sell';
  quantity: number;
  price: number;
  expectedAmount: number;
}

export interface BotStats {
  opportunitiesFound: number;
  tradesExecuted: number;
  totalProfit: number;
  successRate: number;
  activeExchanges: number;
}

class BackendAPI {
  private baseUrl = 'http://localhost:8000'; // Python FastAPI backend
  private ws: WebSocket | null = null;

  async startBot(config: BotConfig): Promise<boolean> {
    try {
      const response = await fetch(`${this.baseUrl}/api/bot/start`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(config)
      });
      return response.ok;
    } catch (error) {
      console.error('Failed to start bot:', error);
      return false;
    }
  }

  async stopBot(): Promise<boolean> {
    try {
      const response = await fetch(`${this.baseUrl}/api/bot/stop`, {
        method: 'POST'
      });
      return response.ok;
    } catch (error) {
      console.error('Failed to stop bot:', error);
      return false;
    }
  }

  async getOpportunities(): Promise<ArbitrageOpportunity[]> {
    try {
      const response = await fetch(`${this.baseUrl}/api/opportunities`);
      if (response.ok) {
        return await response.json();
      }
      return [];
    } catch (error) {
      console.error('Failed to fetch opportunities:', error);
      return [];
    }
  }

  async getTrades(): Promise<DetailedTradeLog[]> {
    try {
      const response = await fetch(`${this.baseUrl}/api/trades`);
      if (response.ok) {
        return await response.json();
      }
      return [];
    } catch (error) {
      console.error('Failed to fetch trades:', error);
      return [];
    }
  }

  async getTradeStats(): Promise<TradeStatistics | null> {
    try {
      const response = await fetch(`${this.baseUrl}/api/trade-stats`);
      if (response.ok) {
        return await response.json();
      }
      return null;
    } catch (error) {
      console.error('Failed to fetch trade stats:', error);
      return null;
    }
  }

  async executeOpportunity(opportunityId: string): Promise<boolean> {
    try {
      const response = await fetch(`${this.baseUrl}/api/opportunities/${opportunityId}/execute`, {
        method: 'POST'
      });
      return response.ok;
    } catch (error) {
      console.error('Failed to execute opportunity:', error);
      return false;
    }
  }

  async toggleAutoTrading(autoTrading: boolean): Promise<boolean> {
    try {
      const response = await fetch(`${this.baseUrl}/api/bot/toggle-auto-trading`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ autoTrading })
      });
      return response.ok;
    } catch (error) {
      console.error('Failed to toggle auto-trading:', error);
      return false;
    }
  }
  async getStats(): Promise<BotStats | null> {
    try {
      const response = await fetch(`${this.baseUrl}/api/stats`);
      if (response.ok) {
        return await response.json();
      }
      return null;
    } catch (error) {
      console.error('Failed to fetch stats:', error);
      return null;
    }
  }

  connectWebSocket(onMessage: (data: any) => void): void {
    try {
      console.log('Connecting to WebSocket...');
      this.ws = new WebSocket(`ws://localhost:8000/ws`);

      this.ws.onopen = () => {
        console.log('WebSocket connected');
      };

      this.ws.onmessage = (event) => {
        try {
          console.log('Raw WebSocket message:', event.data);
          const data = JSON.parse(event.data);
          console.log('Parsed WebSocket data:', data);
          
          // Handle different message types
          if (data.type === 'opportunities_update') {
            console.log('Received opportunities update:', data.data, 'Length:', Array.isArray(data.data) ? data.data.length : 'Not array');
          } else if (data.type === 'trade_executed') {
            console.log('Received trade execution:', data.data);
          } else if (data.type === 'opportunity_executed') {
            console.log('Received opportunity execution:', data.data);
          } else if (data.type === 'auto_trading_changed') {
            console.log('Auto-trading mode changed:', data.data);
          } else {
            console.log('Unknown message type:', data.type);
          }
          
          onMessage(data);
        } catch (error) {
          console.error('Failed to parse WebSocket message:', error);
          console.error('Raw message was:', event.data);
        }
      };

      this.ws.onclose = () => {
        console.log('WebSocket disconnected');
        // Attempt to reconnect after 5 seconds
        setTimeout(() => this.connectWebSocket(onMessage), 5000);
      };

      this.ws.onerror = (error) => {
        console.error('WebSocket error:', error);
      };
    } catch (error) {
      console.error('Failed to connect WebSocket:', error);
    }
  }

  disconnectWebSocket(): void {
    if (this.ws) {
      this.ws.close();
      this.ws = null;
    }
  }
}

export const backendAPI = new BackendAPI();