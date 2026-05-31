import sys
from pathlib import Path
import main_xq.config.config as cfg
from main_xq.utils.logger import get_logger_for_current_module

logger = get_logger_for_current_module(__file__)

# ============== 强制先加路径，再导入 ==============
tdx_config = cfg.MyTdxConfig()
tq_path_str = tdx_config.get(section="PYPLUGIN", key="tdx_user_dir")

if tq_path_str:
    tq_path = Path(tq_path_str).resolve()
    path_str = str(tq_path)
    if path_str not in sys.path:
        sys.path.insert(0, path_str)

# ============== 立即导入 ==============
try:
    import tqcenter

    TQ = tqcenter
    logger.info("✅ tqcenter 加载成功")
except Exception as e:
    TQ = None
    logger.error(f"加载失败: {e}", exc_info=True)
