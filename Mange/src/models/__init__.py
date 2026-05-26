"""
数据模型定义模块

主要功能：
- 定义所有数据库表结构（SQLAlchemy ORM模型）
- 提供数据库实例（db）供全局使用

数据表说明：
- users: 用户信息表（用户名、密码、状态等）
- user_plain_passwords: 明文密码表（用于导出用户信息）
- names: 名称记录表
- follows: 关注记录表
- position_settings: 仓位设置表


"""

from flask_sqlalchemy import SQLAlchemy

# 全局数据库实例，在 app.py 中通过 db.init_app(app) 初始化
db = SQLAlchemy()


# ==================== 用户信息表 ====================
class User(db.Model):
    """
    用户信息模型
    
    表名: users
    用途: 存储系统用户的基本信息
    """
    __tablename__ = 'users'
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password = db.Column(db.String(200), nullable=False)  # 存储哈希后的密码
    is_active = db.Column(db.Boolean, default=True, nullable=False)
    created_at = db.Column(db.DateTime, server_default=db.func.now())
    expire_date = db.Column(db.DateTime, nullable=True)

    def __repr__(self):
        return f'<User {self.username}>'


# ==================== 明文密码表 ====================
class UserPlainPassword(db.Model):
    """
    明文密码模型
    
    表名: user_plain_passwords
    用途: 存储用户明文密码（用于导出功能）
    关联: 通过 username 外键关联 users 表
    """
    __tablename__ = 'user_plain_passwords'
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    username = db.Column(db.String(80), db.ForeignKey('users.username'), unique=True, nullable=False)
    mingwen = db.Column(db.String(200), nullable=False)  # 明文密码
    created_at = db.Column(db.DateTime, server_default=db.func.now())

    user = db.relationship('User', backref=db.backref('plain_password', uselist=False))

    def __repr__(self):
        return f'<UserPlainPassword {self.username}>'


# ==================== 名称记录表 ====================
class Name(db.Model):
    """
    名称记录模型
    
    表名: names
    用途: 存储名称记录
    """
    __tablename__ = 'names'
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    name = db.Column(db.String(100), unique=True, nullable=False)
    created_at = db.Column(db.DateTime, server_default=db.func.now())

    def __repr__(self):
        return f'<Name {self.name}>'


# ==================== 关注记录表 ====================
class Follow(db.Model):
    """
    关注记录模型
    
    表名: follows
    用途: 存储关注记录
    """
    __tablename__ = 'follows'
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    name = db.Column(db.String(100), nullable=False)
    created_at = db.Column(db.DateTime, server_default=db.func.now())

    def __repr__(self):
        return f'<Follow {self.name}>'


# ==================== 仓位设置表 ====================
class PositionSetting(db.Model):
    """
    仓位设置模型
    
    表名: position_settings
    用途: 存储仓位百分比设置
    """
    __tablename__ = 'position_settings'
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    percentage = db.Column(db.Integer, nullable=False, default=60)
    created_at = db.Column(db.DateTime, server_default=db.func.now())
    updated_at = db.Column(db.DateTime, server_default=db.func.now(), onupdate=db.func.now())

    def __repr__(self):
        return f'<PositionSetting {self.percentage}%>'
