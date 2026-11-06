"""
Task Manager
Manages analysis tasks with proper state tracking and persistence
"""

import asyncio
import logging
import uuid
from typing import Dict, List, Optional, Any
from datetime import datetime
from dataclasses import dataclass, field
from enum import Enum
import json

from .models import AnalysisRequest, AnalysisTask, AnalysisStatus
from ..main import AutoGenFinancialAnalysisSystem


class TaskPriority(Enum):
    LOW = 1
    NORMAL = 2
    HIGH = 3
    CRITICAL = 4


@dataclass
class TaskResult:
    """Task execution result"""
    success: bool
    result: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
    execution_time: float = 0.0
    created_at: datetime = field(default_factory=datetime.now)


class TaskManager:
    """Task manager for analysis operations"""

    def __init__(self):
        self.tasks: Dict[str, AnalysisTask] = {}
        self.task_results: Dict[str, TaskResult] = {}
        self.logger = logging.getLogger(__name__)
        self.analysis_system: Optional[AutoGenFinancialAnalysisSystem] = None
        self._lock = asyncio.Lock()

    async def initialize(self, analysis_system: AutoGenFinancialAnalysisSystem):
        """Initialize task manager with analysis system"""
        self.analysis_system = analysis_system
        self.logger.info("Task manager initialized")

    async def create_task(self, request: AnalysisRequest) -> AnalysisTask:
        """Create a new analysis task"""
        task_id = str(uuid.uuid4())

        task = AnalysisTask(
            request=request,
            status=AnalysisStatus.PENDING,
            created_at=datetime.now(),
            progress=0.0
        )

        async with self._lock:
            self.tasks[task_id] = task

        self.logger.info(f"Created task {task_id} for symbols: {request.symbols}")
        return task

    async def get_task(self, task_id: str) -> Optional[AnalysisTask]:
        """Get task by ID"""
        async with self._lock:
            return self.tasks.get(task_id)

    async def update_task_status(
        self,
        task_id: str,
        status: AnalysisStatus,
        progress: float = None,
        message: str = None
    ) -> bool:
        """Update task status"""
        async with self._lock:
            task = self.tasks.get(task_id)
            if not task:
                return False

            task.status = status
            if progress is not None:
                task.progress = progress
            if message:
                task.message = message

            if status == AnalysisStatus.COMPLETED:
                task.completed_at = datetime.now()

            return True

    async def execute_task(self, task_id: str) -> TaskResult:
        """Execute a specific task"""
        task = await self.get_task(task_id)
        if not task:
            return TaskResult(success=False, error=f"Task {task_id} not found")

        start_time = datetime.now()

        try:
            # Update status to running
            await self.update_task_status(task_id, AnalysisStatus.RUNNING, 0.0, "Starting analysis")

            if not self.analysis_system:
                raise RuntimeError("Analysis system not initialized")

            # Execute analysis based on request type
            if len(task.request.symbols) == 1:
                # Single company analysis
                result = await self.analysis_system.analyze_company(task.request.symbols[0])
            else:
                # Portfolio analysis
                result = await self.analysis_system.analyze_portfolio(task.request.symbols)

            # Mark as completed
            await self.update_task_status(task_id, AnalysisStatus.COMPLETED, 100.0, "Analysis completed")

            execution_time = (datetime.now() - start_time).total_seconds()
            task_result = TaskResult(
                success=True,
                result=result,
                execution_time=execution_time
            )

            self.task_results[task_id] = task_result
            return task_result

        except Exception as e:
            self.logger.error(f"Task {task_id} failed: {str(e)}")
            await self.update_task_status(task_id, AnalysisStatus.FAILED, None, f"Analysis failed: {str(e)}")

            execution_time = (datetime.now() - start_time).total_seconds()
            task_result = TaskResult(
                success=False,
                error=str(e),
                execution_time=execution_time
            )

            self.task_results[task_id] = task_result
            return task_result

    async def cancel_task(self, task_id: str) -> bool:
        """Cancel a task"""
        task = await self.get_task(task_id)
        if not task:
            return False

        if task.status in [AnalysisStatus.COMPLETED, AnalysisStatus.FAILED, AnalysisStatus.CANCELLED]:
            return False

        await self.update_task_status(task_id, AnalysisStatus.CANCELLED, None, "Task cancelled")
        return True

    async def get_active_tasks(self) -> List[AnalysisTask]:
        """Get all active tasks"""
        async with self._lock:
            return [
                task for task in self.tasks.values()
                if task.status in [AnalysisStatus.PENDING, AnalysisStatus.RUNNING]
            ]

    async def cleanup_old_tasks(self, days: int = 7):
        """Clean up old tasks"""
        cutoff_date = datetime.now().timestamp() - (days * 24 * 60 * 60)

        async with self._lock:
            tasks_to_remove = [
                task_id for task_id, task in self.tasks.items()
                if task.created_at.timestamp() < cutoff_date
                and task.status in [AnalysisStatus.COMPLETED, AnalysisStatus.FAILED]
            ]

            for task_id in tasks_to_remove:
                del self.tasks[task_id]
                if task_id in self.task_results:
                    del self.task_results[task_id]

        self.logger.info(f"Cleaned up {len(tasks_to_remove)} old tasks")


# Global task manager instance
task_manager = TaskManager()