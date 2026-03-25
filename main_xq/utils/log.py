# main_xq/utils/log.py
import logging
import sys
from pathlib import Path
from logging.handlers import RotatingFileHandler

_initialized = False


def get_project_root():
    """获取项目根目录"""
    return Path(__file__).resolve().parent.parent.parent


def get_module_name_from_file(file_path):
    """
    根据文件路径获取模块名称
    Args:
        file_path: __file__ 变量的值
    Returns:
        模块名，如 'main_xq.base.security_type'
    """
    current_file = Path(file_path).resolve()
    project_root = get_project_root()

    try:
        rel_path = current_file.relative_to(project_root)
        module_name = str(rel_path.with_suffix('')).replace('\\', '.').replace('/', '.')
        return module_name
    except ValueError:
        # 如果不在项目根目录下，返回文件名
        return current_file.stem


def get_logger_for_current_module(file_path):
    """
    为当前模块获取日志器（自动处理直接运行的情况）

    Args:
        file_path: 当前文件的 __file__ 变量

    Returns:
        配置好的 logger 实例

    Usage:
        from main_xq.utils.log import get_logger_for_current_module
        logger = get_logger_for_current_module(__file__)
    """
    module_name = get_module_name_from_file(file_path)
    return get_logger(module_name)


def init_logger(is_debug=True, force=False):
    """初始化日志系统"""
    global _initialized

    if _initialized and not force:
        return logging.getLogger()

    root_dir = get_project_root()
    log_dir = root_dir / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)

    log_file = log_dir / "app.log"

    logger = logging.getLogger()
    logger.handlers.clear()

    level = logging.DEBUG if is_debug else logging.INFO
    logger.setLevel(level)

    formatter = logging.Formatter(
        "%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S"
    )

    console = logging.StreamHandler(sys.stdout)
    console.setLevel(level)
    console.setFormatter(formatter)
    logger.addHandler(console)

    file_handler = RotatingFileHandler(
        filename=log_file,
        maxBytes=10 * 1024 * 1024,
        backupCount=5,
        encoding="utf-8"
    )
    file_handler.setLevel(level)
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)

    _initialized = True

    logger.info(f"日志系统初始化完成，日志文件: {log_file}")

    return logger


def get_logger(name=None):
    """获取日志器"""
    if not _initialized:
        init_logger()

    if name:
        return logging.getLogger(name)
    return logging.getLogger()


# 向后兼容
class _LazyLogger:
    def __getattr__(self, name):
        if not _initialized:
            init_logger()
        return getattr(logging.getLogger(), name)


logger = _LazyLogger()