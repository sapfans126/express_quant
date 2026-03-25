# main_xq/dc/db_connector.py
"""
ExpressQuant（迅驰量化）- 数据库连接工具类
封装MySQL连接、通用CRUD操作，基于sqlalchemy实现
"""
import sqlalchemy
from sqlalchemy.orm import sessionmaker
from main_xq.config import MYSQL_CONFIG, BATCH_INSERT_SIZE


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

    def get_connection(self):
        """获取数据库连接（用于原生SQL操作）"""
        return self.engine.connect()

    def get_session(self):
        """获取数据库会话（用于ORM操作）"""
        return self.Session()

    def execute_sql(self, sql, params=None):
        """
        执行原生SQL语句
        :param sql: SQL语句（字符串）
        :param params: SQL参数（字典/列表）
        :return: 执行结果（查询返回数据，增删改返回影响行数）
        """
        try:
            with self.get_connection() as conn:
                # 执行SQL
                result = conn.execute(sqlalchemy.text(sql), params or {})
                # 提交事务（增删改）
                if sql.strip().upper().startswith(("INSERT", "UPDATE", "DELETE", "CREATE")):
                    conn.commit()
                    return result.rowcount  # 返回影响行数
                # 查询返回数据
                else:
                    return result.fetchall()
        except Exception as e:
            print(f"执行SQL失败：{e}")
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
            return len(df)
        except Exception as e:
            print(f"批量插入失败：{e}")
            raise


# 单例模式（避免重复创建连接池）
db_connector = DBConnector()

# 测试代码（运行该文件时执行）
if __name__ == "__main__":
    # 初始化连接器
    connector = DBConnector()

    # 测试连接
    try:
        result = connector.execute_sql("SELECT DATABASE();")
        print(f"✅ 数据库连接成功，当前库：{result[0][0]}")

        # 测试查询表数量
        table_count = connector.execute_sql(
            "SELECT COUNT(*) FROM INFORMATION_SCHEMA.TABLES WHERE TABLE_SCHEMA = :db",
            params={"db": MYSQL_CONFIG["database"]}
        )
        print(f"📊 库中表数量：{table_count[0][0]}")
    except Exception as e:
        print(f"❌ 数据库操作失败：{e}")