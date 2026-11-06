"""
API Models for AutoGen Financial Analysis System
Data models for API requests and responses
"""

from typing import Dict, List, Optional, Any, Union
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
import uuid
import json


class AnalysisType(Enum):
    """分析类型枚举"""
    QUICK = "quick"
    COMPREHENSIVE = "comprehensive"
    DETAILED = "detailed"
    PORTFOLIO = "portfolio"
    RISK = "risk"
    FINANCIAL = "financial"


class ExportFormat(Enum):
    """导出格式枚举"""
    HTML = "html"
    PDF = "pdf"
    EXCEL = "excel"
    CSV = "csv"
    JSON = "json"
    MARKDOWN = "markdown"
    XML = "xml"


class AnalysisStatus(Enum):
    """分析状态枚举"""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass
class AnalysisRequest:
    """分析请求模型"""
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    symbols: List[str] = field(default_factory=list)
    analysis_type: AnalysisType = AnalysisType.COMPREHENSIVE
    portfolio_weights: Optional[Dict[str, float]] = None
    export_formats: List[ExportFormat] = field(default_factory=lambda: [ExportFormat.HTML])
    options: Dict[str, Any] = field(default_factory=dict)
    callback_url: Optional[str] = None
    priority: int = 0
    created_at: datetime = field(default_factory=datetime.now)
    status: AnalysisStatus = AnalysisStatus.PENDING

    def to_dict(self) -> Dict:
        """转换为字典"""
        return {
            'id': self.id,
            'symbols': self.symbols,
            'analysis_type': self.analysis_type.value,
            'portfolio_weights': self.portfolio_weights,
            'export_formats': [f.value for f in self.export_formats],
            'options': self.options,
            'callback_url': self.callback_url,
            'priority': self.priority,
            'created_at': self.created_at.isoformat(),
            'status': self.status.value
        }

    @classmethod
    def from_dict(cls, data: Dict) -> 'AnalysisRequest':
        """从字典创建实例"""
        return cls(
            id=data.get('id', str(uuid.uuid4())),
            symbols=data.get('symbols', []),
            analysis_type=AnalysisType(data.get('analysis_type', AnalysisType.COMPREHENSIVE.value)),
            portfolio_weights=data.get('portfolio_weights'),
            export_formats=[ExportFormat(f) for f in data.get('export_formats', ['html'])],
            options=data.get('options', {}),
            callback_url=data.get('callback_url'),
            priority=data.get('priority', 0),
            created_at=datetime.fromisoformat(data.get('created_at', datetime.now().isoformat())),
            status=AnalysisStatus(data.get('status', AnalysisStatus.PENDING.value))
        )


@dataclass
class AnalysisResult:
    """分析结果模型"""
    symbol: str
    financial_metrics: Dict[str, Any]
    risk_metrics: Dict[str, Any]
    quant_metrics: Dict[str, Any]
    summary: Dict[str, Any]
    recommendations: List[str]
    data_quality: Dict[str, float]
    analysis_date: datetime

    def to_dict(self) -> Dict:
        """转换为字典"""
        return {
            'symbol': self.symbol,
            'financial_metrics': self.financial_metrics,
            'risk_metrics': self.risk_metrics,
            'quant_metrics': self.quant_metrics,
            'summary': self.summary,
            'recommendations': self.recommendations,
            'data_quality': self.data_quality,
            'analysis_date': self.analysis_date.isoformat()
        }


@dataclass
class PortfolioAnalysisResult:
    """投资组合分析结果模型"""
    symbols: List[str]
    portfolio_weights: Dict[str, float]
    individual_results: Dict[str, AnalysisResult]
    portfolio_metrics: Dict[str, float]
    diversification_analysis: Dict[str, Any]
    recommendations: List[str]
    analysis_date: datetime

    def to_dict(self) -> Dict:
        """转换为字典"""
        return {
            'symbols': self.symbols,
            'portfolio_weights': self.portfolio_weights,
            'individual_results': {k: v.to_dict() for k, v in self.individual_results.items()},
            'portfolio_metrics': self.portfolio_metrics,
            'diversification_analysis': self.diversification_analysis,
            'recommendations': self.recommendations,
            'analysis_date': self.analysis_date.isoformat()
        }


@dataclass
class AnalysisResponse:
    """分析响应模型"""
    request_id: str
    status: AnalysisStatus
    results: Optional[Union[AnalysisResult, PortfolioAnalysisResult, List[AnalysisResult]]] = None
    error_message: Optional[str] = None
    progress: float = 0.0
    estimated_completion: Optional[datetime] = None
    export_files: List[str] = field(default_factory=list)
    created_at: datetime = field(default_factory=datetime.now)
    completed_at: Optional[datetime] = None

    def to_dict(self) -> Dict:
        """转换为字典"""
        response_dict = {
            'request_id': self.request_id,
            'status': self.status.value,
            'progress': self.progress,
            'export_files': self.export_files,
            'created_at': self.created_at.isoformat()
        }

        if self.results:
            if isinstance(self.results, list):
                response_dict['results'] = [r.to_dict() for r in self.results]
            else:
                response_dict['results'] = self.results.to_dict()

        if self.error_message:
            response_dict['error_message'] = self.error_message

        if self.estimated_completion:
            response_dict['estimated_completion'] = self.estimated_completion.isoformat()

        if self.completed_at:
            response_dict['completed_at'] = self.completed_at.isoformat()

        return response_dict


@dataclass
class AnalysisTask:
    """分析任务模型"""
    request: AnalysisRequest
    status: AnalysisStatus = AnalysisStatus.PENDING
    progress: float = 0.0
    error_message: Optional[str] = None
    results: Optional[Union[AnalysisResult, PortfolioAnalysisResult]] = None
    export_files: List[str] = field(default_factory=list)
    created_at: datetime = field(default_factory=datetime.now)
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None

    def to_dict(self) -> Dict:
        """转换为字典"""
        task_dict = {
            'request': self.request.to_dict(),
            'status': self.status.value,
            'progress': self.progress,
            'export_files': self.export_files,
            'created_at': self.created_at.isoformat()
        }

        if self.error_message:
            task_dict['error_message'] = self.error_message

        if self.results:
            if isinstance(self.results, list):
                task_dict['results'] = [r.to_dict() for r in self.results]
            else:
                task_dict['results'] = self.results.to_dict()

        if self.started_at:
            task_dict['started_at'] = self.started_at.isoformat()

        if self.completed_at:
            task_dict['completed_at'] = self.completed_at.isoformat()

        return task_dict


@dataclass
class SystemStatus:
    """系统状态模型"""
    status: str
    uptime: float
    active_tasks: int
    completed_tasks: int
    failed_tasks: int
    system_resources: Dict[str, float]
    api_version: str
    last_updated: datetime = field(default_factory=datetime.now)

    def to_dict(self) -> Dict:
        """转换为字典"""
        return {
            'status': self.status,
            'uptime': self.uptime,
            'active_tasks': self.active_tasks,
            'completed_tasks': self.completed_tasks,
            'failed_tasks': self.failed_tasks,
            'system_resources': self.system_resources,
            'api_version': self.api_version,
            'last_updated': self.last_updated.isoformat()
        }


@dataclass
class ErrorResponse:
    """错误响应模型"""
    error_code: str
    error_message: str
    details: Optional[Dict[str, Any]] = None
    timestamp: datetime = field(default_factory=datetime.now)

    def to_dict(self) -> Dict:
        """转换为字典"""
        response = {
            'error_code': self.error_code,
            'error_message': self.error_message,
            'timestamp': self.timestamp.isoformat()
        }

        if self.details:
            response['details'] = self.details

        return response


@dataclass
class WebSocketMessage:
    """WebSocket消息模型"""
    type: str
    data: Dict[str, Any]
    timestamp: datetime = field(default_factory=datetime.now)

    def to_json(self) -> str:
        """转换为JSON字符串"""
        return json.dumps({
            'type': self.type,
            'data': self.data,
            'timestamp': self.timestamp.isoformat()
        })

    @classmethod
    def from_json(cls, json_str: str) -> 'WebSocketMessage':
        """从JSON字符串创建实例"""
        data = json.loads(json_str)
        return cls(
            type=data['type'],
            data=data['data'],
            timestamp=datetime.fromisoformat(data['timestamp'])
        )


class ValidationError(Exception):
    """验证错误"""
    pass


def validate_analysis_request(request_data: Dict) -> AnalysisRequest:
    """验证分析请求"""
    if not isinstance(request_data, dict):
        raise ValidationError("请求必须是字典格式")

    required_fields = ['symbols']
    for field in required_fields:
        if field not in request_data:
            raise ValidationError(f"缺少必需字段: {field}")

    symbols = request_data['symbols']
    if not isinstance(symbols, list) or len(symbols) == 0:
        raise ValidationError("symbols必须是非空列表")

    for symbol in symbols:
        if not isinstance(symbol, str) or not symbol.strip():
            raise ValidationError("每个symbol必须是非空字符串")

    # 验证投资组合权重
    if 'portfolio_weights' in request_data:
        weights = request_data['portfolio_weights']
        if not isinstance(weights, dict):
            raise ValidationError("portfolio_weights必须是字典")

        total_weight = sum(weights.values())
        if abs(total_weight - 1.0) > 0.01:
            raise ValidationError("投资组合权重总和必须等于1.0")

        for symbol in weights:
            if symbol not in symbols:
                raise ValidationError(f"权重中的symbol {symbol} 不在分析列表中")

    return AnalysisRequest.from_dict(request_data)


def validate_export_formats(formats: List[str]) -> List[ExportFormat]:
    """验证导出格式"""
    valid_formats = []
    for format_str in formats:
        try:
            valid_formats.append(ExportFormat(format_str.lower()))
        except ValueError:
            raise ValidationError(f"不支持的导出格式: {format_str}")
    return valid_formats


class OptimizationObjective(Enum):
    """组合优化目标枚举"""
    MIN_VARIANCE = "min_variance"
    MAX_SHARPE = "max_sharpe"
    RISK_PARITY = "risk_parity"
    EFFICIENT_FRONTIER = "efficient_frontier"


class CovarianceMethod(Enum):
    """协方差估计方法枚举"""
    SAMPLE = "sample"
    LEDOIT_WOLF = "lw"
    EWMA = "ewma"


@dataclass
class OptimizationRequest:
    """组合优化请求模型"""
    symbols: List[str]  # 股票代码列表，如 ["000001", "600519"]
    objective: str = "max_sharpe"  # "min_variance" | "max_sharpe" | "risk_parity" | "efficient_frontier"
    constraints: Optional[Dict[str, Any]] = None  # 约束条件（预留）
    period: str = "1y"  # 历史数据区间
    risk_free_rate: float = 0.03  # 无风险利率（年化）
    cov_method: str = "lw"  # 协方差估计方法: "sample" | "lw" | "ewma"

    def to_dict(self) -> Dict:
        return {
            'symbols': self.symbols,
            'objective': self.objective,
            'constraints': self.constraints,
            'period': self.period,
            'risk_free_rate': self.risk_free_rate,
            'cov_method': self.cov_method,
        }

    @classmethod
    def from_dict(cls, data: Dict) -> 'OptimizationRequest':
        return cls(
            symbols=data.get('symbols', []),
            objective=data.get('objective', 'max_sharpe'),
            constraints=data.get('constraints'),
            period=data.get('period', '1y'),
            risk_free_rate=float(data.get('risk_free_rate', 0.03)),
            cov_method=data.get('cov_method', 'lw'),
        )


@dataclass
class OptimizationResponse:
    """组合优化响应模型"""
    weights: Dict[str, float]  # 最优权重
    portfolio_metrics: Dict[str, Any]  # 组合指标
    frontier_points: Optional[List[Dict[str, Any]]] = None  # 有效前沿曲线（当 objective="efficient_frontier" 时返回）
    error_message: Optional[str] = None
    optimization_time: float = 0.0  # 优化耗时（秒）

    def to_dict(self) -> Dict:
        return {
            'weights': {k: f"{v:.2%}" for k, v in self.weights.items()},
            'portfolio_metrics': self.portfolio_metrics,
            'frontier_points': self.frontier_points,
            'error_message': self.error_message,
            'optimization_time': round(self.optimization_time, 3),
        }