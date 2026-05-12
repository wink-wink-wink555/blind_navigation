"""
数据库操作模块 - 包含所有数据库相关函数
"""
import pymysql
import hashlib
import json
from config import DB_CONFIG
from utils.email_utils import verify_code


def get_db_connection():
    """创建数据库连接"""
    try:
        connection = pymysql.connect(
            **DB_CONFIG,
            cursorclass=pymysql.cursors.DictCursor
        )
        return connection
    except Exception as e:
        print(f"数据库连接错误: {e}")
        return None


def init_database():
    """初始化数据库，创建必要的表"""
    conn = get_db_connection()
    if not conn:
        print("无法连接到数据库，请检查数据库配置")
        return False

    try:
        with conn.cursor() as cursor:
            # 创建用户表，添加email字段
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS users (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    username VARCHAR(50) NOT NULL UNIQUE,
                    password VARCHAR(255) NOT NULL,
                    email VARCHAR(100) NOT NULL UNIQUE,
                    phone VARCHAR(20),
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    last_login DATETIME
                )
            ''')

            # 创建用户设置表
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS user_settings (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    user_id INT NOT NULL,
                    gender VARCHAR(10) DEFAULT '未指定',
                    name VARCHAR(50) DEFAULT '用户',
                    age VARCHAR(10) DEFAULT '未指定',
                    voice_speed VARCHAR(10) DEFAULT '中等',
                    voice_volume VARCHAR(10) DEFAULT '中等',
                    user_mode VARCHAR(10) DEFAULT '盲人端',
                    encourage VARCHAR(10) DEFAULT '开',
                    FOREIGN KEY (user_id) REFERENCES users(id)
                )
            ''')

            # 创建家属联系人表
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS family_contacts (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    user_id INT NOT NULL,
                    name VARCHAR(50) NOT NULL,
                    email VARCHAR(100) NOT NULL,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (user_id) REFERENCES users(id)
                )
            ''')

            # 创建AI模型配置表（按用户隔离，统一存JSON以便扩展更多模型类型）
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS user_ai_settings (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    user_id INT NOT NULL UNIQUE,
                    config TEXT NOT NULL,
                    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
                    FOREIGN KEY (user_id) REFERENCES users(id)
                )
            ''')

        conn.commit()
        print("数据库初始化成功")
        return True
    except Exception as e:
        print(f"数据库初始化失败: {e}")
        return False
    finally:
        conn.close()


def register_user(username, password, email, verification_code, phone=None):
    """注册新用户，增加验证码验证"""
    # 验证邮箱验证码
    code_valid, message = verify_code(email, verification_code)
    if not code_valid:
        return False, message

    conn = get_db_connection()
    if not conn:
        return False, "数据库连接失败"

    try:
        # 密码加密
        password_hash = hashlib.sha256(password.encode()).hexdigest()

        with conn.cursor() as cursor:
            # 检查用户名是否已存在
            cursor.execute("SELECT id FROM users WHERE username = %s", (username,))
            if cursor.fetchone():
                return False, "用户名已存在"

            # 检查邮箱是否已存在
            cursor.execute("SELECT id FROM users WHERE email = %s", (email,))
            if cursor.fetchone():
                return False, "该邮箱已被注册"

            # 插入新用户
            cursor.execute(
                "INSERT INTO users (username, password, email, phone) VALUES (%s, %s, %s, %s)",
                (username, password_hash, email, phone)
            )

            # 获取新用户ID
            user_id = cursor.lastrowid

            # 创建用户设置
            cursor.execute(
                "INSERT INTO user_settings (user_id) VALUES (%s)",
                (user_id,)
            )

        conn.commit()
        return True, "注册成功"
    except Exception as e:
        conn.rollback()
        print(f"注册用户失败: {e}")
        return False, f"注册失败: {str(e)}"
    finally:
        conn.close()


def verify_user(username, password):
    """验证用户登录"""
    conn = get_db_connection()
    if not conn:
        return False, "数据库连接失败", None

    try:
        # 密码加密
        password_hash = hashlib.sha256(password.encode()).hexdigest()

        with conn.cursor() as cursor:
            # 查询用户
            cursor.execute("SELECT id, username FROM users WHERE username = %s AND password = %s",
                           (username, password_hash))
            user = cursor.fetchone()

            if not user:
                return False, "用户名或密码错误", None

            # 更新最后登录时间
            cursor.execute("UPDATE users SET last_login = NOW() WHERE id = %s", (user['id'],))

            # 获取用户设置
            cursor.execute("SELECT * FROM user_settings WHERE user_id = %s", (user['id'],))
            settings = cursor.fetchone()

            if not settings:
                # 如果没有设置，创建默认设置
                cursor.execute("INSERT INTO user_settings (user_id) VALUES (%s)", (user['id'],))
                cursor.execute("SELECT * FROM user_settings WHERE user_id = %s", (user['id'],))
                settings = cursor.fetchone()

        conn.commit()

        # 将设置转换为应用中使用的格式
        user_config = {
            "id": user['id'],
            "username": user['username'],
            "gender": settings['gender'],
            "name": settings['name'],
            "age": settings['age'],
            "voice_speed": settings['voice_speed'],
            "voice_volume": settings['voice_volume'],
            "user_mode": settings['user_mode'],
            "encourage": settings['encourage']
        }

        return True, "登录成功", user_config
    except Exception as e:
        print(f"验证用户失败: {e}")
        return False, f"登录失败: {str(e)}", None
    finally:
        conn.close()


def update_user_settings_in_db(user_id, settings):
    """更新数据库中的用户设置"""
    conn = get_db_connection()
    if not conn:
        return False, "数据库连接失败"

    try:
        with conn.cursor() as cursor:
            # 更新用户设置
            cursor.execute("""
                UPDATE user_settings 
                SET gender = %s, name = %s, age = %s, 
                    voice_speed = %s, voice_volume = %s, user_mode = %s, encourage = %s
                WHERE user_id = %s
                """,
                           (settings["gender"], settings["name"], settings["age"],
                            settings["voice_speed"], settings["voice_volume"], settings["user_mode"],
                            settings["encourage"],
                            user_id)
                           )

        conn.commit()
        return True, "设置更新成功"
    except Exception as e:
        conn.rollback()
        print(f"更新用户设置失败: {e}")
        return False, f"设置更新失败: {str(e)}"
    finally:
        conn.close()


def get_user_settings(user_id):
    """从数据库获取用户设置"""
    conn = get_db_connection()
    if not conn:
        return None, "数据库连接失败"
    
    try:
        with conn.cursor() as cursor:
            cursor.execute("SELECT * FROM user_settings WHERE user_id = %s", (user_id,))
            settings_data = cursor.fetchone()
            
            if not settings_data:
                return None, "找不到用户设置"
            
            return {
                "gender": settings_data['gender'],
                "name": settings_data['name'],
                "age": settings_data['age'],
                "voice_speed": settings_data['voice_speed'],
                "voice_volume": settings_data['voice_volume'],
                "user_mode": settings_data['user_mode'],
                "encourage": settings_data['encourage']
            }, "成功"
    
    except Exception as e:
        print(f"获取用户设置失败: {e}")
        return None, f"获取用户设置失败: {str(e)}"
    finally:
        conn.close()


def get_user_details(user_id):
    """获取用户详细信息"""
    conn = get_db_connection()
    if not conn:
        return None, "数据库连接失败"

    try:
        with conn.cursor() as cursor:
            # 查询用户详细信息
            cursor.execute("""
                SELECT username, email, phone, created_at, last_login
                FROM users
                WHERE id = %s
            """, (user_id,))

            user_info = cursor.fetchone()

            if not user_info:
                return None, "找不到用户信息"

            # 格式化日期时间
            created_at = user_info['created_at'].strftime('%Y-%m-%d %H:%M:%S') if user_info['created_at'] else "未知"
            last_login = user_info['last_login'].strftime('%Y-%m-%d %H:%M:%S') if user_info['last_login'] else "未知"

            return {
                "username": user_info['username'],
                "email": user_info['email'],
                "phone": user_info['phone'] or "未设置",
                "created_at": created_at,
                "last_login": last_login
            }, "成功"

    except Exception as e:
        print(f"获取用户信息失败: {e}")
        return None, f"获取用户信息失败: {str(e)}"
    finally:
        conn.close()


def get_family_contacts(user_id):
    """获取用户的所有家属联系人"""
    conn = get_db_connection()
    if not conn:
        return [], "数据库连接失败"

    try:
        with conn.cursor() as cursor:
            cursor.execute(
                "SELECT id, name, email, created_at FROM family_contacts WHERE user_id = %s ORDER BY id",
                (user_id,)
            )
            contacts = cursor.fetchall()
            for c in contacts:
                if c.get('created_at'):
                    c['created_at'] = c['created_at'].strftime('%Y-%m-%d %H:%M:%S')
            return contacts, "成功"
    except Exception as e:
        print(f"获取家属联系人失败: {e}")
        return [], f"获取失败: {str(e)}"
    finally:
        conn.close()


def add_family_contact(user_id, name, email):
    """添加家属联系人"""
    conn = get_db_connection()
    if not conn:
        return False, "数据库连接失败"

    try:
        with conn.cursor() as cursor:
            cursor.execute(
                "SELECT COUNT(*) as cnt FROM family_contacts WHERE user_id = %s",
                (user_id,)
            )
            count = cursor.fetchone()['cnt']
            if count >= 10:
                return False, "最多只能添加10个家属联系人"

            cursor.execute(
                "INSERT INTO family_contacts (user_id, name, email) VALUES (%s, %s, %s)",
                (user_id, name, email)
            )
        conn.commit()
        return True, "添加成功"
    except Exception as e:
        conn.rollback()
        print(f"添加家属联系人失败: {e}")
        return False, f"添加失败: {str(e)}"
    finally:
        conn.close()


def delete_family_contact(user_id, contact_id):
    """删除家属联系人（确保只能删除自己的）"""
    conn = get_db_connection()
    if not conn:
        return False, "数据库连接失败"

    try:
        with conn.cursor() as cursor:
            cursor.execute(
                "DELETE FROM family_contacts WHERE id = %s AND user_id = %s",
                (contact_id, user_id)
            )
            if cursor.rowcount == 0:
                return False, "联系人不存在"
        conn.commit()
        return True, "删除成功"
    except Exception as e:
        conn.rollback()
        print(f"删除家属联系人失败: {e}")
        return False, f"删除失败: {str(e)}"
    finally:
        conn.close()


def find_family_contact_by_name(user_id, name):
    """根据称呼模糊查找家属联系人"""
    conn = get_db_connection()
    if not conn:
        return None

    try:
        with conn.cursor() as cursor:
            cursor.execute(
                "SELECT id, name, email FROM family_contacts WHERE user_id = %s AND name LIKE %s",
                (user_id, f'%{name}%')
            )
            return cursor.fetchone()
    except Exception as e:
        print(f"查找家属联系人失败: {e}")
        return None
    finally:
        conn.close()


def get_user_ai_settings(user_id):
    """获取用户的AI模型配置（JSON dict）。如果不存在返回 None。"""
    conn = get_db_connection()
    if not conn:
        return None, "数据库连接失败"

    try:
        with conn.cursor() as cursor:
            cursor.execute(
                "SELECT config FROM user_ai_settings WHERE user_id = %s",
                (user_id,)
            )
            row = cursor.fetchone()
            if not row:
                return None, "未找到AI配置"
            try:
                cfg = json.loads(row['config'])
                return cfg, "成功"
            except json.JSONDecodeError as e:
                return None, f"AI配置解析失败: {e}"
    except Exception as e:
        print(f"获取AI配置失败: {e}")
        return None, f"获取AI配置失败: {str(e)}"
    finally:
        conn.close()


def save_user_ai_settings(user_id, config_dict):
    """写入或更新用户的AI模型配置（upsert）。"""
    conn = get_db_connection()
    if not conn:
        return False, "数据库连接失败"

    try:
        config_json = json.dumps(config_dict, ensure_ascii=False)
        with conn.cursor() as cursor:
            cursor.execute(
                """
                INSERT INTO user_ai_settings (user_id, config)
                VALUES (%s, %s)
                ON DUPLICATE KEY UPDATE config = VALUES(config)
                """,
                (user_id, config_json)
            )
        conn.commit()
        return True, "AI配置保存成功"
    except Exception as e:
        conn.rollback()
        print(f"保存AI配置失败: {e}")
        return False, f"AI配置保存失败: {str(e)}"
    finally:
        conn.close()


def update_password(email, new_password):
    """根据邮箱更新密码"""
    conn = get_db_connection()
    if not conn:
        return False, "数据库连接失败"

    try:
        password_hash = hashlib.sha256(new_password.encode()).hexdigest()
        with conn.cursor() as cursor:
            # 查询用户是否存在
            cursor.execute("SELECT id FROM users WHERE email = %s", (email,))
            user = cursor.fetchone()

            if not user:
                return False, "该邮箱未注册"

            # 更新密码
            cursor.execute(
                "UPDATE users SET password = %s WHERE email = %s",
                (password_hash, email)
            )
            conn.commit()
            return True, "密码重置成功"
    except Exception as e:
        conn.rollback()
        print(f"密码重置失败: {e}")
        return False, f"密码重置失败: {str(e)}"
    finally:
        conn.close()

