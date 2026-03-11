# -*- coding: utf-8 -*-
"""
dc_tdx.py - 通达信数据接口（最终完整版）
功能：
1. 本地日线/分钟线数据读取（自动识别指数/股票，兼容所有mootdx版本）
2. 远程行情获取（K线/实时数据）
3. 财务报告解析（下载+解析）
核心特性：
- TdxLocalReader初始化指定market参数（std/ext）
- 日期参数统一为datetime类型，兼容字符串/date输入
- 自动识别指数/股票代码（000001、000985等）
- 手动解析二进制文件作为兜底方案
"""
import os
import sys
import warnings
import struct
from datetime import datetime, date
from pathlib import Path
from typing import Optional, Union, List
import numpy as np
import pandas as pd

# ===================== 第三方依赖导入 =====================
try:
    from mootdx.reader import Reader
    from mootdx.quotes import Quotes
    from mootdx.affair import Affair
except ImportError:
    raise ImportError("请安装mootdx：pip install mootdx>=0.10.0")

# ===================== 全局配置 =====================
# 过滤无关警告
warnings.filterwarnings("ignore", category=FutureWarning)
warnings.filterwarnings("ignore", category=UserWarning)

# 默认配置
DEFAULT_TDX_DIR = "C:/MySAS/TDX"
DEFAULT_TIMEOUT = 10
DEFAULT_RETRY = 3


# ===================== 基础工具函数 =====================
def clean_code(code: str) -> str:
    """
    清洗股票/指数代码，移除后缀、空格等干扰字符
    :param code: 原始代码（如600177.SH、000001 sz）
    :return: 纯数字代码
    """
    return code.strip().upper().replace('SH', '').replace('SZ', '').replace('.', '').replace(' ', '')


def is_index_code(code: str) -> bool:
    """
    精准判断是否为指数代码（解决000001/000985等歧义）
    :param code: 股票/指数代码
    :return: True=指数，False=股票
    """
    clean_code_str = clean_code(code)

    # 指数代码核心规则
    index_rules = [
        # 上海指数：000xxx、88xxx开头
        clean_code_str.startswith(('000', '88')),
        # 深圳指数：399xxx开头
        clean_code_str.startswith('399'),
        # 常见中证指数白名单
        clean_code_str in ['000985', '000300', '000905', '000852'],
        # 显式指数标识
        'INDX' in code.upper() or 'INDEX' in code.upper()
    ]

    # 股票代码排除规则（避免误判）
    stock_rules = [
        # 深圳股票：000xxx但非000001指数（带.SZ后缀）
        (clean_code_str == '000001' and 'SZ' in code.upper()),
        # 其他股票代码开头
        clean_code_str.startswith(('6', '9', '001', '002', '003', '300', '301', '68', '2'))
    ]

    # 优先级：先判断指数，再判断股票
    if any(index_rules) and not any(stock_rules):
        return True
    return False


# ===================== 自动市场识别工具类 =====================
class MarketAutoDetector:
    """自动识别沪深市场代码（0=上海，1=深圳），对用户完全透明"""

    @staticmethod
    def get_hs_market_code(code: str) -> int:
        """
        获取reader.daily所需的沪深市场代码（0/1）
        :param code: 股票/指数代码
        :return: 0=上海，1=深圳
        :raise ValueError: 无法识别时抛出异常
        """
        clean_code_str = clean_code(code)

        # 指数代码的市场判断
        if is_index_code(code):
            if clean_code_str.startswith(('000', '88')):
                return 0  # 上海指数（如000001=上证指数、000985=中证红利）
            elif clean_code_str.startswith('399'):
                return 1  # 深圳指数（如399001=深证成指）
            else:
                raise ValueError(f"无法识别指数代码 {code} 的沪深市场类型")

        # 股票代码的市场判断
        if clean_code_str.startswith(('6', '9')):
            return 0  # 上海股票（60xxx、68xxx、90xxx）
        elif clean_code_str.startswith(('0', '3', '2')):
            return 1  # 深圳股票（00xxx、300xxx、20xxx）
        else:
            raise ValueError(f"无法识别股票代码 {code} 的沪深市场类型（仅支持沪深A股）")

    @staticmethod
    def get_path_market_str(code: str) -> str:
        """
        获取本地文件路径用的市场字符串（sh/sz）
        :param code: 股票/指数代码
        :return: sh=上海，sz=深圳
        """
        hs_code = MarketAutoDetector.get_hs_market_code(code)
        return "sh" if hs_code == 0 else "sz"


# ===================== 本地数据读取器（最终版） =====================
class TdxLocalReader:
    """
    通达信本地数据读取器（初始化指定market参数）
    :param market: 市场类型，std=标准市场（沪深A股/指数），ext=扩展市场（港股/美股/期货）
    :param tdxdir: 通达信安装目录
    """

    def __init__(self, market: str = 'std', tdxdir: str = DEFAULT_TDX_DIR):
        # 核心参数
        self.market = market  # std/ext（Reader.factory用）
        self.tdxdir = tdxdir  # 通达信根目录
        self.reader = None  # mootdx Reader实例

        # 初始化Reader
        self._init_reader()

    def _init_reader(self) -> None:
        """初始化mootdx Reader实例（兼容所有版本）"""
        try:
            # 1. 校验market参数
            if self.market not in ["std", "ext"]:
                raise ValueError(f"market参数仅支持'std'（标准市场）或'ext'（扩展市场），当前值：{self.market}")

            # 2. 校验通达信目录
            if not os.path.exists(self.tdxdir):
                raise FileNotFoundError(f"通达信目录不存在：{self.tdxdir}")

            # 3. 创建Reader实例（移除config参数，兼容低版本）
            self.reader = Reader.factory(market=self.market, tdxdir=self.tdxdir)
            print(f"✅ 通达信本地读取器初始化成功")
            print(f"   ├─ 市场类型：{self.market}")
            print(f"   └─ 通达信目录：{os.path.normpath(self.tdxdir)}")

        except Exception as e:
            print(f"❌ 通达信本地读取器初始化失败：{str(e)}")
            print(f"⚠️ 后续将使用手动解析模式读取数据")
            self.reader = None

    def _get_data_file_path(self, code: str, freq: str = "day") -> str:
        """
        获取本地数据文件的标准化路径
        :param code: 股票/指数代码
        :param freq: 数据频率，day=日线，1min=1分钟，5min=5分钟
        :return: 标准化文件路径
        """
        # 获取路径用的市场字符串（sh/sz）
        market_str = MarketAutoDetector.get_path_market_str(code)
        clean_code_str = clean_code(code)

        # 确定目录和文件后缀
        if freq == "day":
            dir_name = "lday"
            file_suffix = "day"
        elif freq == "1min":
            dir_name = "minline"
            file_suffix = "lc1"
        elif freq == "5min":
            dir_name = "fzline"
            file_suffix = "lc5"
        else:
            raise ValueError(f"不支持的数据频率：{freq}（仅支持day/1min/5min）")

        # 构建并标准化路径（统一分隔符）
        file_path = os.path.normpath(os.path.join(
            self.tdxdir,
            "vipdoc",
            market_str,
            dir_name,
            f"{market_str}{clean_code_str}.{file_suffix}"
        ))
        return file_path


    def _parse_binary_file(self, file_path: str, begin_dt: datetime, end_dt: datetime,
                           freq: str = "day") -> pd.DataFrame:
        """手动解析二进制文件（终极修复版：解决Chunk长度错误+解析全0问题）"""
        data = []
        record_size = 32  # 通达信.day文件每条记录固定32字节
        valid_record_count = 0  # 有效记录数

        with open(file_path, 'rb') as f:
            while True:
                # 1. 严格读取32字节（标准记录长度）
                chunk = f.read(record_size)
                chunk_len = len(chunk)

                # 2. 跳过无效数据：不足32字节/空数据
                if chunk_len != record_size:
                    if chunk_len > 0:
                        print(f"⚠️ 跳过残片数据（长度{chunk_len}≠32）：{chunk}")
                    break

                # 3. 核心解析：指定小端序，仅解析前28字节有效数据
                try:
                    # 格式串说明：<(小端序) + I(日期4字节) + f(开4) + f(高4) + f(低4) + f(收4) + I(量4) + f(额4)
                    date_int, open_p, high_p, low_p, close_p, volume, amount = struct.unpack('<IffffIf', chunk[:28])
                except struct.error as e:
                    print(f"⚠️ 解析单条记录失败：{e} | Chunk: {chunk[:10]}...")
                    continue

                # 4. 过滤无效价格（全0/极小值）
                if open_p <= 0.000001 and high_p <= 0.000001 and low_p <= 0.000001 and close_p <= 0.000001:
                    print(f"⚠️ 跳过无效价格记录（全0）：日期={date_int}")
                    continue

                # 5. 转换日期（兼容异常日期）
                try:
                    year = date_int // 10000
                    month = (date_int % 10000) // 100
                    day = date_int % 100
                    # 校验日期合法性（排除1970/2099等异常年份）
                    if not (1990 <= year <= 2099) or not (1 <= month <= 12) or not (1 <= day <= 31):
                        print(f"⚠️ 跳过异常日期：{year}-{month}-{day}")
                        continue
                    record_dt = datetime(year, month, day)
                except ValueError as e:
                    print(f"⚠️ 日期转换失败：{e} | 原始值={date_int}")
                    continue

                # 6. 过滤日期范围
                if begin_dt <= record_dt <= end_dt:
                    data.append({
                        'datetime': record_dt,
                        'open': round(open_p, 2),
                        'high': round(high_p, 2),
                        'low': round(low_p, 2),
                        'close': round(close_p, 2),
                        'volume': volume,
                        'amount': round(amount, 2)
                    })
                    valid_record_count += 1

        # 7. 校验有效数据
        if not data:
            raise ValueError(
                f"无有效数据！共读取{valid_record_count}条有效记录，但均不在日期范围[{begin_dt.date()}, {end_dt.date()}]内"
            )

        df = pd.DataFrame(data)
        print(f"✅ 手动解析完成：共解析{len(df)}条有效记录")
        return df.sort_values('datetime').reset_index(drop=True)


    def read_daily(
            self,
            code: str,
            begin: Union[str, datetime, date] = datetime(1990, 11, 1),
            end: Union[str, datetime, date] = None,
       ) -> Optional[pd.DataFrame]:
        """
        读取本地日线数据（核心方法）
        :param code: 股票/指数代码（如600177、000001、000985）
        :param begin: 开始日期，支持datetime/date/YYYY-MM-DD字符串，默认2000-01-01
        :param end: 结束日期，支持datetime/date/YYYY-MM-DD字符串，默认当前日期
        :return: 日线数据DataFrame | None
        """

        # 1. 参数预处理（移除market相关逻辑）
        # 日期规范化（统一转为datetime）
        def to_datetime(dt: Union[str, datetime, date]) -> datetime:
            if isinstance(dt, str):
                return datetime.strptime(dt, "%Y-%m-%d")
            elif isinstance(dt, date):
                return datetime.combine(dt, datetime.min.time())
            elif isinstance(dt, datetime):
                return dt
            else:
                raise ValueError(f"不支持的日期格式：{dt}，请使用YYYY-MM-DD字符串或datetime/date对象")

        try:
            begin_dt = to_datetime(begin)
            end_dt = to_datetime(end) if end is not None else datetime.now()
        except Exception as e:
            print(f"❌ 日期格式错误：{str(e)}")
            return None

        # 2. 获取文件路径并检查
        file_path = self._get_data_file_path(code, freq="day")
        if not os.path.exists(file_path) or os.path.getsize(file_path) == 0:
            print(f"❌ 数据文件不存在/为空：{file_path}")
            print(f"⚠️ 请在通达信中下载 {code} 的日线数据（系统→盘后数据下载）")
            return None
        print(f"✅ 数据文件检查通过：{file_path}")

        # 3. 读取数据（直接使用实例初始化的reader，无需重新创建）
        df = None
        clean_code_str = clean_code(code)

        # 方案1：mootdx内置方法（原生正确用法：仅传code参数）
        if self.reader is not None:
            try:
                # 核心修正：reader.daily仅传code，返回全部数据
                df = self.reader.daily(symbol=clean_code_str)
                if df.empty:
                    print(f"❌ {code} 无日线数据")
                    return None
            except Exception as e:
                print(f"⚠️ mootdx内置方法读取失败：{str(e)}")
                print(f"🔍 切换到手动解析模式...")

        # # 方案2：手动解析（兜底）
        # if df is None or df.empty:
        #     try:
        #         df = self._parse_binary_file(file_path, begin_dt, end_dt, freq="day")
        #         print(f"✅ 手动解析模式读取成功（{code}）")
        #     except Exception as e:
        #         print(f"❌ 手动解析失败：{str(e)}")
        #         return None

        # 4. 数据格式化（保持不变）
        df.index.rename(name='datetime', inplace=True)
        df.reset_index(inplace=True)
        df['datetime'] = pd.to_datetime(df['datetime'])
        df = df[(df['datetime'] >= begin_dt) & (df['datetime'] <= end_dt)]
        df.reset_index(drop=True, inplace=True)

        # df['code'] = clean_code_str
        # df['clean_code'] = clean_code(code)
        # df['is_index'] = is_index_code(code)
        # df['pctChg'] = round((df['close'] / df['close'].shift(1) - 1) * 100, 2)
        # df['pctChg'] = df['pctChg'].fillna(0)

        # insert 股票代码
        df.insert(loc=0, column='code', value=clean_code_str)

        # 插入交易资料列
        df['Amp'] = np.nan
        df['pctChg'] = np.nan
        df['Chg'] = np.nan
        df['turn'] = np.nan
        df['pre_close'] = np.nan
        df['AdjFactor'] = np.nan
        df['total_share'] = np.nan
        df['float_share'] = np.nan

        df.sort_values(by='datetime', ascending=True, inplace=True)
        df.reset_index(drop=True, inplace=True)

        print(
            f"✅ 最终读取{code}日线数据：{len(df)}条记录（{begin_dt.strftime('%Y-%m-%d')} 至 {end_dt.strftime('%Y-%m-%d')}）")
        return df

    def read_minute(
            self,
            code: str,
            freq: str = "1min",
            begin: Union[str, datetime, date] = None,
            end: Union[str, datetime, date] = None
    ) -> Optional[pd.DataFrame]:
        """
        读取本地分钟线数据
        :param code: 股票/指数代码
        :param freq: 数据频率，1min=1分钟，5min=5分钟
        :param begin: 开始时间（分钟线建议精确到时分）
        :param end: 结束时间
        :return: 分钟线数据DataFrame | None
        """
        # 1. 参数校验
        if freq not in ["1min", "5min"]:
            print(f"❌ 不支持的分钟线频率：{freq}（仅支持1min/5min）")
            return None

        # 2. 获取文件路径
        file_path = self._get_data_file_path(code, freq=freq)
        if not os.path.exists(file_path) or os.path.getsize(file_path) == 0:
            print(f"❌ 分钟线文件不存在/为空：{file_path}")
            return None

        # 3. 读取数据（简化版，仅手动解析）
        try:
            data = []
            record_size = 32
            with open(file_path, 'rb') as f:
                while True:
                    chunk = f.read(record_size)
                    if not chunk:
                        break

                    # 解析分钟线数据（格式与日线类似，日期为YYYYMMDD，时间为HHMM）
                    date_int = struct.unpack('I', chunk[0:4])[0]
                    time_int = struct.unpack('H', chunk[4:6])[0]
                    open_price = struct.unpack('f', chunk[6:10])[0]
                    high_price = struct.unpack('f', chunk[10:14])[0]
                    low_price = struct.unpack('f', chunk[14:18])[0]
                    close_price = struct.unpack('f', chunk[18:22])[0]
                    volume = struct.unpack('I', chunk[22:26])[0]
                    amount = struct.unpack('f', chunk[26:30])[0]

                    # 转换时间
                    year = date_int // 10000
                    month = (date_int % 10000) // 100
                    day = date_int % 100
                    hour = time_int // 100
                    minute = time_int % 100

                    try:
                        record_dt = datetime(year, month, day, hour, minute)
                    except ValueError:
                        continue  # 跳过无效时间

                    # 过滤时间范围
                    if begin is not None or end is not None:
                        begin_dt = to_datetime(begin) if begin else datetime.min
                        end_dt = to_datetime(end) if end else datetime.max
                        if not (begin_dt <= record_dt <= end_dt):
                            continue

                    data.append({
                        'datetime': record_dt,
                        'open': round(open_price, 2),
                        'high': round(high_price, 2),
                        'low': round(low_price, 2),
                        'close': round(close_price, 2),
                        'volume': volume,
                        'amount': round(amount, 2),
                        'code': code
                    })

            if not data:
                print(f"❌ 无符合条件的{freq}数据")
                return None

            df = pd.DataFrame(data)
            df = df.sort_values('datetime').reset_index(drop=True)
            print(f"✅ 成功读取{code}{freq}数据：{len(df)}条记录")
            return df

        except Exception as e:
            print(f"❌ 读取{freq}数据失败：{str(e)}")
            return None


# ===================== 远程行情客户端 =====================
class TdxRemoteQuotes:
    """通达信远程行情客户端（自动识别市场）"""

    def __init__(self):
        self.client = None
        self.connected = False
        self._init_client()

    def _init_client(self) -> None:
        """初始化远程行情客户端"""
        try:
            self.client = Quotes.factory(market='std')
            print(f"✅ 远程行情客户端初始化成功")
        except Exception as e:
            print(f"❌ 远程行情客户端初始化失败：{str(e)}")

    def connect(self) -> bool:
        """
        连接远程服务器（测试连通性）
        :return: 连接成功返回True，失败返回False
        """
        if self.client is None:
            print(f"❌ 客户端未初始化，无法连接")
            return False

        try:
            # 测试连接（获取测试股票数据）
            self.client.quote(code='600000', market=0)
            self.connected = True
            print(f"✅ 通达信远程服务器连接成功")
            return True
        except Exception as e:
            print(f"❌ 远程服务器连接失败：{str(e)}")
            self.connected = False
            return False

    def get_hist_kline(
            self,
            code: str,
            adjust: str = "qfq",
            begin: Union[str, datetime, date] = datetime(2000, 1, 1),
            end: Union[str, datetime, date] = None
    ) -> Optional[pd.DataFrame]:
        """
        获取远程K线数据
        :param code: 股票/指数代码
        :param adjust: 复权类型，qfq=前复权，hfq=后复权，None=不复权
        :param begin: 开始日期
        :param end: 结束日期
        :return: K线数据DataFrame | None
        """
        if not self.connected:
            print(f"❌ 未连接远程服务器，请先调用connect()")
            return None

        # 1. 参数预处理
        try:
            # 日期规范化
            def to_datetime(dt: Union[str, datetime, date]) -> datetime:
                if isinstance(dt, str):
                    return datetime.strptime(dt, "%Y-%m-%d")
                elif isinstance(dt, date):
                    return datetime.combine(dt, datetime.min.time())
                return dt

            begin_dt = to_datetime(begin)
            end_dt = to_datetime(end) if end is not None else datetime.now()

            # 自动识别沪深市场代码
            hs_market_code = MarketAutoDetector.get_hs_market_code(code)
            clean_code_str = clean_code(code)

        except Exception as e:
            print(f"❌ 参数预处理失败：{str(e)}")
            return None

        # 2. 获取K线数据
        try:
            df = self.client.bars(
                code=clean_code_str,
                frequency=9,  # 9=日线，0=1分钟，1=5分钟
                market=hs_market_code,
                start=0,
                count=10000,
                adjust=adjust if adjust else None
            )

            if df is None or df.empty:
                print(f"❌ 无{code}远程K线数据")
                return None

            # 3. 数据格式化
            df['datetime'] = pd.to_datetime(df['datetime'])
            df = df[(df['datetime'] >= begin_dt) & (df['datetime'] <= end_dt)]
            df.reset_index(drop=True, inplace=True)

            # 统一列名
            df.rename(columns={'vol': 'volume'}, inplace=True)
            df['code'] = code
            df['pctChg'] = round((df['close'] / df['close'].shift(1) - 1) * 100, 2)
            df['pctChg'] = df['pctChg'].fillna(0)

            print(f"✅ 成功获取{code}{adjust}K线数据：{len(df)}条记录")
            return df

        except Exception as e:
            print(f"❌ 获取远程K线数据失败：{str(e)}")
            return None

    def get_realtime_quote(self, codes: List[str]) -> Optional[pd.DataFrame]:
        """
        获取实时行情数据
        :param codes: 股票/指数代码列表（如['600177', '000001']）
        :return: 实时行情DataFrame | None
        """
        if not self.connected:
            print(f"❌ 未连接远程服务器，请先调用connect()")
            return None

        try:
            data = []
            for code in codes:
                try:
                    hs_code = MarketAutoDetector.get_hs_market_code(code)
                    clean_code_str = clean_code(code)
                    quote = self.client.quote(code=clean_code_str, market=hs_code)
                    if quote is not None and not quote.empty:
                        quote['code'] = code
                        quote['is_index'] = is_index_code(code)
                        data.append(quote.iloc[0])
                except Exception as e:
                    print(f"⚠️ 获取{code}实时行情失败：{str(e)}")

            if not data:
                print(f"❌ 无有效实时行情数据")
                return None

            df = pd.DataFrame(data)
            print(f"✅ 成功获取{len(df)}个标的的实时行情")
            return df

        except Exception as e:
            print(f"❌ 获取实时行情失败：{str(e)}")
            return None


# ===================== 财务报告解析 =====================
class TdxFinancialReport:
    """财务报告解析工具（下载+解析gpcw文件）"""

    @staticmethod
    def download_and_parse(rpt_date: Union[str, datetime, date] = None, downdir: str = None) -> Optional[pd.DataFrame]:
        """
        下载并解析财务报告数据
        :param rpt_date: 报告日期（如2023-12-31）
        :param downdir: 下载目录，默认项目根目录/doc
        :return: 财报数据DataFrame | None
        """
        # 1. 参数预处理
        if rpt_date is None:
            rpt_date = datetime.now().replace(year=datetime.now().year - 1, month=12, day=31)

        try:
            if isinstance(rpt_date, str):
                rpt_date = datetime.strptime(rpt_date, "%Y-%m-%d")
            elif isinstance(rpt_date, date):
                rpt_date = datetime.combine(rpt_date, datetime.min.time())
        except Exception as e:
            print(f"❌ 报告日期格式错误：{str(e)}")
            return None

        # 2. 确定下载目录
        if downdir is None:
            try:
                # 默认项目根目录/doc
                script_dir = Path(__file__).parent
                project_root = script_dir.parent.parent
                downdir = project_root / 'doc'
            except Exception:
                # 备用：当前目录/doc
                downdir = Path.cwd() / 'doc'

        downdir = Path(downdir)
        downdir.mkdir(exist_ok=True)

        # 3. 下载/解析文件
        str_date = rpt_date.strftime('%Y%m%d')
        file_name = f'gpcw{str_date}.zip'
        file_path = downdir / file_name

        print(f"📁 财报文件路径：{os.path.normpath(file_path)}")

        # 3.1 下载文件
        if not file_path.exists():
            print(f"⚠️ 财报文件不存在，尝试下载：{file_name}")
            try:
                b_download = Affair.fetch(downdir=str(downdir), filename=file_name)
                if not b_download:
                    print(f"❌ 财报文件下载失败")
                    return None
            except Exception as e:
                print(f"❌ 财报下载失败：{str(e)}")
                return None

        # 3.2 解析文件
        try:
            df = Affair.parse(downdir=str(downdir), filename=file_name)
            if df is None or df.empty:
                print(f"❌ 财报解析结果为空")
                return None

            # 数据清洗
            df = df.reset_index()
            df['report_date'] = pd.to_datetime(df['report_date'], format='%Y%m%d', errors='coerce')

            # 处理重复列名
            new_columns = list(df.columns)
            column_mapping = {
                143: '财务费用A', 237: 'N筹资活动产生的现金流量净额A',
                233: '归属于母公司所有者的净利润A', 235: '经营活动产生的现金流量净额A',
                198: '净资产收益率A', 234: '扣除非经常性损益后的净利润A',
                236: '投资活动产生的现金流量净额A', 238: '现金及现金等价物净增加额A',
                581: '信用减值损失(万元)A'
            }

            for idx, name in column_mapping.items():
                if idx < len(new_columns):
                    new_columns[idx] = name

            df.columns = new_columns
            df.drop_duplicates(subset=['code', 'report_date'], keep='first', inplace=True)

            print(f"✅ 财报解析完成：{len(df)}条记录，{len(df.columns)}个字段")
            return df

        except Exception as e:
            print(f"❌ 财报解析失败：{str(e)}")
            return None


# ===================== 自测代码 =====================
if __name__ == "__main__":
    print("=" * 80)
    print("📊 通达信数据接口（dc_tdx.py）自测开始")
    print("=" * 80)

    # 1. 本地数据读取测试
    print("\n【1. 本地数据读取测试】")
    local_reader = TdxLocalReader(market='std', tdxdir=DEFAULT_TDX_DIR)

    # 1.1 读取股票（600177）
    df_stock = local_reader.read_daily(
        code="600177",
        begin=datetime(2024, 1, 1),
        end=datetime.now()
    )

    # 1.2 读取指数（000985）
    df_index = local_reader.read_daily(
        code="000985",
        begin="2024-01-01",
        end=date.today()
    )

    # 1.3 读取双重身份代码（000001.SZ 股票）
    df_000001_stock = local_reader.read_daily(
        code="000001.SZ",
        begin=datetime(2024, 1, 1)
    )

    # 2. 远程行情测试
    print("\n【2. 远程行情获取测试】")
    remote_quotes = TdxRemoteQuotes()
    remote_quotes.connect()

    # 2.1 获取K线数据
    df_kline = remote_quotes.get_hist_kline(
        code="600177",
        adjust="qfq",
        begin=datetime(2024, 1, 1)
    )

    # 2.2 获取实时行情
    df_realtime = remote_quotes.get_realtime_quote(codes=["600177", "000985"])

    # 3. 财报解析测试
    print("\n【3. 财务报告解析测试】")
    df_report = TdxFinancialReport.download_and_parse("2023-12-31")

    # 4. 结果汇总
    print("\n" + "=" * 80)
    print("📊 自测结果汇总")
    print("=" * 80)
    print(f"1. 本地股票数据：{'成功' if df_stock is not None else '失败'}")
    print(f"2. 本地指数数据：{'成功' if df_index is not None else '失败'}")
    print(f"3. 000001.SZ股票数据：{'成功' if df_000001_stock is not None else '失败'}")
    print(f"4. 远程K线数据：{'成功' if df_kline is not None else '失败'}")
    print(f"5. 实时行情数据：{'成功' if df_realtime is not None else '失败'}")
    print(f"6. 财务报告数据：{'成功' if df_report is not None else '失败'}")
    print("=" * 80)