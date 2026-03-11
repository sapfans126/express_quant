def test_clean_code(code_utils):
    """测试代码清洗"""
    clean = code_utils["clean_code"]
    # 正常用例
    assert clean("600177") == "600177"
    assert clean("000001.SZ") == "000001"
    assert clean("sh600177") == "600177"
    assert clean("bj920001") == "920001"
    # 边界用例
    assert clean("abc123") == "000123"  # 提取123 → 左侧补零到6位
    assert clean("600") == "000600"     # 600 → 000600
    assert clean("") == ""              # 空字符串返回空（匹配修复后的逻辑）
    assert clean("   ") == ""           # 全空格也返回空（新增：增强测试）