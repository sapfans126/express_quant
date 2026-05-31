import re
from typing import List, Dict, Any
import pandas as pd

# ===================== 日志配置 =====================
from main_xq.utils.logger import get_logger_for_current_module, _initialized

logger = get_logger_for_current_module(__file__)

# 导入证券类型枚举
from main_xq.base.security_type import MARKET, MARKET_TYPE, SECURITY_TYPE, SECURITY_CODE_MAP


def parse_security_code(
        symbol: str,
        security_type: SECURITY_TYPE | str = SECURITY_TYPE.CN_AS) -> Dict[str, Any]:
    """
    解析证券代码，自动标准化格式（支持 sh600000 / 600000.sh / 600000）

    Args:
        symbol: 证券代码字符串
        security_type: 证券类型（枚举/字符串均可）

    Returns:
        标准化结果字典：code/market/pre_fix/security_type/error
    """
    return_result = {
        'code': '',
        'market': '',
        'pre_fix': '',
        'security_type': '',
        'error': ''
    }

    if not isinstance(symbol, str) or not symbol.strip():
        return_result['error'] = '证券代码不能为空且必须为字符串类型'
        logger.error(return_result['error'])
        return return_result

    # 处理证券类型（支持枚举 / 字符串）
    if security_type is None:
        sec_type_str = "CN_AS"
    elif hasattr(security_type, 'value') and security_type.__class__.__name__ == 'SECURITY_TYPE':
        sec_type_str = security_type.value
        logger.debug(f"检测到枚举类型证券类型，解析值：{sec_type_str}")
    elif isinstance(security_type, str):
        sec_type_str = security_type.strip()
    else:
        sec_type_str = str(security_type)

    # 校验证券类型是否有效
    if not SECURITY_TYPE.has_value(sec_type_str):
        valid_types = [item.value for item in SECURITY_TYPE]
        return_result['error'] = f'无效证券类型：{sec_type_str}，可选值：{valid_types}'
        logger.error(return_result['error'])
        return return_result

    # 清洗代码并正则解析市场与代码
    code_clean = symbol.strip().lower()
    pattern = r'^(?:(sh|sz|bj))?(\d{6})(?:\.(sh|sz|bj))?$'
    match = re.match(pattern, code_clean)

    market, pure_code = None, code_clean
    if match:
        market_prefix = match.group(1)
        pure_code = match.group(2)
        market_suffix = match.group(3)
        market = market_prefix or market_suffix

    # 校验前缀与市场映射
    prefix = pure_code[:2]
    type_info = SECURITY_CODE_MAP.get(sec_type_str, {})

    if not type_info or prefix not in type_info.get('prefix_map', {}):
        return_result['error'] = f'证券类型({sec_type_str})与代码({pure_code})前缀不匹配'
        logger.error(return_result['error'])
        return return_result

    match_info = type_info['prefix_map'][prefix]

    # 市场一致性校验
    if market and market != match_info['market']:
        return_result['error'] = f'代码市场({market})与映射表市场({match_info["market"]})不一致'
        logger.error(return_result['error'])
        return return_result

    # 填充最终结果
    return_result['code'] = pure_code
    return_result['market'] = match_info['market']
    return_result['pre_fix'] = match_info['pre_fix']
    return_result['security_type'] = match_info['type']

    logger.debug(f"证券代码解析成功：{symbol} → {return_result}")
    return return_result


def parse_security_code_list(
        symbols: List[str],
        security_type: SECURITY_TYPE | str = SECURITY_TYPE.CN_AS
) -> Dict[str, Any]:
    """
    批量解析证券代码列表，确保所有代码：
    1. 格式合法
    2. 市场统一
    3. 前缀统一
    4. 类型统一
    遇到错误立即中断，不继续执行

    Args:
        symbols: 证券代码列表
        security_type: 证券类型

    Returns:
        批量解析结果字典（code 为列表）
    """
    return_result = {
        'code': [],
        'market': '',
        'pre_fix': '',
        'security_type': '',
        'error': ''
    }

    # 基础校验
    if not isinstance(symbols, list):
        return_result['error'] = '输入必须为列表类型'
        logger.error(return_result['error'])
        return return_result

    if not symbols:
        return_result['error'] = '证券代码列表不能为空'
        logger.error(return_result['error'])
        return return_result

    # 基准信息
    base_market = None
    base_pre_fix = None
    base_sec_type = None
    success_codes = []

    # 遍历解析
    for idx, symbol in enumerate(symbols):
        parse_result = parse_security_code(symbol, security_type)

        if parse_result['error']:
            return_result['error'] = f'第{idx + 1}个代码【{symbol}】解析失败：{parse_result["error"]}'
            logger.error(return_result['error'])
            return return_result

        # 第一个代码作为基准
        if idx == 0:
            base_market = parse_result['market']
            base_pre_fix = parse_result['pre_fix']
            base_sec_type = parse_result['security_type']
            success_codes.append(parse_result['code'])
            continue

        # 市场一致性
        if parse_result['market'] and base_market and parse_result['market'] != base_market:
            return_result['error'] = f'第{idx + 1}个代码【{symbol}】市场不统一：{parse_result["market"]} vs {base_market}'
            logger.error(return_result['error'])
            return return_result

        # 前缀一致性
        if parse_result['pre_fix'] and base_pre_fix and parse_result['pre_fix'] != base_pre_fix:
            return_result['error'] = f'第{idx + 1}个代码【{symbol}】前缀不统一'
            logger.error(return_result['error'])
            return return_result

        # 类型一致性
        if parse_result['security_type'] and base_sec_type and parse_result['security_type'] != base_sec_type:
            return_result['error'] = f'第{idx + 1}个代码【{symbol}】证券类型不统一'
            logger.error(return_result['error'])
            return return_result

        success_codes.append(parse_result['code'])

    # 全部成功
    return_result['code'] = success_codes
    return_result['market'] = base_market
    return_result['pre_fix'] = base_pre_fix
    return_result['security_type'] = base_sec_type

    logger.info(f"批量解析完成，共成功解析 {len(success_codes)} 个代码")
    return return_result


def normalize_stock_codes(
        stock_list: List[str],
        security_type: SECURITY_TYPE | str = SECURITY_TYPE.CN_AS
) -> Dict[str, Any]:
    """
    将各种格式的股票代码统一转换为 '代码.市场' 格式（如 '600519.SH'）

    支持的输入格式：
        - '600519.SH' / '600519.sh' → '600519.SH'
        - 'SH600519' / 'sh600519' → '600519.SH'
        - '600519' → '600519.SH'（自动识别市场）
        - '600519SH' / '600519sh' → '600519.SH'

    Args:
        stock_list: 股票代码列表，支持多种格式
        security_type: 证券类型，默认 A 股

    Returns:
        字典格式：
        {
            'codes_list_query': ['600519.SH', '000858.SZ'],  # 标准化后的代码列表
            'error': '',                          # 错误信息
            'invalid_codes': []                   # 无效的代码
        }

    Examples:
        >>> normalize_stock_codes(['600519.SH', '000858.SZ'])
        {'codes_list_query': ['600519.SH', '000858.SZ'], 'error': '', 'invalid_codes': []}

        >>> normalize_stock_codes(['SH600519', 'sz000858'])
        {'codes_list_query': ['600519.SH', '000858.SZ'], 'error': '', 'invalid_codes': []}

        >>> normalize_stock_codes(['600519', '000858'])
        {'codes_list_query': ['600519.SH', '000858.SZ'], 'error': '', 'invalid_codes': []}

        >>> normalize_stock_codes(['600519SH', '000858SZ'])
        {'codes_list_query': ['600519.SH', '000858.SZ'], 'error': '', 'invalid_codes': []}
    """
    return_result = {
        'codes_list_query': [],
        'error': '',
        'invalid_codes': []
    }

    # 基础校验
    if not isinstance(stock_list, list):
        return_result['error'] = '输入必须为列表类型'
        logger.error(return_result['error'])
        return return_result

    if not stock_list:
        return_result['error'] = '股票代码列表不能为空'
        logger.error(return_result['error'])
        return return_result

    # 处理证券类型
    if security_type is None:
        sec_type_str = "CN_AS"
    elif hasattr(security_type, 'value') and security_type.__class__.__name__ == 'SECURITY_TYPE':
        sec_type_str = security_type.value
    elif isinstance(security_type, str):
        sec_type_str = security_type.strip()
    else:
        sec_type_str = str(security_type)

    # 校验证券类型
    if not SECURITY_TYPE.has_value(sec_type_str):
        valid_types = [item.value for item in SECURITY_TYPE]
        return_result['error'] = f'无效证券类型：{sec_type_str}，可选值：{valid_types}'
        logger.error(return_result['error'])
        return return_result

    # 获取该类型的前缀映射
    type_info = SECURITY_CODE_MAP.get(sec_type_str, {})
    prefix_map = type_info.get('prefix_map', {})

    for raw_code in stock_list:
        if not isinstance(raw_code, str):
            logger.warning(f"跳过非字符串代码：{raw_code}")
            return_result['invalid_codes'].append(raw_code)
            continue

        code_clean = raw_code.strip()
        if not code_clean:
            logger.warning(f"跳过空代码")
            return_result['invalid_codes'].append(raw_code)
            continue

        # 尝试匹配各种格式
        normalized_code = None

        # 格式1：600519.SH 或 600519.sh
        match1 = re.match(r'^(\d{6})\.([a-zA-Z]{2})$', code_clean)
        if match1:
            code_num = match1.group(1)
            market_suffix = match1.group(2).upper()
            # 验证市场后缀是否正确
            for prefix, info in prefix_map.items():
                if info['market'].upper() == market_suffix:
                    normalized_code = f"{code_num}.{market_suffix}"
                    break
            if normalized_code:
                return_result['codes_list_query'].append(normalized_code)
                continue

        # 格式2：SH600519 或 sh600519
        match2 = re.match(r'^([a-zA-Z]{2})(\d{6})$', code_clean)
        if match2:
            market_prefix = match2.group(1).upper()
            code_num = match2.group(2)
            # 验证市场前缀是否正确
            for prefix, info in prefix_map.items():
                if info['pre_fix'].upper() == market_prefix:
                    normalized_code = f"{code_num}.{info['market'].upper()}"
                    break
            if normalized_code:
                return_result['codes_list_query'].append(normalized_code)
                continue

        # 格式3：600519SH 或 600519sh
        match3 = re.match(r'^(\d{6})([a-zA-Z]{2})$', code_clean)
        if match3:
            code_num = match3.group(1)
            market_suffix = match3.group(2).upper()
            for prefix, info in prefix_map.items():
                if info['market'].upper() == market_suffix:
                    normalized_code = f"{code_num}.{market_suffix}"
                    break
            if normalized_code:
                return_result['codes_list_query'].append(normalized_code)
                continue

        # 格式4：纯数字 600519
        match4 = re.match(r'^(\d{6})$', code_clean)
        if match4:
            code_num = match4.group(1)
            prefix = code_num[:2]
            # 根据前缀自动识别市场
            if prefix in prefix_map:
                info = prefix_map[prefix]
                normalized_code = f"{code_num}.{info['market'].upper()}"
                return_result['codes_list_query'].append(normalized_code)
                continue

        # 所有格式都不匹配
        logger.warning(f"无法识别的代码格式：{raw_code}")
        return_result['invalid_codes'].append(raw_code)

    # 检查是否有无效代码
    if return_result['invalid_codes']:
        return_result['error'] = f"存在 {len(return_result['invalid_codes'])} 个无效代码"
        logger.warning(return_result['error'])
    else:
        logger.info(f"成功标准化 {len(return_result['codes_list_query'])} 个代码")

    return return_result

# 便捷函数：快速转换单个代码
def normalize_stock_code(
        stock_code: str,
        security_type: SECURITY_TYPE | str = SECURITY_TYPE.CN_AS
) -> str|None:
    """
    转换单个股票代码为 '600519.SH' 格式

    Args:
        stock_code: 单个股票代码
        security_type: 证券类型

    Returns:
        标准化后的代码，如果无效返回空字符串

    Examples:
        >>> normalize_stock_code('SH600519')
        '600519.SH'
        >>> normalize_stock_code('600519')
        '600519.SH'
    """
    return_code = normalize_stock_codes([stock_code], security_type)
    if return_code['codes_list_query']:
        return return_code['codes_list_query'][0]
    return None


def normalize_stock_codes_simple(
        stock_list: List[str],
        security_type: SECURITY_TYPE | str = SECURITY_TYPE.CN_AS
) -> List[str]:
    """
    简化版：直接将股票代码列表转换为 '600519.SH' 格式
    只关心成功的代码，不需要错误详情（大多数情况）
    Args:
        stock_list: 股票代码列表
        security_type: 证券类型

    Returns:
        标准化后的代码列表，无效代码会被过滤掉

    Examples:
        >>> normalize_stock_codes_simple(['600519.SH', 'SH600036', '000001', 'invalid'])
        ['600519.SH', '600036.SH', '000001.SZ']
    """
    normal_codes = normalize_stock_codes(stock_list, security_type)
    return normal_codes['codes_list_query']


def simplify_pure_stock_code(
        stock_code: str,
        security_type: SECURITY_TYPE | str = SECURITY_TYPE.CN_AS
) -> str:
    """
    将股票代码简化为纯股票代码（先标准化，再去除后缀）

    支持输入格式：
        - 标准化格式：'600519.SH', 'AAPL.US', '0700.HK'
        - 前缀格式：'SH600519', 'sz000858'
        - 纯数字：'600519', '000858'
        - 数字+后缀：'600519SH', '000858SZ'

    Args:
        stock_code: 股票代码（支持多种格式）
        security_type: 证券类型，默认 A 股

    Returns:
        纯股票代码：
        - A股: '600519'
        - 港股: '00700'
        - 美股: 'AAPL'
        - 无效: ''

    Examples:
        >>> simplify_pure_stock_code('600519.SH')
        '600519'
        >>> simplify_pure_stock_code('SH600519')
        '600519'
        >>> simplify_pure_stock_code('600519')
        '600519'
        >>> simplify_pure_stock_code('700', security_type='HK_STOCK')
        '00700'
    """
    if not isinstance(stock_code, str) or not stock_code.strip():
        return ''

    # # 先标准化为 '代码.市场' 格式
    # from main_xq.base.code_utils import normalize_stock_code
    normalized = normalize_stock_code(stock_code, security_type)

    if not normalized:
        return ''

    # 再去掉市场后缀，只保留代码部分
    pure_code = normalized.split('.')[0]

    # 港股特殊处理：确保是5位数字
    if security_type == 'HK_STOCK' or (hasattr(security_type, 'value') and security_type.value == 'HK_STOCK'):
        if pure_code.isdigit():
            pure_code = pure_code.zfill(5)

    return pure_code


def simplify_pure_stock_codes(
        stock_codes: List[str],
        security_type: SECURITY_TYPE | str = SECURITY_TYPE.CN_AS
) -> Dict[str, Any]:
    """
    批量将股票代码简化为纯股票代码

    Args:
        stock_codes: 股票代码列表（支持多种格式）
        security_type: 证券类型

    Returns:
        字典格式：
        {
            'codes_list_query': ['600519', '000858'],
            'error': '',
            'invalid_codes': []
        }
    """
    return_result = {
        'codes_list_query': [],
        'error': '',
        'invalid_codes': []
    }

    if not isinstance(stock_codes, list):
        return_result['error'] = '输入必须为列表类型'
        logger.error(return_result['error'])
        return return_result

    if not stock_codes:
        return_result['error'] = '代码列表不能为空'
        logger.error(return_result['error'])
        return return_result

    for stock_code in stock_codes:
        pure_code = simplify_pure_stock_code(stock_code, security_type)
        if pure_code:
            return_result['codes_list_query'].append(pure_code)
        else:
            return_result['invalid_codes'].append(stock_code)

    if return_result['invalid_codes']:
        return_result['error'] = f"存在 {len(return_result['invalid_codes'])} 个无效代码"
        logger.warning(return_result['error'])
    else:
        logger.info(f"成功简化 {len(return_result['codes_list_query'])} 个代码")

    return return_result


def simplify_pure_stock_codes_simple(
        stock_codes: List[str],
        security_type: SECURITY_TYPE | str = SECURITY_TYPE.CN_AS
) -> List[str]:
    """
    简化版：批量将股票代码转换为纯股票代码（只返回代码列表）
    """
    result = simplify_pure_stock_codes(stock_codes, security_type)
    return result['codes_list_query']


def code_column_to_pure(
        df: pd.DataFrame,
        column_name: str,
        security_type: SECURITY_TYPE | str = SECURITY_TYPE.CN_AS,
        new_column_name: str = None
) -> pd.DataFrame:
    """
    将 DataFrame 中某一列的各种格式股票代码简化为纯股票代码
    """
    import pandas as pd

    if new_column_name is None:
        if column_name == 'code':
            new_column_name = 'pure_code'
        else:
            new_column_name = f"{column_name}_pure"

    df[new_column_name] = df[column_name].apply(
        lambda x: simplify_pure_stock_code(x, security_type) if pd.notna(x) else ''
    )

    success_count = (df[new_column_name] != '').sum()
    logger.info(f"成功简化 {success_count}/{len(df)} 个代码为纯代码")

    return df

#
# # 假设有一个 DataFrame，其中一列是标准化代码
# df = pd.DataFrame({
#     'code': ['600519.SH', '000858.SZ', '300750.SZ', '002415.SZ'],
#     'name': ['贵州茅台', '五粮液', '宁德时代', '海康威视'],
#     'close': [1680.50, 152.30, 185.60, 32.50]
# })
#
# print("原始 DataFrame:")
# print(df)
#
# # 转换为纯代码（自动添加 'pure_code' 列）
# df = code_column_to_pure(df, 'code')
#
# print("\n转换后:")
# print(df)




# # ===================== 测试函数 =====================
# def run_all_tests():
#     """运行所有测试（普通Python模式，无pytest）"""
#     logger.info("=" * 60)
#     logger.info("开始运行 code_utils 模块测试")
#     logger.info("=" * 60)
#
#     # 测试1：正常统一市场
#     logger.info("\n【测试1】正常统一市场")
#     res1 = parse_security_code_list(['sh600519','sh600036'])
#     if res1['error']:
#         logger.error(f"失败：{res1['error']}")
#     else:
#         logger.info(f"成功：{res1['code']}")
#
#     # 测试2：市场不一致
#     logger.info("\n【测试2】市场不一致（预期失败）")
#     res2 = parse_security_code_list(['sh600519','sz000001'])
#     if res2['error']:
#         logger.warning(f"预期错误：{res2['error']}")
#     else:
#         logger.info(f"成功：{res2['code']}")
#
#     logger.info("\n" + "=" * 60)
#     logger.info("所有测试执行完成")
#     logger.info("=" * 60)


# ===================== 模块加载日志（你要的规范版） =====================
# if __name__ == "__main__":
#     # 直接运行：初始化日志
#     if not _initialized:
#         from main_xq.utils.log import init_logger
#         init_logger(is_debug=True)
#
#     logger.info("工具模块 code_utils.py 已成功加载")
#
#     # 直接运行测试
#     run_all_tests()
# else:
#     # 被导入时输出DEBUG
#     logger.debug("工具模块 code_utils.py 已被导入")

# 测试各种格式
if __name__ == "__main__":
    test_cases1 = [
        ['600519.SH', '000858.SZ'],           # 标准格式
        ['SH600519', 'sz000858'],             # 前缀格式
        ['600519', '000858'],                 # 纯数字
        ['600519SH', '000858SZ'],             # 后缀格式
        ['600519.sh', '000858.sz'],           # 小写后缀
        ['sh600519', 'SZ000858'],             # 大小写混合
    ]

    for codes in test_cases1:
        result = normalize_stock_codes(codes)
        print(f"输入: {codes}")
        print(f"输出: {result['codes_list_query']}")
        print(f"无效: {result['invalid_codes']}")
        print("-" * 40)

    # 测试各种格式
    test_cases2 = [
        ('600519.SH', 'CN_AS'),
        ('SH600519', 'CN_AS'),
        ('600519', 'CN_AS'),
        ('600519SH', 'CN_AS'),
        ('700', 'HK_STOCK'),
        ('00700.HK', 'HK_STOCK'),
        ('HK00700', 'HK_STOCK'),
        ('AAPL.US', 'US_STOCK'),
        ('AAPL', 'US_STOCK'),
    ]

    for code, stype in test_cases2:
        result = simplify_pure_stock_code(code, stype)
        print(f"{code:15} → {result}")