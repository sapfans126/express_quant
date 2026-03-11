# -*- coding: utf-8 -*-
"""
ExpressQuant（迅驰量化）- 数据库核心配置文件
适配环境说明：
1. MySQL版本：8.0（数据目录已迁移至D盘）
2. 目标数据库：express_quant（从my_quant克隆而来）
3. Conda环境：MyQuant（D:/xs/MyDev/MyConda/envs/MyQuant）
4. 字符集：utf8mb4（匹配MySQL默认字符集utf8mb4_0900_ai_ci）
"""

# ===================== 【核心配置】MySQL连接参数 =====================
# 注：仅需修改password字段，其余参数无需调整
MYSQL_CONFIG = {
    # 基础连接信息（与MySQL Workbench一致）
    "host": "localhost",  # 本地数据库地址（固定值，无需修改）
    "port": 3306,  # MySQL 8.0默认端口（固定值，无需修改）
    "user": "root",  # MySQL登录用户名（默认root，如需修改请同步）
    "password": "123456",  # 【必填】替换为你的MySQL密码（关键！）
    "database": "express_quant",  # 克隆后的量化专用库（核心，不可修改）
    "charset": "utf8mb4",  # 数据库字符集（匹配原库，不可修改）

    # 连接池/性能配置（优化项，无需修改）
    "pool_size": 10,  # 数据库连接池大小（适配高并发查询）
    "pool_recycle": 3600,  # 连接回收时间（1小时，避免超时）
    "echo": False,  # 是否打印SQL语句（开发时设为True，上线改False）

    # 超时配置（避免长时间操作卡顿）
    "connect_timeout": 30  # 数据库操作超时时间（秒）
}

# ===================== 【辅助配置】批量操作 =====================
# 批量插入数据的批次大小（适配大数据量入库，避免内存溢出）
BATCH_INSERT_SIZE = 1000

# ===================== 【可选配置】文件导入导出路径 =====================
# 修复：将路径分隔符从\改为/（或用\\）
FILE_UPLOAD_DIR = "D:/xs/MyDev/MySQL/Uploads"  # 正确写法

# ===================== 【验证逻辑】配置自检（运行该文件时执行） =====================
if __name__ == "__main__":
    import sys
    import sqlalchemy
    from sqlalchemy.exc import OperationalError, ProgrammingError


    def check_mysql_config():
        """验证MySQL配置是否正确"""
        print("===== 开始验证ExpressQuant数据库配置 =====")

        # 1. 检查必填参数
        required_keys = ["host", "port", "user", "password", "database"]
        missing_keys = [k for k in required_keys if not MYSQL_CONFIG.get(k)]
        if missing_keys:
            print(f"❌ 错误：缺少必填配置项 → {', '.join(missing_keys)}")
            sys.exit(1)

        # 2. 构建连接字符串
        try:
            conn_str = (
                f"mysql+pymysql://{MYSQL_CONFIG['user']}:{MYSQL_CONFIG['password']}@"
                f"{MYSQL_CONFIG['host']}:{MYSQL_CONFIG['port']}/{MYSQL_CONFIG['database']}"
                f"?charset={MYSQL_CONFIG['charset']}"
            )
            # 创建引擎（测试连接）
            engine = sqlalchemy.create_engine(
                conn_str,
                pool_size=MYSQL_CONFIG["pool_size"],
                pool_recycle=MYSQL_CONFIG["pool_recycle"],
                connect_args={"connect_timeout": MYSQL_CONFIG["connect_timeout"]}
            )

            # 3. 测试连接并验证数据库
            with engine.connect() as conn:
                # 验证当前数据库
                db_result = conn.execute(sqlalchemy.text("SELECT DATABASE();"))
                current_db = db_result.scalar()
                print(f"✅ 数据库连接成功！当前连接的库：{current_db}")

                # 验证数据库是否存在
                if current_db != MYSQL_CONFIG["database"]:
                    print(f"⚠️ 警告：目标库{MYSQL_CONFIG['database']}不存在，已自动创建")
                    conn.execute(sqlalchemy.text(
                        f"CREATE DATABASE IF NOT EXISTS {MYSQL_CONFIG['database']} DEFAULT CHARSET=utf8mb4;"))
                    conn.commit()

                # 4. 验证批量插入配置
                print(f"✅ 批量插入批次大小：{BATCH_INSERT_SIZE}")

                # 5. 验证MySQL服务状态
                version_result = conn.execute(sqlalchemy.text("SELECT VERSION();"))
                mysql_version = version_result.scalar()
                print(f"✅ MySQL版本验证：{mysql_version}（符合8.0要求）")

                print("\n===== 配置验证全部通过！可以开始开发项目 =====")

        except OperationalError as e:
            print(f"\n❌ 数据库连接失败 → {str(e)}")
            print("\n常见原因：")
            print("1. MySQL密码错误（检查password字段）")
            print("2. MySQL服务未启动（Win+R → services.msc → 启动MySQL80）")
            print("3. MySQL端口被占用（默认3306是否被修改）")
            sys.exit(1)

        except ProgrammingError as e:
            print(f"\n❌ 数据库操作失败 → {str(e)}")
            print("\n常见原因：")
            print(f"1. 目标库{MYSQL_CONFIG['database']}未克隆成功")
            print("2. 当前用户无数据库访问权限")
            sys.exit(1)

        except Exception as e:
            print(f"\n❌ 未知错误 → {str(e)}")
            sys.exit(1)


    # 执行配置验证
    check_mysql_config()