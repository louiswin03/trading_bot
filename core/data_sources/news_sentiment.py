"""
News sentiment analysis from CryptoPanic and NewsAPI
"""
import requests
from datetime import datetime, timedelta
from typing import Dict, List, Optional
from retry import retry
import config.settings as settings

try:
    from textblob import TextBlob
    TEXTBLOB_AVAILABLE = True
except ImportError:
    TEXTBLOB_AVAILABLE = False


class CryptoPanicNews:
    """
    Fetch crypto news from CryptoPanic
    Free tier: 20 requests/day without auth
    """

    API_URL = "https://cryptopanic.com/api/v1/posts/"

    def __init__(self, api_key: str = None):
        self.api_key = api_key or settings.CRYPTOPANIC_API_KEY

    @retry(tries=3, delay=2)
    def fetch_news(self, currencies: str = "BTC,ETH", filter_type: str = "hot") -> Optional[List[Dict]]:
        """
        Fetch latest crypto news

        Args:
            currencies: Comma-separated list of currencies (BTC, ETH, etc.)
            filter_type: 'hot', 'rising', 'bullish', 'bearish', 'important', 'saved', 'lol'

        Returns:
            list: List of news articles with sentiment
        """
        params = {
            'currencies': currencies,
            'filter': filter_type,
            'public': 'true'
        }

        if self.api_key:
            params['auth_token'] = self.api_key

        try:
            response = requests.get(self.API_URL, params=params, timeout=10)
            response.raise_for_status()
            data = response.json()

            if 'results' in data:
                articles = []
                for item in data['results'][:20]:  # Limit to 20 most recent
                    article = {
                        'title': item.get('title', ''),
                        'source': item.get('source', {}).get('title', 'Unknown'),
                        'published_at': datetime.fromisoformat(item['published_at'].replace('Z', '+00:00')),
                        'url': item.get('url', ''),
                        'kind': item.get('kind', 'news'),  # news, media, blog
                        'votes': item.get('votes', {})
                    }

                    # Calculate sentiment from votes and title
                    article['sentiment'] = self._calculate_sentiment(article)
                    articles.append(article)

                return articles

        except Exception as e:
            print(f"Error fetching CryptoPanic news: {e}")
            return None

    def _calculate_sentiment(self, article: Dict) -> Dict:
        """
        Calculate sentiment from article data

        Returns:
            dict: {
                'score': float (-1 to 1),
                'label': str ('positive', 'negative', 'neutral'),
                'confidence': float (0 to 1)
            }
        """
        # Use votes if available
        votes = article.get('votes', {})
        positive = votes.get('positive', 0)
        negative = votes.get('negative', 0)
        total = positive + negative

        if total > 0:
            vote_score = (positive - negative) / total
            confidence = min(total / 20, 1.0)  # More votes = higher confidence
        else:
            vote_score = 0
            confidence = 0

        # Use TextBlob for title sentiment if available
        text_score = 0
        if TEXTBLOB_AVAILABLE and article.get('title'):
            try:
                blob = TextBlob(article['title'])
                text_score = blob.sentiment.polarity  # -1 to 1
            except:
                pass

        # Combine scores
        combined_score = (vote_score * 0.7 + text_score * 0.3) if total > 0 else text_score

        # Determine label
        if combined_score > 0.1:
            label = 'positive'
        elif combined_score < -0.1:
            label = 'negative'
        else:
            label = 'neutral'

        return {
            'score': combined_score,
            'label': label,
            'confidence': confidence
        }

    def get_overall_sentiment(self, currencies: str = "BTC") -> Optional[Dict]:
        """
        Get overall market sentiment from recent news

        Returns:
            dict: {
                'score': float (-1 to 1),
                'label': str,
                'positive_count': int,
                'negative_count': int,
                'neutral_count': int
            }
        """
        articles = self.fetch_news(currencies=currencies)
        if not articles:
            return None

        scores = [a['sentiment']['score'] for a in articles]
        labels = [a['sentiment']['label'] for a in articles]

        avg_score = sum(scores) / len(scores) if scores else 0

        return {
            'score': avg_score,
            'normalized_score': (avg_score + 1) / 2,  # 0 to 1 scale
            'label': 'positive' if avg_score > 0.1 else 'negative' if avg_score < -0.1 else 'neutral',
            'positive_count': labels.count('positive'),
            'negative_count': labels.count('negative'),
            'neutral_count': labels.count('neutral'),
            'total_articles': len(articles)
        }


class NewsAnalyzer:
    """Aggregate news sentiment from multiple sources"""

    def __init__(self):
        self.cryptopanic = CryptoPanicNews()

    def get_market_sentiment(self, asset: str = "BTC") -> Dict:
        """
        Get overall market sentiment score

        Returns:
            dict: {
                'score': float (0-1, normalized),
                'signal': str,
                'sources': dict
            }
        """
        result = {
            'score': 0.5,  # Neutral default
            'signal': 'NEUTRAL',
            'sources': {}
        }

        # CryptoPanic sentiment
        cp_sentiment = self.cryptopanic.get_overall_sentiment(currencies=asset)
        if cp_sentiment:
            result['sources']['cryptopanic'] = cp_sentiment
            result['score'] = cp_sentiment['normalized_score']

            # Determine signal
            if cp_sentiment['score'] > 0.2:
                result['signal'] = 'BULLISH'
            elif cp_sentiment['score'] < -0.2:
                result['signal'] = 'BEARISH'

        return result


if __name__ == "__main__":
    # Test
    analyzer = NewsAnalyzer()
    sentiment = analyzer.get_market_sentiment("BTC")

    print(f"\n📰 Market Sentiment Analysis:")
    print(f"Overall Score: {sentiment['score']:.2f}")
    print(f"Signal: {sentiment['signal']}")

    if 'cryptopanic' in sentiment['sources']:
        cp = sentiment['sources']['cryptopanic']
        print(f"\nCryptoPanic:")
        print(f"  Positive: {cp['positive_count']}")
        print(f"  Negative: {cp['negative_count']}")
        print(f"  Neutral: {cp['neutral_count']}")
