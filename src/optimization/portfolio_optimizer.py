"""投资组合优化模块 - 基于马科维茨均值-方差模型"""

from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, field
import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

import numpy as np
import pandas as pd
from scipy.optimize import minimize
from sklearn.covariance import LedoitWolf

from ..data.data_models import PortfolioMetrics, OptimizationResult
from ..data.astock_collector import AStockDataCollector

logger = logging.getLogger(__name__)


@dataclass
class WeightConstraints:
    """权重约束"""
    long_only: bool = True  # 不允许做空（权重 >= 0）
    min_weight: float = 0.0  # 单资产最小权重
    max_weight: float = 1.0  # 单资产最大权重


class PortfolioOptimizer:
    """投资组合优化器 - 基于马科维茨均值-方差模型"""

    def __init__(self):
        self.data_collector = AStockDataCollector()
        self.returns_df: Optional[pd.DataFrame] = None
        self.cov_matrix: Optional[np.ndarray] = None
        self.symbols: List[str] = []
        self.logger = logger

    def prepare_data(self, symbols: List[str], period: str = "1y") -> pd.DataFrame:
        """
        获取多只股票的历史数据并计算日收益率矩阵

        Args:
            symbols: 股票代码列表
            period: 历史数据区间，如 "1y", "6mo", "2y"

        Returns:
            日收益率 DataFrame（index=日期，columns=股票代码）
        """
        all_returns = {}

        for symbol in symbols:
            try:
                data = self.data_collector.collect_stock_data(symbol, period=period)
                hist = data.get('historical_data')
                if hist is not None and not hist.empty and 'close' in hist.columns:
                    returns = hist['close'].pct_change().dropna()
                    all_returns[symbol] = returns
                    self.logger.info(f"获取 {symbol} 数据: {len(returns)} 个交易日")
                else:
                    self.logger.warning(f"{symbol} 无历史数据，跳过")
            except Exception as e:
                self.logger.error(f"获取 {symbol} 数据失败: {e}")

        if not all_returns:
            raise ValueError("没有任何股票的数据可用")

        # 对齐日期索引
        self.returns_df = pd.DataFrame(all_returns)
        # 前向填充，然后删除仍有 NaN 的行
        self.returns_df = self.returns_df.ffill().dropna()
        self.symbols = list(self.returns_df.columns)
        self.logger.info(f"收益率矩阵形状: {self.returns_df.shape}")
        return self.returns_df

    def estimate_covariance(self, returns_df: Optional[pd.DataFrame] = None,
                           method: str = "lw") -> np.ndarray:
        """
        估计协方差矩阵

        Args:
            returns_df: 日收益率矩阵，不传入则使用 self.returns_df
            method: "sample"（样本协方差）| "lw"（Ledoit-Wolf收缩）| "ewma"（指数加权）

        Returns:
            协方差矩阵 (n x n)
        """
        if returns_df is None:
            returns_df = self.returns_df

        if returns_df is None or returns_df.empty:
            raise ValueError("收益率数据为空，请先调用 prepare_data()")

        # 删除含有 NaN 的行
        returns_df = returns_df.dropna()

        if returns_df.empty:
            raise ValueError("删除 NaN 后数据为空")

        n = len(returns_df.columns)

        if method == "sample":
            cov = returns_df.cov().values

        elif method == "lw":
            # Ledoit-Wolf 收缩估计（自动优化收缩强度）
            try:
                lw = LedoitWolf()
                lw.fit(returns_df.values)
                cov = lw.covariance_
            except ValueError as e:
                self.logger.warning(f"Ledoit-Wolf 失败，降级为样本协方差: {e}")
                cov = returns_df.cov().values

        elif method == "ewma":
            # 指数加权移动平均协方差（lambda=0.94，行业标准）
            lambda_decay = 0.94
            returns_np = returns_df.values
            T, n = returns_np.shape
            # 计算 EWMA 协方差
            mean_vec = returns_np.mean(axis=0)
            centered = returns_np - mean_vec
            # 初始化
            cov = np.cov(centered[:10].T) if T > 10 else np.cov(centered.T)
            weighted_sum = np.zeros((n, n))
            weight_total = 0.0
            for t in range(T):
                w = lambda_decay ** t
                weighted_sum += w * np.outer(centered[t], centered[t])
                weight_total += w
            cov = weighted_sum / weight_total if weight_total > 0 else cov

        else:
            raise ValueError(f"未知的协方差估计方法: {method}")

        self.cov_matrix = cov
        return cov

    def compute_portfolio_metrics(self, weights: np.ndarray,
                                   returns_df: Optional[pd.DataFrame] = None,
                                   cov_matrix: Optional[np.ndarray] = None,
                                   risk_free_rate: float = 0.03) -> PortfolioMetrics:
        """
        计算组合的各项风险收益指标

        Args:
            weights: 资产权重向量 (n,)
            returns_df: 日收益率矩阵
            cov_matrix: 协方差矩阵
            risk_free_rate: 无风险利率（年化）

        Returns:
            PortfolioMetrics 对象
        """
        if returns_df is None:
            returns_df = self.returns_df
        if cov_matrix is None:
            cov_matrix = self.cov_matrix

        if returns_df is None or cov_matrix is None:
            raise ValueError("数据未初始化")

        # 年化预期收益（历史均值 × 252）
        expected_returns = returns_df.mean().values  # 日均收益
        annual_return = float(np.dot(weights, expected_returns) * 252)

        # 年化波动率
        annual_vol = float(np.sqrt(np.dot(weights, np.dot(cov_matrix, weights))) * np.sqrt(252))

        # 夏普比率
        sharpe = (annual_return - risk_free_rate) / annual_vol if annual_vol > 0 else 0.0

        # VaR / CVaR（95%，基于日收益率分布）
        portfolio_returns = returns_df.values @ weights
        var_95 = float(np.percentile(portfolio_returns, 5))
        cvar_95 = float(portfolio_returns[portfolio_returns <= var_95].mean()) if np.any(portfolio_returns <= var_95) else var_95

        # 最大回撤
        cumulative = (1 + portfolio_returns).cumprod()
        rolling_max = np.maximum.accumulate(cumulative)
        drawdown = (cumulative / rolling_max) - 1
        max_drawdown = float(drawdown.min())

        # 累计收益
        cumulative_return = float(cumulative[-1] - 1) if len(cumulative) > 0 else 0.0

        # 权重映射
        weights_dict = {self.symbols[i]: float(weights[i])
                        for i in range(len(weights)) if weights[i] > 1e-6}

        metrics = PortfolioMetrics(
            expected_return=annual_return,
            volatility=annual_vol,
            sharpe_ratio=sharpe,
            var_95=var_95,
            cvar_95=cvar_95,
            max_drawdown=max_drawdown,
            cumulative_return=cumulative_return,
            weights=weights_dict
        )

        # ===== 新增：Sortino / Calmar / Treynor / Omega =====
        # 下行标准差（仅计算低于目标收益的波动）
        daily_target = 0.0  # 盈亏平衡点
        downside_returns = np.minimum(portfolio_returns - daily_target, 0)
        downside_variance = np.mean(downside_returns ** 2)
        downside_std = float(np.sqrt(downside_variance) * np.sqrt(252)) if downside_variance > 0 else 0.0
        metrics.downside_dev = downside_std

        # Sortino = (Rp - Rf) / 下行标准差
        metrics.sortino_ratio = (annual_return - risk_free_rate) / downside_std if downside_std > 0 else 0.0

        # Calmar = (Rp - Rf) / |MaxDrawdown|
        max_dd_abs = abs(max_drawdown) if max_drawdown != 0 else 1e-10
        metrics.calmar_ratio = (annual_return - risk_free_rate) / max_dd_abs if max_dd_abs > 1e-10 else 0.0

        # Treynor：组合层面 Beta=1（组合本身是市场组合的模拟），用组合波动率作为分母
        beta = 1.0  # 组合的系统性风险近似为1
        metrics.treynor_ratio = (annual_return - risk_free_rate) / beta if beta != 0 else 0.0

        # Omega = 上尾收益之和 / 下尾损失之和
        gains = float(np.sum(np.maximum(portfolio_returns - daily_target, 0)))
        losses = float(np.sum(np.maximum(daily_target - portfolio_returns, 0)))
        if losses > 1e-10:
            metrics.omega_ratio = gains / losses
        else:
            metrics.omega_ratio = float('inf') if gains > 0 else 1.0

        return metrics

    def min_variance(self, returns_df: Optional[pd.DataFrame] = None,
                     cov_matrix: Optional[np.ndarray] = None) -> OptimizationResult:
        """
        最小方差组合优化（有效前沿左端点）

        Args:
            returns_df: 日收益率矩阵
            cov_matrix: 协方差矩阵

        Returns:
            OptimizationResult
        """
        if returns_df is None:
            returns_df = self.returns_df
        if cov_matrix is None:
            cov_matrix = self.cov_matrix

        if returns_df is None or cov_matrix is None:
            return OptimizationResult(error_message="数据未初始化")

        n = len(self.symbols)
        cov = cov_matrix

        # 目标函数: w^T Σ w（组合方差）
        def portfolio_variance(w):
            return np.dot(w, np.dot(cov, w))

        # 约束: 权重和=1, w >= 0
        constraints = [
            {'type': 'eq', 'fun': lambda w: np.sum(w) - 1},
        ]
        bounds = [(0, 1) for _ in range(n)]  # 不允许做空

        # 初始点：等权重
        w0 = np.ones(n) / n

        result = minimize(
            portfolio_variance,
            w0,
            method='SLSQP',
            bounds=bounds,
            constraints=constraints,
            options={'ftol': 1e-10}
        )

        if not result.success:
            return OptimizationResult(error_message=f"优化失败: {result.message}")

        w = result.x
        w = np.maximum(w, 0)
        w = w / w.sum() if w.sum() > 0 else w

        portfolio_metrics = self.compute_portfolio_metrics(w, returns_df, cov_matrix)
        return OptimizationResult(weights=dict(zip(self.symbols, w)), portfolio_metrics=portfolio_metrics)

    def max_sharpe(self, returns_df: Optional[pd.DataFrame] = None,
                   cov_matrix: Optional[np.ndarray] = None,
                   risk_free_rate: float = 0.03) -> OptimizationResult:
        """
        最大夏普比率组合优化

        Args:
            returns_df: 日收益率矩阵
            cov_matrix: 协方差矩阵
            risk_free_rate: 无风险利率

        Returns:
            OptimizationResult
        """
        if returns_df is None:
            returns_df = self.returns_df
        if cov_matrix is None:
            cov_matrix = self.cov_matrix

        if returns_df is None or cov_matrix is None:
            return OptimizationResult(error_message="数据未初始化")

        n = len(self.symbols)
        mu = returns_df.mean().values * 252  # 年化收益向量
        cov = cov_matrix
        rf = risk_free_rate

        # 目标函数: 负夏普比率（最小化）
        def neg_sharpe(w):
            port_return = np.dot(mu, w)
            port_vol = np.sqrt(np.dot(w, np.dot(cov, w)))
            if port_vol < 1e-10:
                return 1e10
            return -(port_return - rf) / port_vol

        constraints = [
            {'type': 'eq', 'fun': lambda w: np.sum(w) - 1},
        ]
        bounds = [(0, 1) for _ in range(n)]

        w0 = np.ones(n) / n

        result = minimize(
            neg_sharpe,
            w0,
            method='SLSQP',
            bounds=bounds,
            constraints=constraints,
            options={'ftol': 1e-10}
        )

        if not result.success:
            return OptimizationResult(error_message=f"优化失败: {result.message}")

        w = result.x
        w = np.maximum(w, 0)
        w = w / w.sum() if w.sum() > 0 else w

        portfolio_metrics = self.compute_portfolio_metrics(w, returns_df, cov_matrix, risk_free_rate)
        return OptimizationResult(weights=dict(zip(self.symbols, w)), portfolio_metrics=portfolio_metrics)

    def efficient_frontier(self, returns_df: Optional[pd.DataFrame] = None,
                           cov_matrix: Optional[np.ndarray] = None,
                           n_points: int = 50,
                           risk_free_rate: float = 0.03) -> OptimizationResult:
        """
        计算有效前沿曲线

        Args:
            returns_df: 日收益率矩阵
            cov_matrix: 协方差矩阵
            n_points: 前沿曲线上的点数
            risk_free_rate: 无风险利率

        Returns:
            OptimizationResult（frontier_points 包含前沿上所有组合）
        """
        if returns_df is None:
            returns_df = self.returns_df
        if cov_matrix is None:
            cov_matrix = self.cov_matrix

        if returns_df is None or cov_matrix is None:
            return OptimizationResult(error_message="数据未初始化")

        n = len(self.symbols)
        mu = returns_df.mean().values * 252  # 年化
        cov = cov_matrix

        # 目标收益范围：从最小方差组合收益到最大收益
        min_return = float(np.min(mu))
        max_return = float(np.max(mu))

        # 辅助函数：在目标收益约束下最小化方差
        def min_var_with_target(target_ret):
            def objective(w):
                return np.dot(w, np.dot(cov, w))

            def return_constraint(w):
                return np.dot(mu, w) - target_ret

            constraints = [
                {'type': 'eq', 'fun': lambda w: np.sum(w) - 1},
                {'type': 'ineq', 'fun': return_constraint},
            ]
            bounds = [(0, 1) for _ in range(n)]
            w0 = np.ones(n) / n

            result = minimize(
                objective,
                w0,
                method='SLSQP',
                bounds=bounds,
                constraints=constraints,
                options={'ftol': 1e-10}
            )
            return result

        frontier_points: List[PortfolioMetrics] = []

        for i in range(n_points):
            target_return = min_return + (max_return - min_return) * i / (n_points - 1)
            try:
                result = min_var_with_target(target_return)
                if result.success:
                    w = np.maximum(result.x, 0)
                    w = w / w.sum() if w.sum() > 0 else w
                    metrics = self.compute_portfolio_metrics(w, returns_df, cov_matrix, risk_free_rate)
                    frontier_points.append(metrics)
            except Exception:
                continue

        # 找全局最小方差组合（左端点）
        min_var_result = self.min_variance(returns_df, cov_matrix)
        if min_var_result.error_message == "" and min_var_result.portfolio_metrics:
            all_returns = [fp.expected_return for fp in frontier_points]
            if min_var_result.portfolio_metrics.expected_return not in all_returns:
                frontier_points.insert(0, min_var_result.portfolio_metrics)

        # 按预期收益排序
        frontier_points.sort(key=lambda x: x.expected_return)

        return OptimizationResult(
            weights={} if frontier_points else {},
            portfolio_metrics=frontier_points[-1] if frontier_points else None,
            frontier_points=frontier_points
        )

    def risk_parity(self, returns_df: Optional[pd.DataFrame] = None,
                    cov_matrix: Optional[np.ndarray] = None) -> OptimizationResult:
        """
        风险平价组合 - 每类资产对组合风险的贡献相等

        用梯度下降求解（无闭式解）
        """
        if returns_df is None:
            returns_df = self.returns_df
        if cov_matrix is None:
            cov_matrix = self.cov_matrix

        if returns_df is None or cov_matrix is None:
            return OptimizationResult(error_message="数据未初始化")

        n = len(self.symbols)

        # 初始等权重
        w = np.ones(n) / n

        # 梯度下降优化
        learning_rate = 0.01
        max_iter = 1000
        tolerance = 1e-8

        for iteration in range(max_iter):
            # 各资产边际风险贡献
            portfolio_vol = float(np.sqrt(np.dot(w, np.dot(cov_matrix, w))))
            if portfolio_vol < 1e-10:
                break

            # 风险贡献 = w_i * (Sigma @ w)_i / portfolio_vol
            marginal_contrib = np.dot(cov_matrix, w) / portfolio_vol
            risk_contrib = w * marginal_contrib

            # 目标：各资产风险贡献相等
            target_contrib = portfolio_vol / n
            gradient = marginal_contrib - target_contrib / w  # 简化梯度

            w_new = w - learning_rate * gradient
            w_new = np.maximum(w_new, 1e-6)  # 不允许接近零
            w_new = w_new / w_new.sum()  # 归一化

            if np.linalg.norm(w_new - w) < tolerance:
                w = w_new
                break
            w = w_new

        portfolio_metrics = self.compute_portfolio_metrics(w, returns_df, cov_matrix)
        return OptimizationResult(weights=dict(zip(self.symbols, w)), portfolio_metrics=portfolio_metrics)

    def optimize(self, symbols: List[str], period: str = "1y",
                 objective: str = "max_sharpe",
                 cov_method: str = "lw",
                 risk_free_rate: float = 0.03) -> OptimizationResult:
        """
        统一入口：执行组合优化

        Args:
            symbols: 股票代码列表
            period: 历史数据区间
            objective: "min_variance" | "max_sharpe" | "risk_parity" | "efficient_frontier"
            cov_method: "sample" | "lw" | "ewma"
            risk_free_rate: 无风险利率

        Returns:
            OptimizationResult
        """
        self.logger.info(f"开始优化: symbols={symbols}, objective={objective}")

        # 数据准备
        returns_df = self.prepare_data(symbols, period)

        # 协方差估计
        cov_matrix = self.estimate_covariance(returns_df, method=cov_method)

        # 执行优化
        if objective == "min_variance":
            return self.min_variance(returns_df, cov_matrix)
        elif objective == "max_sharpe":
            return self.max_sharpe(returns_df, cov_matrix, risk_free_rate)
        elif objective == "risk_parity":
            return self.risk_parity(returns_df, cov_matrix)
        elif objective == "efficient_frontier":
            return self.efficient_frontier(returns_df, cov_matrix, n_points=50, risk_free_rate=risk_free_rate)
        else:
            return OptimizationResult(error_message=f"未知优化目标: {objective}")