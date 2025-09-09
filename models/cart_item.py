from sqlalchemy import Column, BigInteger, Integer, String, ForeignKey
from sqlalchemy.orm import relationship
from datetime import date, timedelta
from utils.database import Base

class CartItem(Base):
    """购物车项目模型"""
    __tablename__ = "cart_items"

    # 主键字段 - 使用BIGINT UNSIGNED
    id = Column(BigInteger, primary_key=True, autoincrement=True, comment='购物车项ID')
    
    # 外键字段 - 关联到用户表
    user_id = Column(BigInteger, ForeignKey('users.id', ondelete='CASCADE', onupdate='CASCADE'), 
                     nullable=False, comment='关联的用户ID')
    
    # 外键字段 - 关联到零件详情表
    part_details_id = Column(BigInteger, ForeignKey('part_details.id', ondelete='CASCADE', onupdate='CASCADE'), 
                            nullable=False, comment='关联的零件详情ID')
    
    # 数量字段
    quantity = Column(Integer, nullable=False, default=1, comment='数量')
    
    # 预计交付日期字段
    expected_delivery_date = Column(String(255), nullable=True, comment='预计交付日期')

    # 关联关系 - 与用户表的关系
    user = relationship("User", back_populates="cart_items", lazy="select")
    
    # 关联关系 - 与零件详情表的关系
    part_details = relationship("PartDetails", back_populates="cart_items", lazy="select")

    def __repr__(self):
        """返回购物车项目对象的字符串表示"""
        return f"<CartItem(id={self.id}, user_id={self.user_id}, part_details_id={self.part_details_id}, quantity={self.quantity})>"

    def to_dict(self):
        """将购物车项目对象转换为字典"""
        return {
            'id': self.id,
            'user_id': self.user_id,
            'part_details_id': self.part_details_id,
            'quantity': self.quantity,
            'expected_delivery_date': self.expected_delivery_date
        }

    def to_dict_with_details(self):
        """将购物车项目对象转换为包含零件详情的字典"""
        return {
            'id': self.id,
            'user_id': self.user_id,
            'part_details_id': self.part_details_id,
            'quantity': self.quantity,
            'expected_delivery_date': self.expected_delivery_date,
            'part_details': self.part_details.to_dict() if self.part_details else None
        }

    def calculate_subtotal(self):
        """计算小计（数量 × 单价）"""
        if self.part_details and self.part_details.unit_price:
            return float(self.part_details.unit_price) * self.quantity
        return 0.0

    def calculate_total(self):
        """计算总计（数量 × 总价）"""
        if self.part_details and self.part_details.total_price:
            return float(self.part_details.total_price) * self.quantity
        return 0.0

    def update_quantity(self, new_quantity: int, db_session):
        """更新数量"""
        if new_quantity <= 0:
            raise ValueError("数量必须大于0")
        self.quantity = new_quantity
        db_session.commit()
        return self

    def set_delivery_date(self, delivery_date: date, db_session):
        """设置预计交付日期"""
        self.expected_delivery_date = delivery_date
        db_session.commit()
        return self

    def is_available(self):
        """检查零件是否可用（基于零件详情状态）"""
        return self.part_details is not None

    def get_delivery_info(self):
        """获取交付信息"""
        return {
            'expected_delivery_date': self.expected_delivery_date,
            'is_urgent': self.expected_delivery_date and self.expected_delivery_date <= date.today() + timedelta(days=7) if self.expected_delivery_date else False
        }

    @classmethod
    def create_cart_item(cls, db_session, user_id: int, part_details_id: int, 
                        quantity: int = 1, expected_delivery_date: date = None):
        """创建购物车项目（使用现有的零件详情）"""
        # 检查是否已存在相同的购物车项目
        existing_item = db_session.query(cls).filter(
            cls.user_id == user_id,
            cls.part_details_id == part_details_id
        ).first()
        
        if existing_item:
            # 如果已存在，增加数量
            existing_item.quantity += quantity
            if expected_delivery_date:
                existing_item.expected_delivery_date = expected_delivery_date
            db_session.commit()
            db_session.refresh(existing_item)
            return existing_item
        else:
            # 创建新的购物车项目
            cart_item = cls(
                user_id=user_id,
                part_details_id=part_details_id,
                quantity=quantity,
                expected_delivery_date=expected_delivery_date
            )
            db_session.add(cart_item)
            db_session.commit()
            db_session.refresh(cart_item)
            return cart_item

    @classmethod
    def create_cart_item_with_new_part_details(cls, db_session, user_id: int, file_id: int,
                                             quantity: int = 1, expected_delivery_date: date = None, **part_kwargs):
        """创建购物车项目并为其创建独立的零件详情"""
        from models.part_details import PartDetails
        
        # 先创建购物车项
        cart_item = cls(
            user_id=user_id,
            part_details_id=None,  # 临时设为None
            quantity=quantity,
            expected_delivery_date=expected_delivery_date
        )
        db_session.add(cart_item)
        db_session.flush()  # 获取cart_item的ID但不提交
        
        # 为购物车项创建独立的零件详情
        part_details = PartDetails.create_for_cart(
            db_session=db_session,
            file_id=file_id,
            cart_item_id=cart_item.id,
            **part_kwargs
        )
        
        # 更新购物车项的part_details_id
        cart_item.part_details_id = part_details.id
        db_session.commit()
        db_session.refresh(cart_item)
        return cart_item

    @classmethod
    def get_user_cart_items(cls, db_session, user_id: int):
        """获取用户的所有购物车项目"""
        return db_session.query(cls).filter(cls.user_id == user_id).all()

    @classmethod
    def get_cart_item_by_id(cls, db_session, cart_item_id: int, user_id: int = None):
        """根据ID获取购物车项目"""
        query = db_session.query(cls).filter(cls.id == cart_item_id)
        if user_id:
            query = query.filter(cls.user_id == user_id)
        return query.first()

    @classmethod
    def get_cart_item_by_part_details(cls, db_session, user_id: int, part_details_id: int):
        """根据零件详情ID获取购物车项目"""
        return db_session.query(cls).filter(
            cls.user_id == user_id,
            cls.part_details_id == part_details_id
        ).first()

    @classmethod
    def clear_user_cart(cls, db_session, user_id: int):
        """清空用户购物车并删除所有关联的零件详情"""
        # 获取用户的所有购物车项目
        cart_items = db_session.query(cls).filter(cls.user_id == user_id).all()
        
        # 收集所有关联的零件详情ID
        part_details_ids = [item.part_details_id for item in cart_items if item.part_details_id]
        
        # 删除购物车项目
        db_session.query(cls).filter(cls.user_id == user_id).delete()
        
        # 删除所有关联的零件详情
        if part_details_ids:
            from models.part_details import PartDetails
            db_session.query(PartDetails).filter(PartDetails.id.in_(part_details_ids)).delete()
            print(f"✅ 清空购物车时删除了 {len(part_details_ids)} 个零件详情")
        
        db_session.commit()

    @classmethod
    def get_cart_summary(cls, db_session, user_id: int):
        """获取购物车摘要信息"""
        cart_items = cls.get_user_cart_items(db_session, user_id)
        
        total_items = len(cart_items)
        total_quantity = sum(item.quantity for item in cart_items)
        total_amount = sum(item.calculate_subtotal() for item in cart_items)
        
        return {
            'total_items': total_items,
            'total_quantity': total_quantity,
            'total_amount': total_amount,
            'items': [item.to_dict_with_details() for item in cart_items]
        }

    @classmethod
    def remove_cart_item(cls, db_session, cart_item_id: int, user_id: int):
        """删除购物车项目并直接删除关联的零件详情"""
        cart_item = cls.get_cart_item_by_id(db_session, cart_item_id, user_id)
        if cart_item:
            # 获取关联的零件详情ID
            part_details_id = cart_item.part_details_id
            
            # 删除购物车项目
            db_session.delete(cart_item)
            
            # 直接删除关联的零件详情（不再检测引用关系）
            if part_details_id:
                from models.part_details import PartDetails
                part_details = db_session.query(PartDetails).filter(PartDetails.id == part_details_id).first()
                if part_details:
                    db_session.delete(part_details)
                    print(f"✅ 零件详情删除成功: ID={part_details_id}")
            
            db_session.commit()
            return True
        return False
