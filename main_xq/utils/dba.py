# main_xq/dm/dba.py
"""
ExpressQuant（迅驰量化）- 数据库连接工具类
封装MySQL连接、通用CRUD操作，基于sqlalchemy实现
"""
import sqlalchemy
from sqlalchemy.orm import sessionmaker
from main_xq.config.config import get_mysql_config




class DBConnector:
    """数据库连接与操作类"""

    def __init__(self, config=None):
        """
        初始化数据库连接
        :param config: MySQL配置字典，如果为None则从配置文件加载
        """
        # 加载MySQL配置
        if config is None:
            # 从配置文件加载
            mysql_config_obj = get_mysql_config()
            self.mysql_config = mysql_config_obj.get_connection_config()
        else:
            # 使用传入的配置（便于测试）
            self.mysql_config = config

        # 构建数据库连接字符串
        self.conn_str = (
            f"mysql+pymysql://{self.mysql_config['user']}:{self.mysql_config['password']}@"
            f"{self.mysql_config['host']}:{self.mysql_config['port']}/{self.mysql_config['database']}"
            f"?charset={self.mysql_config['charset']}"
        )

        # 创建数据库引擎（连接池）
        self.engine = sqlalchemy.create_engine(
            self.conn_str,
            pool_size=self.mysql_config["pool_size"],
            pool_recycle=self.mysql_config.get("pool_recycle", 3600),
            echo=self.mysql_config.get("echo", False),
            connect_args={"connect_timeout": self.mysql_config.get("connect_timeout", 10)}
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
                if sql.strip().upper().startswith(("INSERT", "UPDATE", "DELETE", "CREATE", "DROP", "ALTER")):
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
                chunksize=self.mysql_config.get("batch_insert_size", 1000)
            )
            return len(df)
        except Exception as e:
            print(f"批量插入失败：{e}")
            raise

    def test_connection(self):
        """测试数据库连接"""
        try:
            result = self.execute_sql("SELECT 1 as test, DATABASE() as db, VERSION() as version")
            if result:
                row = result[0]
                return {
                    'success': True,
                    'database': row[1],
                    'version': row[2]
                }
        except Exception as e:
            return {
                'success': False,
                'error': str(e)
            }


# 单例模式（避免重复创建连接池）
db_connector = DBConnector()

# 测试代码（运行该文件时执行）
if __name__ == "__main__":
    print("=== MySQL 连接测试 ===\n")

    try:
        mysql_cfg = get_mysql_config()
        config_dict = mysql_cfg.get_connection_config()

        # 打印配置（注意隐藏密码）
        print("MySQL 配置加载情况：")
        print(f"  host: {config_dict['host']}")
        print(f"  port: {config_dict['port']}")
        print(f"  user: {config_dict['user']}")
        print(f"  password: {'*' * len(config_dict['password'])} (长度: {len(config_dict['password'])})")
        print(f"  database: {config_dict['database']}")

        # 测试连接
        connector = DBConnector(config_dict)
        result = connector.test_connection()
        print(f"连接测试: {result}")

    except Exception as e:
        print(f"配置加载失败: {e}")


    # 初始化连接器
    connector = DBConnector()

    # 测试连接
    test_result = connector.test_connection()
    if test_result['success']:
        print(f"✅ 数据库连接成功")
        print(f"   数据库：{test_result['database']}")
        print(f"   版本：{test_result['version']}")

        # 测试查询表数量
        try:
            table_count = connector.execute_sql(
                "SELECT COUNT(*) FROM INFORMATION_SCHEMA.TABLES WHERE TABLE_SCHEMA = :db",
                params={"db": connector.mysql_config['database']}
            )
            print(f"📊 库中表数量：{table_count[0][0]}")
        except Exception as e:
            print(f"查询表数量失败：{e}")

        # 打印配置信息
        print(f"\n⚙️ 当前配置：")
        print(f"   连接池大小：{connector.mysql_config['pool_size']}")
        print(f"   批量插入大小：{connector.mysql_config.get('batch_insert_size', 1000)}")
        print(f"   SQL日志：{connector.mysql_config.get('echo', False)}")
    else:
        print(f"❌ 数据库连接失败：{test_result['error']}")