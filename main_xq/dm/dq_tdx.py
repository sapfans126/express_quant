# -*- coding: utf-8 -*-
"""
通达信数据查询模块 (Database Query)
支持 import main_xq.dm.dq_tdx as dq
"""
import datetime
from typing import List, Dict, Optional
import pandas as pd
from base import AdjustMode, normalize_stock_code,normalize_stock_codes
from main_xq.dm.dba import db_connector

from main_xq.utils.logger import get_logger_for_current_module
logger = get_logger_for_current_module(__file__)

# ======================  分类/板块成份股  ======================
# A股股票清单
def codes_list_query(table: str = "codes_list") -> pd.DataFrame:
    """
    查询股票代码列表
    :param table: 表名，默认为 codes_list_query
    :return: 包含股票代码的DataFrame
    """

    sql = f"SELECT * FROM {table}"
    df = db_connector.execute_sql(sql)

    if df is None or (isinstance(df, pd.DataFrame) and df.empty):
        return pd.DataFrame()

    # 如果返回的是DataFrame，直接返回
    if isinstance(df, pd.DataFrame):
        return df

    # 如果返回的是列表，转换为DataFrame
    if isinstance(df, list) and df:
        # 假设第一行是数据，需要获取列名
        # 这里需要根据实际情况调整
        return pd.DataFrame(df)

    return pd.DataFrame()


#  股票基本信息
def basic_info_select(code: str, table: str = "as_basic_info") -> pd.DataFrame:
    # sql = """
    #     SELECT code, name, industry, listing_date, issue_price,
    #            total_share, float_share, marketCap, floatCap
    #     FROM {} WHERE code = :code
    # """.format(table)
    # data = db_connector.execute_sql(sql, {"code": code})
    #    return {}
    # cols = ["code", "name", "industry", "listing_date", "issue_price",
    #         "total_share", "float_share", "marketCap", "floatCap"]
    # return dict(zip(cols, data[0]))

    # 格式化代碼
    # _code = normalize_stock_code(code)
    _code = code
    if _code is None:
        logger.error(f"原始代码：{code}，股票代码标准化失败!")
        return pd.DataFrame()

    sql = """
        SELECT * FROM {} WHERE code = %s
    """.format(table)

    df_data = db_connector.read_sql_to_df(sql=sql, params=(code,))

    if df_data is None or len(df_data) == 0:
        return pd.DataFrame()
    return df_data


def listing_date_get(code: str, table: str = "as_basic_info") -> Optional[datetime.date]:

    # 格式化代碼
    # _code = normalize_stock_code(code)
    _code = code
    if _code is None:
        logger.error(f"原始代码：{code}，股票代码标准化失败!")
        return None

    df_info = basic_info_select(code=_code, table=table)

    if df_info is None or len(df_info) == 0 or 'listing_date' not in df_info.columns:
        logger.debug(f"股票 {_code}: 未找到基本信息或缺少 listing_date 列")
        return None

    listing_date = df_info['listing_date'].iloc[0]

    if pd.isna(listing_date):
        logger.debug(f"股票 {_code}: listing_date 为空")
        return None

    try:
        return pd.to_datetime(listing_date).date()
    except (ValueError, TypeError) as e:
        logger.warning(f"股票 {_code}: 日期转换失败 - {listing_date}, 错误: {e}")
        return None


def basic_info_all(table: str = "as_basic_info") -> pd.DataFrame:
    sql = f"SELECT * FROM {table}"
    return db_connector.read_sql_to_df(sql)

# ==================== 行情类信息 ====================
def xdxr_info_query(
    codes_list: list,
    table_name: str = 'as_xdxr',
    batch_size: int = 1000  # 每批1000个，绝对安全
) -> pd.DataFrame:
    """
    批量查询分红送股/除权除息信息，自动分批，无长度限制
    """
    if not codes_list:
        logger.warning("股票代码列表为空")
        return pd.DataFrame()

    codes_normalize = normalize_stock_codes(codes_list)

    # 取出【有效标准化后的代码列表】
    _codes_list = codes_normalize["codes_list_query"]
    if _codes_list is None or len(_codes_list)==0:
        logger.warning("没有有效股票代码，全部无法解析")
        return pd.DataFrame()

    # 自动去重
    _codes_list = list(set(_codes_list))
    df_list = []

    try:
        # 自动分批，避免超长列表
        for i in range(0, len(_codes_list), batch_size):
            batch_codes = _codes_list[i:i+batch_size]
            placeholders = ", ".join(["%s"] * len(batch_codes))

            sql = f"""
                SELECT * 
                FROM {table_name} 
                WHERE code IN ({placeholders})
                ORDER BY code, date DESC
            """

            df_batch = db_connector.read_sql_to_df(sql, params=tuple(batch_codes))
            if not df_batch.empty:
                df_list.append(df_batch)

        # 合并结果
        df_final = pd.concat(df_list, ignore_index=True) if df_list else pd.DataFrame()
        logger.info(f"分红资料查询完成，共 {len(df_final)} 笔")
        return df_final

    except Exception as e:
        logger.error(f"查询失败: {e}")
        return pd.DataFrame()

def xdxr_last_record_get(
    code: str,
    table_name: str = 'as_xdxr'
) -> pd.DataFrame:
    """
    从 as_xdxr 获取某只股票的最后一笔（最新）除权除息记录

    :param code: 股票代码，例如 '000858.SZ'
    :param table_name: 除权除息表名，默认 'as_xdxr'
    :return: 最后一条记录的 DataFrame，无数据则返回空DataFrame
    """
    # 格式化代碼
    # _code = normalize_stock_code(code)
    _code = code
    if _code is None:
        logger.error(f"原始代码：{code}，股票代码标准化失败!")
        return pd.DataFrame()

    try:
        sql = f"""
            SELECT *
            FROM {table_name}
            WHERE code = %s
            ORDER BY date DESC  -- 这里改成 date
            LIMIT 1
        """
        df = db_connector.read_sql_to_df(sql, params=(_code,))

        if df is None or len(df) == 0:
            # logger.info(f"{_code} 无除权除息记录")
            return pd.DataFrame()

        # logger.info(f"{_code} 最后一笔除权息日期：{df.iloc[0]['date']}")  # 这里改成 date
        return df

    except Exception as e:
        logger.error(f"查询 {_code} 最后一笔除权息失败：{str(e)}")
        return pd.DataFrame()


def xdxr_last_date_get(code: str, table_name: str = 'as_xdxr') -> datetime.date | None:
    """
    从 as_xdxr 获取最后一笔除权除息记录，并返回除权日期
    :param code: 股票代码
    :param table_name: 除权除息表名，默认 'as_xdxr'
    :return: 最后除权日期 date，无数据返回 None
    """
    df_last = xdxr_last_record_get(code, table_name=table_name)

    if df_last.empty:
        return None

    # 改成 .date()  返回纯日期类型
    last_date = pd.to_datetime(df_last['date'].iloc[0]).date()

    return last_date


def hist_price_select(
    code: str,
    from_time=None,
    end_time=None,
    adjust: AdjustMode = AdjustMode.NONE,
    table: str = None
) -> pd.DataFrame:
    """
    从数据库读取股票历史K线数据
    自动根据 adjust 复权类型匹配表名：as_hist_price_d_{后缀}
    :param code: 股票代码
    :param from_time: 起始时间 (date/datetime/str)，None=不限制
    :param end_time: 结束时间 (date/datetime/str)，None=不限制
    :param adjust: 复权类型
    :param table: 手动指定表名，优先级最高
    :return: DataFrame，按 datetime 升序排列，无数据返回空DF
    """
    # 格式化代碼
    # _code = normalize_stock_code(code)
    _code = code
    if _code is None:
        logger.error(f"原始代码：{_code}，股票代码标准化失败!")
        return pd.DataFrame()

    # ---------------- 1. 自动匹配表名（与 save 完全一致） ----------------
    if table is None:
        suffix_map = {
            AdjustMode.NONE: "na",
            AdjustMode.BACK: "ba",
            AdjustMode.FRONT: "fa",
            AdjustMode.PBA: "pba",
            AdjustMode.RBA: "rba",
            AdjustMode.PFA: "pfa",
            AdjustMode.RFA: "rfa"
        }
        adjust_suffix = suffix_map.get(adjust, "na")
        table = f"as_hist_price_d_{adjust_suffix}"

    # if not db_connector.table_exists(table):
    #     return pd.DataFrame()

    # ---------------- 2. 构建条件 SQL ----------------
    base_sql = f"SELECT * FROM {table} WHERE code = :code"
    params = {"code": _code}

    # 时间条件（兼容 str / date / datetime）
    if from_time is not None:
        base_sql += " AND datetime >= :from_time"
        params["from_time"] = pd.to_datetime(from_time)
    if end_time is not None:
        base_sql += " AND datetime <= :end_time"
        params["end_time"] = pd.to_datetime(end_time)

    base_sql += " ORDER BY datetime ASC"

    # ---------------- 3. 查询并返回 DF ----------------
    try:
        df = db_connector.read_sql_to_df(base_sql, params=params)
        if df.empty:
            logger.info(f"【{table}】{_code} 无价格数据")
        return df
    except Exception as e:
        logger.error(f"查询 {_code} 价格失败：{str(e)}")
        return pd.DataFrame()


# ==================== 使用示例 ====================
if __name__ == "__main__":
    # codes_list = codes_list_query()
    # print(codes_list)

    # df_basic_info = basic_info_select(code='000156.SZ')
    # print(df_basic_info)
    #
    # l_date = listing_date_get(code='000156.SZ')
    # print(l_date)

    df_xd_xr = xdxr_info_query(['000156.SZ', '600985.SH'])
    print(df_xd_xr)