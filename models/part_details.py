from sqlalchemy import Column, BigInteger, String, Integer, Boolean, DateTime, ForeignKey, DECIMAL, Enum
from sqlalchemy.orm import relationship
from datetime import datetime
from utils.database import Base

class PartDetails(Base):
    """零件详情模型"""
    __tablename__ = "part_details"

    # 主键字段 - 使用BIGINT UNSIGNED
    id = Column(BigInteger, primary_key=True, autoincrement=True, comment='零件详情ID')
    
    # 外键字段 - 关联到文件表
    file_id = Column(BigInteger, ForeignKey('files.id', ondelete='CASCADE', onupdate='CASCADE'), 
                     nullable=False, comment='关联的上传文件ID')
    
    # 记录类型字段（新增）
    record_type = Column(Enum('order', 'cart', name='record_type_enum'), 
                        nullable=False, comment='记录类型：order-订单相关，cart-购物车相关')
    source_id = Column(BigInteger, nullable=True, comment='来源ID：订单ID或购物车项ID')
    
    # 基础信息字段
    material_access_id = Column(String(255), nullable=True, comment='材质访问ID')
    material = Column(String(100), nullable=True, comment='材质')
    quantity = Column(Integer, nullable=False, default=1, comment='零件数量')
    tolerance = Column(String(50), nullable=True, comment='公差')
    tolerance_access_id = Column(String(255), nullable=True, comment='公差访问ID')
    roughness = Column(String(50), nullable=True, comment='粗糙度')
    roughness_access_id = Column(String(255), nullable=True, comment='粗糙度访问ID')
    has_thread = Column(Boolean, nullable=False, default=False, comment='是否有螺纹 (0:否, 1:是)')
    has_assembly = Column(Boolean, nullable=False, default=False, comment='是否有装配关系 (0:否, 1:是)')
    
    # 尺寸信息字段 - 使用DECIMAL保证精度
    length = Column(DECIMAL(10, 3), nullable=True, comment='长度 (mm)')
    width = Column(DECIMAL(10, 3), nullable=True, comment='宽度 (mm)')
    height = Column(DECIMAL(10, 3), nullable=True, comment='高度 (mm)')
    surface_area = Column(DECIMAL(10, 3), nullable=True, comment='表面积 (mm²)')
    volume = Column(DECIMAL(10, 3), nullable=True, comment='体积 (mm³)')

    # 表面处理一字段
    surface_treatment = Column(String(100), nullable=True, comment='表面处理工艺名称')
    treatment1_option = Column(String(100), nullable=True, comment='表面处理一选项')
    treatment1_color = Column(String(100), nullable=True, comment='表面处理一颜色')
    treatment1_gloss = Column(String(100), nullable=True, comment='表面处理一光泽')
    treatment1_drawing = Column(String(255), nullable=True, comment='表面处理一图纸路径或ID')

    # 表面处理二字段
    treatment2_option = Column(String(100), nullable=True, comment='表面处理二选项')
    treatment2_color = Column(String(100), nullable=True, comment='表面处理二颜色')
    treatment2_gloss = Column(String(100), nullable=True, comment='表面处理二光泽')
    treatment2_drawing = Column(String(255), nullable=True, comment='表面处理二图纸路径或ID')
    
    # 关联的工艺ID字段
    craft_access_id1 = Column(String(255), nullable=True, comment='表面处理一ID')
    craft_attribute_color_access_ids1 = Column(String(255), nullable=True, comment='表面处理一颜色ID')
    craft_attribute_glossiness_access_ids1 = Column(String(255), nullable=True, comment='表面处理一光泽ID')
    craft_attribute_file_access_ids1 = Column(String(255), nullable=True, comment='表面处理一图纸ID')
    craft_access_id2 = Column(String(255), nullable=True, comment='表面处理二ID')
    craft_attribute_color_access_ids2 = Column(String(255), nullable=True, comment='表面处理二颜色ID')
    craft_attribute_glossiness_access_ids2 = Column(String(255), nullable=True, comment='表面处理二光泽ID')
    craft_attribute_file_access_ids2 = Column(String(255), nullable=True, comment='表面处理二图纸ID')
    
    # 成本与价格信息字段 - 使用DECIMAL保证金额精度
    material_cost = Column(DECIMAL(12, 2), nullable=True, comment='材料费')
    engineering_cost = Column(DECIMAL(12, 2), nullable=True, comment='工程费')
    clamping_cost = Column(DECIMAL(12, 2), nullable=True, comment='装夹费')
    processing_cost = Column(DECIMAL(12, 2), nullable=True, comment='加工费')
    expedited_price = Column(DECIMAL(12, 2), nullable=True, comment='加急费')
    surface_cost = Column(DECIMAL(12, 2), nullable=True, comment='表面处理费')
    unit_price = Column(DECIMAL(12, 2), nullable=True, comment='单价')
    total_price = Column(DECIMAL(12, 2), nullable=True, comment='总价')
    total_shipping_fee = Column(DECIMAL(12, 2), nullable=True, comment='总运费')
    tax_fee = Column(DECIMAL(12, 2), nullable=True, comment='税费')
    jlc_radio = Column(String(255), nullable=True, comment='JLC Radio (具体含义根据业务定义)')
    yt_radio = Column(String(255), nullable=True, comment='YT Radio (具体含义根据业务定义)')

    # 关联关系 - 与文件表的关系
    file = relationship("Files", back_populates="part_details", lazy="select")
    
    # 关联关系 - 与订单表的关系（一对多）
    orders = relationship("Order", back_populates="part_details", lazy="dynamic")
    
    # 关联关系 - 与购物车项目表的关系（一对多）
    cart_items = relationship("CartItem", back_populates="part_details", lazy="dynamic")

    def __repr__(self):
        """返回零件详情对象的字符串表示"""
        return f"<PartDetails(id={self.id}, material='{self.material}', quantity={self.quantity})>"

    def to_dict(self):
        """将零件详情对象转换为字典"""
        return {
            'id': self.id,
            'file_id': self.file_id,
            'record_type': self.record_type,
            'source_id': self.source_id,
            'material_access_id': self.material_access_id,
            'material': self.material,
            'quantity': self.quantity,
            'tolerance': self.tolerance,
            'tolerance_access_id': self.tolerance_access_id,
            'roughness': self.roughness,
            'roughness_access_id': self.roughness_access_id,
            'has_thread': self.has_thread,
            'has_assembly': self.has_assembly,
            'length': float(self.length) if self.length else None,
            'width': float(self.width) if self.width else None,
            'height': float(self.height) if self.height else None,
            'surface_area': float(self.surface_area) if self.surface_area else None,
            'volume': float(self.volume) if self.volume else None,
            'surface_treatment': self.surface_treatment,
            'treatment1_option': self.treatment1_option,
            'treatment1_color': self.treatment1_color,
            'treatment1_gloss': self.treatment1_gloss,
            'treatment1_drawing': self.treatment1_drawing,
            'treatment2_option': self.treatment2_option,
            'treatment2_color': self.treatment2_color,
            'treatment2_gloss': self.treatment2_gloss,
            'treatment2_drawing': self.treatment2_drawing,
            'craft_access_id1': self.craft_access_id1,
            'craft_attribute_color_access_ids1': self.craft_attribute_color_access_ids1,
            'craft_attribute_glossiness_access_ids1': self.craft_attribute_glossiness_access_ids1,
            'craft_attribute_file_access_ids1': self.craft_attribute_file_access_ids1,
            'craft_access_id2': self.craft_access_id2,
            'craft_attribute_color_access_ids2': self.craft_attribute_color_access_ids2,
            'craft_attribute_glossiness_access_ids2': self.craft_attribute_glossiness_access_ids2,
            'craft_attribute_file_access_ids2': self.craft_attribute_file_access_ids2,
            'material_cost': float(self.material_cost) if self.material_cost else None,
            'engineering_cost': float(self.engineering_cost) if self.engineering_cost else None,
            'clamping_cost': float(self.clamping_cost) if self.clamping_cost else None,
            'processing_cost': float(self.processing_cost) if self.processing_cost else None,
            'expedited_price': float(self.expedited_price) if self.expedited_price else None,
            'surface_cost': float(self.surface_cost) if self.surface_cost else None,
            'unit_price': float(self.unit_price) if self.unit_price else None,
            'total_price': float(self.total_price) if self.total_price else None,
            'total_shipping_fee': float(self.total_shipping_fee) if self.total_shipping_fee else None,
            'tax_fee': float(self.tax_fee) if self.tax_fee else None,
            'jlc_radio': self.jlc_radio,
            'yt_radio': self.yt_radio
        }

    def calculate_total_price(self):
        """计算总价"""
        costs = [
            self.material_cost or 0,
            self.engineering_cost or 0,
            self.clamping_cost or 0,
            self.processing_cost or 0,
            self.expedited_price or 0,
            self.surface_cost or 0
        ]
        return sum(costs) * self.quantity

    def update_pricing(self, db_session):
        """更新价格信息"""
        self.total_price = self.calculate_total_price()
        if self.quantity > 0:
            self.unit_price = self.total_price / self.quantity
        db_session.commit()
        return self

    def get_dimensions(self):
        """获取尺寸信息"""
        return {
            'length': float(self.length) if self.length else None,
            'width': float(self.width) if self.width else None,
            'height': float(self.height) if self.height else None,
            'surface_area': float(self.surface_area) if self.surface_area else None,
            'volume': float(self.volume) if self.volume else None
        }

    def get_treatment_info(self):
        """获取表面处理信息"""
        return {
            'surface_treatment': self.surface_treatment,
            'treatment1': {
                'option': self.treatment1_option,
                'color': self.treatment1_color,
                'gloss': self.treatment1_gloss,
                'drawing': self.treatment1_drawing,
                'craft_access_id': self.craft_access_id1,
                'color_access_ids': self.craft_attribute_color_access_ids1,
                'glossiness_access_ids': self.craft_attribute_glossiness_access_ids1,
                'file_access_ids': self.craft_attribute_file_access_ids1
            },
            'treatment2': {
                'option': self.treatment2_option,
                'color': self.treatment2_color,
                'gloss': self.treatment2_gloss,
                'drawing': self.treatment2_drawing,
                'craft_access_id': self.craft_access_id2,
                'color_access_ids': self.craft_attribute_color_access_ids2,
                'glossiness_access_ids': self.craft_attribute_glossiness_access_ids2,
                'file_access_ids': self.craft_attribute_file_access_ids2
            }
        }

    def get_cost_breakdown(self):
        """获取成本明细"""
        return {
            'material_cost': float(self.material_cost) if self.material_cost else 0,
            'engineering_cost': float(self.engineering_cost) if self.engineering_cost else 0,
            'clamping_cost': float(self.clamping_cost) if self.clamping_cost else 0,
            'processing_cost': float(self.processing_cost) if self.processing_cost else 0,
            'expedited_price': float(self.expedited_price) if self.expedited_price else 0,
            'surface_cost': float(self.surface_cost) if self.surface_cost else 0,
            'unit_price': float(self.unit_price) if self.unit_price else 0,
            'total_price': float(self.total_price) if self.total_price else 0,
            'total_shipping_fee': float(self.total_shipping_fee) if self.total_shipping_fee else 0,
            'tax_fee': float(self.tax_fee) if self.tax_fee else 0,
            'quantity': self.quantity
        }

    @classmethod
    def create_part_details(cls, db_session, file_id: int, record_type: str, source_id: int = None, **kwargs):
        """创建零件详情"""
        part_details = cls(
            file_id=file_id,
            record_type=record_type,
            source_id=source_id,
            material_access_id=kwargs.get('material_access_id'),
            material=kwargs.get('material'),
            quantity=kwargs.get('quantity', 1),
            tolerance=kwargs.get('tolerance'),
            tolerance_access_id=kwargs.get('tolerance_access_id'),
            roughness=kwargs.get('roughness'),
            roughness_access_id=kwargs.get('roughness_access_id'),
            has_thread=kwargs.get('has_thread', False),
            has_assembly=kwargs.get('has_assembly', False),
            length=kwargs.get('length'),
            width=kwargs.get('width'),
            height=kwargs.get('height'),
            surface_area=kwargs.get('surface_area'),
            volume=kwargs.get('volume'),
            surface_treatment=kwargs.get('surface_treatment'),
            treatment1_option=kwargs.get('treatment1_option'),
            treatment1_color=kwargs.get('treatment1_color'),
            treatment1_gloss=kwargs.get('treatment1_gloss'),
            treatment1_drawing=kwargs.get('treatment1_drawing'),
            treatment2_option=kwargs.get('treatment2_option'),
            treatment2_color=kwargs.get('treatment2_color'),
            treatment2_gloss=kwargs.get('treatment2_gloss'),
            treatment2_drawing=kwargs.get('treatment2_drawing'),
            craft_access_id1=kwargs.get('craft_access_id1'),
            craft_attribute_color_access_ids1=kwargs.get('craft_attribute_color_access_ids1'),
            craft_attribute_glossiness_access_ids1=kwargs.get('craft_attribute_glossiness_access_ids1'),
            craft_attribute_file_access_ids1=kwargs.get('craft_attribute_file_access_ids1'),
            craft_access_id2=kwargs.get('craft_access_id2'),
            craft_attribute_color_access_ids2=kwargs.get('craft_attribute_color_access_ids2'),
            craft_attribute_glossiness_access_ids2=kwargs.get('craft_attribute_glossiness_access_ids2'),
            craft_attribute_file_access_ids2=kwargs.get('craft_attribute_file_access_ids2'),
            material_cost=kwargs.get('material_cost'),
            engineering_cost=kwargs.get('engineering_cost'),
            clamping_cost=kwargs.get('clamping_cost'),
            processing_cost=kwargs.get('processing_cost'),
            expedited_price=kwargs.get('expedited_price'),
            surface_cost=kwargs.get('surface_cost'),
            unit_price=kwargs.get('unit_price'),
            total_price=kwargs.get('total_price'),
            total_shipping_fee=kwargs.get('total_shipping_fee'),
            tax_fee=kwargs.get('tax_fee'),
            jlc_radio=kwargs.get('jlc_radio'),
            yt_radio=kwargs.get('yt_radio')
        )
        db_session.add(part_details)
        db_session.commit()
        db_session.refresh(part_details)
        return part_details

    @classmethod
    def get_part_details_by_file(cls, db_session, file_id: int):
        """根据文件ID获取零件详情"""
        return db_session.query(cls).filter(cls.file_id == file_id).first()

    @classmethod
    def get_part_details_by_material(cls, db_session, material: str, limit: int = 20, offset: int = 0):
        """根据材质获取零件详情列表"""
        return db_session.query(cls).filter(
            cls.material == material
        ).offset(offset).limit(limit).all()

    @classmethod
    def get_part_details_by_price_range(cls, db_session, min_price: float, max_price: float, 
                                       limit: int = 20, offset: int = 0):
        """根据价格范围获取零件详情列表"""
        return db_session.query(cls).filter(
            cls.total_price >= min_price,
            cls.total_price <= max_price
        ).offset(offset).limit(limit).all()

    @classmethod
    def create_for_order(cls, db_session, file_id: int, order_id: int, **kwargs):
        """为订单创建独立的零件详情"""
        return cls.create_part_details(
            db_session=db_session,
            file_id=file_id,
            record_type='order',
            source_id=order_id,
            **kwargs
        )

    @classmethod
    def create_for_cart(cls, db_session, file_id: int, cart_item_id: int, **kwargs):
        """为购物车项创建独立的零件详情"""
        return cls.create_part_details(
            db_session=db_session,
            file_id=file_id,
            record_type='cart',
            source_id=cart_item_id,
            **kwargs
        )

    @classmethod
    def get_by_record_type(cls, db_session, record_type: str, source_id: int = None):
        """根据记录类型和来源ID获取零件详情"""
        query = db_session.query(cls).filter(cls.record_type == record_type)
        if source_id:
            query = query.filter(cls.source_id == source_id)
        return query.all()

    @classmethod
    def copy_part_details(cls, db_session, source_part_details, record_type: str, source_id: int):
        """复制零件详情到新的记录类型"""
        # 获取源零件详情的所有属性
        kwargs = {}
        for column in source_part_details.__table__.columns:
            if column.name not in ['id', 'record_type', 'source_id']:
                kwargs[column.name] = getattr(source_part_details, column.name)
        
        return cls.create_part_details(
            db_session=db_session,
            file_id=source_part_details.file_id,
            record_type=record_type,
            source_id=source_id,
            **kwargs
        )
