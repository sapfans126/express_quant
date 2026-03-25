# -*- coding: utf-8 -*-
"""
dc 模块：通达信数据读取与行情获取核心模块
"""
# 对外暴露核心类，简化外部导入（如：from main_xq.dc import TdxLocalReader）
from .dc_tdx import TdxLocalReader, TdxRemoteQuotes, TdxFinancialReport
from .utils.code_utils import (
    clean_code, is_index_code, get_market_code, get_code_type, standardize_code
)

__all__ = [
    # 核心类
    "TdxLocalReader",
    "TdxRemoteQuotes",
    "TdxFinancialReport",
    # 通用工具函数
    "clean_code",
    "is_index_code",
    "get_market_code",
    "get_code_type",
    "standardize_code"
]