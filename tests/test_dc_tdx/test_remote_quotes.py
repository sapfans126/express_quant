# -*- coding: utf-8 -*-
"""
test_remote_quotes.py - 远程行情客户端测试
"""
import pytest
import pandas as pd


def test_remote_connect(remote_quotes):
    """测试远程连接（兼容模式）"""
    assert remote_quotes.connect() is True


def test_get_hist_kline(remote_quotes, test_config):
    """测试股票K线获取"""
    # 测试前复权K线
    df_qfq = remote_quotes.get_hist_kline(
        symbol="600177",
        adjust="qfq",
        begin=test_config["date_range"]["begin"],
        end=test_config["date_range"]["end"]
    )
    if df_qfq is not None:
        assert isinstance(df_qfq, pd.DataFrame)
        assert len(df_qfq) > 0
        assert "code" in df_qfq.columns
        assert "pctChg" in df_qfq.columns
    else:
        pytest.skip("远程获取600177 K线失败，跳过测试")

    # 测试错误场景：指数用股票接口
    df_error = remote_quotes.get_hist_kline(symbol="000001")
    assert df_error is None


def test_get_xdxr_data(remote_quotes):
    """测试除权除息数据"""
    df_xdxr = remote_quotes.get_xdxr_data(symbol="600177")
    if df_xdxr is not None:
        assert isinstance(df_xdxr, pd.DataFrame)
        assert len(df_xdxr) > 0
        assert "code" in df_xdxr.columns
        assert "cash_div" in df_xdxr.columns
    else:
        pytest.skip("未获取到600177除权除息数据，跳过测试")


def test_get_index_data(remote_quotes, test_config):
    """测试指数数据获取"""
    # 测试上证指数
    df_index = remote_quotes.get_index_data(
        index_code="000001",
        market="sh",
        begin=test_config["date_range"]["begin"],
        end=test_config["date_range"]["end"]
    )
    if df_index is not None:
        assert isinstance(df_index, pd.DataFrame)
        assert len(df_index) > 0
        assert "code" in df_index.columns
    else:
        pytest.skip("未获取到上证指数数据，跳过测试")

    # 测试错误场景：股票用指数接口
    df_error = remote_quotes.get_index_data(index_code="600177")
    assert df_error is None


def test_get_f10_info(remote_quotes):
    """测试F10数据获取"""
    df_f10 = remote_quotes.get_f10_info(symbol="600177", item="公司概况")
    if df_f10 is not None:
        assert isinstance(df_f10, pd.DataFrame)
    else:
        pytest.skip("未获取到600177 F10数据，跳过测试")
