# ================ db =============
# 数据库连接字符串（建议从环境变量读取）
import os
import time

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, scoped_session

#========= jwt ===========
SECRET_KEY = os.getenv("COC_JWT_SECRET_KEY", "")
ALGORITHM = "HS256"
EXPIRE_SEC = 60 * 60 * 24
DEFAULT_ROOM_NAME = "双服打鱼房间"
#需要填写 后端api的域名地址
BACK_END_DOMAIN = os.getenv("COC_BACK_END_DOMAIN", "")

#云手机密钥
#======== cloud phone =======
access_key_id = os.getenv("COC_CLOUD_PHONE_ACCESS_KEY_ID", "")
access_key_secret = os.getenv("COC_CLOUD_PHONE_ACCESS_KEY_SECRET", "")

# ================== db ==============
#使用psql
DATABASE_URL = os.getenv("COC_DATABASE_URL", "")

if DATABASE_URL:
    # 创建全局 engine
    engine = create_engine(DATABASE_URL, echo=False, pool_size=20, max_overflow=20, pool_recycle=240, pool_pre_ping=True)
else:
    engine = None

# 创建 Session 工厂
SessionFactory = sessionmaker(bind=engine)

# 创建线程安全的 Session
session = scoped_session(SessionFactory)

# 仅成员房间的每个人可用时常(秒)
MEMBER_ONLY_USE_HOURS = 3

INIT_SCRCPY_LINK = False


# ============= 计数器 ============
class RateLimiter:
    @classmethod
    def incr(cls, key, redis_cli, window_sec=10):
        now = time.time()
        pipe = redis_cli.pipeline()
        # 删除10秒前数据
        pipe.zremrangebyscore(key, 0, now - window_sec)
        # 插入当前时间戳
        pipe.zadd(key, {f"{now:.6f}": now})
        pipe.expire(key, window_sec + 2)
        pipe.execute()

    @classmethod
    def get_count(cls, key, redis_cli, window_sec=10) -> int:
        now = time.time()

        redis_cli.zremrangebyscore(key, 0, now - window_sec)

        return redis_cli.zcard(key)
    
# 超时计时器线程池
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FutureTimeoutError

# 全局唯一复用线程池，整个项目共用
_GLOBAL_TIMEOUT_EXECUTOR = ThreadPoolExecutor(max_workers=1)

# 全局统一超时异常
class OperationTimeoutError(Exception):
    pass


def run_with_timeout(func, timeout_sec: float, *args, **kwargs):
    """使用独立的线程池，避免全局状态问题"""
    start_time = time.time()

    # 每个调用使用独立的线程池
    with ThreadPoolExecutor(max_workers=1) as executor:
        try:
            future = executor.submit(func, *args, **kwargs)
            return future.result(timeout=timeout_sec)
        except FutureTimeoutError:
            elapsed = time.time() - start_time
            elapsed_minutes = elapsed / 60
            if elapsed_minutes >= 1:
                time_str = f"{elapsed_minutes:.2f} 分钟 ({elapsed:.2f} 秒)"
            else:
                time_str = f"{elapsed:.2f} 秒"
            raise OperationTimeoutError(
                f"操作超时 {timeout_sec} 秒，"
                f"实际运行 {time_str} 后抛出"
            )
