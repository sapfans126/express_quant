"""
复权模式枚举（专为通达信接口设计）
输入: na/ba/fa (任意大小写)
输出: none/back/front (通达信标准值)
"""
from enum import Enum

from enum import Enum


class AdjustMode(Enum):
    NONE = "none"  # 不复权（原始价格）

    # 后复权 BACK -> BA
    BACK = "back"  # 后复权（标准）
    PBA = "pba"  # 定点后复权
    RBA = "rba"  # 等比后复权

    # 前复权 FRONT -> FA
    FRONT = "front"  # 前复权（标准）
    PFA = "pfa"  # 定点前复权
    RFA = "rfa"  # 等比前复权

    @classmethod
    def from_code(cls, code: str | None) -> "AdjustMode":
        """
        支持输入：
        na / none   → NONE
        ba / back   → BACK
        pba         → PBA
        rba         → RBA
        fa / front  → FRONT
        pfa         → PFA
        rfa         → RFA
        不区分大小写
        """
        if not code:
            return cls.NONE

        c = str(code).strip().lower()

        mapping = {
            "na": cls.NONE,
            "none": cls.NONE,

            "ba": cls.BACK,
            "back": cls.BACK,
            "pba": cls.PBA,
            "rba": cls.RBA,

            "fa": cls.FRONT,
            "front": cls.FRONT,
            "pfa": cls.PFA,
            "rfa": cls.RFA,
        }
        return mapping.get(c, cls.NONE)

