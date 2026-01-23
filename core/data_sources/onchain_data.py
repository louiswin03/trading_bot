"""
On-chain data from Glassnode and free alternatives
"""
import requests
from datetime import datetime, timedelta
from typing import Dict, Optional, List
from retry import retry
import config.settings as settings


class GlassnodeMetrics:
    """
    Fetch on-chain metrics from Glassnode
    Requires API key (free tier available)
    """

    API_URL = "https://api.glassnode.com/v1/metrics"

    def __init__(self, api_key: str = None):
        self.api_key = api_key or settings.GLASSNODE_API_KEY

    @retry(tries=3, delay=2)
    def _fetch_metric(self, endpoint: str, asset: str = "BTC", interval: str = "24h") -> Optional[List]:
        """Generic method to fetch Glassnode metrics"""
        if not self.api_key:
            return None

        params = {
            'a': asset,
            'i': interval,
            'api_key': self.api_key
        }

        try:
            url = f"{self.API_URL}/{endpoint}"
            response = requests.get(url, params=params, timeout=10)
            response.raise_for_status()
            return response.json()

        except Exception as e:
            print(f"Error fetching Glassnode metric {endpoint}: {e}")
            return None

    def get_exchange_flows(self, asset: str = "BTC") -> Optional[Dict]:
        """
        Get exchange inflow/outflow data

        Interpretation:
        - High inflow: Potential selling pressure (bearish)
        - High outflow: Accumulation (bullish)
        """
        inflow = self._fetch_metric("transactions/transfers_volume_exchanges_in", asset)
        outflow = self._fetch_metric("transactions/transfers_volume_exchanges_out", asset)

        if not inflow or not outflow:
            return None

        latest_inflow = inflow[-1]['v'] if inflow else 0
        latest_outflow = outflow[-1]['v'] if outflow else 0

        net_flow = latest_outflow - latest_inflow

        return {
            'inflow': latest_inflow,
            'outflow': latest_outflow,
            'net_flow': net_flow,
            'signal': 'BULLISH' if net_flow > 0 else 'BEARISH',
            'score': self._normalize_exchange_flow(net_flow),
            'timestamp': datetime.fromtimestamp(inflow[-1]['t']) if inflow else datetime.now()
        }

    def get_whale_activity(self, asset: str = "BTC") -> Optional[Dict]:
        """
        Get large transaction volume (whale activity)

        High whale activity can indicate:
        - Distribution (whales selling) = bearish
        - Accumulation (whales buying) = bullish
        """
        data = self._fetch_metric("transactions/transfers_volume_sum_more_100k_usd", asset)

        if not data:
            return None

        recent = data[-7:]  # Last 7 data points
        avg_volume = sum(d['v'] for d in recent) / len(recent)
        latest_volume = data[-1]['v']

        return {
            'current_volume': latest_volume,
            'avg_volume': avg_volume,
            'activity_level': 'HIGH' if latest_volume > avg_volume * 1.2 else 'NORMAL',
            'timestamp': datetime.fromtimestamp(data[-1]['t'])
        }

    def get_mvrv_ratio(self, asset: str = "BTC") -> Optional[Dict]:
        """
        Get MVRV (Market Value to Realized Value) Ratio

        Interpretation:
        - MVRV > 3.7: Overvalued, potential top (bearish)
        - MVRV < 1.0: Undervalued, potential bottom (bullish)
        - MVRV 1.0-3.7: Normal range
        """
        data = self._fetch_metric("indicators/mvrv", asset)

        if not data:
            return None

        mvrv = data[-1]['v']

        signal = 'NEUTRAL'
        score = 0.5

        if mvrv < 1.0:
            signal = 'STRONG_BUY'
            score = 0.9
        elif mvrv < 1.5:
            signal = 'BUY'
            score = 0.7
        elif mvrv > 3.7:
            signal = 'STRONG_SELL'
            score = 0.1
        elif mvrv > 3.0:
            signal = 'SELL'
            score = 0.3

        return {
            'mvrv': mvrv,
            'signal': signal,
            'score': score,
            'timestamp': datetime.fromtimestamp(data[-1]['t'])
        }

    def get_supply_distribution(self, asset: str = "BTC") -> Optional[Dict]:
        """
        Get supply held by different cohorts

        Accumulation by long-term holders = bullish
        """
        data = self._fetch_metric("distribution/balance_1pct_holders", asset)

        if not data:
            return None

        current = data[-1]['v']
        month_ago = data[-30]['v'] if len(data) > 30 else current

        trend = 'ACCUMULATING' if current > month_ago else 'DISTRIBUTING'

        return {
            'top_1pct_supply': current,
            'trend': trend,
            'signal': 'BULLISH' if trend == 'ACCUMULATING' else 'BEARISH',
            'timestamp': datetime.fromtimestamp(data[-1]['t'])
        }

    def _normalize_exchange_flow(self, net_flow: float) -> float:
        """Normalize exchange flow to 0-1 score"""
        # Simplified normalization
        # Positive flow (outflow > inflow) = bullish = high score
        if net_flow > 0:
            return min(0.5 + (net_flow / 100000), 1.0)
        else:
            return max(0.5 + (net_flow / 100000), 0.0)


class OnChainAnalyzer:
    """
    Aggregate on-chain metrics from multiple sources
    Includes free alternatives when Glassnode is not available
    """

    def __init__(self):
        self.glassnode = GlassnodeMetrics()

    def get_onchain_score(self, asset: str = "BTC") -> Dict:
        """
        Get overall on-chain health score

        Returns:
            dict: {
                'score': float (0-1),
                'signal': str,
                'metrics': dict
            }
        """
        result = {
            'score': 0.5,  # Neutral default
            'signal': 'NEUTRAL',
            'metrics': {}
        }

        scores = []

        # Exchange flows
        flows = self.glassnode.get_exchange_flows(asset)
        if flows:
            result['metrics']['exchange_flows'] = flows
            scores.append(flows['score'])

        # MVRV Ratio
        mvrv = self.glassnode.get_mvrv_ratio(asset)
        if mvrv:
            result['metrics']['mvrv'] = mvrv
            scores.append(mvrv['score'])

        # Supply distribution
        distribution = self.glassnode.get_supply_distribution(asset)
        if distribution:
            result['metrics']['supply_distribution'] = distribution
            dist_score = 0.7 if distribution['signal'] == 'BULLISH' else 0.3
            scores.append(dist_score)

        # Calculate average score
        if scores:
            result['score'] = sum(scores) / len(scores)

            # Determine signal
            if result['score'] > 0.7:
                result['signal'] = 'BULLISH'
            elif result['score'] < 0.3:
                result['signal'] = 'BEARISH'

        return result


class FreeOnChainData:
    """
    Free on-chain data alternatives (no API key required)
    Uses blockchain.com and other free APIs
    """

    @retry(tries=3, delay=2)
    def get_btc_hash_rate(self) -> Optional[Dict]:
        """Get Bitcoin hash rate (indicator of network health)"""
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

    @retry(tries=3, delay=2)
    def get_btc_difficulty(self) -> Optional[Dict]:
        """Get Bitcoin mining difficulty"""
        try:
            url = "https://blockchain.info/q/getdifficulty"
            response = requests.get(url, timeout=10)
            response.raise_for_status()

            difficulty = float(response.text)

            return {
                'difficulty': difficulty,
                'timestamp': datetime.now()
            }

        except Exception as e:
            print(f"Error fetching difficulty: {e}")
            return None

    @retry(tries=3, delay=2)
    def get_mempool_size(self) -> Optional[Dict]:
        """Get mempool size (pending transactions)"""
        try:
            url = "https://blockchain.info/q/getmempoolsize"
            response = requests.get(url, timeout=10)
            response.raise_for_status()

            mempool_size = int(response.text)

            # High mempool = network congestion = potential bearish
            signal = 'BEARISH' if mempool_size > 100000 else 'NEUTRAL'

            return {
                'mempool_size': mempool_size,
                'signal': signal,
                'timestamp': datetime.now()
            }

        except Exception as e:
            print(f"Error fetching mempool size: {e}")
            return None


if __name__ == "__main__":
    # Test free data sources
    free_data = FreeOnChainData()

    print("\n⛓️  Free On-Chain Data:")

    hash_rate = free_data.get_btc_hash_rate()
    if hash_rate:
        print(f"Hash Rate: {hash_rate['hash_rate']:.2e} H/s")

    mempool = free_data.get_mempool_size()
    if mempool:
        print(f"Mempool Size: {mempool['mempool_size']} transactions")
        print(f"Signal: {mempool['signal']}")
