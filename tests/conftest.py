# -*- coding: utf-8 -*-
"""
conftest.py - dc_tdx测试全局配置/夹具
"""
import pytest
from pathlib import Path
from main_xq.dc.dc_tdx import TdxLocalReader, TdxRemoteQuotes
from main_xq.dc.utils.code_utils import (
    clean_code, is_index_code, get_market_code, get_code_type
)

# ===================== 全局测试配置 =====================
@pytest.fixture(scope="session")
def test_config():
    """全局测试配置"""
    return {
        "tdxdir": "C:/MySAS/TDX",  # 替换为你的通达信实际目录
        "test_stock_codes": ["600177", "000001", "920001"],
        "test_index_codes": ["000001", "399001", "899050"],
        "date_range": {
            "begin": "2024-01-01",
            "end": "2024-12-31"
        },
        "retry_times": 2,
        "report_date": "2023-12-31"  # 已发布的财报日期
    }

# ===================== 测试夹具（复用对象） =====================
@pytest.fixture(scope="module")
def local_reader(test_config):
    """本地读取器夹具（模块级复用）"""
    reader = TdxLocalReader(tdxdir=test_config["tdxdir"])
    yield reader

@pytest.fixture(scope="module")
def remote_quotes(test_config):
    """远程行情客户端夹具（模块级复用）"""
    quotes = TdxRemoteQuotes(retry=test_config["retry_times"])
    yield quotes
    # 测试结束后断开连接
    quotes.disconnect()

# ===================== 通用工具夹具 =====================
@pytest.fixture(scope="session")
def code_utils():
    """代码工具函数夹具"""
    return {
        "clean_code": clean_code,
        "is_index_code": is_index_code,
        "get_market_code": get_market_code,
        "get_code_type": get_code_type
    }