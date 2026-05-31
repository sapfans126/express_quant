# my_tq.py
"""
通达信 TdxQuant 封装类
统一管理 tqcenter 的连接和操作
"""
import sys
from pathlib import Path
import atexit
import pandas as pd
import numpy as np
from typing import List, Dict, Optional
import inspect

# import main_xq.base.code_utils as utl

# 导入配置和日志
import main_xq.config.config as cfg
import main_xq.base.code_utils as utl
from main_xq.utils.logger import get_logger_for_current_module


logger = get_logger_for_current_module(__file__)

class MyTQ:
    """通达信 TdxQuant 封装类（简化版）"""

    def __init__(self, file_path: str = None):
        """
        初始化，自动建立连接

        Args:
            file_path: 当前文件的 __file__ 路径，如果不传则自动获取
        """
        self._tq = None
        self._connected = False
        self._current_file_path = None

        # 自动初始化
        if file_path:
            self.initialize(file_path)
        else:
            # 尝试自动获取调用者的文件路径
            try:
                frame = inspect.currentframe().f_back
                caller_file = frame.f_globals.get('__file__', '')
                if caller_file:
                    self.initialize(caller_file)
                else:
                    logger.warning("无法自动获取文件路径，请手动调用 initialize(__file__)")
            except:
                logger.warning("自动初始化失败，请手动调用 initialize(__file__)")

        # 注册退出时自动关闭
        atexit.register(self.close)

    def initialize(self, file_path: str = None) -> bool:
        """
        初始化连接

        Args:
            file_path: 当前文件的 __file__ 路径（必需，传给 tqcenter）
        """
        if self._connected:
            return True

        # 保存路径
        if file_path:
            self._current_file_path = file_path
        elif self._current_file_path is None:
            # 如果没有传且之前也没保存，尝试自动获取调用者的文件路径
            frame = inspect.currentframe().f_back
            self._current_file_path = frame.f_globals.get('__file__', '')
            if not self._current_file_path:
                raise ValueError("initialize() 需要传入 file_path 参数")

        # 加载 tqcenter
        if self._tq is None:
            if not self._load_tqcenter():
                return False

        # 初始化（需要传 path）
        try:
            self._tq.initialize(self._current_file_path)  # ✅ 传路径
            self._connected = True
            logger.info("TdxQuant 初始化成功")
            return True
        except Exception as e:
            logger.error(f"初始化失败: {e}")
            return False

    def _load_tqcenter(self) -> bool:
        """加载 tqcenter 模块"""
        try:
            tdx_config = cfg.MyTdxConfig()
            tq_path = tdx_config.get(section="PYPlUGIN", key="tdx_user_dir")

            if not tq_path:
                logger.error("未配置 tdx_user_dir")
                return False

            tq_path = Path(tq_path)
            if not tq_path.exists():
                logger.error(f"路径不存在: {tq_path}")
                return False

            tq_file = tq_path / "tqcenter.py"
            if not tq_file.exists():
                logger.error(f"核心文件不存在: {tq_file}")
                return False

            # 添加到系统路径
            tq_path_str = str(tq_path)
            if tq_path_str not in sys.path:
                sys.path.insert(0, tq_path_str)

            # 导入
            import tqcenter
            self._tq = tqcenter.tq
            logger.info("tqcenter 加载成功")
            return True

        except Exception as e:
            logger.error(f"加载 tqcenter 失败: {e}")
            return False

    def close(self):
        """关闭连接"""
        if self._tq and hasattr(self._tq, 'close'):
            try:
                self._tq.close()
            except:
                pass
        self._connected = False
        logger.info("TdxQuant 连接已关闭")

    def _check(self):
        """检查连接状态"""
        if not self._connected:
            raise RuntimeError("请先调用 initialize()")

    @property
    def is_connected(self) -> bool:
        """连接状态"""
        return self._connected

    @property
    def raw(self):
        """获取原始 tq 对象"""
        return self._tq

    # ==================== 分类/板块成份股 ====================
    def get_stock_list(self, market: str = '5', list_type:int = 1) -> list:
        """获取股票列表"""
        self._check()
        return self._tq.get_stock_list(market=market,list_type=list_type)

    def get_sector_list(self,list_type: int = 1) -> list:
        """获取所有板块列表"""
        self._check()
        return self._tq.get_sector_list(list_type=list_type)

    def get_stock_list_in_sector(self, block_code: str,
                         block_type: int = 0,
                         list_type: int = 1) -> list:
        """
        获取板块成分股
        #接口使用 :
            获取A股成份股时支持板块名称或板块代码两种方式传入
            block_type=0 表示传入板块指数代码或板块指数名称（默认）
            block_type=1 表示传入自定义板块简称 需要是客户端中预先定义好自定义板块的简称 如果是ZXG表示是自选股；TJG表示是临时条件股
            list_type = 0 只返回代码，list_type = 1 返回代码和名称
        """
        self._check()
        return self._tq.get_stock_list_in_sector(
            block_code=block_code,block_type=block_type,list_type=list_type)

    # ==================== 行情数据接口 ====================
    def get_market_data(
            self,
            field_list: Optional[List[str]] = None,
            stock_list: Optional[List[str]] = None,
            period: str = '1d',
            start_time: str = '',
            end_time: str = '',
            count: int = -1,
            dividend_type: Optional[str] = None,
            fill_data: bool = False,
    ) -> pd.DataFrame | None:
        """
        获取历史K线数据（封装通达信接口）
        """
        self._check()

        # 标准化股票代码
        _normalized_codes = utl.normalize_stock_codes_simple(stock_list)

        if not _normalized_codes:
            logger.warning("没有有效的股票代码")
            return pd.DataFrame()

        # 处理默认值
        if field_list is None:
            field_list = []
        if dividend_type is None:
            dividend_type = 'none'

        # 调用通达信接口
        result = self._tq.get_market_data(
            field_list=field_list,
            stock_list=_normalized_codes,
            period=period,
            start_time=start_time,
            end_time=end_time,
            count=count,
            dividend_type=dividend_type,
            fill_data=fill_data
        )

        if not result:
            return None

        # ============================================================
        # 第一步：将每个字段的 DataFrame 合并成 MultiIndex
        # ============================================================
        dfs = []
        for field, df in result.items():
            # 创建 MultiIndex: (字段名, 股票代码)
            df.columns = pd.MultiIndex.from_product([[field], _normalized_codes])
            dfs.append(df)

        # 按列合并
        multi_df = pd.concat(dfs, axis=1).sort_index()

        # ============================================================
        # 第二步：从宽格式转换为长格式
        # ============================================================
        # stack: 将股票代码从列索引转为行索引
        result_df = multi_df.stack(level=1, future_stack=True).reset_index()

        # 重命名 stack 产生的临时列
        result_df.rename(columns={'level_0': 'temp_date', 'level_1': 'code'}, inplace=True)

        # ============================================================
        # 第三步：处理日期时间
        # ============================================================
        if 'Date' in result_df.columns and 'Time' in result_df.columns:
            # 合并 Date 和 Time 字段
            result_df['datetime'] = pd.to_datetime(
                result_df['Date'].astype(str) + ' ' + result_df['Time'].astype(str)
            )
            # 删除原始日期时间列和临时列
            result_df.drop(columns=['Date', 'Time', 'temp_date'], inplace=True)
        elif 'Date' in result_df.columns:
            # 只有 Date 字段
            result_df['datetime'] = pd.to_datetime(result_df['Date'])
            result_df.drop(columns=['Date', 'temp_date'], inplace=True)
        else:
            # 使用索引作为日期
            result_df['datetime'] = pd.to_datetime(result_df['temp_date'], format='%Y%m%d')
            result_df.drop(columns=['temp_date'], inplace=True)

        # ============================================================
        # 第四步：重命名其他字段为小写
        # ============================================================
        column_mapping = {
            'Open': 'open',
            'High': 'high',
            'Low': 'low',
            'Close': 'close',
            'Volume': 'volume',
            'Amount': 'amount',
            'ForwardFactor': 'adj_factor',
            'VolInStock': 'vol_in_stock'
        }

        for old_name, new_name in column_mapping.items():
            if old_name in result_df.columns:
                result_df.rename(columns={old_name: new_name}, inplace=True)

        # ============================================================
        # 第五步：数据类型转换
        # ============================================================
        numeric_cols = ['open', 'high', 'low', 'close', 'volume', 'amount', 'adj_factor', 'vol_in_stock']
        for col in numeric_cols:
            if col in result_df.columns:
                result_df[col] = pd.to_numeric(result_df[col], errors='coerce')

        # 数值列四舍五入
        round_cols = ['open', 'high', 'low', 'close']
        for col in round_cols:
            if col in result_df.columns:
                result_df[col] = result_df[col].round(4)

        # ============================================================
        # 第六步：排序和整理
        # ============================================================
        result_df.sort_values(['code', 'datetime'], inplace=True)
        result_df.reset_index(drop=True, inplace=True)

        # 定义最终列顺序
        final_columns = [
            'code', 'datetime',
            'open', 'high', 'low', 'close',
            'volume', 'amount',
            'Amp', 'pctChg', 'Chg', 'turn', 'pre_close',  # 预留的欄位
            'adj_factor', 'vol_in_stock'
        ]

        # 确保所有列都存在
        for col in final_columns:
            if col not in result_df.columns:
                result_df[col] = np.nan

        return result_df[final_columns]

    def get_market_snapshot(self, stock_list: list) -> pd.DataFrame:
        """获取实时行情快照"""
        self._check()  # ✅ 修正：统一用 _check()
        return self._tq.get_market_snapshot(stock_list)

    def subscribe_quote(self, stock_list: list, callback=None):
        """订阅实时行情"""
        self._check()  # ✅ 修正
        return self._tq.subscribe_quote(stock_list, callback)

    def unsubscribe_hq(self, stock_list: list):
        """取消订阅"""
        self._check()  # ✅ 修正
        return self._tq.unsubscribe_hq(stock_list)

    # 获取分红配送数据
    def get_divid_factors(self, stock_code: str,
                          start_time: str,
                          end_time: str) -> pd.DataFrame:
        """获取指定时间段内的分红配送数据"""
        self._check()  # ✅ 修正
        return self._tq.get_divid_factors(stock_code=stock_code,
                                          start_time=start_time,
                                          end_time=end_time)

    # 获取每天的股本数据
    def get_gb_info(self, stock_code: str = '',
                    date_list: list[str] = [],
                    count: int = 1) -> list[dict]:

        """ 获取指定股票的股本数据"""
        self._check()  # ✅ 修正
        return self._tq.get_gb_info(stock_code=stock_code,
                                    date_list=date_list,
                                    count=count)


    def get_gb_info_by_date(self,stock_code:str='',
                            start_date:str='',
                            end_date:str='')->list[dict]:

        self._check()  # ✅ 修正
        return self._tq.get_gb_info_by_date(stock_code=stock_code,
                                    start_date=start_date,
                                    end_date = end_date)


    # ==================== 股票信息接口 ====================





    def get_stock_info(self, stock_code: str) -> dict:
        """获取股票基本信息"""
        self._check()
        return self._tq.get_stock_info(stock_code)

    def get_more_info(self, stock_code: str) -> dict:
        """获取指定股票更细节的信息"""
        self._check()
        return self._tq.get_more_info(stock_code)

    # ==================== 板块管理接口 ====================
    def create_sector(self, block_code: str, block_name: str) -> bool:
        """创建自定义板块"""
        self._check()
        return self._tq.create_sector(block_code, block_name)

    def delete_sector(self, block_code: str) -> bool:
        """删除自定义板块"""
        self._check()
        return self._tq.delete_sector(block_code)

    def rename_sector(self, block_code: str, new_name: str) -> bool:
        """重命名板块"""
        self._check()
        return self._tq.rename_sector(block_code, new_name)

    def clear_sector(self, block_code: str) -> bool:
        """清空板块"""
        self._check()
        return self._tq.clear_sector(block_code)

    # ==================== 财务数据接口 ====================
    def get_financial_data(
            self,
            stock_list: list,
            report_type: str = 'latest',
            **kwargs
    ) -> pd.DataFrame:
        """获取财务数据"""
        self._check()
        return self._tq.get_financial_data(
            stock_list=stock_list,
            report_type=report_type,
            **kwargs
        )



    # ==================== 交易接口 ====================
    def order_stock(
            self,
            stock_code: str,
            price: float,
            volume: int,
            direction: str = 'buy',
            order_type: str = 'limit'
    ) -> dict:
        """委托下单"""
        self._check()
        return self._tq.order_stock(
            stock_code=stock_code,
            price=price,
            volume=volume,
            direction=direction,
            order_type=order_type
        )

    # ==================== 消息接口 ====================
    def send_message(self, message: str):
        """发送消息到通达信客户端"""
        self._check()
        return self._tq.send_message(message)

    def send_file(self, file_path: str):
        """发送文件到通达信客户端"""
        self._check()
        return self._tq.send_file(file_path)

    def send_warn(self, warn_info: dict):
        """发送预警信息"""
        self._check()
        return self._tq.send_warn(warn_info)

    # ==================== 工具接口 ====================
    def get_trading_calendar(self, start_date: str, end_date: str) -> list:
        """获取交易日历"""
        self._check()
        return self._tq.get_trading_calendar(start_date, end_date)

    def get_trading_dates(self, start_date: str, end_date: str) -> list:
        """获取交易日"""
        self._check()
        return self._tq.get_trading_dates(start_date, end_date)

    def refresh_cache(self):
        """刷新缓存"""
        self._check()
        return self._tq.refresh_cache()

    def refresh_kline(self, stock_list: list = None):
        """刷新K线数据"""
        self._check()
        return self._tq.refresh_kline(stock_list)

# ==================== 全局实例 ====================
g_tq = MyTQ()

