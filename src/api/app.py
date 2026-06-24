"""
FastAPI Application for A-Stock Financial Analysis System
"""

from fastapi import FastAPI, HTTPException, BackgroundTasks, WebSocket, WebSocketDisconnect, UploadFile, File, Form
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, FileResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from contextlib import asynccontextmanager
import asyncio
import logging
import uvicorn
from typing import Dict, List, Optional, Any
from datetime import datetime
import sys
import os
import tempfile
import io
from pathlib import Path

# 添加项目根目录
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from src.data.astock_collector import AStockDataCollector
from src.analysis.financial_analyzer import FinancialAnalyzer
from src.risk.risk_analyzer import RiskAnalyzer
from src.risk.joint_risk_analyzer import JointRiskAnalyzer
from simple_autogen.astock_autogen_system import AStockAutoGenSystem
from src.pdf.pdf_processor import PDFProcessor
from src.agents.pdf_risk_agent import PDFRiskAgent
from src.optimization.portfolio_optimizer import PortfolioOptimizer
from .models import OptimizationRequest, OptimizationResponse
from .export import generate_export


# 全局变量
analysis_system = None
websocket_manager = None
pdf_tasks: Dict[str, Dict] = {}
pdf_agent = None
MINIMAX_API_KEY = "sk-cp-fuHam45Wah1ay6BsZk8ACLYzV3p8_ID5NgTwJE09Kc9kCFdzwiSYzOvD2IfceEcwA-d5l8Dehm7Cks11hQa6i4moTJk-pinWhpBlR2KxsOsJ1V8zZx5S5MY"


@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期管理"""
    global analysis_system
    analysis_system = AStockAutoGenSystem("sk-cp-fuHam45Wah1ay6BsZk8ACLYzV3p8_ID5NgTwJE09Kc9kCFdzwiSYzOvD2IfceEcwA-d5l8Dehm7Cks11hQa6i4moTJk-pinWhpBlR2KxsOsJ1V8zZx5S5MY")
    yield


def create_app() -> FastAPI:
    """创建FastAPI应用"""
    app = FastAPI(
        title="A-Stock Financial Analysis API",
        description="A股智能体金融分析系统API",
        version="1.0.0",
        lifespan=lifespan
    )

    # 配置CORS
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # 静态文件服务
    try:
        app.mount("/static", StaticFiles(directory="web"), name="static")
    except Exception as e:
        logging.warning(f"Failed to mount static files: {e}")

    # 根路径 - 返回web界面
    @app.get("/")
    async def root():
        try:
            return FileResponse("web/index.html")
        except Exception:
            return JSONResponse({
                "message": "A-Stock Financial Analysis API",
                "version": "1.0.0",
                "docs": "/docs"
            })

    # 错误处理
    @app.exception_handler(Exception)
    async def general_error_handler(request, exc: Exception):
        logging.error(f"未处理的异常: {str(exc)}")
        return JSONResponse(
            status_code=500,
            content={"error_code": "INTERNAL_ERROR", "error_message": str(exc)}
        )

    # 数据收集器
    data_collector = AStockDataCollector()
    financial_analyzer = FinancialAnalyzer()
    risk_analyzer = RiskAnalyzer()
    joint_risk_analyzer = JointRiskAnalyzer()

    # 存储任务
    tasks: Dict[str, Dict] = {}

    # ==================== API 路由 ====================

    @app.get("/api/v1/symbols/{symbol}/info")
    async def get_symbol_info(symbol: str):
        """获取股票信息"""
        try:
            info = data_collector.get_stock_info(symbol)
            if not info:
                raise HTTPException(status_code=404, detail="股票不存在")
            return {"code": 200, "data": info}
        except Exception as e:
            logging.error(f"获取股票信息失败: {str(e)}")
            raise HTTPException(status_code=500, detail=str(e))

    @app.get("/api/v1/symbols/{symbol}/historical")
    async def get_historical_data(symbol: str, period: str = "1y"):
        """获取历史K线数据"""
        try:
            end_date = datetime.now().strftime("%Y%m%d")
            if period == "1y":
                start_date = "20250524"
            elif period == "6mo":
                start_date = "20241124"
            else:
                start_date = "20250524"

            df = data_collector.get_historical_data(symbol, "daily", start_date, end_date)
            return {"code": 200, "data": df.to_dict('records') if not df.empty else []}
        except Exception as e:
            logging.error(f"获取历史数据失败: {str(e)}")
            raise HTTPException(status_code=500, detail=str(e))

    @app.get("/api/v1/symbols/{symbol}/financial")
    async def get_financial_data(symbol: str):
        """获取财务数据"""
        try:
            data = data_collector.get_financial_data(symbol)
            result = {}
            for key, df in data.items():
                result[key] = df.to_dict('records') if not df.empty else []
            return {"code": 200, "data": result}
        except Exception as e:
            logging.error(f"获取财务数据失败: {str(e)}")
            raise HTTPException(status_code=500, detail=str(e))

    @app.post("/api/v1/analysis")
    async def create_analysis(request_data: Dict[str, Any], background_tasks: BackgroundTasks):
        """创建分析任务"""
        try:
            symbols = request_data.get("symbols", [])
            if not symbols:
                raise HTTPException(status_code=422, detail="股票代码不能为空")

            task_id = f"task_{datetime.now().timestamp()}"
            export_format = request_data.get("export_format", "html")
            analysis_type = request_data.get("analysis_type", "comprehensive")
            tasks[task_id] = {
                "id": task_id,
                "symbols": symbols,
                "status": "pending",
                "created_at": datetime.now().isoformat(),
                "result": None,
                "progress": 0,
                "step": "等待处理...",
                "export_format": export_format,
                "analysis_type": analysis_type
            }

            background_tasks.add_task(run_analysis, task_id, symbols, export_format, analysis_type)

            return {
                "code": 200,
                "data": {
                    "task_id": task_id,
                    "status": "pending",
                    "message": "分析任务已创建"
                }
            }
        except Exception as e:
            logging.error(f"创建分析任务失败: {str(e)}")
            raise HTTPException(status_code=500, detail=str(e))

    async def run_analysis(task_id: str, symbols: List[str], export_format: str = "html", analysis_type: str = "comprehensive"):
        """执行分析任务"""
        try:
            tasks[task_id]["status"] = "running"
            tasks[task_id]["progress"] = 0
            tasks[task_id]["step"] = "正在收集数据..."
            tasks[task_id]["export_format"] = export_format
            tasks[task_id]["analysis_type"] = analysis_type

            results = []
            for i, symbol in enumerate(symbols):
                # 更新进度
                tasks[task_id]["progress"] = (i / len(symbols)) * 100
                tasks[task_id]["step"] = f"正在收集 {symbol} 数据..."

                # 收集数据
                data = data_collector.collect_stock_data(symbol)
                if not data or not data.get('info'):
                    results.append({"symbol": symbol, "error": "数据获取失败"})
                    continue

                info = data.get('info', {})

                # 根据分析类型执行不同分析
                if analysis_type == "joint_risk":
                    # 联合风控分析
                    tasks[task_id]["progress"] = 30 + (i / len(symbols)) * 30
                    tasks[task_id]["step"] = f"正在计算 {symbol} 联合风控模型..."

                    joint_metrics = joint_risk_analyzer.analyze(data)
                    risk_metrics = risk_analyzer.calculate_metrics(data)

                    # 将RiskAnalyzer计算的M-Score传入joint_metrics（综合评分需要）
                    joint_metrics.m_score = risk_metrics.m_score
                    joint_metrics.m_score_interpretation = risk_metrics.m_score_interpretation

                    tasks[task_id]["progress"] = 70 + (i / len(symbols)) * 25
                    tasks[task_id]["step"] = f"正在生成 {symbol} 风控报告..."

                    results.append({
                        "symbol": symbol,
                        "name": info.get('name', symbol),
                        "price": info.get('price', 0),
                        "pe": info.get('pe_ttm', '-'),
                        "pb": info.get('pb', '-'),
                        "ps": info.get('ps_ttm', '-'),
                        "market_cap": f"{info.get('market_cap', 0)/1e8:.2f}亿" if info.get('market_cap') else '-',
                        "float_market_cap": f"{info.get('float_market_cap', 0)/1e8:.2f}亿" if info.get('float_market_cap') else '-',
                        "risk_metrics": risk_metrics.to_dict(),
                        "joint_risk_metrics": joint_metrics.to_dict(),
                        "analysis_type": "joint_risk",
                    })
                else:
                    # 综合分析（默认）
                    tasks[task_id]["progress"] = 30 + (i / len(symbols)) * 20
                    tasks[task_id]["step"] = f"正在计算 {symbol} 财务指标..."

                    financial_metrics = financial_analyzer.calculate_metrics(data)
                    risk_metrics = risk_analyzer.calculate_metrics(data)

                    tasks[task_id]["progress"] = 60 + (i / len(symbols)) * 20
                    tasks[task_id]["step"] = f"正在生成 {symbol} 分析报告..."

                    financial_analysis = financial_analyzer.generate_analysis_text(data, financial_metrics)
                    risk_analysis = risk_analyzer.generate_analysis_text(data, risk_metrics)

                    results.append({
                        "symbol": symbol,
                        "name": info.get('name', symbol),
                        "price": info.get('price', 0),
                        "financial_metrics": financial_metrics.to_dict(),
                        "risk_metrics": risk_metrics.to_dict(),
                        "financial_analysis": financial_analysis,
                        "risk_analysis": risk_analysis,
                        "pe": info.get('pe_ttm', '-'),
                        "pb": info.get('pb', '-'),
                        "ps": info.get('ps_ttm', '-'),
                        "market_cap": f"{info.get('market_cap', 0)/1e8:.2f}亿" if info.get('market_cap') else '-',
                        "float_market_cap": f"{info.get('float_market_cap', 0)/1e8:.2f}亿" if info.get('float_market_cap') else '-',
                        "analysis_type": "comprehensive",
                    })

                tasks[task_id]["progress"] = 90 + (i / len(symbols)) * 10
                tasks[task_id]["step"] = f"正在完成 {symbol} ..."

            tasks[task_id]["status"] = "completed"
            tasks[task_id]["progress"] = 100
            tasks[task_id]["step"] = "分析完成"
            tasks[task_id]["result"] = results
            tasks[task_id]["completed_at"] = datetime.now().isoformat()

        except Exception as e:
            logging.error(f"分析任务执行失败: {str(e)}")
            tasks[task_id]["status"] = "failed"
            tasks[task_id]["error"] = str(e)

    @app.get("/api/v1/analysis/{task_id}")
    async def get_analysis_status(task_id: str):
        """获取任务状态"""
        if task_id not in tasks:
            raise HTTPException(status_code=404, detail="任务不存在")
        return {"code": 200, "data": tasks[task_id]}

    @app.get("/api/v1/analysis/{task_id}/result")
    async def get_analysis_result(task_id: str):
        """获取分析结果"""
        if task_id not in tasks:
            raise HTTPException(status_code=404, detail="任务不存在")

        task = tasks[task_id]
        if task["status"] != "completed":
            return {"code": 400, "message": "任务未完成", "status": task["status"]}

        return {"code": 200, "data": task["result"]}

    @app.get("/api/v1/analysis")
    async def list_analyses(limit: int = 50, offset: int = 0):
        """获取任务列表"""
        task_list = list(tasks.values())
        task_list.sort(key=lambda x: x.get("created_at", ""), reverse=True)
        return {"code": 200, "data": task_list[offset:offset+limit]}

    @app.get("/api/v1/system/status")
    async def get_system_status():
        """获取系统状态"""
        return {
            "code": 200,
            "data": {
                "status": "healthy",
                "uptime": "running",
                "active_tasks": len([t for t in tasks.values() if t["status"] == "running"]),
                "completed_tasks": len([t for t in tasks.values() if t["status"] == "completed"]),
                "api_version": "1.0.0"
            }
        }

    @app.get("/api/v1/export/{task_id}")
    async def export_analysis(task_id: str, format: str = None):
        """
        导出分析结果为指定格式文件

        Args:
            task_id: 分析任务ID
            format: 导出格式，不传则使用任务创建时选择的格式
        """
        if task_id not in tasks:
            raise HTTPException(status_code=404, detail="任务不存在")

        task = tasks[task_id]
        if task["status"] != "completed":
            raise HTTPException(status_code=400, detail="任务未完成，无法导出")

        # 如果未指定格式，使用任务创建时选择的格式
        fmt = format or task.get("export_format", "html")
        results = task.get("result")
        if not results:
            raise HTTPException(status_code=404, detail="分析结果为空")

        try:
            content, mime, ext = generate_export(results, fmt)
            filename = f"astock_report_{task_id[:8]}.{ext}"
            return StreamingResponse(
                io.BytesIO(content),
                media_type=mime,
                headers={"Content-Disposition": f"attachment; filename*=UTF-8''{filename}"}
            )
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e))
        except Exception as e:
            logging.error(f"导出失败: {str(e)}")
            raise HTTPException(status_code=500, detail=f"导出失败: {str(e)}")

    @app.get("/health")
    async def health_check():
        return {"status": "healthy", "timestamp": datetime.now().isoformat()}

    # WebSocket端点（简化版，不做认证）
    @app.websocket("/ws")
    async def websocket_endpoint(websocket: WebSocket):
        """WebSocket endpoint for real-time updates"""
        await websocket.accept()
        try:
            while True:
                data = await websocket.receive_text()
                # 简单的心跳响应
                if data == "ping":
                    await websocket.send_text("pong")
                else:
                    await websocket.send_text(f"Received: {data}")
        except Exception:
            pass  # 连接关闭

    # ==================== PDF年报风险分析端点 ====================

    @app.post("/api/v1/risk/analyze-pdf")
    async def analyze_pdf_risk(
        background_tasks: BackgroundTasks,
        file: UploadFile = File(...),
        company_name: str = Form("")
    ):
        """上传PDF年报进行风险分析"""
        try:
            # 验证文件类型
            if not file.filename.endswith('.pdf'):
                raise HTTPException(status_code=422, detail="仅支持PDF格式文件")

            # 创建任务
            task_id = f"pdf_task_{datetime.now().timestamp()}"
            pdf_tasks[task_id] = {
                "id": task_id,
                "company_name": company_name,
                "status": "uploading",
                "progress": 0,
                "step": "正在上传文件...",
                "created_at": datetime.now().isoformat(),
                "result": None,
                "error": None
            }

            # 保存上传的文件到临时目录
            with tempfile.NamedTemporaryFile(delete=False, suffix='.pdf') as tmp_file:
                content = await file.read()
                tmp_file.write(content)
                tmp_path = tmp_file.name

            pdf_tasks[task_id]["status"] = "processing"
            pdf_tasks[task_id]["step"] = "正在提取PDF文本..."
            pdf_tasks[task_id]["progress"] = 20

            # 在后台执行分析
            background_tasks.add_task(run_pdf_analysis, task_id, tmp_path, company_name)

            return {
                "code": 200,
                "data": {
                    "task_id": task_id,
                    "status": "processing",
                    "message": "PDF分析任务已创建"
                }
            }

        except HTTPException:
            raise
        except Exception as e:
            logging.error(f"创建PDF分析任务失败: {str(e)}")
            raise HTTPException(status_code=500, detail=str(e))

    @app.get("/api/v1/risk/{task_id}")
    async def get_pdf_task_status(task_id: str):
        """获取PDF分析任务状态"""
        if task_id not in pdf_tasks:
            raise HTTPException(status_code=404, detail="任务不存在")
        return {"code": 200, "data": pdf_tasks[task_id]}

    @app.get("/api/v1/risk/{task_id}/result")
    async def get_pdf_task_result(task_id: str):
        """获取PDF分析结果"""
        if task_id not in pdf_tasks:
            raise HTTPException(status_code=404, detail="任务不存在")

        task = pdf_tasks[task_id]
        if task["status"] == "failed":
            return {"code": 500, "message": task.get("error", "分析失败")}
        if task["status"] != "completed":
            return {"code": 400, "message": "任务未完成", "status": task["status"]}

        return {"code": 200, "data": task["result"]}

    @app.get("/api/v1/risk/tasks")
    async def list_pdf_tasks(limit: int = 50, offset: int = 0):
        """获取PDF分析任务列表"""
        task_list = list(pdf_tasks.values())
        task_list.sort(key=lambda x: x.get("created_at", ""), reverse=True)
        return {"code": 200, "data": task_list[offset:offset+limit]}

    def run_pdf_analysis(task_id: str, pdf_path: str, company_name: str):
        """后台执行PDF分析任务"""
        try:
            global pdf_agent
            if pdf_agent is None:
                pdf_agent = PDFRiskAgent(MINIMAX_API_KEY)

            processor = PDFProcessor()

            # 提取文本
            pdf_tasks[task_id]["progress"] = 30
            pdf_tasks[task_id]["step"] = "正在提取PDF文本..."
            logging.info(f"[{task_id}] 开始提取PDF文本: {pdf_path}")

            text = processor.extract_text(pdf_path, max_pages=100)
            logging.info(f"[{task_id}] 提取文本长度: {len(text)}")

            if not text or len(text) < 100:
                raise Exception(f"PDF文本提取失败或内容过少: 长度{len(text) if text else 0}")

            # 提取财务附注相关内容
            pdf_tasks[task_id]["progress"] = 50
            pdf_tasks[task_id]["step"] = "正在分析财务内容..."
            financial_text = processor.extract_financial_notes(text)
            logging.info(f"[{task_id}] 财务附注文本长度: {len(financial_text)}")

            if not financial_text:
                logging.info(f"[{task_id}] 财务附注为空，尝试提取债务相关内容")
                financial_text = processor.extract_debt_related_content(text)
                logging.info(f"[{task_id}] 债务相关内容长度: {len(financial_text)}")

            if not financial_text:
                financial_text = text[:20000]
                logging.info(f"[{task_id}] 使用原始文本前20000字符")

            if len(financial_text) < 50:
                raise Exception("提取的财务内容过少，无法进行分析")

            pdf_tasks[task_id]["progress"] = 70
            pdf_tasks[task_id]["step"] = "正在进行LLM分析..."
            logging.info(f"[{task_id}] 开始LLM分析，文本长度: {len(financial_text)}")

            # 调用LLM分析
            result = pdf_agent.analyze(financial_text, company_name)
            logging.info(f"[{task_id}] LLM分析完成，结果长度: {len(result) if result else 0}")

            pdf_tasks[task_id]["status"] = "completed"
            pdf_tasks[task_id]["progress"] = 100
            pdf_tasks[task_id]["step"] = "分析完成"
            pdf_tasks[task_id]["result"] = {
                "company_name": company_name,
                "analysis": result
            }
            logging.info(f"[{task_id}] 任务完成")

        except Exception as e:
            logging.error(f"PDF分析任务失败: {str(e)}")
            pdf_tasks[task_id]["status"] = "failed"
            pdf_tasks[task_id]["error"] = str(e)
        finally:
            # 清理临时文件
            try:
                os.unlink(pdf_path)
            except Exception:
                pass

    # ==================== 投资组合优化端点 ====================

    @app.post("/api/v1/optimize/portfolio")
    async def optimize_portfolio(request_data: Dict[str, Any]):
        """
        投资组合优化

        支持优化目标:
        - min_variance: 最小方差组合
        - max_sharpe: 最大夏普比率组合
        - risk_parity: 风险平价组合
        - efficient_frontier: 有效前沿（返回完整曲线）
        """
        import time
        start_time = time.time()

        try:
            symbols = request_data.get("symbols", [])
            if not symbols or len(symbols) < 2:
                raise HTTPException(status_code=422, detail="至少需要2只股票才能进行组合优化")

            objective = request_data.get("objective", "max_sharpe")
            period = request_data.get("period", "1y")
            risk_free_rate = float(request_data.get("risk_free_rate", 0.03))
            cov_method = request_data.get("cov_method", "lw")

            # 执行优化
            optimizer = PortfolioOptimizer()
            result = optimizer.optimize(
                symbols=symbols,
                period=period,
                objective=objective,
                cov_method=cov_method,
                risk_free_rate=risk_free_rate
            )

            elapsed = time.time() - start_time

            if result.error_message:
                return {
                    "code": 400,
                    "message": result.error_message,
                    "optimization_time": round(elapsed, 3)
                }

            return {
                "code": 200,
                "data": {
                    "weights": {k: f"{v:.2%}" for k, v in result.weights.items()},
                    "portfolio_metrics": result.portfolio_metrics.to_raw_dict() if result.portfolio_metrics else {},
                    "frontier_points": [p.to_raw_dict() for p in result.frontier_points] if result.frontier_points else [],
                    "optimization_time": round(elapsed, 3)
                }
            }

        except HTTPException:
            raise
        except Exception as e:
            logging.error(f"组合优化失败: {str(e)}")
            raise HTTPException(status_code=500, detail=str(e))

    return app


# 创建应用实例
app = create_app()


if __name__ == "__main__":
    uvicorn.run(
        "src.api.app:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level="info"
    )