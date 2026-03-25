from typing import NamedTuple, Tuple,List, Dict, Optional,Any
import numpy as np
from numpy import dtype, void


class Columns(NamedTuple):
    """通达信数据格式定义"""
    name: str  # 类型名称 如 day/min/5min
    sub_dir: str # 文件子目录
    file_suffix:str # 文件后缀
    struct_fmt: str  # struct格式字符串（用于验证大小）
    field_names: List[str]  # 字段名列表
    numpy_dtypes: List[Any]  # NumPy数据类型列表
    scale_factors: List[float]  # 缩放系数列表（1.0表示不缩放）

    @property
    def dtype(self) -> np.dtype:
        """生成NumPy dtype对象"""
        return np.dtype(list(zip(self.field_names, self.numpy_dtypes)))

    @property
    def record_size(self) -> int:
        """计算记录大小（字节）"""
        return self.dtype.itemsize

# 通达信不同数据文件的格式定义
TDX_FILE_FORMAT: Dict[str, Columns] = {
    "day": Columns(
        name="day",
        sub_dir = "lday",
        file_suffix = "day",
        struct_fmt="<IIIIIfII",  # 用于验证
        field_names=["datetime", "open", "high", "low", "close", "amount", "volume", "unused1"],
        numpy_dtypes=[
            np.uint32,  # datetime: 20240101格式
            np.uint32,  # open: 需要缩放÷1000
            np.uint32,  # high: 需要缩放÷1000
            np.uint32,  # low: 需要缩放÷1000
            np.uint32,  # close: 需要缩放÷1000
            np.float32,  # amount: 成交额
            np.uint32,  # volume: 成交量
            np.uint32,  # unused1
        ],
        scale_factors=[1.0, 0.01, 0.01, 0.01, 0.01, 1.0, 1.0, 1.0]
    ),
    "min": Columns(
        name="min",
        sub_dir = "lday",
        file_suffix="lc1",
        struct_fmt="<IIfffffII",
        field_names=["datetime", "open", "high", "low", "close", "amount", "volume", "unused1", "unused2"],
        numpy_dtypes=[
            np.uint32,  # datetime: 93000000格式（时分秒毫秒）
            np.float32,  # open: 直接是float，无需缩放
            np.float32,  # high
            np.float32,  # low
            np.float32,  # close
            np.float32,  # amount
            np.uint32,  # volume
            np.uint32,  # unused1
            np.uint32  # unused2
        ],
        scale_factors=[1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0]
    ),
    "5min": Columns(
        name="5min",
        sub_dir = "lday",
        file_suffix="lc5",
        struct_fmt="<IIfffffII",
        field_names=["datetime", "open", "high", "low", "close", "amount", "volume", "unused1", "unused2"],
        numpy_dtypes=[
            np.uint32,  # datetime
            np.float32,  # open
            np.float32,  # high
            np.float32,  # low
            np.float32,  # close
            np.float32,  # amount
            np.uint32,  # volume
            np.uint32,  # unused1
            np.uint32  # unused2
        ],
        scale_factors=[1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0]
    ),
}


class TdxFormatter:
    @staticmethod
    def get_tdxfile_format(file_type: str) -> Columns:
        """
        获取通达信文件格式定义

        Args:
            file_type: 文件类型，如 "day"（日线）、"min"（分钟线）、"5min"（5分钟线）
        Returns:

        """
        # 统一文件类型为小写，增强兼容性
        file_type = file_type.lower()

        # 检查文件类型是否支持
        if file_type not in TDX_FILE_FORMAT:
            supported_types = list(TDX_FILE_FORMAT.keys())
            raise ValueError(
                f"不支持的文件类型: {file_type}，当前支持的类型为: {supported_types}"
            )

        return TDX_FILE_FORMAT[file_type]

        # # 获取对应的格式定义
        # format_def = TDX_FILE_FORMAT[file_type]
        #
        # # 文件子目录
        # tdx_sub_dir = format_def.sub_dir
        #
        # # 从format_def中获取field_names和numpy_dtypes合成dtype
        # # # 方法1：直接使用format_def的dtype属性（推荐）
        # # dtype = format_def.dtype
        #
        # # 方法2：手动合成（如果需要更灵活的控制）
        # dtype = np.dtype(list(zip(format_def.field_names, format_def.numpy_dtypes)))
        #
        # # 获取缩放系数列表的副本，避免外部修改影响原数据
        # scale_factors = format_def.scale_factors.copy()
        #
        # return tdx_sub_dir, dtype, scale_factors

# if __name__ == "__main__":
#     tds = TdxFormatter.get_tdxfile_format('day')
#     print(tds.sub_dir)
#     print(tds.field_names)
#     print(tds)

