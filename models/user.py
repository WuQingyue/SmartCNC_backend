from sqlalchemy import Column, BigInteger, String, DateTime, Enum, Text
from sqlalchemy.orm import relationship
from datetime import datetime
from utils.database import Base

class User(Base):
    __tablename__ = "users"

    # 主键字段 - 使用BIGINT UNSIGNED
    id = Column(BigInteger, primary_key=True, autoincrement=True, comment='唯一用户ID')
    
    # 邮箱字段 - 唯一约束
    email = Column(String(255), nullable=False, unique=True, comment='用户登录邮箱')
    
    # 密码哈希字段
    password_hash = Column(String(255), nullable=False, comment='哈希加密后的密码')
    
    # 登录类型字段
    login_type = Column(Enum('email', 'google', name='login_type'), 
                       nullable=False, default='email', comment='登录类型')
    
    # 用户角色字段
    role = Column(Enum('user', 'admin', name='user_role'), 
                 nullable=False, default='user', comment='用户角色: user-普通用户, admin-管理员')
    
    # 时间戳字段
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow, 
                       comment='账户创建时间')
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow, 
                       onupdate=datetime.utcnow, comment='账户最后更新时间')

    # 添加关联关系（如果需要的话）
    files = relationship("Files", back_populates="user", cascade="all, delete")
    addresses = relationship("Address", back_populates="user", cascade="all, delete")
    orders = relationship("Order", back_populates="user", cascade="all, delete")

    def __repr__(self):
        """返回用户对象的字符串表示"""
        return f"<User(id={self.id}, email='{self.email}', role='{self.role}')>"

    def to_dict(self):
        """将用户对象转换为字典"""
        return {
            'id': self.id,
            'email': self.email,
            'login_type': self.login_type,
            'role': self.role,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None
        }