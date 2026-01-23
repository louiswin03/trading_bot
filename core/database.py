"""
Database management for trade history and analytics
"""
import sqlite3
from datetime import datetime
from typing import Dict, List, Optional
from pathlib import Path
import json
import config.settings as settings


class TradingDatabase:
    """SQLite database for storing trade history and analytics"""

    def __init__(self, db_path: Path = None):
        self.db_path = db_path or settings.DB_PATH
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_database()

    def _init_database(self):
        """Initialize database tables"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        # Trades table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS trades (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TIMESTAMP NOT NULL,
                pair TEXT NOT NULL,
                side TEXT NOT NULL,
                strategy TEXT NOT NULL,
                entry_price REAL NOT NULL,
                exit_price REAL,
                quantity REAL NOT NULL,
                entry_timestamp TIMESTAMP NOT NULL,
                exit_timestamp TIMESTAMP,
                pnl REAL,
                pnl_percentage REAL,
                status TEXT NOT NULL,
                exit_reason TEXT,
                technical_score REAL,
                sentiment_score REAL,
                onchain_score REAL,
                volume_score REAL,
                composite_score REAL,
                tp_level REAL,
                sl_level REAL,
                max_drawdown REAL,
                max_profit REAL,
                notes TEXT
            )
        ''')

        # Signals table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS signals (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TIMESTAMP NOT NULL,
                pair TEXT NOT NULL,
                signal TEXT NOT NULL,
                strength TEXT NOT NULL,
                strategy TEXT NOT NULL,
                price REAL NOT NULL,
                composite_score REAL,
                technical_score REAL,
                sentiment_score REAL,
                onchain_score REAL,
                volume_score REAL,
                acted_upon BOOLEAN DEFAULT 0,
                trade_id INTEGER,
                factors_json TEXT,
                FOREIGN KEY (trade_id) REFERENCES trades(id)
            )
        ''')

        # Performance metrics table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS performance_metrics (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TIMESTAMP NOT NULL,
                strategy TEXT NOT NULL,
                pair TEXT NOT NULL,
                period TEXT NOT NULL,
                total_trades INTEGER,
                winning_trades INTEGER,
                losing_trades INTEGER,
                winrate REAL,
                total_pnl REAL,
                avg_pnl REAL,
                avg_win REAL,
                avg_loss REAL,
                max_drawdown REAL,
                sharpe_ratio REAL,
                profit_factor REAL
            )
        ''')

        # Market data cache
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS market_data_cache (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TIMESTAMP NOT NULL,
                source TEXT NOT NULL,
                data_type TEXT NOT NULL,
                asset TEXT NOT NULL,
                data_json TEXT NOT NULL,
                expires_at TIMESTAMP
            )
        ''')

        conn.commit()
        conn.close()

    def add_trade(self, trade_data: Dict) -> int:
        """
        Add a new trade to the database

        Args:
            trade_data: Dictionary containing trade information

        Returns:
            int: Trade ID
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute('''
            INSERT INTO trades (
                timestamp, pair, side, strategy, entry_price, exit_price,
                quantity, entry_timestamp, exit_timestamp, pnl, pnl_percentage,
                status, exit_reason, technical_score, sentiment_score,
                onchain_score, volume_score, composite_score, tp_level,
                sl_level, max_drawdown, max_profit, notes
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            trade_data.get('timestamp', datetime.now()),
            trade_data['pair'],
            trade_data['side'],
            trade_data['strategy'],
            trade_data['entry_price'],
            trade_data.get('exit_price'),
            trade_data.get('quantity', 0),
            trade_data['entry_timestamp'],
            trade_data.get('exit_timestamp'),
            trade_data.get('pnl'),
            trade_data.get('pnl_percentage'),
            trade_data.get('status', 'OPEN'),
            trade_data.get('exit_reason'),
            trade_data.get('technical_score'),
            trade_data.get('sentiment_score'),
            trade_data.get('onchain_score'),
            trade_data.get('volume_score'),
            trade_data.get('composite_score'),
            trade_data.get('tp_level'),
            trade_data.get('sl_level'),
            trade_data.get('max_drawdown'),
            trade_data.get('max_profit'),
            trade_data.get('notes')
        ))

        trade_id = cursor.lastrowid
        conn.commit()
        conn.close()

        return trade_id

    def update_trade(self, trade_id: int, update_data: Dict):
        """Update an existing trade"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        # Build dynamic UPDATE query
        fields = []
        values = []
        for key, value in update_data.items():
            fields.append(f"{key} = ?")
            values.append(value)

        values.append(trade_id)
        query = f"UPDATE trades SET {', '.join(fields)} WHERE id = ?"

        cursor.execute(query, values)
        conn.commit()
        conn.close()

    def add_signal(self, signal_data: Dict) -> int:
        """Add a trading signal to the database"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        # Convert factors to JSON-serializable format
        factors = signal_data.get('factors', {})
        def make_serializable(obj):
            """Convert datetime and other non-serializable objects"""
            if isinstance(obj, datetime):
                return obj.isoformat()
            elif isinstance(obj, dict):
                return {k: make_serializable(v) for k, v in obj.items()}
            elif isinstance(obj, list):
                return [make_serializable(item) for item in obj]
            return obj

        factors_clean = make_serializable(factors)

        cursor.execute('''
            INSERT INTO signals (
                timestamp, pair, signal, strength, strategy, price,
                composite_score, technical_score, sentiment_score,
                onchain_score, volume_score, factors_json
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            signal_data.get('timestamp', datetime.now()),
            signal_data['pair'],
            signal_data['signal'],
            signal_data['strength'],
            signal_data['strategy'],
            signal_data['price'],
            signal_data.get('composite_score'),
            signal_data.get('technical_score'),
            signal_data.get('sentiment_score'),
            signal_data.get('onchain_score'),
            signal_data.get('volume_score'),
            json.dumps(factors_clean)
        ))

        signal_id = cursor.lastrowid
        conn.commit()
        conn.close()

        return signal_id

    def get_trades(self, filters: Dict = None, limit: int = None) -> List[Dict]:
        """
        Get trades with optional filters

        Args:
            filters: Dictionary of filters (pair, strategy, status, etc.)
            limit: Maximum number of trades to return

        Returns:
            List of trade dictionaries
        """
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        query = "SELECT * FROM trades"
        where_clauses = []
        values = []

        if filters:
            for key, value in filters.items():
                where_clauses.append(f"{key} = ?")
                values.append(value)

        if where_clauses:
            query += " WHERE " + " AND ".join(where_clauses)

        query += " ORDER BY timestamp DESC"

        if limit:
            query += f" LIMIT {limit}"

        cursor.execute(query, values)
        rows = cursor.fetchall()

        trades = [dict(row) for row in rows]
        conn.close()

        return trades

    def get_performance_stats(self, strategy: str = None, pair: str = None,
                             days: int = None) -> Dict:
        """
        Calculate performance statistics

        Returns:
            dict: Performance metrics
        """
        filters = {'status': 'CLOSED'}
        if strategy:
            filters['strategy'] = strategy
        if pair:
            filters['pair'] = pair

        trades = self.get_trades(filters)

        if not trades:
            return {
                'total_trades': 0,
                'winning_trades': 0,
                'losing_trades': 0,
                'winrate': 0,
                'total_pnl': 0,
                'avg_pnl': 0
            }

        # Filter by date if needed
        if days:
            cutoff = datetime.now().timestamp() - (days * 86400)
            trades = [t for t in trades if t['timestamp'].timestamp() > cutoff]

        total_trades = len(trades)
        wins = [t for t in trades if t['pnl_percentage'] and t['pnl_percentage'] > 0]
        losses = [t for t in trades if t['pnl_percentage'] and t['pnl_percentage'] <= 0]

        winning_trades = len(wins)
        losing_trades = len(losses)
        winrate = (winning_trades / total_trades * 100) if total_trades > 0 else 0

        total_pnl = sum(t['pnl_percentage'] or 0 for t in trades)
        avg_pnl = total_pnl / total_trades if total_trades > 0 else 0
        avg_win = sum(t['pnl_percentage'] for t in wins) / winning_trades if winning_trades > 0 else 0
        avg_loss = sum(t['pnl_percentage'] for t in losses) / losing_trades if losing_trades > 0 else 0

        # Calculate profit factor
        total_win_amount = sum(t['pnl_percentage'] for t in wins)
        total_loss_amount = abs(sum(t['pnl_percentage'] for t in losses))
        profit_factor = total_win_amount / total_loss_amount if total_loss_amount > 0 else 0

        return {
            'total_trades': total_trades,
            'winning_trades': winning_trades,
            'losing_trades': losing_trades,
            'winrate': winrate,
            'total_pnl': total_pnl,
            'avg_pnl': avg_pnl,
            'avg_win': avg_win,
            'avg_loss': avg_loss,
            'profit_factor': profit_factor,
            'best_trade': max(trades, key=lambda x: x['pnl_percentage'] or 0) if trades else None,
            'worst_trade': min(trades, key=lambda x: x['pnl_percentage'] or 0) if trades else None
        }

    def cache_market_data(self, source: str, data_type: str, asset: str,
                         data: Dict, expires_in: int = 300):
        """Cache external market data to reduce API calls"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        expires_at = datetime.fromtimestamp(datetime.now().timestamp() + expires_in)

        cursor.execute('''
            INSERT INTO market_data_cache (
                timestamp, source, data_type, asset, data_json, expires_at
            ) VALUES (?, ?, ?, ?, ?, ?)
        ''', (
            datetime.now(),
            source,
            data_type,
            asset,
            json.dumps(data),
            expires_at
        ))

        conn.commit()
        conn.close()

    def get_cached_data(self, source: str, data_type: str, asset: str) -> Optional[Dict]:
        """Retrieve cached market data if not expired"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        cursor.execute('''
            SELECT * FROM market_data_cache
            WHERE source = ? AND data_type = ? AND asset = ?
            AND expires_at > ?
            ORDER BY timestamp DESC
            LIMIT 1
        ''', (source, data_type, asset, datetime.now()))

        row = cursor.fetchone()
        conn.close()

        if row:
            return json.loads(row['data_json'])
        return None


if __name__ == "__main__":
    # Test database
    db = TradingDatabase()

    # Add a test trade
    trade_id = db.add_trade({
        'pair': 'BTCUSDT',
        'side': 'BUY',
        'strategy': 'bollinger+div',
        'entry_price': 50000,
        'quantity': 0.01,
        'entry_timestamp': datetime.now(),
        'status': 'OPEN',
        'composite_score': 0.75
    })

    print(f"✅ Added trade with ID: {trade_id}")

    # Get performance stats
    stats = db.get_performance_stats()
    print(f"\n📊 Performance Stats:")
    print(f"Total Trades: {stats['total_trades']}")
    print(f"Winrate: {stats['winrate']:.2f}%")
