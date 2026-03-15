import os
from mytdx.config import get_config
from typing import Optional

class FileUtil():

    @staticmethod
    # 从配置文件读取通达信数据目录
    def get_tdx_data_dir() -> str:
        config = get_config()
        data_dir = config.get("TDX_DATA", "tdx_data_dir")

        # 配置校验：如果未读取到配置，使用默认值（容错）
        if data_dir is None:
            data_dir = "C:/MySAS/TDX/vipdoc"
            print(f"⚠️ 未从mytdx.ini读取到tdx_data_dir，使用默认路径：{self.data_dir}")
        # else:
        #     print(f"✅ 从配置文件读取数据目录：{self.data_dir}")

        return  data_dir


    @staticmethod
    def build_file_path(subdir:str, tdx_dir:str=None) -> str:
        """
        实例方法：合成文件路径（支持多级子目录，如 sh/lday；不校验代码位数）
        :param subdir: 子目录路径（支持多级，如 sh/lday、sz/minline、ds/day 等）
        :param tdx_dir: TDX 数据文件目录 (默认"C:/MySAS/TDX/vipdoc")
        :return: 文件路径
        """
        if not isinstance(subdir, str) or subdir.strip() == "":
            raise ValueError("子目录路径不能为空")
        subdir_clean = os.path.normpath(subdir.strip())  # 处理多级目录+统一分隔符

        if tdx_dir is None or len(tdx_dir) == 0:
            tdx_data_dir = FileUtil.get_tdx_data_dir()
        else:
            tdx_data_dir = tdx_dir

        # 确定基础目录（tdx_data_dir + 多级subdir）
        file_path = os.path.join(tdx_data_dir, subdir_clean)

        return file_path

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