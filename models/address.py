from sqlalchemy import Column, BigInteger, String, Boolean, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from datetime import datetime
from utils.database import Base

class Address(Base):
    """用户收货地址模型"""
    __tablename__ = "addresses"

    # 主键字段 - 使用BIGINT UNSIGNED
    id = Column(BigInteger, primary_key=True, autoincrement=True, comment='唯一地址ID')
    
    # 外键字段 - 关联到用户表
    user_id = Column(BigInteger, ForeignKey('users.id', ondelete='CASCADE', onupdate='CASCADE'), 
                     nullable=False, comment='关联的用户ID')
    
    # 收件人信息字段
    contact_name = Column(String(100), nullable=False, comment='收件人姓名')
    contact_phone = Column(String(20), nullable=False, comment='收件人联系电话')
    
    # 地址详细信息字段
    address_detail = Column(String(255), nullable=False, comment='详细收货地址 (包括省、市、区、街道、门牌号)')
    shipping_method = Column(String(255), nullable=False, comment='运输方式')
    country_code = Column(String(255), nullable=False, comment='国家')
    province = Column(String(255), nullable=False, comment='省')
    city = Column(String(255), nullable=False, comment='城市')
    post_name = Column(String(255), nullable=False, comment='物流名称')
    postal_code = Column(String(255), nullable=False, comment='邮编')
    
    # 默认地址标识字段
    is_default = Column(Boolean, nullable=False, default=False, comment='是否为该用户的默认地址')
    
    # 时间戳字段
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow, 
                       comment='地址创建时间')
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow, 
                       onupdate=datetime.utcnow, comment='地址最后更新时间')

    # 关联关系 - 与用户表的关系
    user = relationship("User", back_populates="addresses")

    def __repr__(self):
        """返回地址对象的字符串表示"""
        return f"<Address(id={self.id}, user_id={self.user_id}, contact_name='{self.contact_name}')>"

    def to_dict(self):
        """将地址对象转换为字典"""
        return {
            'id': self.id,
            'user_id': self.user_id,
            'contact_name': self.contact_name,
            'contact_phone': self.contact_phone,
            'address_detail': self.address_detail,
            'shipping_method': self.shipping_method,
            'country_code': self.country_code,
            'province': self.province,
            'city': self.city,
            'post_name': self.post_name,
            'postal_code': self.postal_code,
            'is_default': self.is_default,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None
        }

    def update_default_status(self, db_session):
        """更新默认地址状态 - 确保每个用户只有一个默认地址"""
        if self.is_default:
            # 将同一用户的其他地址设置为非默认
            other_addresses = db_session.query(Address).filter(
                Address.user_id == self.user_id,
                Address.id != self.id
            ).all()
            
            for addr in other_addresses:
                addr.is_default = False
            
            db_session.commit()