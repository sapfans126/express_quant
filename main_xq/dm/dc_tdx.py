# dc_tdx.py
"""
通达信数据读取模块 - 函数式 + 自动连接管理
"""
from typing import List, Optional,Dict
import pandas as pd
from datetime import date,datetime,time,timedelta
from concurrent.futures import ThreadPoolExecutor, as_completed
import sys
import threading
from concurrent.futures import ThreadPoolExecutor
from sqlalchemy import text, bindparam
import math
from pandas import DataFrame

from base import AdjustMode, normalize_stock_code
import main_xq.base.code_utils as code_utl

import main_xq.dm.dq_tdx as dq
from main_xq.dm.dba import db_connector
from main_xq.dm.mytdx.my_tq.my_tq import g_tq
from main_xq.utils.logger import get_logger_for_current_module

logger = get_logger_for_current_module(__file__)


# ========================== 分类/板块成份股 =========================
def codes_list(
        source: str = None,
        bsave: bool = True
) -> pd.DataFrame:
    """
    获取股票代码和名称列表（标准化格式）

    参数：
        source: 股票来源
            - 市场代码：1-3位数字，如 '5'（所有A股）、'51'（创业板）、'23'（沪深300）等
            - 板块：其他所有内容（板块代码、板块名称）
            - 默认 None = 全部A股
        bsave: 是否将结果保存到数据库，默认 True

    返回：
        DataFrame，包含两列：
            - code: 标准化股票代码（如 '600519.SH'）
            - name: 股票名称
    """

    # 1. 获取原始数据（返回 list，元素为 {'Code': xxx, 'Name': xxx} 格式）
    if source is None:
        data_list = g_tq.get_stock_list()
        logger.info("获取全部A股股票列表")

    elif source.isdigit() and 1 <= len(source) <= 3:
        data_list = g_tq.get_stock_list(market=source)
        logger.info(f"使用市场代码 '{source}' 获取股票列表")

    else:
        data_list = g_tq.get_stock_list_in_sector(block_code=source)
        logger.info(f"使用板块 '{source}' 获取成分股")

    # 2. 转换为 DataFrame 并统一列名为小写
    df_result = pd.DataFrame(data_list)
    df_result = df_result.rename(columns={'Code': 'code', 'Name': 'name'})

    # 3. 去重
    df_result = df_result.drop_duplicates(subset=['code']).reset_index(drop=True)

    # 4. 保存到数据库（仅当source为None或'5'时才保存）
    if bsave and (source is None or source == '5') and not df_result.empty:
        try:
            save_result = codes_list_save(df_code_list=df_result)
            logger.info(f"保存完成 - 删除: {save_result[0]}, 插入: {save_result[1]}")
        except Exception as e:
            logger.error(f"保存到数据库失败: {e}")

    logger.info(f"成功获取 {len(df_result)} 只股票")
    return df_result


def codes_list_save(
        df_code_list: pd.DataFrame,
        table_name: str = 'as_codes_list',
) -> list:
    """
    保存股票代码列表到数据库（先删除旧记录，再插入新记录）

    Args:
        df_code_list: 包含股票代码的 DataFrame（必须包含 code 列）
        table_name: 目标表名

    Returns:
        list: [deleted_count, inserted_count]
    """
    save_result = [0, 0]

    try:
        # 1. 校验 DataFrame
        if df_code_list.empty:
            logger.warning("DataFrame 为空，无法保存")
            return save_result

        if 'code' not in df_code_list.columns:
            raise ValueError("DataFrame中找不到列: code")

        # 2. 去重处理
        original_count = len(df_code_list)
        df_code_list = df_code_list.drop_duplicates(subset=['code'])
        if len(df_code_list) < original_count:
            logger.info(f"去除重复股票代码: {original_count} -> {len(df_code_list)}")

        # 3. 添加时间戳
        df_code_list['update_time'] = datetime.now()

        # 4. 先删除旧记录 ↓↓↓ 这部分全部替换成下面这段
        # if db_connector.table_exists(table_name):
        codes = df_code_list['code'].unique().tolist()
        batch_size = 500
        total_deleted = 0

        for i in range(0, len(codes), batch_size):
            batch = codes[i:i + batch_size]
            # ✅ SQLAlchemy 正确写法：命名参数 :code
            placeholders = ', '.join([f':code_{j}' for j in range(len(batch))])
            sql = f"DELETE FROM {table_name} WHERE code IN ({placeholders})"

            # ✅ 构造字典参数（必须是字典）
            params = {f'code_{j}': val for j, val in enumerate(batch)}

            # 执行删除
            deleted = db_connector.execute_sql(sql, params)
            total_deleted += deleted if deleted else 0
            logger.debug(f"删除批次 {i // batch_size + 1}: {len(batch)} 条，影响 {deleted} 行")

        logger.info(f"删除 {total_deleted} 条旧记录")
        save_result[0] = total_deleted

        # 5. 插入新数据
        total_inserted = db_connector.batch_insert(df=df_code_list, table_name=table_name)
        save_result[1] = total_inserted

        logger.info(f"成功插入 {total_inserted} 条股票代码到表 {table_name}")
        return save_result

    except Exception as e:
        logger.error(f"保存股票代码失败: {e}")
        raise


def get_sector_list() -> List[str]:
    """获取所有板块列表"""
    return g_tq.get_sector_list()



# ==================== 行情类信息 ====================
def basic_info_update(stock_code: str, bsave: bool = True, force_update:bool=False) \
        -> tuple[pd.DataFrame,list]:
    """
    更新股票基础信息
    :param stock_code: 股票代码
    :param bsave: 是否保存数据
    :param force_update: 是否强制更新
    :return: (dataframe结果, 列表[刪除，插入])
    """
    # 初始更新結果
    update_result = [0,0]

    # 獲取股票信息
    # logger.info(f"正在读取 {stock_code} 的基本数据... ", extra={"terminator": ""})
    stock_info = g_tq.get_stock_info(stock_code) or {}
    more_info = g_tq.get_more_info(stock_code) or {}

    if stock_info is None or len(stock_info)== 0:
        return pd.DataFrame(),update_result

    # 处理上市日期
    listing_date = stock_info.get('J_start')
    if listing_date and listing_date not in (0, '0'):
        try:
            ld = str(int(listing_date)) if isinstance(listing_date, (int, float)) else str(listing_date)
            if len(ld) == 8 and ld.isdigit():
                listing_date = f"{ld[:4]}-{ld[4:6]}-{ld[6:8]}"
            else:
                listing_date = None
        except:
            listing_date = None
    else:
        listing_date = None

    # 处理发行价
    issue_price = more_info.get('IPO_Price')
    if issue_price in (0, '0', None):
        issue_price = None

    info = {
        'code': stock_code,
        'name': stock_info.get('Name'),
        'listing_date': listing_date,
        'delist_date': None,
        'issue_price': issue_price,
        'industry': stock_info.get('rs_hyname'),
        'industry_code': stock_info.get('rs_hycode_sim'),
        'blockzscode': stock_info.get('blockzscode'),
        'total_share': stock_info.get('J_zgb'),
        'float_share': stock_info.get('ActiveCapital'),
        'marketCap': more_info.get('Zsz'),
        'floatCap': more_info.get('Ltsz')
    }

    df_info = pd.DataFrame([info])
    if bsave:
        update_result = basic_info_save(basic_info=df_info,force_save=force_update)

    return df_info,update_result


def basic_info_save(basic_info, table: str = 'as_basic_info',force_save: bool = False):
    """
    保存单只股票信息到数据库（支持 字典 / 单行DataFrame）
    采用先删除再插入的方式，确保数据最新
    :param basic_info: dict 或 pd.DataFrame（单行）
    :param table: 表名
    :param force_save: 是否强制保存
                      - True: 已存在数据 → 先删除再插入
                      - False: 已存在数据 → 不做任何更新
    :return: [删除笔数, 插入笔数]
    """
    # 初始化返回结果 [删除笔数, 插入笔数]
    save_result = [0, 0]

    # ====================== 统一转成 DataFrame ======================
    if isinstance(basic_info, dict):
        df_info = pd.DataFrame([basic_info])
    elif isinstance(basic_info, pd.DataFrame):
        if len(basic_info) > 1:
            # logger.warning(f"basic_info_save 是单笔保存函数，DataFrame包含{len(basic_info_update)}行，只处理第一行数据")
            df_info = basic_info.iloc[[0]].copy()
        else:
            df_info = basic_info.copy()
    else:
        logger.error(f"不支持的数据类型: {type(basic_info)}")
        raise TypeError("只支持 dict 或 pd.DataFrame")

    # 检查必要性
    if df_info.empty or 'code' not in df_info.columns:
        logger.warning("DataFrame为空或缺少code列，跳过保存")
        return save_result

    # 加更新时间
    df_info['updtime'] = datetime.now()

    # 获取股票代码
    code = df_info.iloc[0]['code']

    # ====================== 先判断：数据是否已存在 ======================
    data_exists = False
    # if db_connector.table_exists(table):
    try:
        check_sql = f"SELECT 1 FROM {table} WHERE code = :code LIMIT 1"
        check_result = db_connector.execute_sql(check_sql, {'code': code})
        data_exists = len(check_result) > 0
    except Exception as e:
        logger.error(f"检查数据是否存在失败 - 股票:{code}, 错误:{e}")
        return save_result

    # ====================== 核心逻辑 ======================
    # 1. 数据已存在 + 不强制保存 → 直接跳过
    if data_exists and not force_save:
        # logger.info(f"股票:{code} 数据已存在，force_save=False，跳过更新")
        return save_result

    # 2. 数据已存在 + 强制保存 → 先删除
    if data_exists and force_save:
        try:
            delete_sql = f"DELETE FROM {table} WHERE code = :code"
            result = db_connector.execute_sql(delete_sql, {'code': code})
            save_result[0] = result.rowcount if hasattr(result, 'rowcount') else 1
            # logger.info(f"股票:{code} 强制保存：删除旧数据 {save_result[0]} 条")
        except Exception as e:
            logger.error(f"删除数据失败 - 股票:{code}, 表:{table}, 错误:{e}")
            return save_result

    # 3. 无论是否删除过，最终都插入新数据
    try:
        db_connector.batch_insert(df_info, table, if_exists='append')
        save_result[1] = 1
        # logger.info(f"保存成功 - 股票:{code}, 删除:{save_result[0]}, 插入:{save_result[1]}")
    except Exception as e:
        logger.error(f"插入数据失败 - 股票:{code}, 表:{table}, 错误:{e}")

    return save_result


def basic_info_update_mass(codes: list = None,
                           bsave: bool = True, force_update: bool = False) -> pd.DataFrame:
    """
    批量获取多只股票的基本信息
    :param codes: 股票代码列表，如果为None或空，则调用codes_list_update()获取所有股票代码
    :param bsave: 是否保存到数据库
    :param force_update: 是否强制保存
                    - True: 已存在数据 → 先删除再插入
                    - False: 已存在数据 → 不做任何更新
    :return: 包含多只股票信息的DataFrame
    """
    df_info_list = []

    # 如果stock_codes为空，则获取所有股票代码
    if not codes:
        logger.info("股票代码列表为空，调用codes_list_update()获取所有股票代码")
        try:
            df_codes = codes_list()
            if df_codes.empty or 'code' not in df_codes.columns:
                logger.error("获取股票代码列表失败：DataFrame为空或缺少code列")
                return pd.DataFrame()
            logger.info(f"获取到{len(df_codes)}只股票代码")
        except Exception as e:
            logger.error(f"获取股票代码列表失败: {e}")
            return pd.DataFrame()
        _codes = df_codes['code'].tolist()
    else:
        _codes=codes

    logger.info(f"开始批量获取股票信息，共{len(_codes)}只")

    df_result = pd.DataFrame()
    for code in _codes:
        _info,_ = basic_info_update(code, bsave=bsave, force_update=force_update)
        if _info is None or len(_info) == 0 or 'code' not in _info.columns:
            continue
        # 有效数据，加入列表
        df_info_list.append(_info)

    # 最后合并
    df_result = pd.concat(df_info_list, ignore_index=True) if df_info_list else pd.DataFrame()

    return df_result

def basic_info_update_multi(codes: list = None,
                            bsave: bool = True, force_update:bool=False,
                            max_workers: int = 10) -> pd.DataFrame:
    """
    【多线程并发】批量获取股票基本信息，并支持自动保存到数据库

    功能说明：
    1. 自动获取全部股票代码 或 使用传入的股票代码列表
    2. 多线程并发调用 basic_info_update() 函数抓取单只股票数据
    3. 支持是否自动保存、是否强制更新数据
    4. 最终合并所有结果返回完整 DataFrame

    :param codes: 股票代码列表，如 ['000001', '600000']
                  若为 None 或空列表，则自动从 codes_list() 获取全市场股票代码
    :param bsave: 是否将抓取到的数据保存至数据库
                  True = 保存；False = 仅获取不保存
    :param force_update: 是否强制更新数据（仅在 bsave=True 时生效）
                         True = 数据已存在则先删除再插入
                         False = 数据已存在则跳过不更新
    :param max_workers: 多线程最大并发数，默认 10，根据机器性能调整
    :return: 合并后的所有股票基本信息 DataFrame
             无数据时返回空 DataFrame
    """
    # ===================== 1. 获取股票列表（和你原来完全一样） =====================
    if not codes:
        logger.info("股票代码列表为空，调用codes_list_update()获取所有股票代码")
        try:
            df_codes = codes_list()
            if df_codes.empty or 'code' not in df_codes.columns:
                logger.error("获取股票代码列表失败：DataFrame为空或缺少code列")
                return pd.DataFrame()
            logger.info(f"获取到{len(df_codes)}只股票代码")
        except Exception as e:
            logger.error(f"获取股票代码列表失败: {e}")
            return pd.DataFrame()
        _codes = df_codes['code'].tolist()
    else:
        _codes = codes

    if not _codes:
        logger.warning("无股票代码可处理")
        return pd.DataFrame()

    logger.info(f"【多线程】开始获取，共 {len(_codes)} 只股票，线程数：{max_workers}")

    # ===================== 2. 多线程调用【你现有的函数】 =====================
    df_list = []
    lock = threading.Lock()

    def worker(code):
        try:
            # 直接调用你原来的函数，不重复任何代码！
            df,_ = basic_info_update(code, bsave=bsave, force_update=force_update)

            # 只做判断 + 线程安全加入
            if df is not None and not df.empty and 'code' in df.columns:
                with lock:
                    df_list.append(df)
        except Exception as e:
            logger.error(f"股票 {code} 处理异常: {str(e)}")

    # 启动线程池
    with ThreadPoolExecutor(max_workers) as executor:
        executor.map(worker, _codes)

    # ===================== 3. 合并结果 =====================
    df_result = pd.concat(df_list, ignore_index=True) if df_list else pd.DataFrame()
    logger.info(f"【多线程】处理完成，有效数据：{len(df_result)} 条")

    return df_result


def hist_price(code:str,
               start_time: datetime = None, end_time: datetime=None,
               period :str='1d', adjust : AdjustMode = AdjustMode.NONE
               ) -> pd.DataFrame:
    """
        获取股票历史K线数据（支持复权）
        Parameters
        code : str
            证券代码，格式如：'600000.SH'、'000001.SZ'、'399300.SZ'
        start_time : datetime, optional
            数据开始时间（包含）
            - 若为 None，默认取标的可获取的最早历史时间
            - 格式：datetime(2023, 1, 1)
        end_time : datetime, optional
            数据结束时间（包含）
            - 若为 None，默认取当前最新交易日
            - 格式：datetime(2024, 1, 1)
        period : str, default '1d'
            K 线周期，支持以下类型：
            - 分钟线: '1m', '5m', '10m', '15m', '30m', '1h'
            - 日线:   '1d', '45d'
            - 周线:   '1w'
            - 月线:   '1mon'
            - 季线:   '1q'
            - 年线:   '1y'
        adjust : AdjustMode, default AdjustMode.NONE
            复权模式，通过枚举类指定：
            - AdjustMode.NONE: 不复权（原始价格）
            - AdjustMode.FORWARD: 前复权（常用，最新价为真实市场价）
            - AdjustMode.BACKWARD: 后复权（上市价不变）
        bsave : bool, default False
            是否将获取的数据保存到数据库
            - True: 自动保存为 CSV 文件到指定目录
            - False: 仅返回 DataFrame，不保存

        Returns
             pd.DataFrame
                标准 K 线数据表，列包含：
                - datetime: 时间索引
                - open: 开盘价
                - high: 最高价
                - low: 最低价
                - close: 收盘价
                - volume: 成交量
                - amount: 成交额（可选）

    Raises
    ------
    ValueError
        当 period 传入不支持的周期时抛出
    ConnectionError
        数据源网络请求失败时抛出
    FileNotFoundError
        标的代码不存在时抛出

    Examples
        --------
        # >>> from datetime import datetime
        # >>> df = hist_price(
        # ...     code='600000.SH',
        # ...     start_time=datetime(2023, 1, 1),
        # ...     end_time=datetime(2024, 1, 1),
        # ...     period='1d',
        # ...     adjust=AdjustMode.FORWARD,
        # ...     bsave=False
        # ... )
        # >>> print(df.head())
    """

    # 1. 代码规范化
    try:
        _code = normalize_stock_code(code)
    except ValueError as e:
        raise ValueError(f"股票代码错误: {e}")

    # 2. 周期校验（接口原生支持的周期）
    valid_periods = ['5m', '15m', '30m', '1h', '1d', '1w', '1mon', '1m', '10m', '45d', '1q', '1y']
    period_lower = period.lower()
    if period_lower not in valid_periods:
        raise ValueError(f'周期格式错误：{period}（支持{valid_periods}）')

    # 3. 判断是否为分钟级别数据（需要精确时间）
    minute_periods = ['1m', '5m', '10m', '15m', '30m', '1h']
    is_minute_data = period_lower in minute_periods

    # 4. 时间参数处理
    if start_time is None:
        _start_time = datetime(year=1990,month=1,day=1)
    else:
        _start_time = start_time

    if end_time is None:
        _end_time = datetime.now()
    else:
        _end_time = end_time

    if _start_time > _end_time:
        _start_time = _end_time - timedelta(days=1)

    # if is_minute_data:
    #     # 分钟线：保留时分秒
    #     if start_time is None:
    #         start_param = datetime.now() - timedelta(days=30)
    #     else:
    #         start_param = start_time
    #
    #     if end_time is None:
    #         end_param = datetime.now()
    #     else:
    #         end_param = end_time
    #
    #     start_str_or_dt = start_param
    #     end_str_or_dt = end_param
    # else:
    #     # 日线及以上：只需要日期
    #     if start_time is None:
    #         start_str_or_dt = '1990-01-01'
    #     else:
    #         start_str_or_dt = start_time.strftime('%Y-%m-%d')
    #
    #     if end_time is None:
    #         end_str_or_dt = datetime.now().strftime('%Y-%m-%d')
    #     else:
    #         end_str_or_dt = end_time.strftime('%Y-%m-%d')

    str_start_time = _start_time.strftime("%Y%m%d%H%M%S")
    str_end_time = _end_time.strftime("%Y%m%d%H%M%S")

    # 5. 获取数据（直接传递用户输入的周期）
    try:
        df_price = g_tq.get_market_data(
            stock_list = [_code],
            start_time=str_start_time,
            end_time =str_end_time,
            dividend_type= adjust.value,
            period=period  # 直接使用用户输入的周期
        )
    except Exception as e:
        raise RuntimeError(f"数据获取失败 ({_code}, {period}): {e}")

    if df_price.empty:
        print(f"警告: {_code} 在指定期间无数据")
        return pd.DataFrame()

    # 6. 数据标准化
    # df_price.columns = [col.lower() for col in df_price.columns]

    # 7. 可选保存数据库
    # if bsave:
    #     try:
    #         save_to_database(_code, df_price, period, adjust)
    #     except Exception as e:
    #         print(f"保存到数据库失败: {e}")

    return df_price

def hist_price_save(
    df_price: pd.DataFrame,
    adjust: AdjustMode = AdjustMode.NONE,
    table: str = None
) -> list:
    """
    保存股票历史K线数据到数据库
    自动根据 adjust 复权类型匹配表名：as_hist_price_d_{后缀}
    :param df_price: 历史价格DataFrame，必须包含 code, datetime 列
    :param adjust: 复权类型
    :param table: 手动指定表名，优先级最高
    :return: [删除笔数, 插入笔数]
    """
    total_delete = 0
    total_insert = 0

    # ===================== 自动匹配表名（核心逻辑） =====================
    if table is None:
        # 按你要求映射后缀
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

    # ===================== 空数据/必要列检查 =====================
    if df_price.empty:
        logger.warning(f"{table} 数据为空，跳过保存")
        return [total_delete, total_insert]

    if not all(col in df_price.columns for col in ['code', 'datetime']):
        logger.error(f"{table} 缺少 code 或 datetime 列")
        return [total_delete, total_insert]

    try:
        # ===================== 表存在 → 按code+时间区间删除 =====================
        # if db_connector.table_exists(table):
        df_group = df_price.groupby('code').agg(
            min_dt=('datetime', 'min'),
            max_dt=('datetime', 'max')
        ).reset_index()

        for _, row in df_group.iterrows():
            code = row['code']
            min_dt = row['min_dt']
            max_dt = row['max_dt']

            del_sql = f"""
                DELETE FROM {table}
                WHERE code = :code
                AND datetime BETWEEN :min_dt AND :max_dt
            """
            del_rows = db_connector.execute_sql(del_sql, {
                "code": code,
                "min_dt": min_dt,
                "max_dt": max_dt
            })
            total_delete += del_rows

        logger.info(f"【{table}】删除旧数据 {total_delete} 条")

        # ===================== 批量插入新数据 =====================
        db_connector.batch_insert(df_price, table, if_exists='append')
        total_insert = len(df_price)
        logger.info(f"【{table}】插入新数据 {total_insert} 条")

    except Exception as e:
        logger.error(f"保存失败 {table}: {str(e)}")

    return [total_delete, total_insert]


def hist_price_day_na_update(
        code: str,
        start_time: datetime = None,
        bsave: bool = True
) -> tuple[pd.DataFrame|None, pd.DataFrame | None, list]:
    """
    獲取單隻股票日線歷史價格（無復權），並保存到數據庫

    Args:
        code: 股票代碼
        start_time: 開始時間
        bsave: 是否保存到數據庫

    Returns:
        tuple:
            - df_price (pd.DataFrame | None): 价格数据
            - df_factor (pd.DataFrame | None): 复权因子数据
            - save_result (list): 保存结果 [insert_count, update_count]
    """
    logger.info(f"開始獲取 {code} 日線歷史價格（無復權）")

    # 更新結果
    upd_result = [0,0]

    # 獲取基本資料
    df_basic_info = dq.basic_info_select(code)

    if df_basic_info is None or len(df_basic_info) == 0:
        df_basic_info,_= basic_info_update(code, force_update=True)
        if df_basic_info is None or len(df_basic_info) == 0:
            return None,None,upd_result

    _code = df_basic_info['code'].iloc[0]

    # 取出发行价
    issue_price = df_basic_info.iloc[0]['issue_price']

    # 检查：无效值全部变成 None
    if pd.isna(issue_price) or issue_price is None or float(issue_price) <= 0:
        issue_price = None
    else:
        issue_price = float(issue_price)

    # 取上市日期
    listing_date = df_basic_info.iloc[0]['listing_date']

    # 日期无效：空值、错误格式 → 全部设为 None
    if pd.isna(listing_date) or listing_date is None or listing_date == '':
        logger.warning(f"{code} 上市日期无效，设为 None")
        listing_date = date(year=1991,month=1,day=1)
    else:
        # 转成标准日期格式（安全处理）
        listing_date = pd.to_datetime(listing_date).date()

    # 獲取歷史記錄
    df_hist_price = dq.hist_price_select(code=_code)
    if df_hist_price is None or len(df_hist_price)==0:
        db_last_time = None
        init_adj_factor = 1
    else:
        df_hist_price.sort_values('datetime',inplace=True)
        df_hist_price.reset_index(drop=True,inplace=True)
        # db_last_row = df_hist_price.tail(1)
        db_last_time = df_hist_price['datetime'].iloc[-1]

    # 開始時間
    if start_time:
        if db_last_time:
            if start_time < db_last_time:
                _start_time = start_time
            else:
                _start_time = db_last_time
        else:
            _start_time = datetime.combine(listing_date, datetime.min.time())
            # init_adj_factor = 1
    else:
        if db_last_time:
            _start_time = db_last_time
        else:
            _start_time = datetime.combine(listing_date, datetime.min.time())
            # init_adj_factor = 1

    # 更新除權信息
    try:
        _df_xdxr_all, _xdxr_result = dividend_info_update(stock_code=_code, bsave=True)
    except (ValueError, RuntimeError) as e:
        logger.error(e)
        return None,None,upd_result

    if _df_xdxr_all is None or len(_df_xdxr_all)==0:
        _df_xdxr_all = pd.DataFrame()

    # 獲取全部價格
    try:
        _df_na_all = hist_price(
            code=_code,
            # start_time=start_time,
            period='1d',
            adjust=AdjustMode.NONE
        )
    except Exception as e:
        logger.error(f"獲取 {_code} 歷史價格失敗: {str(e)}")
        return None,None, upd_result

    # 空值判斷
    if _df_na_all is None or len(_df_na_all)==0:
        logger.warning(f"{code} 無歷史價格數據")
        return None, None, upd_result
    else:
        _df_na_all.sort_values(by='datetime',inplace=True)
        _df_na_all.reset_index(drop=True,inplace=True)

    # 分隔新舊數據
    _df_new_price = _df_na_all[_df_na_all['datetime']>=_start_time].copy()
    if _df_new_price is None or len(_df_new_price) == 0:
        return df_hist_price,_df_xdxr_all,upd_result
    _df_new_price.reset_index(drop=True, inplace=True)

    _df_keep_price = df_hist_price[df_hist_price['datetime']<_start_time].copy()
    if _df_keep_price is None or len(_df_keep_price) == 0:
        _df_keep_price = None
        first_pre_close = issue_price
    else:
        _df_keep_price.reset_index(drop=True,inplace=True)
        first_pre_close = _df_keep_price.iloc[-1]['close']

    # 獲取股本信息
    try:
        _df_equity = equity_info(stock_code=_code)
    except Exception as e:
        logger.error(f"獲取 {_code} 股本信息失敗: {str(e)}")
        return None, None, upd_result

    # 确保日期格式并提取日期部分
    _df_new_price['date'] = pd.to_datetime(_df_new_price['datetime']).dt.date
    _df_equity['date'] = pd.to_datetime(_df_equity['datetime']).dt.date

    # 合并股本字段到 _df_new_price
    _df_new_price = _df_new_price.merge(
        _df_equity[['date', 'float_share', 'total_share']],
        on='date',
        how='left'
        )

    # 删除临时日期列
    _df_new_price = _df_new_price.drop('date', axis=1)

    # # first pre_close
    # df_before = _df_na_all[_df_na_all['datetime'] < _start_time]
    # if not df_before.empty:
    #     first_pre_close = df_before.iloc[-1]['close']
    #     last_datetime = df_before.iloc[-1]['datetime']
    # else:
    #     first_pre_close = issue_price

    #计算pre_close（昨日收盘价）
    _df_new_price['pre_close'] = _df_new_price['close'].shift(1)
    # 第一笔资料的pre_close價格
    _df_new_price.loc[_df_new_price.index[0], 'pre_close'] = first_pre_close

    # # 填入股本信息
    # first_time = _df_price.iloc[0]['datetime']
    # float_share_end_time = _df_price.iloc[-1]['datetime']
    # float_share_start_time = float_share_end_time
    # total_share_end_time = float_share_end_time
    # total_share_start_time = total_share_end_time
    # post_float = 0
    # post_total = 0


    for xdxr in _df_xdxr_all.itertuples():
        # # 更新总股本
        # if not math.isnan(xdxr.post_total) and xdxr.post_total > 0:
        #     total_share_start_time = pd.to_datetime(datetime.combine(xdxr.date, time()))
        #     post_total = xdxr.post_total
        #     _df_price.loc[
        #         (_df_price['datetime'] >= total_share_start_time)
        #         & (_df_price['datetime'] <= total_share_end_time),
        #         'total_share'
        #     ] = post_total
        #     total_share_end_time = total_share_start_time -pd.Timedelta(days=1)

        # # 更新流通股本
        # if not math.isnan(xdxr.post_float) and xdxr.post_float > 0:
        #     float_share_start_time = pd.to_datetime(datetime.combine(xdxr.date, time()))
        #     post_float = xdxr.post_float
        #     _df_price.loc[
        #         (_df_price['datetime'] >= float_share_start_time)
        #         & (_df_price['datetime'] <= float_share_end_time),
        #         'float_share'
        #     ] = post_float
        #     float_share_end_time = float_share_start_time -pd.Timedelta(days=1)

        #修正除权日的前收盘价，同花顺、通达信对不复权价格并不修正除权日的昨日收盘价
        if xdxr.type == 1:
            #根据交易时间，找出除权除息的第一个交易日（防止某些股票停牌期间除权除息).
            xdxr_time = pd.to_datetime(datetime.combine(xdxr.date,datetime.min.time()))
            xdxr_day_mask = _df_na_all['datetime'] >= xdxr_time
            xdxr_day_match = _df_na_all.loc[xdxr_day_mask].head(1)
            if not xdxr_day_match.empty:
                xdxr_trade_time = xdxr_day_match['datetime'].iloc[0]
                xdxr_day_item = _df_new_price.query("datetime == @xdxr_trade_time")
                if not xdxr_day_item.empty:
                    idx = xdxr_day_item.index[0]
                    old_pre_close = xdxr_day_item['pre_close'].values[0]
                    new_pre_close = ((old_pre_close - xdxr.cash_div + xdxr.ri_price * xdxr.ri)/
                         (1+xdxr.stock_div+xdxr.ri))
                    _df_new_price.at[idx, 'pre_close'] = new_pre_close  # 回写
            continue

    # 填入其他交易数据
    # 计算换手率
    _df_new_price['turn'] = _df_new_price['volume'] / _df_new_price['float_share']

    # 计算涨跌
    _df_new_price['Chg'] = _df_new_price['close'] - _df_new_price['pre_close']

    # 计算涨幅
    _df_new_price['pctChg'] = _df_new_price['Chg'] / _df_new_price['pre_close'] * 100

    # 计算振幅
    _df_new_price['Amp'] = (_df_new_price['high'] - _df_new_price['low'] )/ _df_new_price['pre_close'] * 100

    # 计算复权因子
    # if init_adj_factor != 1:
    #     pre_adj_factor = init_adj_factor * (1+df_price.loc[0,'pctChg']/100)
    # df_price['factor'] = 1+ df_price['pctChg']/100
    # # 第一行不参与连乘
    # df_price.loc[0,'factor'] = 1
    #
    # # 计算累积乘积，并乘以初始值
    # df_price['AdjFactor'] = init_adj_factor * df_price['factor'].cumprod()
    # # 清理临时列
    # df_price.drop(columns=['factor'], inplace=True)

    # logger.info(f"{code} 獲取完成，共 {len(_df_new_price)} 條數據")

    # 合并新舊
    if _df_keep_price is None or len(_df_keep_price)==0:
        df_na_price = _df_new_price
    else:
        df_na_price = pd.concat([_df_keep_price, _df_new_price], ignore_index=True)

    df_na_price.sort_values('datetime',inplace=True)
    df_na_price.reset_index(drop=True,inplace=True)

    # ===================== 2. 保存到數據庫 =====================
    if bsave:
        try:
            upd_result = hist_price_save(_df_new_price)
            logger.info(f"{code}除權價格保存完成 | 刪除:{upd_result[0]} 條, 插入:{upd_result[1]} 條")
        except Exception as e:
            logger.error(f"{code} 保存失敗: {str(e)}")

    return df_na_price,_df_xdxr_all,upd_result

# 根据除权数据，计算更新通达信股票的日历史价格(前复权:价格复权法)
def hist_price_day_pfa_calc(
        code: str,
        df_na_all:pd.DataFrame=None,
        df_xdxr_all:pd.DataFrame=None,
        start_time: datetime = None,
        bsave: bool = True)->tuple[pd.DataFrame|None, list]:

    upd_result = [0,0]

    # 获取不复权价格
    if df_na_all is None or len(df_na_all)==0:
        _df_na_all = dq.hist_price_select(code=code)
        if _df_na_all is None or len(_df_na_all)==0:
            upd_result[0] = -3
            return None,upd_result
    else:
        _df_na_all = df_na_all.copy()

    _df_na_all.sort_values('datetime',inplace=True)
    _df_na_all.reset_index(drop=True,inplace=True)

    listing_time = _df_na_all.iloc[0]['datetime']

    # 获取在数据库中的历史复权资料
    _df_hist_pfa = dq.hist_price_select(code=code,adjust=AdjustMode.PFA)
    if _df_hist_pfa is None or len(_df_hist_pfa)==0:
        _start_time = listing_time
    else:
        _df_hist_pfa.sort_values('datetime',inplace=True)
        _df_hist_pfa.reset_index(drop=True,inplace=True)
        _start_time = _df_hist_pfa['datetime'].iloc[-1]

    # 處理開始時間
    if start_time:
        if start_time < _start_time:
            _start_time = start_time

    if _start_time < listing_time:
        _start_time = listing_time

    # 更新除權信息
    if df_xdxr_all is None or len(df_xdxr_all)==0:
        try:
            _df_xdxr_all, _xdxr_result = dividend_info_update(stock_code=code, bsave=True)
        except (ValueError, RuntimeError) as e:
            logger.error(e)
            return None,upd_result
    else:
        _df_xdxr_all = df_xdxr_all.copy()

    # 沒有除權信息，無需復權
    if _df_xdxr_all is None or len(_df_xdxr_all) ==0 :
        _df_new_pfa = _df_na_all[_df_na_all['datetime']>=_start_time].copy()
        if bsave:
            _,upd_result = hist_price_save(_df_new_pfa,AdjustMode.PFA)
        return _df_new_pfa,upd_result

    _df_xdxr_all.sort_values(by='date',inplace=True)
    _df_xdxr_all.reset_index(drop=True,inplace=True)

    lastest_ex_date = _df_xdxr_all['date'].max()
    lastest_ex_time = datetime.combine(lastest_ex_date,datetime.min.time())

    # 给定的start_time在最后的除权除息日之前,前复权需要从上市日期开始全部重新计算
    if lastest_ex_time > _start_time:
        _start_time = listing_time
        _df_new_pfa = _df_na_all.copy()
    # 否则只要copy 除权价格
    else:
        _df_new_pfa = _df_na_all[_df_na_all['datetime']>=_start_time].copy()
        if bsave:
             _,upd_result = hist_price_save(_df_new_pfa,AdjustMode.PFA)
        return _df_new_pfa,upd_result

    # 进行除权计算
    _df_new_pfa = _df_na_all[_df_na_all['datetime']>=_start_time].copy()
    price_fields = ['open', 'high','low','close']
    init_pre_close = _df_new_pfa.iloc[0]['pre_close'] #这实际上是发行价

    for xdxr in _df_xdxr_all.itertuples():
        _ex_time = pd.to_datetime(xdxr.date)
        _ex_xdxr_rows = _df_new_pfa['datetime'] < _ex_time

        # 对除权日之前的价格进行复权处理
        _df_new_pfa.loc[_ex_xdxr_rows, price_fields] = \
            ((_df_new_pfa.loc[_ex_xdxr_rows, price_fields] - xdxr.cash_div + xdxr.ri_price * xdxr.ri)
             /(1+ xdxr.stock_div+xdxr.ri))

        # 对初始pre_close 进行复权处理
        init_pre_close = ((init_pre_close - xdxr.cash_div + xdxr.ri_price * xdxr.ri)/
                          (1+ xdxr.stock_div+xdxr.ri))

    # 重新计算pre_close
    _df_new_pfa['pre_close'] = _df_new_pfa['close'].shift(1)
    _df_new_pfa.loc[0,'pre_close']=init_pre_close

    # 计算涨跌
    _df_new_pfa['Chg'] = _df_new_pfa['close'] - _df_new_pfa['pre_close']

    # 计算涨幅
    _df_new_pfa['pctChg'] = _df_new_pfa['Chg'] / _df_new_pfa['pre_close'] * 100

    # 计算振幅
    _df_new_pfa['Amp'] = (_df_new_pfa['high'] - _df_new_pfa['low'] )/ _df_new_pfa['pre_close'] * 100

    if bsave:
        _, upd_result = hist_price_save(_df_new_pfa, AdjustMode.PFA)

    return _df_new_pfa, upd_result


# 根据除权数据，计算更新通达信股票的日历史价格(后复权:价格复权法)
def hist_price_day_pba_calc(
        code: str,
        df_na_all:pd.DataFrame=None,
        df_xdxr_all:pd.DataFrame=None,
        start_time: datetime = None,
        bsave: bool = True)->tuple[pd.DataFrame|None, list]:

    upd_result = [0,0]

    # 获取不复权价格
    if df_na_all is None or len(df_na_all)==0:
        _df_na_all = dq.hist_price_select(code=code)
        if _df_na_all is None or len(_df_na_all)==0:
            upd_result[0] = -3
            return None,upd_result
    else:
        _df_na_all = df_na_all.copy()

    _df_na_all.sort_values('datetime',inplace=True)
    _df_na_all.reset_index(drop=True,inplace=True)

    listing_time = _df_na_all.iloc[0]['datetime']

    # 获取在数据库中的历史复权资料
    _df_hist_pba = dq.hist_price_select(code=code,adjust=AdjustMode.PBA)
    if _df_hist_pba is None or len(_df_hist_pba)==0:
        _start_time = listing_time
    else:
        _df_hist_pba.sort_values('datetime',inplace=True)
        _df_hist_pba.reset_index(drop=True,inplace=True)
        _start_time = _df_hist_pba['datetime'].iloc[-1]

    # 處理開始時間
    if start_time:
        if start_time < _start_time:
            _start_time = start_time

    if _start_time < listing_time:
        _start_time = listing_time

    # 更新除權信息
    if df_xdxr_all is None or len(df_xdxr_all)==0:
        try:
            _df_xdxr_all, _xdxr_result = dividend_info_update(stock_code=code, bsave=True)
        except (ValueError, RuntimeError) as e:
            logger.error(e)
            return None,upd_result
    else:
        _df_xdxr_all = df_xdxr_all.copy()

    # 沒有除權信息，無需復權
    if _df_xdxr_all is None or len(_df_xdxr_all) ==0 :
        _df_new_pba = _df_na_all[_df_na_all['datetime']>=_start_time].copy()
        if bsave:
            _,upd_result = hist_price_save(_df_new_pba,AdjustMode.PBA)
        return _df_new_pba,upd_result

    _df_xdxr_all.sort_values(by='date',ascending=False,inplace=True)
    _df_xdxr_all.reset_index(drop=True,inplace=True)

    # 进行除权计算
    _df_new_pba = _df_na_all[_df_na_all['datetime'] >= _start_time].copy()
    # #已经是最新资料了,无需复权
    # if _df_new_pba is None or len(_df_new_pba)==0:
    #     return None,upd_result

    _df_new_pba.reset_index(drop=True,inplace=True)

    # 准备第一笔资料的pre_close
    first_pre_close = _df_new_pba.iloc[0]['pre_close']
    first_pre_close_time = _df_na_all[_df_na_all['datetime'] < _start_time]['datetime'].max()

    #
    if first_pre_close_time is None:
        first_pre_close_time = listing_time

    # 复权的栏位
    price_fields = ['open', 'high','low','close']
    for xdxr in _df_xdxr_all.itertuples():
        m_ex_time = pd.to_datetime(xdxr.date)
        ex_xdxr_rows = _df_new_pba['datetime'] >= m_ex_time
        # 复权
        _df_new_pba.loc[ex_xdxr_rows, price_fields] = \
            (_df_new_pba.loc[ex_xdxr_rows, price_fields] * (1 + xdxr.stock_div + xdxr.ri)
             + xdxr.cash_div - xdxr.ri_price * xdxr.ri)

        # 对第一笔资料的pre_close 也进行复权
        if first_pre_close_time >= m_ex_time:
            first_pre_close = (first_pre_close * (1 + xdxr.stock_div + xdxr.ri)
                               + xdxr.cash_div - xdxr.ri_price * xdxr.ri)

    # 重新计算pre_close
    _df_new_pba['pre_close'] = _df_new_pba['close'].shift(1)
    _df_new_pba.loc[0, 'pre_close'] = first_pre_close

    # 计算涨跌
    _df_new_pba['Chg'] = _df_new_pba['close'] - _df_new_pba['pre_close']

    # 计算涨幅
    _df_new_pba['pctChg'] = _df_new_pba['Chg'] / _df_new_pba['pre_close'] * 100

    # 计算振幅
    _df_new_pba['Amp'] = (_df_new_pba['high'] - _df_new_pba['low'] )/ _df_new_pba['pre_close'] * 100

    if bsave:
        _, upd_result = hist_price_save(_df_new_pba, AdjustMode.PBA)

    return _df_new_pba, upd_result


def hist_price_day_update(
        code: str,
        start_time: datetime = None,
        adjust: Optional[set[AdjustMode]] = None
) -> dict[AdjustMode, list]:
    """
    更新股票日線價格數據（支持多種除權模式）

    此函數會更新指定股票的日線價格數據，並根據指定的除權模式，
    計算對應的復權價格。預設會計算三種模式：未復權、前復權、後復權。

    Args:
        code (str): 股票代碼，例如 '000001'、'600000'
        start_time (datetime, optional): 開始日期時間，如果為 None 則從最早數據開始
        adjust (Optional[set[AdjustMode]], optional): 需要更新的除權模式集合。
            如果為 None，則預設更新所有三種模式 {NONE, PFA, PBA}。
            可以只指定部分模式，例如 {AdjustMode.PFA} 只更新前復權。

    Returns:
        dict[AdjustMode, list]: 返回一個字典，鍵為除權模式，值為對應的更新結果列表。
            每個更新結果列表的具體格式由各底層函數決定，通常包含：
            - 更新記錄數
            - 成功/失敗狀態
            - 其他調試信息

    Examples:
        >>> # 更新所有三種模式
        >>> result = hist_price_day_update('000001')
        >>>
        >>> # 只更新前復權和後復權
        >>> result = hist_price_day_update('000001', adjust={AdjustMode.PFA, AdjustMode.PBA})
        >>>
        >>> # 從指定日期開始更新
        >>> from datetime import datetime
        >>> result = hist_price_day_update('000001', start_time=datetime(2023, 1, 1))

    Note:
        - 除權模式 NONE 始終會被包含在更新中，即使 adjust 參數中沒有指定
        - 未復權價格更新是其他復權模式的基礎，所以無論如何都會執行
        - 前復權(PFA)和後復權(PBA)的計算依賴於未復權的基礎數據
    """

    # 除權模式是必須的
    # 確保 NONE 模式始終存在，作為其他復權計算的基礎
    if adjust is None:
        # 預設：更新所有三種模式
        _adjust_set = {AdjustMode.NONE, AdjustMode.PFA, AdjustMode.PBA}
    else:
        # 用戶指定模式時，確保 NONE 模式也被包含
        _adjust_set = {AdjustMode.NONE}.union(adjust)

    # 初始化返回結果字典
    # 鍵：除權模式，值：對應的更新結果列表
    update_result: dict[AdjustMode, list] = {}

    # ========== 1. 更新未復權價格（基礎數據） ==========
    # 無論如何都需要執行，因為前復權和後復權依賴於這些基礎數據
    # 返回值說明：
    #   _df_na_all: 完整的未復權日線數據 DataFrame
    #   _df_xdxr_all: 完整的除權息事件數據 DataFrame
    #   _save_result: 本次更新的結果記錄（列表格式）
    _df_na_all, _df_xdxr_all, _save_result = (
        hist_price_day_na_update(code=code, start_time=start_time)
    )
    # 記錄未復權模式的更新結果
    update_result[AdjustMode.NONE] = _save_result

    # ========== 2. 更新前復權價格 ==========
    # 僅當用戶要求 PFA 模式時才計算
    if AdjustMode.PFA in _adjust_set:
        # 計算前復權價格
        # 參數說明：
        #   code: 股票代碼
        #   df_na_all: 未復權日線數據
        #   df_xdxr_all: 除權息事件數據
        #   start_time: 開始時間
        # 返回值說明：
        #   _df_pfa: 前復權價格數據 DataFrame
        #   _save_result: 本次更新的結果記錄
        _df_pfa, _save_result = hist_price_day_pfa_calc(
            code=code,
            df_na_all=_df_na_all,
            df_xdxr_all=_df_xdxr_all,
            start_time=start_time
        )
        # 記錄前復權模式的更新結果
        update_result[AdjustMode.PFA] = _save_result

    # ========== 3. 更新後復權價格 ==========
    # 僅當用戶要求 PBA 模式時才計算
    if AdjustMode.PBA in _adjust_set:
        # 計算後復權價格
        # 參數說明：
        #   code: 股票代碼
        #   df_na_all: 未復權日線數據
        #   df_xdxr_all: 除權息事件數據
        #   start_time: 開始時間
        # 返回值說明：
        #   _df_pba: 後復權價格數據 DataFrame
        #   _save_result: 本次更新的結果記錄
        _df_pba, _save_result = hist_price_day_pba_calc(
            code=code,
            df_na_all=_df_na_all,
            df_xdxr_all=_df_xdxr_all,
            start_time=start_time
        )
        # 記錄後復權模式的更新結果
        update_result[AdjustMode.PBA] = _save_result

    # 返回包含所有請求模式的更新結果
    return update_result


def hist_price_day_update_multi(
        codes: Optional[List[str]] = None,
        start_time: Optional[datetime] = None,
        max_workers: int = 8,
        adjust: Optional[set[AdjustMode]] = None,
        progress_callback: Optional[callable] = None
) -> Dict[str, Dict[AdjustMode, list]]:
    """
    多線程更新多支股票的日線價格數據

    Args:
        codes (Optional[List[str]]): 股票代碼列表，如果為 None 則需要從其他來源獲取
        start_time (Optional[datetime]): 開始日期時間，如果為 None 則從最早數據開始
        max_workers (int): 最大工作線程數，默認為 8
        adjust (Optional[set[AdjustMode]]): 需要更新的除權模式集合
        progress_callback (Optional[callable]): 進度回調函數，接收參數 (current, total, code, status)

    Returns:
        Dict[str, Dict[AdjustMode, list]]: 返回一個字典，鍵為股票代碼，值為該股票的更新結果

    Examples:
        >>> # 更新多支股票的所有模式
        >>> codes = ['000001', '000002', '600000', '600001']
        >>> results = hist_price_day_update_multi(codes, max_workers=4)
        >>>
        >>> # 只更新前復權和後復權
        >>> results = hist_price_day_update_multi(
        ...     codes,
        ...     adjust={AdjustMode.PFA, AdjustMode.PBA},
        ...     max_workers=8
        ... )
        >>>
        >>> # 帶進度回調
        >>> def on_progress(current, total, code, status):
        ...     print(f"進度: {current}/{total} - {code}: {status}")
        >>> results = hist_price_day_update_multi(codes, progress_callback=on_progress)
    """

    if not codes:
        logger.warning("股票代碼列表為空，無需更新")
        return {}

    # 用於存儲所有更新結果
    all_results: Dict[str, Dict[AdjustMode, list]] = {}

    # 用於線程安全的結果寫入
    result_lock = threading.Lock()

    # 統計信息
    success_count = 0
    fail_count = 0
    fail_lock = threading.Lock()

    def update_single_stock(code: str, idx: int, total: int) -> tuple[str, Dict[AdjustMode, list], bool]:
        """
        更新單支股票（在工作線程中執行）

        Returns:
            tuple: (股票代碼, 更新結果, 是否成功)
        """
        try:
            logger.info(f"開始更新股票 {code} ({idx + 1}/{total})")

            # 調用原始的更新函數
            result = hist_price_day_update(
                code=code,
                start_time=start_time,
                adjust=adjust
            )

            logger.info(f"成功更新股票 {code}，獲得 {len(result)} 種除權模式數據")

            # 進度回調
            if progress_callback:
                progress_callback(idx + 1, total, code, "success")

            return code, result, True

        except Exception as e:
            logger.error(f"更新股票 {code} 失敗: {str(e)}", exc_info=True)

            # 返回空結果
            error_result = {}

            # 進度回調
            if progress_callback:
                progress_callback(idx + 1, total, code, f"failed: {str(e)}")

            return code, error_result, False

    # 使用線程池執行任務
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        # 提交所有任務
        future_to_code = {
            executor.submit(update_single_stock, code, idx, len(codes)): (code, idx)
            for idx, code in enumerate(codes)
        }

        # 處理完成的任務
        for future in as_completed(future_to_code):
            code, idx = future_to_code[future]
            try:
                result_code, result_data, is_success = future.result()

                # 線程安全地寫入結果
                with result_lock:
                    all_results[result_code] = result_data
                    if is_success:
                        success_count += 1
                    else:
                        fail_count += 1

            except Exception as e:
                logger.error(f"獲取股票 {code} 更新結果時發生異常: {str(e)}")
                with result_lock:
                    all_results[code] = {}
                    fail_count += 1

                if progress_callback:
                    progress_callback(idx + 1, len(codes), code, f"exception: {str(e)}")

    # 輸出統計信息
    logger.info(f"多線程更新完成 - 總數: {len(codes)}, 成功: {success_count}, 失敗: {fail_count}")

    return all_results


def hist_price_day_update_multi_batch(
        codes: Optional[List[str]]=None,
        start_time: Optional[datetime] = None,
        max_workers: int = 8,
        batch_size: int = 100,
        adjust: Optional[set[AdjustMode]] = None,
        progress_callback: Optional[callable] = None
) -> Dict[str, Dict[AdjustMode, list]]:
    """
    分批多線程更新大量股票（避免一次性提交過多任務）

    Args:
        codes (List[str]): 股票代碼列表
        start_time (Optional[datetime]): 開始日期時間
        max_workers (int): 最大工作線程數
        batch_size (int): 每批處理的股票數量
        adjust (Optional[set[AdjustMode]]): 需要更新的除權模式集合
        progress_callback (Optional[callable]): 進度回調函數

    Returns:
        Dict[str, Dict[AdjustMode, list]]: 所有股票的更新結果
    """
    all_results = {}

    # 如果stock_codes为空，则获取所有股票代码
    if not codes:
        logger.info("股票代码列表为空，调用codes_list_update()获取所有股票代码")
        try:
            df_codes = codes_list()
            if df_codes.empty or 'code' not in df_codes.columns:
                logger.error("获取股票代码列表失败：DataFrame为空或缺少code列")
                return all_results
            logger.info(f"获取到{len(df_codes)}只股票代码")
        except Exception as e:
            logger.error(f"获取股票代码列表失败: {e}")
            return all_results
        _codes = df_codes['code'].tolist()
    else:
        _codes=codes


    total_batches = (len(_codes) + batch_size - 1) // batch_size

    logger.info(f"開始分批更新 {len(_codes)} 支股票，分為 {total_batches} 批，每批 {batch_size} 支")

    for batch_idx in range(total_batches):
        start_idx = batch_idx * batch_size
        end_idx = min(start_idx + batch_size, len(_codes))
        batch_codes = _codes[start_idx:end_idx]

        logger.info(f"處理第 {batch_idx + 1}/{total_batches} 批，股票範圍: {start_idx}-{end_idx}")

        # 定義批次的進度回調（包裝原來的回調）
        def batch_progress_callback(current, total, code, status):
            if progress_callback:
                # 計算全局進度
                global_current = start_idx + current
                global_total = len(codes)
                progress_callback(global_current, global_total, code, status)

        # 更新當前批次
        batch_results = hist_price_day_update_multi(
            codes=batch_codes,
            start_time=start_time,
            max_workers=max_workers,
            adjust=adjust,
            progress_callback=batch_progress_callback
        )

        # 合併結果
        all_results.update(batch_results)

        logger.info(f"第 {batch_idx + 1} 批更新完成，獲得 {len(batch_results)} 支股票的結果")

    logger.info(f"所有批次更新完成，總共獲得 {len(all_results)} 支股票的結果")
    return all_results

    # # 示例1: 基本使用
    # stock_codes = ['000001', '000002', '600000', '600001', '600036', '000858']
    #
    # results = hist_price_day_update_multi(
    #     codes=stock_codes,
    #     start_time=datetime(2023, 1, 1),
    #     max_workers=4
    # )
    #
    # # 打印結果統計
    # for code, result in results.items():
    #     print(f"股票 {code}: 更新了 {len(result)} 種模式")
    #     for mode, update_info in result.items():
    #         print(f"  - {mode}: {update_info}")
    #
    # # 示例2: 帶進度回調
    # def show_progress(current, total, code, status):
    #     percentage = (current / total) * 100
    #     print(f"[{percentage:.1f}%] {code}: {status}")
    #
    # results2 = hist_price_day_update_multi(
    #     codes=stock_codes[:10],
    #     max_workers=5,
    #     progress_callback=show_progress
    # )
    #
    # # 示例3: 處理大量股票（分批）
    # many_codes = [f"{i:06d}" for i in range(1000)]  # 1000支股票
    # results3 = hist_price_day_update_multi_batch(
    #     codes=many_codes,
    #     batch_size=200,
    #     max_workers=8,
    #     progress_callback=show_progress
    # )



def equity_info(stock_code:str,
                start_date:date=None,
                end_date:date=None)->pd.DataFrame|None:

    # 转换日期格式
    start_str = start_date.strftime("%Y%m%d") if start_date else ''
    end_str = end_date.strftime("%Y%m%d") if end_date else ''

    # 获取股本数据（直接在底层函数过滤）
    try:
        dict_equity = g_tq.get_gb_info_by_date(
            stock_code=stock_code,
            start_date=start_str,
            end_date=end_str
        )
    except Exception as e:
        raise RuntimeError(f"获取股本数据失败 ({stock_code}): {e}")

    if dict_equity is None or len(dict_equity) == 0:
        return None

    # 转换为 DataFrame
    df_equity = pd.DataFrame(dict_equity)

    # 重命名列
    df_equity = df_equity.rename(columns={
        'Date': 'datetime',
        'Ltgb': 'float_share',
        'Zgb': 'total_share'
    })

    # 关键修复：正确解析日期格式
    # 如果 datetime 是数字（如 20220122）或字符串，转换为日期
    if df_equity['datetime'].dtype in ['int64', 'float64']:
        # 数字格式：20220122 -> 2022-01-22
        df_equity['datetime'] = pd.to_datetime(df_equity['datetime'], format='%Y%m%d', errors='coerce')
    else:
        # 字符串格式：尝试多种格式
        df_equity['datetime'] = pd.to_datetime(df_equity['datetime'], errors='coerce')

    # 删除无效日期（如果有）
    df_equity = df_equity.dropna(subset=['datetime'])

    # 重置索引
    df_equity = df_equity.reset_index(drop=True)

    # 按日期排序
    df_equity = df_equity.sort_values('datetime')

    return df_equity


def dividend_info_update(stock_code: str,
                         start_date: date = None,
                         bsave: bool = False) ->  tuple[pd.DataFrame|None, list]:
    save_result=[0,0]

    _code = stock_code

    # 1. 获取上市日期
    _listing_date = dq.listing_date_get(code=_code)
    if _listing_date is None:
        raise ValueError(f"股票 {_code} 未上市，无法获取除权除息数据")

    # 2. 獲取歷史記錄,並確立查询起始日期
    _df_xdxr_old = dq.xdxr_info_query([_code])
    if _df_xdxr_old is None or len(_df_xdxr_old) == 0:
        _start_date = _listing_date
    else:
        db_date = _df_xdxr_old['date'].max()
        last_date = db_date.date() if hasattr(db_date, 'date') else db_date
        _start_date = last_date + timedelta(days=1)

    # 如果輸入的start_date 比 db_date=_start_date 早，就從輸入的start_date開始强制更新
    if start_date and start_date < _start_date:
        _start_date = start_date

    # 3. 获取除权除息数据
    try:
        df_divid = g_tq.get_divid_factors(
            stock_code=_code,
            start_time=_listing_date.strftime("%Y%m%d"),
            end_time=date.today().strftime("%Y%m%d")
        )
    except Exception as e:
        raise RuntimeError(f"获取分红送配数据失败 ({_code}): {e}")

    # 4. 确定需要查询股本的日期列表
    if df_divid is None or len(df_divid)==0:
        # 無分紅
        return None,save_result

    # ============================================================
    # 数据处理
    # ============================================================

    # 1. 将索引（日期）转换为普通列
    if isinstance(df_divid.index, pd.DatetimeIndex):
        df_divid.reset_index(inplace=True)
        df_divid.rename(columns={'index': 'date'}, inplace=True)

    if 'Date' in df_divid.columns:
        df_divid.rename(columns={'Date': 'date'}, inplace=True)

    # 2. 在第一列插入股票代码
    df_divid.insert(0, 'code', _code)

    # 3. 转换日期格式
    df_divid['date'] = pd.to_datetime(df_divid['date']).dt.date

    # 4. 转换数据类型（str -> 数值）
    # 列名映射（原始列名 -> 新列名）
    column_mapping = {
        'Type': 'type',
        'Bonus': 'cash_div',
        'AllotPrice': 'ri_price',
        'ShareBonus': 'stock_div',
        'Allotment': 'ri'
        }

    # 重命名列
    for old_name, new_name in column_mapping.items():
        if old_name in df_divid.columns:
            df_divid.rename(columns={old_name: new_name}, inplace=True)

    # 5. 数值列类型转换
    numeric_cols = ['type', 'cash_div', 'ri_price', 'stock_div', 'ri']
    for col in numeric_cols:
        if col in df_divid.columns:
            df_divid[col] = pd.to_numeric(df_divid[col], errors='coerce').fillna(0)

    # 6. 每股数据转换（原始数据是每10股）
    # cash_div: 每10股派息 -> 每股派息
    if 'cash_div' in df_divid.columns:
        df_divid['cash_div'] = (df_divid['cash_div'] / 10).round(4)

    # stock_div: 每10股送股 -> 每股送股
    if 'stock_div' in df_divid.columns:
        df_divid['stock_div'] = (df_divid['stock_div'] / 10).round(4)

    # ri: 每10股配股 -> 每股配股
    if 'ri' in df_divid.columns:
        df_divid['ri'] = (df_divid['ri'] / 10).round(4)

    # 7. type 转换为整数
    if 'type' in df_divid.columns:
        df_divid['type'] = df_divid['type'].astype(int)

    # 8. 排序
    df_divid.sort_values(['code', 'date'], inplace=True)
    df_divid.reset_index(drop=True, inplace=True)

    # 9. 定义最终列顺序
    final_columns = [
        'code', 'date', 'type',
        'cash_div', 'ri_price', 'stock_div', 'ri'
        ]

    # 确保所有列都存在
    for col in final_columns:
        if col not in df_divid.columns:
            df_divid[col] = None

    df_divid = df_divid[final_columns]

    # 11. 保存
    df_tobe_update = df_divid[df_divid['date'] >= _start_date]
    if df_tobe_update is None or len(df_tobe_update)==0:
        return df_divid,save_result

    if bsave:
        save_result = dividend_info_save(df_xdxr=df_tobe_update)

    return df_divid,save_result

# ------------------------------
# 批量更新分红（多线程版本）
# ------------------------------
def dividend_info_update_multi(codes: str = None,
                               from_date:date = None,
                               max_workers: int = 10) -> list:
    """
    多线程批量更新 分红/除权除息 信息
    :param codes: 单个/多个股票代码，逗号分隔，空=全部
    :param from_date: 從什麽時候開始更新 ,輸入了date(year=1990,month=1,day=1)表示完全更新
    :param max_workers: 线程数，默认 10（安全不封号）
    :return: 共有多少支股票更新，數據庫刪除的筆數和插入的筆數
    """
    update_result=[0,0,0]

    # 1. 获取股票列表
    if codes is None or codes.strip() == "":
        df_codes = codes_list()
        if df_codes.empty:
            logger.error("未获取到任何股票代码")
            return update_result
        code_list = df_codes["code"].tolist()
    else:
        code_list = [c.strip() for c in codes.split(",") if c.strip()]

    total = len(code_list)
    logger.info(f"【多线程】开始更新分红数据，共 {total} 只股票，线程数：{max_workers}")

    all_new_data: List[pd.DataFrame] = []
    lock = threading.Lock()  # 线程安全锁

    # --------------------
    # 单个股票处理函数
    # --------------------
    def process_one_stock(code):
        try:
            # 取数据库最后一笔除权日
            _from_date = None
            last_date = dq.xdxr_last_date_get(code)
            if last_date is None:
                _from_date = None
            else:
                if from_date :
                    if last_date < from_date:
                        _from_date = last_date + timedelta(days=1)
                    else:
                        _from_date = from_date

            # 调用你的函数 → 自动抓新数据 + 保存数据库
            _, save_result = dividend_info_update(
                stock_code=code,
                start_date=_from_date,
                bsave=True
            )

            # 直接累加（save_result 总是 [删除笔数, 插入笔数]）
            with lock:
                # 只要有删除或插入，就算更新了该股票
                if save_result[0] > 0 or save_result[1] > 0:
                    update_result[0] += 1  # 更新股票数

                update_result[1] += save_result[0]  # 累加删除笔数
                update_result[2] += save_result[1]  # 累加插入笔数

            # 日志记录
            if save_result[0] > 0 or save_result[1] > 0:
                logger.info(f"✅ {code} 完成 (删除:{save_result[0]}, 插入:{save_result[1]})")
            else:
                logger.info(f"ℹ️ {code} 无变化")

        except Exception as e:
            logger.error(f"❌ {code} 处理失败：{str(e)}")

    # --------------------
    # 多线程执行
    # --------------------
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        # 提交所有任务
        futures = [executor.submit(process_one_stock, code) for code in code_list]

        # 等待完成
        for future in as_completed(futures):
            try:
                future.result()
            except Exception as e:
                logger.error(f"线程执行异常：{str(e)}")

    logger.info(f"✅ 多线程更新完成！更新股票:{update_result[0]} 只，"
                f"删除:{update_result[1]} 条，插入:{update_result[2]} 条")

    return update_result


def dividend_info_save(df_xdxr, table_name='as_xdxr'):
    """
    保存除权除息数据到数据库
    Parameters
        df_equity_dividend : DataFrame
            已处理好列名的除权除息数据，包含列：
            code, date, type, descr, cash_div, ri_price, stock_div, ri,
            reverse_split, pre_float, post_float, pre_total, post_total, wnt_qty, exc_price
        table_name : str, default='as_xdxr'
            数据库表名
        if_exists : str, default='replace'
            表存在时的处理方式：'replace'(替换), 'append'(追加), 'fail'(失败)

    Returns
        list[删除笔数, 插入笔数]
    """
    save_result = [0,0]

    if df_xdxr is None or len(df_xdxr) == 0:
        return save_result

    # 加更新时间
    # df_xdxr['updtime'] = datetime.now()
    df_xdxr.loc[:, 'updtime'] = datetime.now()
    codes = df_xdxr['code'].unique().tolist()
    min_date = df_xdxr['date'].min()
    max_date = df_xdxr['date'].max()

    # 删除旧记录
    # if db_connector.table_exists(table_name):
    # 构建删除SQL：删除指定股票在指定日期范围内的数据
    placeholders = ','.join(['%s'] * len(codes))
    delete_sql = f"""
                DELETE FROM {table_name} 
                WHERE code IN ({placeholders}) 
                AND date >= %s 
                AND date <= %s
            """
    # 参数：股票代码列表 + 开始日期 + 结束日期
    params = codes + [min_date, max_date]

    delete_sql = text(f"""
    DELETE FROM {table_name}
    WHERE code IN :codes
    AND date >= :min_date
    AND date <= :max_date
    """).bindparams(
        bindparam("codes", expanding=True)
    )

    params = {"codes": codes, "min_date": min_date, "max_date": max_date}

    save_result[0] = db_connector.execute_sql(delete_sql, params=params)
    logger.info(f"删除了 {save_result[0]} 条旧数据（股票: {len(codes)}只, 日期: {min_date} ~ {max_date}）")

    # 插入新记录
    save_result[1] = db_connector.batch_insert(df_xdxr,table_name)
    logger.info(f"成功插入 {save_result[1]} 条股票代码到表 {table_name}")

    return save_result

# ==================== 辅助函数 ====================

# ==================== 使用示例 ====================
if __name__ == "__main__":
    # # 板块列表
    # s_list = get_sector_list()
    # print(f"板块总数：{len(s_list)}")
    # print("板块列表：")
    # for sector in s_list:
    #     print(sector)

    # # 代码列表
    # df_codes = codes_list()
    # # df_codes = codes_list('轮动趋势')
    # df_codes = codes_list(source='10',bsave=False)
    # print(f"获取到 {len(df_codes)} 只股票")
    # print(df_codes)

    # # 证券信息
    # info = basic_info_update('001393.SZ')
    # print(info)
    # info = basic_info_update('000885.SZ',force_update=True)
    # print(info)
    # basic_info_update_mass()
    # 2026-05-18 08:57:25
    # 2026-05-18 09:01:35 - dm.mytdx.my_tq.my_tq - INFO - TdxQuant     连接已关闭
    # info = basic_info_update('001237.SZ')
    # stock_list = ['000001.SZ', '600001.SH', '300001.SZ', '000002.SZ', '600002.SH']
    # stock_list = ['001237.SZ','001365.SZ','001393.SZ','603435.SH','688635.SH','920096.BJ','920178.BJ']
    # df_infos = basic_info_update_mass(stock_list, bsave=True,force_update=True)
    # df_infos = basic_info_update_multi(force_update=True)
    # print(df_infos)
    # # 2026-05-18 10:33:24 ~ 2026-05-18 10:37:58 = 4:30min

    # info = basic_info_update('002422.SZ', bsave=False)
    # info = basic_info_update('002422.SZ')
    # print(info)
    # print(f"股票名称: {info['name']}")
    # print(f"行业: {info['industry']}")

    # 批量获取（小批量测试）
    # df = as_basic_info_update_mass(['000001.SZ', '600000.SH'], use_multithread=True)
    # print(df.head())

    # 分红送配
    # df_share_divid= dividend_info_update(stock_code='600177.SH',bsave=True)
    # print(df_share_divid)
    # df_share_divid= dividend_info_update(stock_code='920981.BJ',bsave=True)
    # print(df_share_divid)
    # df_share_divid= dividend_info_update(stock_code='600177.SH',bsave=True)
    # print(df_share_divid)

    # df_div = dq.xdxr_info_query(['000858.SZ'])
    # df_div = dq.xdxr_info_query(['920981.BJ'])
    #
    # print("\n分红送配明细：")
    # print(df_div.sort_values("date", ascending=False))
    # print(df_divid)
    # dividend_info_update_multi()
    # 15：38：01  ~ 15：48：00

    # 股本信息
    # df_equ = equity_info('920981.BJ')
    # print(df_equ)

    # 获取K线行情
    # df_prices = hist_price('600177.SH',period='1d',adjust=AdjustMode.NONE)
    # print(df_prices)
    # save_result = hist_price_save(df_prices)
    # df_na_price,df_xdxr,result = (
    # # # #     hist_price_day_na_update('301221.SZ'))
    #     hist_price_day_na_update('600177.SH', start_time=datetime(year=2026, month=5, day=1)))
    # print(df_na_price,df_xdxr,result)
    #
    # df_pfa_prices,result = hist_price_day_pfa_calc(
    #     '600177.SH',df_na_all=df_na_price,df_xdxr_all=df_xdxr,
    #     start_time=datetime(year=1991, month=1, day=1))
    # print(df_pfa_prices,result)
    # df_pba_prices, result = hist_price_day_pba_calc(
    #     '600177.SH', df_na_all=df_na_price,df_xdxr_all=df_xdxr,
    #     start_time=datetime(year=1991, month=1, day=1))
    # print(df_pba_prices, result)

    # dict_result = hist_price_day_update('000885.SZ')
    # print(dict_result)

    # 示例1: 基本使用
    # stock_codes = ['000001.SZ', '000002.SZ', '600000.SH', '600001.SH', '600036.SH', '000858.SZ']

    # results = hist_price_day_update_multi(
    #     codes=stock_codes,
    #     start_time=datetime(1990, 1, 1),
    #     max_workers=4
    # )
    #
    # # 打印結果統計
    # for code, result in results.items():
    #     print(f"股票 {code}: 更新了 {len(result)} 種模式")
    #     for mode, update_info in result.items():
    #         print(f"  - {mode}: {update_info}")

    # # 示例2: 帶進度回調
    # def show_progress(current, total, code, status):
    #     percentage = (current / total) * 100
    #     print(f"[{percentage:.1f}%] {code}: {status}")
    #
    # results2 = hist_price_day_update_multi(
    #     codes=stock_codes[:10],
    #     max_workers=5,
    #     progress_callback=show_progress
    # )

    # # 示例3: 帶進度回調
    # many_codes = [
    #     f"{i:06d}.SH" if i < 600000 else f"{i:06d}.SZ"
    #     for i in range(600000, 601000)
    # ]  # 生成1000支股票代碼，前500支滬市，後500支深市
    #
    # results3 = hist_price_day_update_multi_batch(
    #     codes=many_codes,
    #     batch_size=200,  # 每批200支股票
    #     max_workers=8,  # 8個線程並行
    #     start_time=datetime(1990, 1, 1),
    #     progress_callback=show_progress
    # )

    # no_xdxr_stocks = [
    #     # 深圳市場 (SZ)
    #     '000885.SZ',
    #     '000993.SZ',
    #     '001220.SZ',
    #     '001237.SZ',
    #     '001239.SZ',
    #     '001257.SZ',
    #     '001280.SZ',
    #     '001312.SZ',
    #     '001325.SZ',
    #     '001330.SZ',
    #     '001332.SZ',
    #     '001365.SZ',
    #     '001390.SZ',
    #     '001393.SZ',
    #     '001396.SZ',
    #     '002615.SZ',
    #     '002850.SZ',
    #     '002950.SZ',
    #     '002953.SZ',
    #     '002955.SZ',
    #     '002956.SZ',
    #     '300014.SZ',
    #     '300111.SZ',
    #
    #     # 上海市場 (SH)
    #     '600410.SH',
    #     '601112.SH',
    #     '601186.SH',
    #     '603092.SH',
    #     '603175.SH',
    #     '603201.SH',
    #     '603210.SH',
    #     '603248.SH',
    #     '603262.SH',
    #     '603284.SH',
    #     '603293.SH',
    #     '603334.SH',
    #     '603352.SH',
    #     '603370.SH',
    #     '603376.SH',
    #     '603402.SH',
    #     '603407.SH',
    #     '603418.SH',
    #     '603435.SH',
    #     '603459.SH',
    #     '603861.SH',
    #
    #     # 科創板 (688)
    #     '688031.SH',
    #     '688039.SH',
    #     '688047.SH',
    #     '688062.SH',
    #     '688071.SH',
    #     '688107.SH',
    #     '688132.SH',
    #     '688141.SH',
    #     '688165.SH',
    #     '688173.SH',
    #     '688176.SH',
    #     '688177.SH',
    #     '688180.SH',
    #     '688192.SH',
    #     '688197.SH',
    #     '688220.SH',
    #     '688221.SH',
    #     '688234.SH',
    #     '688235.SH',
    #     '688246.SH',
    #     '688266.SH',
    #     '688277.SH',
    #     '688280.SH',
    #     '688302.SH',
    #     '688306.SH',
    #     '688316.SH',
    #     '688322.SH',
    #     '688326.SH',
    #     '688331.SH',
    #     '688343.SH',
    #     '688351.SH',
    #     '688358.SH',
    #     '688371.SH',
    #     '688373.SH',
    #     '688382.SH',
    #     '688387.SH',
    #     '688416.SH',
    #     '688428.SH',
    #     '688435.SH',
    #     '688443.SH',
    #     '688449.SH',
    #     '688469.SH',
    #     '688506.SH',
    #     '688512.SH',
    #     '688515.SH',
    #     '688520.SH',
    #     '688521.SH',
    #     '688525.SH',
    #     '688538.SH',
    #     '688561.SH',
    #     '688567.SH',
    #     '688635.SH',
    #     '688653.SH',
    #     '688702.SH',
    #     '688712.SH',
    #     '688727.SH',
    #     '688729.SH',
    #     '688759.SH',
    #     '688765.SH',
    #     '688775.SH',
    #     '688781.SH',
    #     '688783.SH',
    #     '688785.SH',
    #     '688790.SH',
    #     '688795.SH',
    #     '688796.SH',
    #     '688802.SH',
    #     '688805.SH',
    #     '688807.SH',
    #     '688808.SH',
    #
    #     # 北交所 (BJ)
    #     '920008.BJ',
    #     '920011.BJ',
    #     '920012.BJ',
    #     '920015.BJ',
    #     '920020.BJ',
    #     '920026.BJ',
    #     '920028.BJ',
    #     '920045.BJ',
    #     '920047.BJ',
    #     '920056.BJ',
    #     '920069.BJ',
    #     '920078.BJ',
    #     '920086.BJ',
    #     '920091.BJ',
    #     '920096.BJ',
    #     '920101.BJ',
    #     '920124.BJ',
    #     '920125.BJ',
    #     '920156.BJ',
    #     '920159.BJ',
    #     '920166.BJ',
    #     '920168.BJ',
    #     '920177.BJ',
    #     '920178.BJ',
    #     '920181.BJ',
    #     '920186.BJ',
    #     '920188.BJ',
    #     '920191.BJ',
    #     '920200.BJ',
    #     '920220.BJ',
    #     '920223.BJ',
    #     '920305.BJ',
    #     '920493.BJ',
    #     '920578.BJ',
    #     '920873.BJ',
    # ]
    #
    # print(f"總共 {len(no_xdxr_stocks)} 支股票無除權數據")

    all_abnormal_stocks = [
        # 失败股票
        '688047.SH',
        '688729.SH',
        '920086.BJ',
        '920101.BJ',
        # 警告股票
        '002955.SZ',
        '603370.SH',
        '603435.SH',
        '688192.SH',
        '688234.SH',
        '688373.SH',
        '688449.SH',
        '688506.SH',
        '688635.SH',
        '688775.SH',
        '688785.SH',
        '920220.BJ',
    ]

    ret = hist_price_day_update_multi_batch(all_abnormal_stocks)
    print(ret)

    # ret= hist_price_day_update('688047.SH')
    # print(ret)

    # df_gb = equity_info('600177.SH')
    # print(df_gb)
    # df_prices = g_tq.get_market_data(stock_list=['300396.SZ'])
    # print(df_prices)


    # #
    # shares = g_tq.get_gb_info(stock_code='301538.SZ',
    #                           date_list= ['19900101','20241010','20250527'],
    #                           count=3)
    # print(shares)
