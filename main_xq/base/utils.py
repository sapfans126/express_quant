import re
from main_xq.base.security_type import MARKET, MARKET_TYPE, SECURITY_TYPE, SECURITY_CODE_MAP

def parse_security_code(
        symbol: str,
        security_type: SECURITY_TYPE | str = SECURITY_TYPE.CN_AS # 支持枚举实例/字符串，默认枚举实例
) -> dict:
    """
    解析证券代码，提取标准化信息（支持省略.value）
    :param symbol: 待解析的证券代码（支持格式：sh600001/600001.sh/600001 等）
    :param security_type: 可选，指定证券类型（枚举实例/字符串，如SECURITY_TYPE.CN_AS/'CN_AS'），默认CN_AS
    :return: 标准化信息字典
    """
    # 初始化返回结果
    result = {
        'code': '',
        'market': '',
        'pre_fix': '',
        'security_type': '',
        'error': ''
    }

    # 参数校验 & 统一转换为字符串值（核心：自动处理枚举实例）
    if not isinstance(symbol, str) or symbol.strip() == '':
        result['error'] = '证券代码不能为空且必须为字符串类型'
        return result

    # 自动提取枚举实例的value，兼容字符串输入
    if isinstance(security_type, SECURITY_TYPE):
        sec_type_str = security_type.value  # 枚举实例→字符串
    else:
        sec_type_str = security_type  # 字符串直接使用

    # 校验证券类型有效性
    if not SECURITY_TYPE.has_value(sec_type_str):
        valid_types = [item.value for item in SECURITY_TYPE]
        result['error'] = f'无效的证券类型：{security_type}，可选值：{valid_types}'
        return result

    # 清洗代码（去除空格、大小写统一）
    code_clean = symbol.strip().lower()

    # 步骤3：正则提取纯数字代码和市场标识
    market = None
    pattern = r'^(?:(sh|sz|bj))?(\d{6})(?:\.(sh|sz|bj))?$'
    match = re.match(pattern, code_clean)

    if match:
        # 提取匹配结果
        market_prefix = match.group(1)
        pure_code = match.group(2)
        market_suffix = match.group(3)
        market = market_prefix if market_prefix else market_suffix
    else:
        pure_code = code_clean
    #     result['error'] = f'证券代码格式无效：{symbol}，支持格式：sh600001/600001.sh/600001'
    #     return result

    # 无前后缀时，从映射表匹配
    prefix = pure_code[:2]
    type_info = SECURITY_CODE_MAP[sec_type_str]
    if prefix not in type_info['prefix_map']:
        result['error'] = f'证券类型：{security_type}和代码：{pure_code} 不一致'
        return result

    match_info = type_info['prefix_map'][prefix]
    # 验证代码中的获得的market和SECURITY_CODE_MAP中的market是否一致
    if market:
        if market != match_info['market']:
            result['error'] = f'代码中的证券市场：{market}和映射表中的市场：{match_info['market']} 不一致'
            return result

    result['code'] = pure_code
    result['market'] = match_info['market']
    result['pre_fix'] = match_info['pre_fix']
    result['security_type'] = match_info['type']

    return result


def parse_security_code_list(
        symbols: list[str],
        security_type: SECURITY_TYPE | str = SECURITY_TYPE.CN_AS # 支持枚举实例/字符串，默认枚举实例
) -> dict:

    """
        批量解析证券代码列表，验证所有代码格式正确且市场一致

        Args:
            symbols: 证券代码列表
            security_type: 可选，指定证券类型（枚举实例/字符串，如SECURITY_TYPE.CN_AS/'CN_AS'），默认CN_AS

        Returns:
            标准化信息字典，与 parse_security_code 格式一致，但 code 字段为列表：
            {
                'code': list[str],      # 解析后的纯代码列表（仅当全部有效时）
                'market': str,           # 统一的市场（如果都有相同市场）
                'pre_fix': str,          # 统一的前缀（如果都有相同前缀）
                'security_type': str,    # 证券类型
                'error': str              # 错误信息（如果有）
            }
        """
    # 初始化返回结果（与 parse_security_code 格式一致）
    result = {
        'code': [],  # 改为列表
        'market': '',
        'pre_fix': '',
        'security_type': '',
        'error': ''
        }

    # 参数校验
    if not isinstance(symbols, list):
        result['error'] = '证券代码列表必须为列表类型'
        return result

    if not symbols:
        result['error'] = '证券代码列表不能为空'
        return result

    # 用于记录第一个有效代码的信息，作为一致性基准
    base_market = None
    base_pre_fix = None
    base_sec_type = None

    # 存储解析成功的代码
    success_codes = []

    # 遍历解析每个代码
    for i, symbol in enumerate(symbols):
        # 解析当前代码
        parse_result = parse_security_code(symbol, security_type)

        # 检查是否有错误
        if parse_result['error']:
            result['error'] = f'第{i + 1}个代码 "{symbol}" 解析失败：{parse_result["error"]}'
            return result

       # 如果是第一个成功解析的代码，记录基准信息
        if i == 0:
            base_market = parse_result['market']
            base_pre_fix = parse_result['pre_fix']
            base_sec_type = parse_result['security_type']
            success_codes.append(parse_result['code'])
            continue

        # 检查市场一致性（如果当前代码有市场，基准也有市场）
        if parse_result['market'] and base_market:
            if parse_result['market'] != base_market:
                result['error'] = (f'第{i+1}个代码 "{symbol}" 市场不一致：'
                                  f'当前市场="{parse_result["market"]}", '
                                  f'基准市场="{base_market}"')
                return result

        # 检查前缀一致性（逻辑同上）
        if parse_result['pre_fix'] and base_pre_fix:
            if parse_result['pre_fix'] != base_pre_fix:
                result['error'] = (f'第{i+1}个代码 "{symbol}" 前缀不一致：'
                                  f'当前前缀="{parse_result["pre_fix"]}", '
                                  f'基准前缀="{base_pre_fix}"')
                return result

        # 检查证券类型一致性
        if parse_result['security_type'] and base_sec_type:
            if parse_result['security_type'] != base_sec_type:
                result['error'] = (f'第{i+1}个代码 "{symbol}" 证券类型不一致：'
                                  f'当前类型="{parse_result["security_type"]}", '
                                  f'基准类型="{base_sec_type}"')
                return result

        # 记录成功解析的代码
        success_codes.append(parse_result['code'])

    # 全部通过验证，填充结果
    result['code'] = success_codes
    result['market'] = base_market
    result['pre_fix'] = base_pre_fix
    result['security_type'] = base_sec_type

    return result


# ------------------- 测试用例（可省略.value） -------------------
# 测试函数
def test_parse_security_code_list():
    """测试批量解析的中断逻辑"""

    test_cases = [
        {
            'name': '正常情况 - 全部一致',
            'symbols': ['sh600519', 'sh600036', 'sh600000'],
            'expected_error': ''
        },
        {
            'name': '混合前后缀但一致',
            'symbols': ['sh600519', '600036.sh', 'sh600000.sh'],
            'expected_error': ''
        },
        {
            'name': '包含无市场代码（允许）',
            'symbols': ['sh600519', '600036', '600000'],
            'expected_error': ''
        },
        {
            'name': '市场不一致 - 应该在第2个中断',
            'symbols': ['sh600519', 'sz000001', '600036'],
            'expected_error': '第2个代码 "sz000001" 市场不一致'
        },
        {
            'name': '前缀不一致 - 应该在第2个中断',
            'symbols': ['600001', '300001', '600002'],
            'expected_error': '第2个代码 "300001" 前缀不一致'
        },
        {
            'name': '包含无效代码 - 应该在第2个中断',
            'symbols': ['sh600519', '600036xxx', '600000'],
            'expected_error': '第2个代码 "600036xxx" 解析失败'
        },
        {
            'name': '无市场后跟有市场（允许）',
            'symbols': ['600036', 'sh600519', '600000'],
            'expected_error': ''
        },
        {
            'name': '空列表',
            'symbols': [],
            'expected_error': '证券代码列表不能为空'
        }
    ]

    print("=" * 70)
    print("测试 parse_security_code_list 中断逻辑")
    print("=" * 70)

    for tc in test_cases:
        print(f"\n测试: {tc['name']}")
        print(f"输入: {tc['symbols']}")

        result = parse_security_code_list(tc['symbols'])

        if result['error'] == tc['expected_error']:
            status = "✓"
        else:
            status = "✗"

        print(f"结果: {status}")
        if result['error']:
            print(f"错误: {result['error']}")
            print(f"预期错误: {tc['expected_error']}")
        else:
            print(f"成功解析: {result['code']}")
            print(f"市场: {result['market']}, 前缀: {result['pre_fix']}")

        print("-" * 50)


# 演示中断位置
def demonstrate_early_termination():
    """演示提前中断的位置"""

    print("\n" + "=" * 70)
    print("演示提前中断位置")
    print("=" * 70)

    # 测试用例：在第3个位置有市场不一致
    test_symbols = ['sh600001', 'sh600002', 'sz300003', 'sh600004']

    print(f"\n输入列表: {test_symbols}")
    print("开始解析...\n")

    result = {
        'code': [],
        'market': '',
        'pre_fix': '',
        'security_type': '',
        'error': ''
    }

    base_market = None
    base_pre_fix = None

    for i, symbol in enumerate(test_symbols, 1):
        print(f"步骤{i}: 解析 '{symbol}'")

        # 模拟解析过程（这里用实际函数）
        parse_result = parse_security_code(symbol)

        if parse_result['error']:
            print(f"  ❌ 解析失败: {parse_result['error']}")
            result['error'] = f'第{i}个代码 "{symbol}" 解析失败'
            break

        print(f"  ✅ 解析成功: code={parse_result['code']}, market={parse_result['market']}")

        if i == 1:
            base_market = parse_result['market']
            base_pre_fix = parse_result['pre_fix']
            result['code'].append(parse_result['code'])
            print(f"  📌 设置为基准: market={base_market}, pre_fix={base_pre_fix}")
            continue

        # 检查市场一致性
        if parse_result['market'] and base_market:
            if parse_result['market'] != base_market:
                print(f"  ❌ 市场不一致: 当前={parse_result['market']}, 基准={base_market}")
                result['error'] = f'第{i}个代码 "{symbol}" 市场不一致'
                break
        elif parse_result['market'] and not base_market:
            base_market = parse_result['market']
            print(f"  📌 更新基准市场: {base_market}")

        result['code'].append(parse_result['code'])
        print(f"  ✅ 通过验证")

    if result['error']:
        print(f"\n❌ 解析终止于第{len(result['code']) + 1}个代码")
        print(f"   错误: {result['error']}")
        print(f"   已成功解析: {result['code']}")
    else:
        print(f"\n✅ 全部解析成功: {result['code']}")


if __name__ == "__main__":
    test_parse_security_code_list()
    demonstrate_early_termination()