# main_xq/dm/dba.py
"""
ExpressQuant（迅驰量化）- 数据库连接工具类
封装MySQL连接、通用CRUD操作，基于sqlalchemy实现
"""
import configparser
from pathlib import Path
import sqlalchemy
from sqlalchemy.orm import sessionmaker

# 导入日志模块
from main_xq.utils.logger import get_logger_for_current_module

logger = get_logger_for_current_module(__file__)


def load_mysql_config():
    """加载 MySQL 配置文件"""
    # 获取配置文件路径
    config_file = Path(__file__).parent.parent / "config" / "mysql.ini"

    if not config_file.exists():
        raise FileNotFoundError(f"配置文件不存在: {config_file}")

    config = configparser.ConfigParser()
    config.read(config_file, encoding='utf-8')

    # 读取配置
    mysql_config = {
        'host': config.get('mysql', 'host'),
        'port': config.getint('mysql', 'port'),
        'user': config.get('mysql', 'user'),
        'password': config.get('mysql', 'password'),
        'database': config.get('mysql', 'database'),
        'charset': config.get('mysql', 'charset'),
        'pool_size': config.getint('connection_pool', 'pool_size'),
        'pool_recycle': config.getint('connection_pool', 'pool_recycle'),
        'connect_timeout': config.getint('connection_pool', 'connect_timeout'),
        'echo': config.getboolean('performance', 'echo'),
        'batch_insert_size': config.getint('performance', 'batch_insert_size'),
    }

    logger.info(f"MySQL配置加载成功: {mysql_config['host']}:{mysql_config['port']}/{mysql_config['database']}")
    return mysql_config


# 加载配置
MYSQL_CONFIG = load_mysql_config()
BATCH_INSERT_SIZE = MYSQL_CONFIG['batch_insert_size']


class DBConnector:
    """数据库连接与操作类"""

    def __init__(self):
        # 构建数据库连接字符串
        self.conn_str = (
            f"mysql+pymysql://{MYSQL_CONFIG['user']}:{MYSQL_CONFIG['password']}@"
            f"{MYSQL_CONFIG['host']}:{MYSQL_CONFIG['port']}/{MYSQL_CONFIG['database']}"
            f"?charset={MYSQL_CONFIG['charset']}"
        )
        # 创建数据库引擎（连接池）
        self.engine = sqlalchemy.create_engine(
            self.conn_str,
            pool_size=MYSQL_CONFIG["pool_size"],
            pool_recycle=MYSQL_CONFIG.get("pool_recycle", 3600),
            echo=MYSQL_CONFIG["echo"],
            connect_args={"connect_timeout": MYSQL_CONFIG["connect_timeout"]}
        )
        # 创建会话工厂（用于ORM操作）
        self.Session = sessionmaker(bind=self.engine)
        logger.info(f"数据库连接池初始化成功，pool_size={MYSQL_CONFIG['pool_size']}")

    def get_connection(self):
        """获取数据库连接（用于原生SQL操作）"""
        return self.engine.connect()

    def get_session(self):
        """获取数据库会话（用于ORM操作）"""
        return self.Session()

    # def execute_sql(self, sql, params=None):
    #     """
    #     执行原生SQL语句
    #     :param sql: SQL语句（字符串）
    #     :param params: SQL参数（支持字典、列表、元组）
    #     :return: 执行结果（查询返回数据，增删改返回影响行数）
    #     """
    #     try:
    #         with self.get_connection() as conn:
    #             # ✅ 关键修改：处理列表参数
    #             if params is None:
    #                 # result = conn.execute(sqlalchemy.text(sql))
    #                 result = conn.execute(sql)  # 这里！不要包 text()
    #             elif isinstance(params, list):
    #                 # 【关键】普通列表 = 单次执行，转 tuple！
    #                 # 只有 list 里面全是 tuple 时，才叫批量执行
    #                 # result = conn.execute(sqlalchemy.text(sql), tuple(params))
    #                 result = conn.execute(sql, tuple(params))  # 这里！
    #             elif isinstance(params, (tuple, dict)):
    #                 # tuple / dict 直接用
    #                 # result = conn.execute(sqlalchemy.text(sql), params)
    #                 result = conn.execute(sql, params)  # 这里！
    #             else:
    #                 # result = conn.execute(sqlalchemy.text(sql), params)
    #                 result = conn.execute(sql, params)
    #
    #             # 提交事务（增删改）
    #             if sql.strip().upper().startswith(("INSERT", "UPDATE", "DELETE", "CREATE")):
    #                 conn.commit()
    #                 affected_rows = result.rowcount
    #                 logger.debug(f"执行写操作成功，影响行数: {affected_rows}")
    #                 return affected_rows
    #             # 查询返回数据
    #             else:
    #                 rows = result.fetchall()
    #                 logger.debug(f"执行查询成功，返回行数: {len(rows)}")
    #                 return rows
    #     except Exception as e:
    #         logger.error(f"执行SQL失败: {e}\nSQL: {sql}")
    #         raise

    def execute_sql(self, sql, params=None):
        """
        执行原生SQL语句
        :param sql: SQL语句（字符串 或 TextClause）
        :param params: SQL参数（支持字典、列表、元组）
        :return: 执行结果（查询返回数据，增删改返回影响行数）
        """
        try:
            with self.get_connection() as conn:
                from sqlalchemy import text

                # ======================
                # 智能处理：字符串转 text，TextClause 直接用
                # ======================
                if isinstance(sql, str):
                    sql = text(sql)

                # ======================
                # 执行逻辑
                # ======================
                if params is None:
                    result = conn.execute(sql)

                elif isinstance(params, list):
                    result = conn.execute(sql, tuple(params))

                elif isinstance(params, (tuple, dict)):
                    result = conn.execute(sql, params)

                else:
                    result = conn.execute(sql, params)

                # ======================
                # 获取SQL字符串（兼容 TextClause）
                # ======================
                sql_str = sql.text.strip().upper()

                # ======================
                # 写事务提交
                # ======================
                if sql_str.startswith(("INSERT", "UPDATE", "DELETE", "CREATE")):
                    conn.commit()
                    affected_rows = result.rowcount
                    logger.debug(f"执行写操作成功，影响行数: {affected_rows}")
                    return affected_rows

                # ======================
                # 查询返回结果
                # ======================
                else:
                    rows = result.fetchall()
                    logger.debug(f"执行查询成功，返回行数: {len(rows)}")
                    return rows

        except Exception as e:
            logger.error(f"执行SQL失败: {e}\nSQL: {sql}")
            raise

    def batch_insert(self, df, table_name, if_exists="append"):
        """
        批量插入DataFrame数据到指定表
        :param df: 待插入的DataFrame
        :param table_name: 目标表名（直接使用，无前缀）
        :param if_exists: 存在时的处理方式：append-追加，replace-替换，fail-报错
        :return: 插入行数
        """
        try:
            # 直接使用表名，无需拼接前缀
            full_table_name = table_name
            # 批量插入（按配置的批次大小）
            df.to_sql(
                name=full_table_name,
                con=self.engine,
                if_exists=if_exists,
                index=False,
                chunksize=BATCH_INSERT_SIZE
            )
            logger.info(f"批量插入成功，表: {table_name}, 行数: {len(df)}, 模式: {if_exists}")
            return len(df)
        except Exception as e:
            logger.error(f"批量插入失败: {e}, 表: {table_name}")
            raise

    def table_exists(self, table_name: str) -> bool:
        """
        检查表是否存在（数据库无关）

        Args:
            table_name: 表名

        Returns:
            bool: True=存在, False=不存在

        Examples:
            >>> db.table_exists('as_code_list_tdx')
            True
        """
        try:
            from sqlalchemy import inspect
            inspector = inspect(self.engine)
            exists = table_name in inspector.get_table_names()
            logger.debug(f"检查表 {table_name} 存在性: {exists}")
            return exists
        except Exception as e:
            logger.error(f"检查表 {table_name} 是否存在失败: {e}")
            return False

    def read_sql_to_df(self, sql, params=None, index_col=None, parse_dates=None):
        """
        使用 pandas 读取 SQL 查询结果到 DataFrame

        :param sql: SQL查询语句（字符串）
        :param params: SQL参数
                       - MySQL/pymysql 使用 %s 占位符时，参数必须是元组或列表
                       - 单个参数也要用元组: (value,)
                       - 多个参数用元组: (value1, value2)
        :param index_col: 设置为索引的列名（可选）
        :param parse_dates: 需要解析为日期的列名列表（可选）
        :return: 包含查询结果的 DataFrame
        """
        try:
            import pandas as pd

            # 处理参数
            if params is not None:
                # 单个非序列参数，包装成元组
                if not isinstance(params, (list, tuple, dict)):
                    params = (params,)

                # 对于 MySQL/pymysql 驱动，使用 %s 占位符，参数需要是元组或列表
                # 注意：不要使用 text() 包装，直接传 SQL 字符串和参数给 pd.read_sql
                # 这样可以保持与 pymysql 驱动的兼容性
                if isinstance(params, dict):
                    # 字典参数需要转换：将 :name 占位符转换为 %s
                    # 或者改用命名参数方式
                    from sqlalchemy import text
                    with self.engine.connect() as conn:
                        df = pd.read_sql(
                            sql=text(sql),
                            con=conn,
                            params=params,
                            index_col=index_col,
                            parse_dates=parse_dates
                        )
                else:
                    # 元组或列表参数，直接传给 pd.read_sql（使用 %s 占位符）
                    df = pd.read_sql(
                        sql=sql,
                        con=self.engine,
                        params=params,
                        index_col=index_col,
                        parse_dates=parse_dates
                    )
            else:
                # 无参数
                df = pd.read_sql(
                    sql=sql,
                    con=self.engine,
                    index_col=index_col,
                    parse_dates=parse_dates
                )

            logger.debug(f"read_sql_to_df 成功，返回 {len(df)} 行，SQL: {sql[:100]}...")
            return df

        except Exception as e:
            logger.error(f"read_sql_to_df 执行失败: {e}\nSQL: {sql}")
            raise


# 单例模式（避免重复创建连接池）
db_connector = DBConnector()

# 测试代码（运行该文件时执行）
if __name__ == "__main__":
    # # 初始化连接器
    connector = DBConnector()
    #
    # # 测试连接
    # try:
    #     result = connector.execute_sql("SELECT DATABASE();")
    #     logger.info(f"✅ 数据库连接成功，当前库：{result[0][0]}")
    #
    #     # 测试查询表数量
    #     table_count = connector.execute_sql(
    #         "SELECT COUNT(*) FROM INFORMATION_SCHEMA.TABLES WHERE TABLE_SCHEMA = :db",
    #         params={"db": MYSQL_CONFIG["database"]}
    #     )
    #     logger.info(f"📊 库中表数量：{table_count[0][0]}")
    #
    #     # 测试 table_exists 方法
    #     test_table = 'as_code_list_tdx'
    #     if connector.table_exists(test_table):
    #         logger.info(f"表 {test_table} 存在")
    #     else:
    #         logger.info(f"表 {test_table} 不存在")
    #
    # except Exception as e:
    #     logger.error(f"❌ 数据库操作失败：{e}")

    # 1. 基本查询
    df_basic_info = db_connector.read_sql_to_df("SELECT * FROM basic_info_update WHERE code = '000012.SZ'")
    print(df_basic_info)


    # 2. 带参数的查询（列表参数）
    df = db_connector.read_sql_to_df(
        "SELECT * FROM basic_info_update WHERE code = %s ",
        params=('000096.SZ',)
    )
    print(df)

    # # 3. 带参数的查询（字典参数）
    # df = db_connector.read_sql_to_df(
    #     "SELECT * FROM users WHERE age > :min_age AND city = :city",
    #     params={'min_age': 18, 'city': 'Beijing'}
    # )
    #
    # # 4. 设置索引列和解析日期
    # df = db_connector.read_sql_to_df(
    #     "SELECT id, name, created_at FROM users",
    #     index_col='id',
    #     parse_dates=['created_at']
    # )

    # 正确的使用方式：
    #
    # python
    # # ✅ 单个参数（元组，注意逗号）
    # df = db_connector.read_sql_to_df(
    #     "SELECT * FROM basic_info_update WHERE code = %s",
    #     params=('000096.SZ',)  # 必须是元组，逗号不能少
    # )
    #
    # # ✅ 单个参数（列表）
    # df = db_connector.read_sql_to_df(
    #     "SELECT * FROM basic_info_update WHERE code = %s",
    #     params=['000096.SZ']  # 列表也可以
    # )
    #
    # # ✅ 多个参数（元组）
    # df = db_connector.read_sql_to_df(
    #     "SELECT * FROM basic_info_update WHERE code = %s AND market = %s",
    #     params=('000096.SZ', 'SZ')
    # )
    #
    # # ✅ 无参数
    # df = db_connector.read_sql_to_df("SELECT * FROM basic_info_update LIMIT 10")