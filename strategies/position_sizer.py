"""
ATR-based Position Sizing

Implements volatility-driven position management.
"""

import pandas as pd
import numpy as np
from typing import Dict, Optional


class ATRPositionSizer:
    """
    ATR volatility-driven position management

    Core formula:
    position_size = (account_capital × risk_per_trade) / (ATR × k)

    Higher volatility (ATR) → smaller position
    Lower volatility (ATR) → larger position
    """

    def __init__(self,
                 initial_capital: float = 2000,
                 risk_per_trade: float = 0.01,
                 atr_multiplier: float = 2.0):
        """
        Initialize position sizer

        Args:
            initial_capital: Starting capital (default ¥2,000)
            risk_per_trade: Risk percentage per trade (default 1%)
            atr_multiplier: ATR multiplier for stop distance (default 2.0)
        """
        self.initial_capital = initial_capital
        self.risk_per_trade = risk_per_trade
        self.atr_multiplier = atr_multiplier

    def calculate_position_size(self,
                                cash: float,
                                price: float,
                                atr: float) -> int:
        """
        Calculate position size based on ATR

        Args:
            cash: Available cash
            price: Current price
            atr: ATR value

        Returns:
            int: Number of shares to buy
        """
        # Calculate risk amount
        risk_amount = self.initial_capital * self.risk_per_trade

        # Calculate stop distance
        stop_distance = atr * self.atr_multiplier

        # Calculate target position value
        if stop_distance > 0 and price > 0:
            # Position value = risk_amount / (stop_distance %)
            stop_distance_pct = stop_distance / price
            if stop_distance_pct > 0:
                target_position_value = risk_amount / stop_distance_pct
            else:
                target_position_value = cash
        else:
            target_position_value = cash

        # Ensure we don't exceed available cash
        position_value = min(target_position_value, cash)

        # Calculate shares
        if price > 0:
            shares = int(position_value / price)
        else:
            shares = 0

        return shares

    def calculate_position_ratio(self, df: pd.DataFrame, idx: int) -> float:
        """
        Calculate position ratio based on ATR (0-1)

        Uses sigmoid to normalize ATR percentage to position ratio.

        Args:
            df: DataFrame with ATR data
            idx: Index to calculate ratio for

        Returns:
            float: Position ratio between 0 and 1
        """
        atr = df.loc[idx, 'atr']
        price = df.loc[idx, 'close']

        if price == 0:
            return 0.5

        # ATR as percentage of price
        atr_pct = atr / price

        # Use sigmoid to normalize to 0-1
        # Higher ATR → lower ratio (smaller position)
        vol_adjustment = 1 / (1 + np.exp(5 * (atr_pct - 0.02)))

        return vol_adjustment

    def calculate_position_ratio_series(self, df: pd.DataFrame) -> pd.Series:
        """
        Calculate position ratio for entire DataFrame

        Args:
            df: DataFrame with 'atr' and 'close' columns

        Returns:
            Series: Position ratios (0-1)
        """
        atr_pct = df['atr'] / df['close'].replace(0, np.finfo(float).eps)

        # Sigmoid normalization
        vol_adjustment = 1 / (1 + np.exp(5 * (atr_pct - 0.02)))

        return vol_adjustment

    def adjust_position_by_strength(self,
                                    base_shares: int,
                                    strength: float,
                                    max_strength: float = 10.0) -> int:
        """
        Adjust position size by signal strength

        Args:
            base_shares: Base number of shares from ATR calculation
            strength: Signal strength (continuous)
            max_strength: Maximum expected strength (default 10)

        Returns:
            int: Adjusted number of shares
        """
        # Normalize strength to 0-1
        strength_ratio = min(abs(strength) / max_strength, 1.0)

        # Adjust shares
        adjusted_shares = int(base_shares * strength_ratio)

        return adjusted_shares

    def calculate_stop_loss_price(self, entry_price: float, atr: float,
                                   is_long: bool = True) -> float:
        """
        Calculate stop loss price based on ATR

        Args:
            entry_price: Entry price
            atr: ATR value
            is_long: True for long position, False for short

        Returns:
            float: Stop loss price
        """
        stop_distance = atr * self.atr_multiplier

        if is_long:
            stop_price = entry_price - stop_distance
        else:
            stop_price = entry_price + stop_distance

        return max(stop_price, 0)  # Ensure non-negative


class KellyPositionSizer:
    """
    Kelly criterion position sizing

    Uses Kelly formula to determine optimal position size based on
    historical win rate and payoff ratio.
    """

    def __init__(self,
                 initial_capital: float = 2000,
                 default_win_rate: float = 0.55,
                 default_payoff: float = 1.5):
        """
        Initialize Kelly position sizer

        Args:
            initial_capital: Starting capital
            default_win_rate: Default win rate (0-1)
            default_payoff: Default payoff ratio (average win / average loss)
        """
        self.initial_capital = initial_capital
        self.win_rate = default_win_rate
        self.payoff = default_payoff

    def update_statistics(self, trades: list):
        """
        Update win rate and payoff from trade history

        Args:
            trades: List of trade dictionaries with 'pnl' key
        """
        if not trades:
            return

        # Calculate win rate
        winning_trades = [t for t in trades if t.get('pnl', 0) > 0]
        self.win_rate = len(winning_trades) / len(trades)

        # Calculate payoff ratio
        if winning_trades:
            avg_win = np.mean([t['pnl'] for t in winning_trades])
            losing_trades = [t for t in trades if t.get('pnl', 0) <= 0]
            if losing_trades:
                avg_loss = abs(np.mean([t['pnl'] for t in losing_trades]))
                self.payoff = avg_win / avg_loss if avg_loss > 0 else 1.0

    def calculate_kelly_fraction(self) -> float:
        """
        Calculate Kelly fraction

        f* = (bp - q) / b

        where:
        b = payoff ratio
        p = win probability
        q = lose probability (1 - p)

        Returns:
            float: Optimal fraction of capital to bet
        """
        b = self.payoff
        p = self.win_rate
        q = 1 - p

        if b <= 0:
            return 0.0

        kelly = (b * p - q) / b

        # Use half-Kelly for safety
        return max(0, kelly * 0.5)

    def calculate_position_size(self, cash: float, price: float) -> int:
        """
        Calculate position size using Kelly criterion

        Args:
            cash: Available cash
            price: Current price

        Returns:
            int: Number of shares to buy
        """
        kelly_frac = self.calculate_kelly_fraction()
        position_value = cash * kelly_frac

        if price > 0:
            shares = int(position_value / price)
        else:
            shares = 0

        return shares


class HybridPositionSizer:
    """
    Hybrid position sizing combining ATR and Kelly

    Uses ATR for risk control and Kelly for capital allocation.
    """

    def __init__(self,
                 initial_capital: float = 2000,
                 atr_sizer: ATRPositionSizer = None,
                 kelly_sizer: KellyPositionSizer = None,
                 atr_weight: float = 0.6):
        """
        Initialize hybrid position sizer

        Args:
            initial_capital: Starting capital
            atr_sizer: ATR position sizer (created if None)
            kelly_sizer: Kelly position sizer (created if None)
            atr_weight: Weight for ATR sizing (0-1, default 0.6)
        """
        self.initial_capital = initial_capital
        self.atr_sizer = atr_sizer or ATRPositionSizer(initial_capital)
        self.kelly_sizer = kelly_sizer or KellyPositionSizer(initial_capital)
        self.atr_weight = atr_weight

    def calculate_position_size(self,
                                cash: float,
                                price: float,
                                atr: float) -> int:
        """
        Calculate hybrid position size

        Args:
            cash: Available cash
            price: Current price
            atr: ATR value

        Returns:
            int: Number of shares to buy
        """
        # Get position sizes from both methods
        atr_shares = self.atr_sizer.calculate_position_size(cash, price, atr)
        kelly_shares = self.kelly_sizer.calculate_position_size(cash, price)

        # Weighted combination
        hybrid_shares = int(
            self.atr_weight * atr_shares +
            (1 - self.atr_weight) * kelly_shares
        )

        return hybrid_shares
