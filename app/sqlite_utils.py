"""SQLite 并发写入辅助函数。"""

import threading
import time
from typing import Callable, TypeVar

from sqlalchemy.exc import OperationalError

from app.models import db

T = TypeVar('T')

#FIX 20260921 串行化应用进程内的服务配置写入，减少 SQLite 写锁竞争  yyj
SQLITE_WRITE_LOCK = threading.RLock()


def _is_sqlite_locked_error(error: Exception) -> bool:
    return 'database is locked' in str(error).lower()


def run_sqlite_write(
    operation: Callable[[], T],
    attempts: int = 5,
    delay: float = 0.2
) -> T:
    """执行 SQLite 写事务，遇到锁冲突时回滚并重试整个事务。"""
    last_error = None

    #FIX 20260921 重试完整写事务并串行化服务相关写入  yyj
    with SQLITE_WRITE_LOCK:
        for attempt in range(attempts):
            try:
                return operation()
            except OperationalError as error:
                if not _is_sqlite_locked_error(error):
                    raise

                last_error = error
                db.session.rollback()
                if attempt + 1 < attempts:
                    time.sleep(delay * (attempt + 1))

    raise last_error
