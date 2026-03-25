# -*- coding: utf-8 -*-
"""
code_utils.py - A股代码规则通用工具（所有数据源模块共用）
"""
from typing import Tuple
from mootdx import consts

# ===================== A股代码规则常量（集中管理） =====================
MARKET_MAP = {
    'sh': consts.MARKET_SH,
    'sz': consts.MARKET_SZ,
    'bj': consts.MARKET_BJ
}

# 修正：将列表改为元组（startswith支持元组，不支持列表）
INDEX_CODE_RULES = {
    'sh': ('000', '88', '99'),  # 沪市指数：000xxx/88xxx/99xxx（元组）
    'sz': ('399',),  # 深市指数：399xxx（元组）
    'bj': ('899',)  # 北交所指数：899xxx（元组）
}

STOCK_CODE_RULES = {
    consts.MARKET_SH: ['60', '68', '90'],  # 沪市：60(主板)/68(科创板)/90(B股)
    consts.MARKET_SZ: ['000', '001', '002', '003', '004', '300', '301', '302', '20'],  # 深市
    consts.MARKET_BJ: ['92', '83', '87', '43']  # 北交所：92(最新)/83/87/43(老代码)
}


# ===================== 核心通用函数 =====================
def clean_code(symbol: str) -> str:
    """
    标准化代码格式（移除前缀/后缀，只保留纯数字）
    修正：空字符串返回空，而非000000
    """
    if not isinstance(symbol, str) or symbol.strip() == "":
        return ""  # 空字符串直接返回空

    # 第一步：只提取数字字符
    digits = [c for c in symbol.lower() if c.isdigit()]
    symbol_clean = ''.join(digits)

    # 第二步：补零到6位（左侧补零，匹配测试用例预期）
    if len(symbol_clean) < 6:
        symbol_clean = symbol_clean.zfill(6)  # 左侧补零
    elif len(symbol_clean) > 6:
        symbol_clean = symbol_clean[:6]

    return symbol_clean


def is_index_code(symbol: str) -> bool:
    """
    通用判断：代码是否为指数（适配所有数据源）
    """
    symbol_clean = clean_code(symbol)
    if len(symbol_clean) != 6:
        return False

    # 先判断是否包含市场后缀（.SZ/.sh/.bj），若有则优先判定为股票
    if any(suffix in symbol.lower() for suffix in ['.sz', '.sh', '.bj']):
        return False

    # 匹配指数代码规则（元组支持startswith）
    for market_prefix in INDEX_CODE_RULES.values():
        if symbol_clean.startswith(market_prefix):
            return True
    return False


def get_market_code(symbol: str) -> int:
    """
    通用判断：代码所属市场（适配所有数据源）
    """
    symbol_clean = clean_code(symbol)
    if len(symbol_clean) != 6:
        return consts.MARKET_SH  # 默认沪市

    # 第一步：优先判断是否为指数（指数的市场规则）
    if is_index_code(symbol):
        if symbol_clean.startswith(INDEX_CODE_RULES['sh']):  # 000/88/99开头 → 沪市
            return consts.MARKET_SH
        elif symbol_clean.startswith(INDEX_CODE_RULES['sz']):  # 399开头 → 深市
            return consts.MARKET_SZ
        elif symbol_clean.startswith(INDEX_CODE_RULES['bj']):  # 899开头 → 北交所
            return consts.MARKET_BJ

    # 第二步：判断股票代码规则
    for market_code, prefix_list in STOCK_CODE_RULES.items():
        for prefix in prefix_list:
            if symbol_clean.startswith(prefix):
                return market_code

    # 兜底默认
    return consts.MARKET_SH


def get_code_type(symbol: str) -> Tuple[str, int]:
    """
    通用判断：代码类型（股票/指数）+ 所属市场（一站式获取）
    """
    symbol_clean = clean_code(symbol)
    if len(symbol_clean) != 6:
        return 'unknown', consts.MARKET_SH

    # 第一步：判断是否为指数（严格规则）
    if is_index_code(symbol):
        market_code = get_market_code(symbol)
        return 'index', market_code

    # 第二步：判断是否为股票
    market_code = get_market_code(symbol)
    return 'stock', market_code


def standardize_code(symbol: str, with_market_prefix: bool = True) -> str:
    """
    代码格式标准化（统一输出：sh600036/sz000001/bj920001 格式）
    """
    symbol_clean = clean_code(symbol)
    if len(symbol_clean) != 6:
        return symbol

    # 获取市场前缀
    market_code = get_market_code(symbol_clean)
    market_prefix = {
        consts.MARKET_SH: 'sh',
        consts.MARKET_SZ: 'sz',
        consts.MARKET_BJ: 'bj'
    }.get(market_code, 'sh')

    if with_market_prefix:
        return f"{market_prefix}{symbol_clean}"
    else:
        return symbol_clean