# -*- coding: utf-8 -*-
import json
from datetime import datetime, date

from sqlalchemy.pool import StaticPool
from sqlalchemy import (
    create_engine, Column, ForeignKey, Integer, String, DateTime, Date, Float
    )
from sqlalchemy.orm import scoped_session, sessionmaker
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy_mixins import AllFeaturesMixin

from config import db_config

class CRUDMixin(object):
    """Mixin that adds convenience methods for CRUD (create, read, update, delete)
    operations.
    """

    @classmethod
    def create(cls, **kwargs):
        """Create a new record and save it the database."""
        instance = cls(**kwargs)
        return instance.save()

    def update(self, commit=True, **kwargs):
        """Update specific fields of a record."""
        for attr, value in kwargs.items():
            setattr(self, attr, value)
        return commit and self.save() or self

    def save(self, commit=True):
        """Save the record."""
        self.session.add(self)
        if commit:
            self.session.commit()
        return self

    def delete(self, commit=True):
        """Remove the record from the database."""
        self.session.delete(self)
        return commit and self.session.commit()


Base = declarative_base()
class BaseModel(Base, CRUDMixin, AllFeaturesMixin):
    __abstract__ = True
    __repr__ = AllFeaturesMixin.__repr__

engine = create_engine(db_config, connect_args={'check_same_thread': False})
session = scoped_session(sessionmaker(engine))
BaseModel.set_session(session)

class RecommendSource(BaseModel):
    '推荐来源'
    __tablename__ = 'recommend_source'
    __repr_attrs__ = ['title', 'source_id']
    id = Column(Integer, primary_key=True, autoincrement=True)
    title = Column(String(32))
    source_id = Column(String(32))


class StockRecommended(BaseModel):
    '推荐'
    __tablename__ = 'stock_recommended'
    id = Column(Integer, primary_key=True, autoincrement=True)
    recommend_source_id = Column(ForeignKey('recommend_source.id'))
    stock = Column(String(32))
    code = Column(String(16))
    recommend_date = Column(Date, default=date.today)


class WinRateDaily(BaseModel):
    '''每日胜率信息'''
    __tablename__ = 'win_rate_daily'
    id = Column(Integer, primary_key=True, autoincrement=True)
    recommend_source_id = Column(ForeignKey('recommend_source.id'))
    recommend_date = Column(Date, default=date.today)

    # 平均涨幅源数据和最大平局涨幅
    s_avg_increase_ = Column(String(1024))
    avg_increase = Column(Float)
    # 最佳持股时间，为平均涨幅列表中最大值的位置
    keep_day = Column(Integer)
    # 胜率源数据和最大胜率
    s_succ_percent_ = Column(String(1024))
    succ_percent = Column(Float)

    def __init__(self, *, s_avg_increase, s_succ_percent, **kw):
        super().__init__(**kw)
        self.s_avg_increase = s_avg_increase
        self.s_succ_percent = s_succ_percent

    @property
    def s_avg_increase(self):
        return json.loads(self.s_avg_increase_)

    @s_avg_increase.setter
    def s_avg_increase(self, s_avg_increase):
        self.s_avg_increase_ = json.dumps(s_avg_increase)
        self.avg_increase = max(s_avg_increase)
        self.keep_day = s_avg_increase.index(self.avg_increase) + 1

    @property
    def s_succ_percent(self):
        return json.loads(self.s_succ_percent_)

    @s_succ_percent.setter
    def s_succ_percent(self, s_succ_percent):
        self.s_succ_percent_ = json.dumps(s_succ_percent)
        self.succ_percent = max(s_succ_percent)
