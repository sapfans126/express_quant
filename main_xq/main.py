# -*- coding: utf-8 -*-
"""
✅ 量化系统 - 唯一主入口文件
所有运行都从这里启动！
"""
import sys
from pathlib import Path

# 1. 设置路径
PROJECT_ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(PROJECT_ROOT))

# 2. 初始化日志（必须在导入其他模块前）
from main_xq.utils.logger import init_logger, get_logger

# 初始化日志系统
init_logger(is_debug=True)

# 获取主入口的logger
logger = get_logger("__main__")

# 3. 启动信息
if __name__ == "__main__":
    logger.info("=" * 60)
    logger.info("🚀 量化交易系统启动成功")
    logger.info(f"📁 项目根目录: {PROJECT_ROOT}")
    logger.info("=" * 60)

    # 4. 加载业务模块
    logger.info("🔽 开始加载系统模块...")

    # from main_xq.base.security_type import SECURITY_CODE_MAP, MARKET
    # from main_xq.dm.mytdx.reader.reader import TdxReader
    #
    # # 可选：测试导入的模块
    # logger.info(f"✅ 常量模块加载成功，市场类型: {[m.value for m in MARKET]}")
    # logger.info(f"✅ TDX读取器加载成功")

    # 5. 完成
    logger.info("✅ 系统初始化全部完成！")
