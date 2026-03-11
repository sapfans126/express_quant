# -*- coding: utf-8 -*-
"""
test_financial_report.py - 财务报告解析测试
"""
import pytest
import pandas as pd
from src.data.dc_tdx import TdxFinancialReport

def test_download_and_parse(test_config):
    """测试财报下载与解析"""
    df_report = TdxFinancialReport.download_and_parse(
        rpt_date=test_config["report_date"]
    )
    if df_report is not None:
        assert isinstance(df_report, pd.DataFrame)
        assert len(df_report) > 0
        assert "code" in df_report.columns
        assert "report_date" in df_report.columns
        # 验证重复列名已处理
        assert "财务费用A" in df_report.columns
        assert "归属于母公司所有者的净利润A" in df_report.columns
    else:
        pytest.skip(f"{test_config['report_date']} 财报未发布/下载失败，跳过测试")