import os
from typing import Optional


class FileUtil:
    @staticmethod
    def build_file_path(tdx_dir: str, subdir: Optional[str] = None) -> str:
        """
        合成文件路径（支持多级子目录）

        Args:
            tdx_dir: TDX 数据文件根目录 (如 "C:/MySAS/TDX/vipdoc")，不能为空
            subdir: 子目录路径（支持多级，如 "sh/lday"），可选，为 None 或空字符串时不添加子目录

        Returns:
            完整的文件路径

        Raises:
            ValueError: 当 tdx_dir 为空时抛出异常
            TypeError: 当参数类型错误时抛出异常
        """
        # 检查 tdx_dir
        if not isinstance(tdx_dir, str):
            raise TypeError(f"tdx_dir 必须是字符串类型，当前是 {type(tdx_dir)}")

        tdx_dir_strip = tdx_dir.strip()
        if not tdx_dir_strip:
            raise ValueError("TDX 数据文件根目录不能为空")

        # 规范化根目录
        tdx_data_dir = os.path.normpath(tdx_dir_strip)

        # 处理子目录
        if subdir is None or not isinstance(subdir, str) or not subdir.strip():
            # subdir 为空时，只返回根目录
            return tdx_data_dir

        # 有有效的子目录时，拼接并返回完整路径
        subdir_clean = os.path.normpath(subdir.strip())
        return os.path.join(tdx_data_dir, subdir_clean)

    @staticmethod
    def build_file_name(code:str, prefix:str, suffix:str)-> str:
        """
        实例方法：合成文件名称（支持多级子目录，如 sh/lday；不校验代码位数）
        :param code: 证券代码（由parse_security_code提前校验，直接使用）
        :param prefix: 文件名前缀（如 sh/sz/bj）
        :param suffix: 文件后缀（如 day/lc1/lc5）
        :return: 文件名称
        """
        if not isinstance(code, str) or code.strip() == "":
            raise ValueError("证券代码不能为空且必须为字符串类型")
        if not isinstance(prefix, str) or prefix.strip() == "":
            raise ValueError("文件名前缀不能为空")
        if not isinstance(suffix, str) or suffix.strip() == "":
            raise ValueError("文件后缀不能为空")

        # 清理输入参数
        code_clean = code.strip()  # 仅去空格，不校验位数
        prefix_clean = prefix.strip()
        suffix_clean = suffix.strip().lower()  # 后缀统一小写

        # 合成文件名（ds目录特殊处理）
        # if subdir_last_part == 'ds':
        #     filename = f"{prefix_clean}#{code_clean}.{suffix_clean}"
        # else:
        filename = f"{prefix_clean}{code_clean}.{suffix_clean}"

        return filename

    @staticmethod
    def build_file_pathname(code: str, subdir: str, prefix: str, suffix: str, tdx_dir:str=None) -> str| None:
        """
        实例方法：合成文件全路径（支持多级子目录，如 sh/lday；不校验代码位数）
        :param code: 证券代码（由parse_security_code提前校验，直接使用）
        :param subdir: 子目录路径（支持多级，如 sh/lday、sz/minline、ds/day 等）
        :param prefix: 文件名前缀（如 sh/sz/bj）
        :param suffix: 文件后缀（如 day/5lc/1lc）
        :return: 完整的文件路径
        """

        try:
            filepath = FileUtil.build_file_path(subdir=subdir,tdx_dir=tdx_dir)
        except ValueError as e:
            print(f"参数错误: {e}")  # 输出: 参数错误: 证
            return None

        try:
            filename = FileUtil.build_file_name(code=code,prefix=prefix,suffix=suffix)
        except ValueError as e:
            print(f"参数错误: {e}")  # 输出: 参数错误: 证
            return None

        full_pathname = os.path.join(filepath,filename)

        return os.path.normpath(full_pathname)

    @staticmethod
    def combine_file_pathname(file_path, file_name):
        """
        将文件夹路径和文件名合成为完整的文件路径

        参数:
            file_path (str): 文件夹路径（可以是相对路径或绝对路径）
            file_name (str): 文件名（可包含后缀，如 "test.txt"）

        返回:
            str: 合成后的完整规范路径
        """
        # 处理边界情况：路径/文件名为空
        if not file_path:
            file_path = "."  # 默认为当前目录
        if not file_name:
            raise ValueError("文件名不能为空！")

        # 核心：拼接路径并规范化（自动处理分隔符、重复斜杠等问题）
        path_name = os.path.join(file_path, file_name)
        # 规范化路径（比如把 "a//b.txt" 转为 "a/b.txt"，处理 "../" 等）
        full_name = os.path.normpath(path_name)

        return full_name


    @staticmethod
    def read_tdxfile(code: str, subdir: str, prefix: str, suffix: str, tdx_dir: str = None) -> Optional[bytes]:
        """
        读取通达信二进制文件的原始二进制数据（不解析）

        :param code: 证券代码（用于构建文件名的核心标识）
        :param subdir: 子目录名称（通达信数据目录下的子文件夹）
        :param prefix: 文件名前缀（构建文件名时的前缀部分）
        :param suffix: 文件后缀（包括扩展名，如 .day、.min5 等）
        :param tdx_dir: 通达信数据根目录（可选，不传则使用默认路径）
        :return: 读取到的原始二进制数据（bytes类型）；文件不存在/为空/读取失败时返回None
        """
        file_pathname = FileUtil.build_file_pathname(
            code=code, subdir=subdir, prefix=prefix, suffix=suffix, tdx_dir=tdx_dir)

        # 1. 文件校验
        if not os.path.exists(file_pathname):
            print(f"❌ 文件不存在：{file_pathname}")
            return None
        if os.path.getsize(file_pathname) == 0:
            print(f"❌ 空文件，无法读取：{file_pathname}")
            return None

        # 2. 读取原始二进制数据
        return FileUtil.read_file(file_pathname)


    @staticmethod
    def read_file(file_pathname:str )-> Optional[bytes]:

        with open(file_pathname, 'rb') as f:
            raw_data = f.read()  # 读取全部二进制数据

        print(f"✅ 成功读取 {os.path.basename(file_pathname)}，数据大小：{len(raw_data)} 字节")

        return raw_data


if __name__ == "__main__":
    tdx_dir = r'C:\MySAS\TDX\vipdoc'
    sub_dir = r'sh\lday'
    path = FileUtil.build_file_path(tdx_dir,sub_dir)
    print(path)