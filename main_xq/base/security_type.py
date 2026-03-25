# -*- coding: utf-8 -*-
"""
常量定义文件
包含市场、标的类型、代码规则等核心常量
"""
import sys
from pathlib import Path
ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(ROOT))

from enum import Enum

# ===================== 日志配置 =====================
# 导入日志工具
from main_xq.utils.log import get_logger_for_current_module,_initialized

# 自动获取正确的模块名
logger = get_logger_for_current_module(__file__)


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

# ===================== 模块加载日志 =====================
# 只在模块被直接运行时输出，导入时不输出
if __name__ == "__main__":
    # 如果是直接运行，确保日志已初始化
    if not _initialized:  # 注意：需要导入 _initialized
        from main_xq.utils.log import init_logger

        init_logger(is_debug=True)

    logger.info(f"常量模块加载完成")
else:
    # 作为模块被导入时，使用 DEBUG 级别输出（仅当调试模式）
    logger.debug(f"常量模块已导入")


# ===================== 独立运行测试 =====================
if __name__ == "__main__":
    logger.info("=" * 50)
    logger.info("常量模块独立测试")
    logger.info("=" * 50)

    logger.info(f"MARKET枚举: {[m.value for m in MARKET]}")
    logger.info(f"SECURITY_TYPE枚举: {[s.value for s in SECURITY_TYPE]}")

    test_codes = ['600001', '000001', '300001', '920001', '110001', '120001']

    logger.info("代码识别测试:")
    for code in test_codes:
        prefix = code[:2]
        found = False
        for sec_type, config in SECURITY_CODE_MAP.items():
            if prefix in config['prefix_map']:
                info = config['prefix_map'][prefix]
                logger.info(f"  {code} -> {info['market']} | {info['type']}")
                found = True
                break
        if not found:
            logger.warning(f"  {code} -> 未识别")

    logger.info("=" * 50)
    logger.info("测试完成")
