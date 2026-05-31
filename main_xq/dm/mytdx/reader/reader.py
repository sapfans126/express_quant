import os
from main_xq.base.security_type import SECURITY_TYPE
import main_xq.config.config as cfg
from typing import Optional
import numpy as np
import pandas as pd
import main_xq.base.code_utils as utl
from .file_format import TdxFormatter, Columns

# 导入日志工具
from main_xq.utils.logger import get_logger_for_current_module

# 自动获取正确的模块名
logger = get_logger_for_current_module(__file__)


class Reader:
    # market：市场类型，默认SH股
    market = "A股"
    # file_type：数据类型，默认日线
    file_type = "day"

    def __init__(self, tdx_data_dir=None):
        """
        初始化Reader实例
        :param tdx_data_dir: 通达信数据目录路径（字符串）
        """
        if tdx_data_dir is None:
            tdx_config = cfg.MyTdxConfig()
            self.tdx_data_dir = tdx_config.get(section="TDX_DATA", key="tdx_data_dir")
        else:
            self.tdx_data_dir = tdx_data_dir

        if not os.path.exists(self.tdx_data_dir):
            logger.error(f"通达信数据目录不存在：{self.tdx_data_dir}")

        logger.info(f"Reader初始化完成，数据目录: {self.tdx_data_dir}")

    @staticmethod
    def read_file(file_pathname: str) -> Optional[bytes]:
        try:
            with open(file_pathname, 'rb') as f:
                raw_data = f.read()
            logger.debug(f"成功读取 {os.path.basename(file_pathname)}，数据大小：{len(raw_data)} 字节")
            return raw_data
        except Exception as e:
            logger.error(f"读取文件失败 {file_pathname}: {e}", exc_info=True)
            return None

    @staticmethod
    def parse_file(raw_data: bytes, fmt_struct: Columns) -> Optional[pd.DataFrame]:
        """
        解析二进制数据为DataFrame
        :param raw_data: 二进制数据
        :param fmt_struct: Columns 实例
        :return: DataFrame
        """
        try:
            _dtype = fmt_struct.dtype
            record_size = _dtype.itemsize
            data_size = len(raw_data)

            if data_size % record_size != 0:
                valid_size = (data_size // record_size) * record_size
                raw_data = raw_data[:valid_size]
                logger.warning(
                    f"原始数据大小 {data_size} 不是记录大小 {record_size} 的整数倍，"
                    f"已截断为 {valid_size} 字节 ({valid_size // record_size} 条记录)"
                )

            data_array = np.frombuffer(raw_data, dtype=_dtype)
            df = pd.DataFrame(data_array)

            # logger.debug(f"numpy解析成功：{len(data_array)}条记录，列：{list(df.columns)}")

            # 应用缩放系数
            if hasattr(fmt_struct, 'scale_factors') and fmt_struct.scale_factors:
                for i, col in enumerate(df.columns):
                    if i < len(fmt_struct.scale_factors) and fmt_struct.scale_factors[i] != 1.0:
                        df[col] = df[col] * fmt_struct.scale_factors[i]

            return df

        except Exception as e:
            logger.error(f"解析文件失败：{e}", exc_info=True)
            return None

    def read_hist_quote(self,
                        symbol: str,
                        security_type: SECURITY_TYPE | str = SECURITY_TYPE.CN_AS,
                        period: str = "day") -> Optional[pd.DataFrame]:
        """读取历史行情数据"""
        logger.info(f"开始读取数据: {symbol}, 类型: {security_type}, 周期: {period}")

        # 解析代码
        clean_code = utl.parse_security_code(symbol=symbol, security_type=security_type)

        if clean_code.get("error"):
            logger.error(f"证券代码解析失败：{clean_code['error']}")
            return None

        code = clean_code.get('code', '')
        market = clean_code.get('market', '')
        file_prefix = clean_code.get('pre_fix', '')

        if not market or not code:
            logger.error("证券代码解析结果不完整")
            return None

        # 获取文件类型格式
        try:
            tdx_fmt = TdxFormatter.get_tdxfile_format(file_type=period)
            logger.debug(
                f"文件格式信息: 名称={tdx_fmt.name}, "
                f"子目录={tdx_fmt.sub_dir}, 后缀={tdx_fmt.file_suffix}, "
                f"字段={tdx_fmt.field_names}, 记录大小={tdx_fmt.record_size}字节"
            )
        except Exception as e:
            logger.error(f"获取文件格式失败: {e}", exc_info=True)
            return None

        # 合成文件路径
        data_dir = os.path.join(self.tdx_data_dir, market, tdx_fmt.sub_dir)

        if not os.path.exists(data_dir):
            logger.error(f"数据目录不存在: {data_dir}")
            return None

        filename = f"{file_prefix}{code}.{tdx_fmt.file_suffix}"
        file_path = os.path.join(data_dir, filename)

        logger.debug(f"数据目录: {data_dir}")
        logger.debug(f"文件名: {filename}")
        logger.debug(f"完整路径: {file_path}")

        if not os.path.exists(file_path):
            logger.error(f"数据文件不存在: {file_path}")
            return None

        # 读取和解析
        raw_data = self.read_file(file_path)
        if raw_data:
            df_quote = self.parse_file(raw_data, tdx_fmt)
            if df_quote is not None:
                # 插入股票代碼
                df_quote.insert(loc=0, column='code', value=code)
                logger.info(f"成功读取 {symbol} 数据，共 {len(df_quote)} 条记录")
            return df_quote
        return None

    def read_hist_price_dd(self,symbol: str,
                           security_type: SECURITY_TYPE | str = SECURITY_TYPE.CN_AS
                           )-> Optional[pd.DataFrame]:
        df_dd = self.read_hist_quote(symbol=symbol,security_type=security_type,period='day')
        if df_dd is None or len(df_dd) == 0:
            return None
        else:
            # 插入交易资料列
            df_dd['Amp'] = np.nan
            df_dd['pctChg'] = np.nan
            df_dd['Chg'] = np.nan
            df_dd['turn'] = np.nan
            df_dd['pre_close'] = np.nan
            df_dd['AdjFactor'] = np.nan
            df_dd['total_share'] = np.nan
            df_dd['float_share'] = np.nan
        return df_dd


# ===================== 测试用例 =====================
if __name__ == "__main__":
    # 注意：测试代码中的 print 可以保留，因为只在直接运行时使用
    # 但也可以改为 logger 以便统一管理

    logger.info("开始测试 Reader 类")

    try:
        rd = Reader()
        logger.info(f"Reader 实例创建成功，数据目录: {rd.tdx_data_dir}")

        d = rd.read_hist_quote(symbol='600000')

        if d is not None:
            logger.info(f"成功读取数据，共 {len(d)} 条记录")
            print(d.head())  # 这里用 print 没问题，因为要显示数据预览
            logger.info(f"数据预览:\n{d.head()}")
        else:
            logger.error("读取数据失败")

    except Exception as e:
        logger.error(f"测试失败: {e}", exc_info=True)
