# -*- coding: utf-8 -*-
"""
test_local_reader.py - 本地数据读取器测试
"""
import pytest
import pandas as pd


def test_local_reader_init(local_reader):
    """测试本地读取器初始化"""
    assert local_reader is not None
    assert local_reader.tdxdir is not None
    assert local_reader.reader is not None


def test_read_daily(local_reader, test_config):
    """测试日线读取"""
    # 测试有数据的股票（以600177为例）
    df = local_reader.read_daily(
        symbol="600177",
        begin=test_config["date_range"]["begin"],
        end=test_config["date_range"]["end"]
    )
    if df is not None:
        # 验证数据结构
        assert isinstance(df, pd.DataFrame)
        assert len(df) > 0
        assert "code" in df.columns
        assert "datetime" in df.columns
        assert "close" in df.columns
        assert "pctChg" in df.columns
        # 验证时间范围
        assert df["datetime"].min() >= pd.to_datetime(test_config["date_range"]["begin"])
        assert df["datetime"].max() <= pd.to_datetime(test_config["date_range"]["end"])
    else:
        pytest.skip("本地无600177数据，跳过测试")


def test_read_minute(local_reader):
    """测试分钟线读取"""
    # 测试1分钟线
    df_1min = local_reader.read_minute(symbol="600177", frequency="1min")
    if df_1min is not None:
        assert isinstance(df_1min, pd.DataFrame)
        assert "code" in df_1min.columns
        assert "datetime" in df_1min.columns
    else:
        pytest.skip("本地无600177 1分钟线数据，跳过测试")

    # 测试5分钟线
    df_5min = local_reader.read_minute(symbol="600177", frequency="5min")
    if df_5min is not None:
        assert isinstance(df_5min, pd.DataFrame)
    else:
        pytest.skip("本地无600177 5分钟线数据，跳过测试")


def test_read_block(local_reader):
    """测试板块数据读取"""
    # 测试概念板块
    df_gn = local_reader.read_block(block_type="block_gn")
    if df_gn is not None:
        assert isinstance(df_gn, pd.DataFrame)
        assert len(df_gn) > 0
    else:
        pytest.skip("本地无概念板块数据，跳过测试")

    # 测试自定义板块
    df_custom = local_reader.read_customer_blocks()
    if df_custom is not None:
        assert isinstance(df_custom, pd.DataFrame)
