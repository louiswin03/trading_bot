"""
Bitquery API integration for on-chain data
Free alternative to Glassnode
"""
import requests
from datetime import datetime, timedelta
from typing import Dict, Optional, List
from retry import retry
import config.settings as settings


class BitqueryOnChain:
    """
    Fetch on-chain data using Bitquery GraphQL API
    Documentation: https://docs.bitquery.io/
    """

    API_URL = "https://graphql.bitquery.io"

    def __init__(self, api_key: str = None):
        self.api_key = api_key or settings.BITQUERY_API_KEY
        self.headers = {
            "Content-Type": "application/json",
            "X-API-KEY": self.api_key
        } if self.api_key else {"Content-Type": "application/json"}

    @retry(tries=3, delay=2)
    def _query(self, query: str) -> Optional[Dict]:
        """Execute GraphQL query"""
        try:
            response = requests.post(
                self.API_URL,
                json={"query": query},
                headers=self.headers,
                timeout=15
            )
            response.raise_for_status()
            return response.json()
        except Exception as e:
            print(f"Bitquery query error: {e}")
            return None

    def get_btc_network_activity(self) -> Optional[Dict]:
        """
        Get Bitcoin network activity (transactions, active addresses)
        High activity can indicate market interest
        """
        query = """
        {
          bitcoin {
            transactions(options: {desc: "date.date", limit: 7}) {
              date: date {
                date
              }
              count
              amount: amount(in: BTC)
            }
          }
        }
        """

        result = self._query(query)
        if not result or 'data' not in result:
            return None

        try:
            txs = result['data']['bitcoin']['transactions']

            # Calculate metrics
            recent_tx_count = sum(tx['count'] for tx in txs[:3])  # Last 3 days
            older_tx_count = sum(tx['count'] for tx in txs[3:])   # Previous days

            trend = "INCREASING" if recent_tx_count > older_tx_count else "DECREASING"
            avg_daily_txs = sum(tx['count'] for tx in txs) / len(txs)

            # Score: high activity = bullish
            activity_ratio = recent_tx_count / older_tx_count if older_tx_count > 0 else 1
            score = min(0.5 + (activity_ratio - 1) * 0.5, 1.0) if activity_ratio > 1 else max(0.5 - (1 - activity_ratio) * 0.5, 0)

            return {
                'avg_daily_transactions': avg_daily_txs,
                'recent_vs_older': activity_ratio,
                'trend': trend,
                'score': score,
                'signal': 'BULLISH' if trend == 'INCREASING' else 'BEARISH',
                'timestamp': datetime.now()
            }
        except Exception as e:
            print(f"Error parsing network activity: {e}")
            return None

    def get_exchange_inflows(self, currency: str = "BTC") -> Optional[Dict]:
        """
        Get exchange inflows/outflows
        Inflow = Potential selling pressure (bearish)
        Outflow = Accumulation (bullish)
        """
        # Note: Bitquery peut avoir des limites sur les données d'exchange
        # Cette requête est un exemple simplifié
        query = f"""
        {{
          bitcoin {{
            inbound: transfers(
              options: {{limit: 100, desc: "block.timestamp.time"}}
              receiver: {{is: "exchange"}}
            ) {{
              block {{
                timestamp {{
                  time(format: "%Y-%m-%d")
                }}
              }}
              amount(in: BTC)
            }}
          }}
        }}
        """

        result = self._query(query)
        if not result or 'data' not in result:
            return None

        try:
            inflows = result['data']['bitcoin'].get('inbound', [])
            total_inflow = sum(float(tx['amount']) for tx in inflows[:50])  # Last 50 txs

            # Simplified scoring
            # High inflow = bearish, Low inflow = bullish
            score = 0.3 if total_inflow > 1000 else 0.7

            return {
                'total_inflow_btc': total_inflow,
                'score': score,
                'signal': 'BEARISH' if total_inflow > 1000 else 'BULLISH',
                'timestamp': datetime.now()
            }
        except Exception as e:
            print(f"Error parsing exchange inflows: {e}")
            return None

    def get_large_transactions(self, min_amount: float = 100) -> Optional[Dict]:
        """
        Get large BTC transactions (whale activity)
        High whale activity can signal market movement
        """
        query = f"""
        {{
          bitcoin {{
            transfers(
              options: {{desc: "block.timestamp.time", limit: 50}}
              amount: {{gt: {min_amount}}}
            ) {{
              block {{
                timestamp {{
                  time(format: "%Y-%m-%d %H:%M:%S")
                }}
              }}
              amount(in: BTC)
              sender {{
                address
              }}
              receiver {{
                address
              }}
            }}
          }}
        }}
        """

        result = self._query(query)
        if not result or 'data' not in result:
            return None

        try:
            transfers = result['data']['bitcoin']['transfers']

            total_whale_volume = sum(float(tx['amount']) for tx in transfers)
            whale_count = len(transfers)
            avg_whale_size = total_whale_volume / whale_count if whale_count > 0 else 0

            return {
                'whale_transactions': whale_count,
                'total_volume_btc': total_whale_volume,
                'avg_transaction_btc': avg_whale_size,
                'activity_level': 'HIGH' if whale_count > 30 else 'NORMAL',
                'timestamp': datetime.now()
            }
        except Exception as e:
            print(f"Error parsing large transactions: {e}")
            return None

    def get_onchain_score(self, asset: str = "BTC") -> Dict:
        """
        Get overall on-chain health score combining multiple metrics
        """
        result = {
            'score': 0.5,
            'signal': 'NEUTRAL',
            'metrics': {}
        }

        scores = []

        # Network activity
        network = self.get_btc_network_activity()
        if network:
            result['metrics']['network_activity'] = network
            scores.append(network['score'])

        # Exchange flows
        flows = self.get_exchange_inflows(asset)
        if flows:
            result['metrics']['exchange_flows'] = flows
            scores.append(flows['score'])

        # Whale activity (informational, no scoring)
        whales = self.get_large_transactions()
        if whales:
            result['metrics']['whale_activity'] = whales

        # Calculate average score
        if scores:
            result['score'] = sum(scores) / len(scores)

            if result['score'] > 0.65:
                result['signal'] = 'BULLISH'
            elif result['score'] < 0.35:
                result['signal'] = 'BEARISH'

        return result


class FreeOnChainFallback:
    """
    Fallback to free APIs when Bitquery is not available
    """

    @retry(tries=3, delay=2)
    def get_btc_mempool(self) -> Optional[Dict]:
        """Get mempool size from blockchain.com"""
        try:
            url = "https://blockchain.info/q/getmempoolsize"
            response = requests.get(url, timeout=10)
            response.raise_for_status()

            mempool_size = int(response.text)

            # High mempool = congestion = bearish
            signal = 'BEARISH' if mempool_size > 100000 else 'NEUTRAL'
            score = 0.3 if mempool_size > 100000 else 0.5

            return {
                'mempool_size': mempool_size,
                'signal': signal,
                'score': score,
                'timestamp': datetime.now()
            }
        except Exception as e:
            print(f"Error fetching mempool: {e}")
            return None

    @retry(tries=3, delay=2)
    def get_btc_hashrate(self) -> Optional[Dict]:
        """Get Bitcoin hash rate"""
        try:
            url = "https://blockchain.info/q/hashrate"
            response = requests.get(url, timeout=10)
            response.raise_for_status()

            hash_rate = float(response.text)

            return {
                'hash_rate': hash_rate,
                'timestamp': datetime.now()
            }
        except Exception as e:
            print(f"Error fetching hash rate: {e}")
            return None


# Combined on-chain data source
class OnChainDataSource:
    """
    Smart on-chain data source that uses Bitquery if available,
    falls back to free sources otherwise
    """

    def __init__(self):
        self.bitquery = BitqueryOnChain()
        self.fallback = FreeOnChainFallback()

    def get_score(self, asset: str = "BTC") -> Dict:
        """Get on-chain score from best available source"""

        # Try Bitquery first
        if settings.BITQUERY_API_KEY:
            bitquery_data = self.bitquery.get_onchain_score(asset)
            if bitquery_data and bitquery_data['metrics']:
                return bitquery_data

        # Fallback to free sources
        result = {
            'score': 0.5,
            'signal': 'NEUTRAL',
            'metrics': {}
        }

        mempool = self.fallback.get_btc_mempool()
        if mempool:
            result['metrics']['mempool'] = mempool
            result['score'] = mempool['score']
            result['signal'] = mempool['signal']

        return result


if __name__ == "__main__":
    # Test
    print("\n⛓️  Testing Bitquery On-Chain Data...\n")

    source = OnChainDataSource()
    data = source.get_score("BTC")

    print(f"Overall Score: {data['score']:.2%}")
    print(f"Signal: {data['signal']}")
    print(f"\nMetrics:")
    for key, value in data['metrics'].items():
        print(f"  {key}: {value}")
