from sqlalchemy import Column, BigInteger, String, Integer, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from datetime import datetime
from utils.database import Base

class Files(Base):
    __tablename__ = "files"

    # 主键字段 - 使用BIGINT UNSIGNED
    id = Column(BigInteger, primary_key=True, autoincrement=True, comment='唯一文件ID')
    
    # 外键字段 - 关联到用户表
    user_id = Column(BigInteger, ForeignKey('users.id', ondelete='CASCADE', onupdate='CASCADE'), 
                     nullable=False, comment='上传该文件的用户ID')
    
    # 文件名字段
    file_name = Column(String(255), nullable=False, comment='上传时的原始文件名')
    
    # 文件路径字段
    file_path = Column(String(255), nullable=False, comment='文件在服务器或云存储上的相对路径')
    
    # 文件大小字段
    file_size = Column(Integer, nullable=True, comment='文件大小 (单位: KB)')
    
    # 文件访问编号字段
    file_info_accessId = Column(String(255), nullable=False, comment='文件访问编号')

    # 产品模型访问编号字段
    product_model_accessId = Column(String(255), nullable=True, comment='产品模型访问编号')
    
    # 文件预览URL字段
    file_url = Column(String(255), nullable=False, comment='文件预览URL')
    
    # 时间戳字段
    uploaded_at = Column(DateTime, nullable=False, default=datetime.utcnow, 
                        comment='上传时间')

    # 添加关联关系
    user = relationship("User", back_populates="files")

    def __repr__(self):
        """返回文件对象的字符串表示"""
        return f"<File(id={self.id}, file_name='{self.file_name}', user_id={self.user_id})>"

    def to_dict(self):
        """将文件对象转换为字典"""
        return {
            'id': self.id,
            'user_id': self.user_id,
            'file_name': self.file_name,
            'file_path': self.file_path,
            'file_size': self.file_size,
            'file_info_accessId': self.file_info_accessId,
            'product_model_accessId': self.product_model_accessId,
            'file_url': self.file_url,
            'uploaded_at': self.uploaded_at.isoformat() if self.uploaded_at else None
        }
