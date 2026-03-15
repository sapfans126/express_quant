import configparser
from pathlib import Path
from typing import Any, List, Tuple, Optional


# ===================== 修复的MultiOptionConfigParser =====================
class MultiOptionConfigParser(configparser.ConfigParser):
    """支持重复option的配置解析器（彻底解决DuplicateOptionError）"""

    def __init__(self, *args, **kwargs):
        kwargs['strict'] = False  # 禁用重复option检查
        super().__init__(*args, **kwargs)
        self._multi_options = {}  # {section: {option: [value1, value2, ...]}}

    def _read(self, fp, fpname):
        """完全自定义解析逻辑，支持重复option"""
        self._multi_options = {}
        current_section = None
        self._sections[current_section] = self._dict()

        for lineno, line in enumerate(fp, 1):
            line = line.strip()
            if not line or line.startswith((';', '#')):
                continue

            # 匹配section
            if line.startswith('[') and line.endswith(']'):
                current_section = line[1:-1].strip()
                if current_section not in self._sections:
                    self._sections[current_section] = self._dict()
                if current_section not in self._multi_options:
                    self._multi_options[current_section] = {}
                continue

            # 匹配option
            if '=' in line and current_section is not None:
                opt, val = line.split('=', 1)
                opt = opt.strip()
                val = val.strip()

                # 存储所有重复值
                if opt not in self._multi_options[current_section]:
                    self._multi_options[current_section][opt] = []
                self._multi_options[current_section][opt].append(val)
                # 保留最后一个值到原生配置
                self._sections[current_section][opt] = val

    def get_multi_options(self, section, option):
        """获取某个section下某个option的所有值（不区分大小写）"""
        # 统一转为小写匹配（解决大小写不一致问题）
        section_lower = section.lower()
        option_lower = option.lower()

        # 遍历所有section，匹配小写名称
        for sec in self._multi_options:
            if sec.lower() == section_lower:
                # 遍历该section下的所有option，匹配小写名称
                for opt in self._multi_options[sec]:
                    if opt.lower() == option_lower:
                        return self._multi_options[sec][opt]
        return []

    # 重写get方法，支持不区分大小写
    def get(self, section, option, *args, **kwargs):
        return super().get(section.lower(), option.lower(), *args, **kwargs)


# ===================== 通用基础配置类 =====================
class BaseConfig:
    """通用配置管理类"""

    def __init__(self, config_filename: str):
        self._current_dir = Path(__file__).resolve().parent
        self._config_path = self._current_dir / config_filename

        if not self._config_path.exists():
            raise FileNotFoundError(f"配置文件不存在: {self._config_path}")

        self._config = MultiOptionConfigParser(allow_no_value=True)
        self._config.read(self._config_path, encoding="utf-8")

    def _resolve_path(self, path_str: str) -> str:
        """解析相对路径为绝对路径"""
        p = Path(path_str)
        return str(p.resolve()) if p.is_absolute() else str((self._current_dir / p).resolve())

    def get(self, section: str, key: str, default: Any = None) -> Any:
        """获取普通配置项（不区分大小写）"""
        try:
            # 关键修复：将 section 和 key 全部转为小写，与 MultiOptionConfigParser 对齐
            value = self._config.get(section.lower(), key.lower())
            if any(kw in key.lower() for kw in ["dir", "path", "uri"]):
                return self._resolve_path(value)
            return value
        except (configparser.NoSectionError, configparser.NoOptionError):
            return default

    # def get(self, section: str, key: str, default: Any = None) -> Any:
    #     """获取普通配置项（不区分大小写）"""
    #     try:
    #         value = self._config.get(section, key)
    #         if any(kw in key.lower() for kw in ["dir", "path", "uri"]):
    #             return self._resolve_path(value)
    #         return value
    #     except (configparser.NoSectionError, configparser.NoOptionError):
    #         return default

    def getint(self, section: str, key: str, default: int = 0) -> int:
        try:
            return self._config.getint(section.lower(), key.lower())
        except (configparser.NoSectionError, configparser.NoOptionError):
            return default

    def getfloat(self, section: str, key: str, default: float = 0.0) -> float:
        try:
            return self._config.getfloat(section.lower(), key.lower())
        except (configparser.NoSectionError, configparser.NoOptionError):
            return default

    def getboolean(self, section: str, key: str, default: bool = False) -> bool:
        try:
            return self._config.getboolean(section.lower(), key.lower())
        except (configparser.NoSectionError, configparser.NoOptionError):
            return default

    def get_list_tuples(self, section: str, key: str, default: List[Tuple] = None) -> List[Tuple]:
        """解析列表元组配置（核心修复：支持大小写不敏感）"""
        default = default or []
        try:
            # 获取所有重复值（不区分大小写）
            values = self._config.get_multi_options(section, key)
            if not values:
                print(f"警告：{section}.{key} 未找到任何值")
                return default

            result = []
            for idx, val in enumerate(values):
                parts = val.strip().split(',')
                if len(parts) == 3:
                    try:
                        name = parts[0].strip()
                        ip = parts[1].strip()
                        port = int(parts[2].strip())
                        result.append((name, ip, port))
                    except ValueError:
                        print(f"警告：第{idx + 1}行值解析失败（格式错误）: {val}")
                else:
                    print(f"警告：第{idx + 1}行值格式错误（需3个字段）: {val}")
            return result
        except Exception as e:
            print(f"解析列表配置失败 {section}.{key}：{e}")
            return default

    def set_list_tuples(self, section: str, key: str, values: List[Tuple]) -> None:
        """写入列表元组配置"""
        if not self._config.has_section(section):
            self._config.add_section(section)

        if section not in self._config._multi_options:
            self._config._multi_options[section] = {}
        self._config._multi_options[section][key] = []

        for val in values:
            if len(val) == 3:
                line = f"{val[0]},{val[1]},{val[2]}"
                self._config._multi_options[section][key].append(line)
                self._config.set(section, key, line)

    def set(self, section: str, key: str, value: Any) -> None:
        """设置普通配置项"""
        if not self._config.has_section(section):
            self._config.add_section(section)
        self._config.set(section, key, str(value))

    def save(self) -> None:
        """保存配置到文件"""
        with open(self._config_path, "w", encoding="utf-8") as f:
            for section in self._config.sections():
                f.write(f"[{section}]\n")

                # 写重复option
                if section in self._config._multi_options:
                    for opt, vals in self._config._multi_options[section].items():
                        for val in vals:
                            f.write(f"{opt} = {val}\n")

                # 写普通option
                normal_options = self._config._sections.get(section, {}).copy()
                if section in self._config._multi_options:
                    for opt in self._config._multi_options[section].keys():
                        normal_options.pop(opt, None)
                for opt, val in normal_options.items():
                    f.write(f"{opt} = {val}\n")

                f.write("\n")

    @property
    def config_path(self) -> str:
        return str(self._config_path)

    @property
    def config_dir(self) -> str:
        return str(self._current_dir)

    def list_all_sections(self):
        """列出配置文件中所有的section（调试用）"""
        return self._config.sections()

    def list_options_in_section(self, section: str):
        """列出指定section下的所有option（调试用）"""
        try:
            return self._config.options(section)
        except configparser.NoSectionError:
            return []


# ===================== 具体配置类 =====================
class MyTdxConfig(BaseConfig):
    """mytdx.ini 配置管理类"""

    def __init__(self):
        super().__init__("mytdx.ini")


class AkShareConfig(BaseConfig):
    """akshare.ini 配置管理类"""

    def __init__(self):
        super().__init__("akshare.ini")


# ===================== 全局单例 =====================
_tdx_config_instance: Optional[MyTdxConfig] = None


def get_tdx_config() -> MyTdxConfig:
    global _tdx_config_instance
    if _tdx_config_instance is None:
        _tdx_config_instance = MyTdxConfig()
    return _tdx_config_instance


_akshare_config_instance: Optional[AkShareConfig] = None


def get_akshare_config() -> AkShareConfig:
    global _akshare_config_instance
    if _akshare_config_instance is None:
        try:
            _akshare_config_instance = AkShareConfig()
        except FileNotFoundError:
            # akshare.ini不存在时返回None，避免程序崩溃
            return None
    return _akshare_config_instance


# ===================== 测试代码（修复解析为空+容错） =====================
if __name__ == "__main__":
    try:
        # 1. 测试TDX配置（核心：调试+解析服务器列表）
        tdx_cfg = get_tdx_config()
        print(f"=== TDX配置信息 ===")
        print(f"配置文件路径: {tdx_cfg.config_path}")

        # 调试：列出所有section和option（关键！匹配实际配置）
        all_sections = tdx_cfg.list_all_sections()
        print(f"配置文件中的所有section: {all_sections}")

        # 遍历所有section，查看每个section下的option
        for sec in all_sections:
            options = tdx_cfg.list_options_in_section(sec)
            print(f"Section [{sec}] 下的option: {options}")

        tdx_data_dir = tdx_cfg.get(section='TDX_DATA',key='tdx_data_dir')
        print(tdx_data_dir)

        # 解析服务器列表（根据实际section/key调整！）
        # 【重要】请根据上面打印的实际名称修改下面的section和key
        hq_hosts = tdx_cfg.get_list_tuples("TDX_SERVER", "hq_hosts")
        print(f"\n解析到的行情服务器列表: {hq_hosts}")



        # 2. 测试AkShare配置（容错处理）
        print(f"\n=== AkShare配置信息 ===")
        ak_cfg = get_akshare_config()
        if ak_cfg:
            print(f"配置文件路径: {ak_cfg.config_path}")
            proxy = ak_cfg.get("NETWORK", "proxy", default="无代理")
            print(f"AkShare代理: {proxy}")
        else:
            print("akshare.ini文件不存在（可选配置，忽略）")

    except FileNotFoundError as e:
        print(f"错误: {e}")
        print("请确保mytdx.ini文件与当前py文件在同一目录下")
    except Exception as e:
        print(f"运行错误: {type(e).__name__} - {e}")