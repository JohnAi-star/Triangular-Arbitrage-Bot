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
          onMessage(data);
        } catch (error) {
          console.error('Failed to parse WebSocket message:', error);
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