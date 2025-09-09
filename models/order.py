from sqlalchemy import Column, BigInteger, String, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from datetime import datetime
from utils.database import Base

class Order(Base):
    """订单模型"""
    __tablename__ = "orders"

    # 主键字段 - 使用BIGINT UNSIGNED
    id = Column(BigInteger, primary_key=True, autoincrement=True, comment='订单ID')
    
    # 外键字段 - 关联到用户表
    user_id = Column(BigInteger, ForeignKey('users.id', ondelete='CASCADE', onupdate='CASCADE'), 
                     nullable=False, comment='关联的用户ID')
    
    # 订单编号字段
    order_number = Column(String(50), nullable=False, unique=True, comment='订单信息访问编号')
    order_code = Column(String(50), nullable=True, comment='订单编号')
    
    # 关联的ID字段
    part_details_id = Column(BigInteger, ForeignKey('part_details.id', ondelete='RESTRICT', onupdate='CASCADE'), 
                            nullable=False, comment='关联的零件详情ID')
    logistics_info_id = Column(BigInteger, nullable=True, comment='物流进度ID')
    
    # 状态字段
    status = Column(String(50), nullable=False, comment='审核与订单状态')
    
    # 时间戳字段
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow, 
                       comment='订单创建时间')
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow, 
                       onupdate=datetime.utcnow, comment='订单最后更新时间')

    # 关联关系 - 与用户表的关系
    user = relationship("User", back_populates="orders", lazy="select")
    
    # 关联关系 - 与零件详情表的关系
    part_details = relationship("PartDetails", back_populates="orders", lazy="select")

    def __repr__(self):
        """返回订单对象的字符串表示"""
        return f"<Order(id={self.id}, order_number='{self.order_number}', status='{self.status}')>"

    def to_dict(self):
        """将订单对象转换为字典"""
        return {
            'id': self.id,
            'user_id': self.user_id,
            'order_number': self.order_number,
            'order_code': self.order_code,
            'part_details_id': self.part_details_id,
            'logistics_info_id': self.logistics_info_id,
            'status': self.status,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None
        }

    def update_status(self, new_status: str, db_session):
        """更新订单状态"""
        self.status = new_status
        self.updated_at = datetime.utcnow()
        db_session.commit()
        return self

    @classmethod
    def get_orders_by_user(cls, db_session, user_id: int, limit: int = 20, offset: int = 0):
        """获取用户的订单列表"""
        return db_session.query(cls).filter(
            cls.user_id == user_id
        ).order_by(cls.created_at.desc()).offset(offset).limit(limit).all()

    @classmethod
    def get_order_by_number(cls, db_session, order_number: str):
        """根据订单编号获取订单"""
        return db_session.query(cls).filter(
            cls.order_number == order_number
        ).first()

    @classmethod
    def get_orders_by_status(cls, db_session, status: str, limit: int = 20, offset: int = 0):
        """根据状态获取订单列表"""
        return db_session.query(cls).filter(
            cls.status == status
        ).order_by(cls.created_at.desc()).offset(offset).limit(limit).all()

    @classmethod
    def create_order(cls, db_session, user_id: int, order_number: str, 
                    part_details_id: int, status: str = "待审核", 
                    order_code: str = None, logistics_info_id: int = None):
        """创建新订单（使用现有的零件详情）"""
        order = cls(
            user_id=user_id,
            order_number=order_number,
            order_code=order_code,
            part_details_id=part_details_id,
            logistics_info_id=logistics_info_id,
            status=status
        )
        db_session.add(order)
        db_session.commit()
        db_session.refresh(order)
        return order

    @classmethod
    def create_order_with_new_part_details(cls, db_session, user_id: int, order_number: str,
                                         file_id: int, status: str = "待审核", 
                                         order_code: str = None, logistics_info_id: int = None, **part_kwargs):
        """创建订单并为其创建独立的零件详情"""
        from models.part_details import PartDetails
        
        # 先创建订单
        order = cls(
            user_id=user_id,
            order_number=order_number,
            order_code=order_code,
            part_details_id=None,  # 临时设为None
            logistics_info_id=logistics_info_id,
            status=status
        )
        db_session.add(order)
        db_session.flush()  # 获取order的ID但不提交
        
        # 为订单创建独立的零件详情
        part_details = PartDetails.create_for_order(
            db_session=db_session,
            file_id=file_id,
            order_id=order.id,
            **part_kwargs
        )
        
        # 更新订单的part_details_id
        order.part_details_id = part_details.id
        db_session.commit()
        db_session.refresh(order)
        return order

    @classmethod
    def create_order_from_cart_item(cls, db_session, user_id: int, order_number: str,
                                   cart_item_id: int, status: str = "待审核",
                                   order_code: str = None, logistics_info_id: int = None):
        """从购物车项创建订单（复制零件详情）"""
        from models.part_details import PartDetails
        from models.cart_item import CartItem
        
        # 获取购物车项
        cart_item = CartItem.get_cart_item_by_id(db_session, cart_item_id, user_id)
        if not cart_item:
            raise ValueError("购物车项不存在")
        
        # 先创建订单
        order = cls(
            user_id=user_id,
            order_number=order_number,
            order_code=order_code,
            part_details_id=None,  # 临时设为None
            logistics_info_id=logistics_info_id,
            status=status
        )
        db_session.add(order)
        db_session.flush()  # 获取order的ID但不提交
        
        # 复制购物车项的零件详情到订单
        part_details = PartDetails.copy_part_details(
            db_session=db_session,
            source_part_details=cart_item.part_details,
            record_type='order',
            source_id=order.id
        )
        
        # 更新订单的part_details_id
        order.part_details_id = part_details.id
        db_session.commit()
        db_session.refresh(order)
        return order

    def is_editable(self):
        """检查订单是否可编辑（根据状态判断）"""
        editable_statuses = ["待审核", "草稿", "待修改"]
        return self.status in editable_statuses

    def can_be_cancelled(self):
        """检查订单是否可以取消"""
        cancellable_statuses = ["待审核", "待支付", "草稿"]
        return self.status in cancellable_statuses
