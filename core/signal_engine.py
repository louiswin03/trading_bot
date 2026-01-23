"""
Multi-factor signal engine
Combines technical, sentiment, and on-chain data
"""
from typing import Dict, Optional
from datetime import datetime
import config.settings as settings
from core.data_sources.fear_greed import FearGreedIndex
from core.data_sources.bitquery_data import OnChainDataSource


class SignalEngine:
    """
    Advanced signal engine that combines multiple data sources

    Factors:
    1. Technical Analysis (40%) - From your existing strategies
    2. Sentiment Analysis (20%) - Fear & Greed + News
    3. On-chain Metrics (25%) - Blockchain data
    4. Volume Analysis (15%) - Volume patterns
    """

    def __init__(self):
        self.fear_greed = FearGreedIndex()
        self.onchain = OnChainDataSource()  # Bitquery + free fallback

        # Weights from config
        self.weights = settings.WEIGHTS

    def calculate_composite_score(self,
                                   technical_signal: str,
                                   technical_confidence: float = 0.7,
                                   pair: str = "BTCUSDT",
                                   current_volume: float = None,
                                   avg_volume: float = None) -> Dict:
        """
        Calculate composite trading score from all factors

        Args:
            technical_signal: Signal from technical strategy ('buy', 'sell', 'neutral')
            technical_confidence: Confidence of technical signal (0-1)
            pair: Trading pair
            current_volume: Current volume
            avg_volume: Average volume

        Returns:
            dict: {
                'final_score': float (0-1),
                'signal': str ('BUY', 'SELL', 'NEUTRAL'),
                'strength': str ('STRONG', 'MODERATE', 'WEAK'),
                'factors': dict,
                'timestamp': datetime
            }
        """
        factors = {}

        # 1. TECHNICAL SCORE (40%)
        technical_score = self._normalize_technical_signal(technical_signal, technical_confidence)
        factors['technical'] = {
            'score': technical_score,
            'signal': technical_signal,
            'confidence': technical_confidence,
            'weight': self.weights['technical']
        }

        # 2. SENTIMENT SCORE (20%)
        sentiment_score = self._get_sentiment_score(pair)
        factors['sentiment'] = {
            'score': sentiment_score['score'],
            'details': sentiment_score,
            'weight': self.weights['sentiment']
        }

        # 3. ON-CHAIN SCORE (25%)
        onchain_score = self._get_onchain_score(pair)
        factors['onchain'] = {
            'score': onchain_score['score'],
            'details': onchain_score,
            'weight': self.weights['onchain']
        }

        # 4. VOLUME SCORE (15%)
        volume_score = self._get_volume_score(current_volume, avg_volume)
        factors['volume'] = {
            'score': volume_score['score'],
            'details': volume_score,
            'weight': self.weights['volume']
        }

        # Calculate weighted final score
        final_score = (
            technical_score * self.weights['technical'] +
            sentiment_score['score'] * self.weights['sentiment'] +
            onchain_score['score'] * self.weights['onchain'] +
            volume_score['score'] * self.weights['volume']
        )

        # Determine signal and strength
        signal, strength = self._determine_signal(final_score, technical_signal)

        return {
            'final_score': final_score,
            'signal': signal,
            'strength': strength,
            'factors': factors,
            'timestamp': datetime.now(),
            'pair': pair
        }

    def _normalize_technical_signal(self, signal: str, confidence: float) -> float:
        """
        Convert technical signal to 0-1 score

        buy/strong_buy -> 0.7-1.0
        neutral -> 0.4-0.6
        sell/strong_sell -> 0.0-0.3
        """
        base_scores = {
            'strong_buy': 0.95,
            'buy': 0.75,
            'neutral': 0.5,
            'sell': 0.25,
            'strong_sell': 0.05
        }

        base = base_scores.get(signal.lower(), 0.5)

        # Adjust by confidence
        if signal.lower() in ['buy', 'strong_buy']:
            return base * confidence
        elif signal.lower() in ['sell', 'strong_sell']:
            return base + (1 - base) * (1 - confidence)
        else:
            return 0.5

    def _get_sentiment_score(self, pair: str) -> Dict:
        """Get sentiment score from Fear & Greed only (free)"""
        result = {
            'score': 0.5,
            'fear_greed': None
        }

        # Fear & Greed Index (100% of sentiment - free!)
        fg_data = self.fear_greed.fetch_current()
        if fg_data:
            result['fear_greed'] = fg_data
            result['score'] = fg_data['score']

        return result

    def _get_onchain_score(self, pair: str) -> Dict:
        """Get on-chain metrics score using Bitquery"""
        asset = pair.replace('USDT', '').replace('USD', '')
        return self.onchain.get_score(asset)

    def _get_volume_score(self, current_volume: Optional[float],
                         avg_volume: Optional[float]) -> Dict:
        """
        Analyze volume patterns

        High volume on price increase = bullish
        High volume on price decrease = bearish
        Low volume = neutral/weak signal
        """
        result = {
            'score': 0.5,
            'ratio': 1.0,
            'interpretation': 'NORMAL'
        }

        if current_volume is None or avg_volume is None or avg_volume == 0:
            return result

        ratio = current_volume / avg_volume
        result['ratio'] = ratio

        if ratio > 1.5:
            result['interpretation'] = 'HIGH_VOLUME'
            result['score'] = 0.7  # High volume confirms signal
        elif ratio > 1.2:
            result['interpretation'] = 'ABOVE_AVERAGE'
            result['score'] = 0.6
        elif ratio < 0.7:
            result['interpretation'] = 'LOW_VOLUME'
            result['score'] = 0.4  # Low volume weakens signal
        else:
            result['interpretation'] = 'NORMAL'
            result['score'] = 0.5

        return result

    def _determine_signal(self, score: float, technical_signal: str) -> tuple:
        """
        Determine final signal and strength

        Returns:
            tuple: (signal, strength)
        """
        # Strong signals
        if score >= settings.STRONG_SIGNAL_THRESHOLD:
            return ('BUY', 'STRONG')
        elif score <= (1 - settings.STRONG_SIGNAL_THRESHOLD):
            return ('SELL', 'STRONG')

        # Moderate signals
        elif score >= settings.SIGNAL_THRESHOLD_BUY:
            return ('BUY', 'MODERATE')
        elif score <= settings.SIGNAL_THRESHOLD_SELL:
            return ('SELL', 'MODERATE')

        # Weak signals (closer to neutral zone)
        elif score >= 0.55:
            return ('BUY', 'WEAK')
        elif score <= 0.45:
            return ('SELL', 'WEAK')

        # Neutral
        else:
            return ('NEUTRAL', 'NEUTRAL')

    def get_detailed_analysis(self, **kwargs) -> str:
        """
        Get human-readable detailed analysis

        Returns:
            str: Formatted analysis report
        """
        result = self.calculate_composite_score(**kwargs)

        report = f"""
==============================================================
           TRADING SIGNAL ANALYSIS REPORT
==============================================================

Pair: {result['pair']}
Timestamp: {result['timestamp'].strftime('%Y-%m-%d %H:%M:%S')}

-- FINAL SIGNAL ----------------------------------------------
  Signal: {result['signal']} ({result['strength']})
  Confidence Score: {result['final_score']:.2%}
--------------------------------------------------------------

-- FACTOR BREAKDOWN ------------------------------------------
|
| [DATA] Technical Analysis (Weight: {result['factors']['technical']['weight']:.0%})
|    Score: {result['factors']['technical']['score']:.2%}
|    Signal: {result['factors']['technical']['signal'].upper()}
|    Confidence: {result['factors']['technical']['confidence']:.2%}
|
| [SENTIMENT] Sentiment Analysis (Weight: {result['factors']['sentiment']['weight']:.0%})
|    Score: {result['factors']['sentiment']['score']:.2%}
"""

        # Add Fear & Greed details
        if result['factors']['sentiment']['details'].get('fear_greed'):
            fg = result['factors']['sentiment']['details']['fear_greed']
            report += f"|    Fear & Greed: {fg['value']}/100 ({fg['classification']})\n"

        # Add News sentiment
        if result['factors']['sentiment']['details'].get('news'):
            news = result['factors']['sentiment']['details']['news']
            report += f"|    News Sentiment: {news['signal']}\n"

        report += f"""|
| [ONCHAIN]️  On-Chain Metrics (Weight: {result['factors']['onchain']['weight']:.0%})
|    Score: {result['factors']['onchain']['score']:.2%}
"""

        # Add on-chain details
        onchain_metrics = result['factors']['onchain']['details'].get('metrics', {})
        for key, value in onchain_metrics.items():
            if isinstance(value, dict) and 'signal' in value:
                report += f"|    {key}: {value['signal']}\n"

        report += f"""|
| [DATA] Volume Analysis (Weight: {result['factors']['volume']['weight']:.0%})
|    Score: {result['factors']['volume']['score']:.2%}
|    Interpretation: {result['factors']['volume']['details']['interpretation']}
|    Ratio: {result['factors']['volume']['details']['ratio']:.2f}x
--------------------------------------------------------------
"""

        return report


if __name__ == "__main__":
    # Test
    engine = SignalEngine()

    result = engine.calculate_composite_score(
        technical_signal='buy',
        technical_confidence=0.8,
        pair='BTCUSDT',
        current_volume=1000000,
        avg_volume=800000
    )

    print(engine.get_detailed_analysis(
        technical_signal='buy',
        technical_confidence=0.8,
        pair='BTCUSDT',
        current_volume=1000000,
        avg_volume=800000
    ))
