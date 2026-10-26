import logging
import os
from logging.handlers import TimedRotatingFileHandler  # 改用标准库

class Logger:
    def __init__(
        self,
        ext_handler: logging.Handler=None,
        name: str = "coc_log",
        log_dir: str = os.path.expanduser("~/logs"),
        console_level: int = logging.DEBUG,
        file_level: int = logging.DEBUG,
        backup_count: int = 24 * 7,
        encoding: str = "utf-8",
    ):
        self.ext_handler = ext_handler
        self.name = name
        self.log_dir = log_dir
        self.console_level = console_level
        self.file_level = file_level
        self.backup_count = backup_count
        self.encoding = encoding

        self.logger = self._init_logger()

    def _init_logger(self) -> logging.Logger:
        logger = logging.getLogger(self.name)
        logger.setLevel(logging.DEBUG)
        logger.propagate = False

        # 清空旧处理器
        logger.handlers.clear()

        # 创建日志目录
        os.makedirs(self.log_dir, exist_ok=True)
        log_file = os.path.join(self.log_dir, f"{self.name}.log")

        # 文件格式
        file_fmt = logging.Formatter(
            "%(asctime)s - %(levelname)s - %(module)s.%(funcName)s:%(lineno)d - %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S"
        )

        # 控制台格式
        console_fmt = logging.Formatter(
            "%(asctime)s - %(levelname)s - %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S"
        )

        # ★★★ 关键改动：使用标准库的 TimedRotatingFileHandler ★★★
        # 标准库的 Handler 在多线程下是安全的
        file_handler = TimedRotatingFileHandler(
            filename=log_file,
            when="H",           # 每小时滚动
            interval=1,
            backupCount=self.backup_count,
            encoding=self.encoding,
            utc=False
        )
        # 设置日志文件后缀格式
        file_handler.suffix = "%Y-%m-%d_%H.log"
        file_handler.setLevel(self.file_level)
        file_handler.setFormatter(file_fmt)
        # 控制台 handler（线程安全）
        console_handler = logging.StreamHandler()
        console_handler.setLevel(self.console_level)
        console_handler.setFormatter(console_fmt)

        logger.addHandler(file_handler)
        logger.addHandler(console_handler)
        if self.ext_handler:
            logger.addHandler(self.ext_handler)
        return logger

    def get_logger(self) -> logging.Logger:
        return self.logger


# 全局日志实例
logger = Logger().get_logger()

if __name__ == '__main__':
    logger.debug("debug")
    logger.info("info")
    logger.warning("warning")
    logger.error("error")