# tests/test_dc_tdx/__init__.py
# -*- coding: utf-8 -*-
"""
test_dc_tdx - dc_tdx模块测试包
"""
from .test_code_utils import (
    test_clean_code,
    test_is_index_code,
    test_get_market_code,
    test_get_code_type
)
from .test_local_reader import (
    test_local_reader_init,
    test_read_daily,
    test_read_minute,
    test_read_block
)
from .test_remote_quotes import (
    test_remote_connect,
    test_get_hist_kline,
    test_get_xdxr_data,
    test_get_index_data,
    test_get_f10_info
)
from .test_financial_report import test_download_and_parse

__all__ = [
    "test_clean_code",
    "test_is_index_code",
    "test_get_market_code",
    "test_get_code_type",
    "test_local_reader_init",
    "test_read_daily",
    "test_read_minute",
    "test_read_block",
    "test_remote_connect",
    "test_get_hist_kline",
    "test_get_xdxr_data",
    "test_get_index_data",
    "test_get_f10_info",
    "test_download_and_parse"
]