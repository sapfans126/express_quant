import os
import base.security_type as typ
from base.security_type import SECURITY_TYPE
import config.config as cfg
from typing import Optional
from typing import cast
import numpy as np
import pandas as pd

import base.code_utils as utl
from file_format import TDX_FILE_FORMAT
from file_format import TdxFormatter
from file_format import Columns

from main_xq.utils.log import logger
import file_utils as fil

# from dc import clean_code


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
        # 实例变量：每个实例独立拥有
        if tdx_data_dir is None:
            tdx_config = cfg.MyTdxConfig()
            self.tdx_data_dir = tdx_config.get(section="TDX_DATA", key="tdx_data_dir")
        else:
            self.tdx_data_dir = tdx_data_dir

        # 验证目录路径是否有效（可选的健壮性检查）
        if not os.path.exists(self.tdx_data_dir):
            raise ValueError(f"指定的通达信数据目录不存在：{self.tdx_data_dir}")

    @staticmethod
    def read_file(file_pathname: str) -> Optional[bytes]:
        with open(file_pathname, 'rb') as f:
            raw_data = f.read()
        print(f"✅ 成功读取 {os.path.basename(file_pathname)}，数据大小：{len(raw_data)} 字节")
        return raw_data

    @staticmethod
    def parse_file(raw_data: bytes, fmt_struct: Columns) -> Optional[pd.DataFrame]:
        """
        解析二进制数据为DataFrame
        :param raw_data: 二进制数据
        :param fmt_struct: Columns 实例
        :return: DataFrame
        """
        try:
            # fmt_struct 已经是 Columns 实例，直接获取其 dtype 属性
            _dtype = fmt_struct.dtype  # 这里会调用 @property，返回 np.dtype 对象

            # 检查数据大小是否是记录大小的整数倍
            record_size = _dtype.itemsize
            data_size = len(raw_data)

            if data_size % record_size != 0:
                # 如果不是整数倍，截断多余字节
                valid_size = (data_size // record_size) * record_size
                raw_data = raw_data[:valid_size]
                print(f"⚠️ 原始数据大小 {data_size} 不是记录大小 {record_size} 的整数倍")
                print(f"   已截断为 {valid_size} 字节 ({valid_size // record_size} 条记录)")

            # 使用 frombuffer 解析
            data_array = np.frombuffer(raw_data, dtype=_dtype)
            df = pd.DataFrame(data_array)

            print(f"✅ numpy解析成功：{len(data_array)}条记录")
            print(f"   DataFrame列：{list(df.columns)}")

            # 应用缩放系数（如果需要）
            if hasattr(fmt_struct, 'scale_factors') and fmt_struct.scale_factors:
                # 对数值列应用缩放
                for i, col in enumerate(df.columns):
                    if i < len(fmt_struct.scale_factors) and fmt_struct.scale_factors[i] != 1.0:
                        df[col] = df[col] * fmt_struct.scale_factors[i]

            return df

        except Exception as e:
            print(f"❌ 解析文件失败：{e}")
            import traceback
            traceback.print_exc()
            return None

    def read_hist_quote(self,
                        symbol: str,
                        security_type: SECURITY_TYPE | str = SECURITY_TYPE.CN_AS,
                        period: str = "day") -> Optional[pd.DataFrame]:

        # 解析代码
        clean_code = utl.parse_security_code(symbol=symbol, security_type=security_type)

        # 检查结果
        if clean_code.get("error"):
            print(f"❌ 证券代码解析失败：{clean_code['error']}")
            return None

        code = clean_code.get('code', '')
        market = clean_code.get('market', '')
        file_prefix = clean_code.get('pre_fix', '')

        if not market or not code:
            print("证券代码解析结果不完整")
            return None

        # 获取文件类型格式
        try:
            # get_tdxfile_format 返回 Columns 实例
            tdx_fmt = TdxFormatter.get_tdxfile_format(file_type=period)

            # 确认 tdx_fmt 是实例
            print(f"📋 文件格式信息：")
            print(f"  - 类型：{type(tdx_fmt)}")
            print(f"  - 名称：{tdx_fmt.name}")
            print(f"  - 子目录：{tdx_fmt.sub_dir}")
            print(f"  - 后缀：{tdx_fmt.file_suffix}")
            print(f"  - 字段：{tdx_fmt.field_names}")
            print(f"  - 记录大小：{tdx_fmt.record_size} 字节")

        except Exception as e:
            print(f"❌ 获取文件格式失败: {e}")
            return None

        # 1. 合成完整的数据目录路径
        data_dir = os.path.join(self.tdx_data_dir, market, tdx_fmt.sub_dir)

        # 检查目录是否存在
        if not os.path.exists(data_dir):
            print(f"❌ 数据目录不存在: {data_dir}")
            return None

        # 2. 合成文件名（前缀 + 代码 + 后缀）
        filename = f"{file_prefix}{code}.{tdx_fmt.file_suffix}"

        # 3. 合成完整文件路径
        file_path = os.path.join(data_dir, filename)

        print(f"📂 数据目录: {data_dir}")
        print(f"📄 文件名: {filename}")
        print(f"🔗 完整路径: {file_path}")

        # 检查文件是否存在
        if not os.path.exists(file_path):
            print(f"❌ 数据文件不存在: {file_path}")
            return None

        # 读取文件
        raw_data = self.read_file(file_path)

        if raw_data:
            # 解析文件
            df_quote = self.parse_file(raw_data, tdx_fmt)
            return df_quote
        else:
            return None




# ===================== 测试用例 =====================
# def test_reader_with_and_without_dir():
#     """测试Reader类：传入tdx_data_dir 和 不传入（从ini读取）两种情况"""
#     print("=== 测试 Reader 类（基于已有mytdx.ini）===\n")
#
#     # ------------------- 测试1：手动传入 tdx_data_dir -------------------
#     print("【测试1】手动传入有效tdx_data_dir")
#     # 替换为你本地的一个有效目录（临时目录/真实TDX目录都可以）
#     manual_dir = os.path.join(os.path.expanduser("~"), "temp_tdx_test")
#     # 确保目录存在
#     os.makedirs(manual_dir, exist_ok=True)
#
#     try:
#         reader1 = Reader(tdx_data_dir=manual_dir)
#         print(f"✅ 实例创建成功")
#         print(f"  - 传入的目录：{manual_dir}")
#         print(f"  - 实例中的目录：{reader1.tdx_data_dir}")
#         print(f"  - 目录存在性：{os.path.exists(reader1.tdx_data_dir)}")
#     except Exception as e:
#         print(f"❌ 测试失败：{e}")
#     finally:
#         # 清理临时目录（如果是测试目录，可选删除）
#         if os.path.exists(manual_dir):
#             os.rmdir(manual_dir)  # 仅删除空目录，避免误删真实数据
#
#     print("\n" + "-" * 60 + "\n")
#
#     # ------------------- 测试2：不传入tdx_data_dir（从ini读取） -------------------
#     print("【测试2】不传入tdx_data_dir（从mytdx.ini读取）")
#     try:
#         # 先验证配置文件是否能正常读取（调试用）
#         tdx_config = cfg.MyTdxConfig()
#         ini_dir = tdx_config.get("TDX_DATA", "tdx_data_dir")
#         print(f"📌 从ini读取的目录：{ini_dir}")
#
#         # 创建Reader实例（不传入目录）
#         reader2 = Reader()
#         print(f"✅ 实例创建成功")
#         print(f"  - 实例中的目录：{reader2.tdx_data_dir}")
#         print(f"  - 目录存在性：{os.path.exists(reader2.tdx_data_dir)}")
#
#         # 验证读取的目录和ini一致
#         assert reader2.tdx_data_dir == ini_dir, "实例目录与ini配置不一致！"
#         print(f"✅ 验证通过：实例目录与ini配置完全一致")
#     except FileNotFoundError as e:
#         print(f"❌ 测试失败：配置文件不存在 - {e}")
#     except ValueError as e:
#         print(f"❌ 测试失败：ini中的目录不存在 - {e}")
#     except AssertionError as e:
#         print(f"❌ 测试失败：{e}")
#     except Exception as e:
#         print(f"❌ 测试失败（未知错误）：{e}")
#
#     print("\n=== 所有测试完成 ===")


if __name__ == "__main__":
    # 运行测试前，确认：
    # 1. mytdx.ini中[TDX_DATA]节下有tdx_data_dir配置
    # 2. config.py中的MyTdxConfig能正确读取该配置
    # 3. Reader类中的cfg.MyTdxConfig导入正常
    # test_reader_with_and_without_dir()
    rd = Reader()
    d = rd.read_hist_quote(symbol='600000')
    print(d)