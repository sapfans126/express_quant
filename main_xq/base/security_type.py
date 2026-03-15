# -*- coding: utf-8 -*-
"""
常量定义文件
包含市场、标的类型、代码规则等核心常量
"""
from enum import Enum

# ===================== 市场相关常量 =====================
# 市场标识（适配通达信/通用金融数据接口）
class MARKET_TYPE(Enum):
    # 市场名称: (标准标识, 扩展标识)
    MARKET_STD = "std"  # 标准
    MARKET_EXT = "ext"  # 扩展

    @classmethod
    def has_value(cls, value):
        return value in [item.value for item in cls]

    @classmethod
    def get_by_value(cls, value):
        for item in cls:
            if item.value == value:
                return item
        return None


# 交易市场
class MARKET(Enum):
    MARKET_SHANGHAI = "sh"
    MARKET_SHENZHEN = "sz"
    MARKET_BEIJING  = "bj"
    MARKET_EXT = "ds"

    @classmethod
    def has_value(cls, value):
        return value in [item.value for item in cls]

    @classmethod
    def get_by_value(cls, value):
        for item in cls:
            if item.value == value:
                return item
        return None


# ===================== 标的类型常量 =====================
# 标的类型标识
class SECURITY_TYPE(Enum):

    CN_AS = "CN_AS"  # 全部A股
    BJ_AS = "BJ_AS"  # 京股
    SZ_AS = "SZ_AS"  # 深圳A股
    SH_AS = 'SH_AS'  # 上海A股
    CN_ETF = "CN_ETF"

    @classmethod
    def has_value(cls, value):
        return value in [item.value for item in cls]

    @classmethod
    def get_by_value(cls, value):
        for item in cls:
            if item.value == value:
                return item
        return None


SECURITY_CODE_MAP = {
    # 全部A股
    'CN_AS' : {
        'rule': '6-D',
        'prefix_map' : {
            '00': {'market': 'sz', 'pre_fix': 'sz', 'type': 'SZ_AS', 'Res1': ''},  # 深圳A股
            '30': {'market': 'sz', 'pre_fix': 'sz', 'type': 'SZ_AS', 'Res1': ''},  # 深圳创业板A股
            '60': {'market': 'sh', 'pre_fix': 'sh', 'type': 'SH_AS', 'Res1': ''},  # 上海A股
            '68': {'market': 'sh', 'pre_fix': 'sh', 'type': 'SH_AS', 'Res1': ''},  # 上海科创板A股
            '92': {'market': 'bj', 'pre_fix': 'bj', 'type': 'BJ_AS', 'Res1': ''},  # 北京A股
            '11': {'market': 'sh', 'pre_fix': 'sh', 'type': 'SH_CB', 'Res1': ''},  # 上海可转债
            '12': {'market': 'sz', 'pre_fix': 'sz', 'type': 'SZ_CB', 'Res1': ''}   # 深圳可转债
        }
    },
    # 深圳A股
    'SZ_AS': {
        'rule': '6-D',
        'prefix_map': {
            '00': {'market': 'sz', 'pre_fix': 'sz', 'type': 'SZ_AS', 'Res1': ''},  # 深圳A股
            '30': {'market': 'sz', 'pre_fix': 'sz', 'type': 'SZ_AS', 'Res1': ''}   # 深圳创业板A股
        }
    },
    # 上海A股
    'SH_AS': {
        'rule': '6-D',
        'prefix_map': {
            '60': {'market': 'sh', 'pre_fix': 'sh', 'type': 'SH_AS', 'Res1': ''},  # 上海A股
            '68': {'market': 'sh', 'pre_fix': 'sh', 'type': 'SH_AS', 'Res1': ''}   # 上海科创板A股
        }
    },
    # 北京A股
    'BJ_AS': {
        'rule': '6-D',
        'prefix_map': {
            '92': {'market': 'bj', 'pre_fix': 'bj', 'type': 'BJ_AS', 'Res1': ''}   # 北京A股
        }
    }

}

# ===================== 导出控制 =====================
__all__ = [
    'MARKET_TYPE',
    'MARKET',
    'SECURITY_TYPE',
    'SECURITY_CODE_MAP'  # 明确导出
]

print("✅ SECURITY_CODE_MAP 定义完成，类型：", type(SECURITY_CODE_MAP))