# -*- coding: utf-8 -*-
import time
import json
import logging
import datetime as dt
from functools import lru_cache
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor

import tushare
import requests
from pandas import DataFrame
from dateutil.parser import parse as dt_parse

from models import RecommendSource, StockRecommended, WinRateDaily

logger = logging.getLogger(__name__)

def now_timestamp():
    return int(time.time() * 1000)


def intellistock_crawler_task():
    '''策略精选爬虫'''
    r_sources = RecommendSource.all()
    with ThreadPoolExecutor(len(r_sources)) as executor:
        for r_source in r_sources:
            crawler = RecommendSourceCrawler(r_source)
            def task():
                try:
                    crawler.run()
                except:
                    logger.warning(r_source, exc_info=True)
            executor.submit(task)


@lru_cache()
def calculate_profit(code, buy_date, keep_days=1):
    '''计算收益百分比，购买日期第二天开盘价减去当天开盘价
    :param code: 代码
    :param buy_date: 购买日期, 格式为%Y-%m-%d
    :param keep_days: 持股天数
    '''
    data = tushare.get_k_data(code, start=buy_date)
    # 尝试获取卖出日期的股票信息,如果没有对应信息则无法计算收益,返回None
    try:
        data.iloc[keep_days]
    except IndexError:
        return None
    last_open_price = data.iloc[keep_days]['open']
    first_open_price = data.iloc[0]['open']
    return (last_open_price - first_open_price)/first_open_price


class RecommendSourceCrawler():
    '''策略精选爬虫类'''

    def __init__(self, r_source_model):
        self.r_source_model = r_source_model

    @staticmethod
    def get_recommend_source_info(source_id):
        INTELLISTOCK_API_PAT = 'https://sec.wedengta.com/getIntelliStock?action=IntelliDetailV2&id={source_id}&_={t}'
        intellistock_api = INTELLISTOCK_API_PAT.format(source_id=source_id, t=now_timestamp())
        text = requests.get(intellistock_api).text
        data = json.loads(text)
        content = json.loads(data['content'])
        return content['stIntelliPickStockV2']

    @staticmethod
    def get_recommend_history(source_id):
        INTELLISTOCK_API_PAT = 'https://sec.wedengta.com/getIntelliStock?action=IntelliSecPool&id={source_id}&_={t}'
        intellistock_api = INTELLISTOCK_API_PAT.format(source_id=source_id, t=now_timestamp())
        text = requests.get(intellistock_api).text
        data = json.loads(text)
        content = json.loads(data['content'])
        return content['vtDaySec']

    def simulate_history_profit(self, keep_days=1, service_charge=0):
        '''获取股票灯塔策略推荐历史，并模拟买卖计算收益
        :param keep_days: 持股天数
        :param service_charge: 手续费率(主要为佣金), 百分比
        '''
        content = self.get_recommend_history(self.r_source_model.source_id)
        # key为对应的列名，value为对应列的值列表
        history_map = defaultdict(list)
        for item in content:
            for stock in item['vtSec']:
                code = stock['sDtCode'][4:]
                recommend_day = item['sOptime']
                history_map['code'].append(code)
                history_map['name'].append(stock['sChnName'])
                history_map['date'].append(recommend_day)
                history_map['profit'].append(calculate_profit(code, recommend_day, keep_days))
                history_map['hs300_profit'].append(calculate_profit('hs300', recommend_day, keep_days))
                history_map['keep_days'] = keep_days
                history_map['service_charge'] = service_charge
        return DataFrame(history_map)

    def run(self):
        logger.info(self.r_source_model)
        content = self.get_recommend_source_info(self.r_source_model.source_id)
        r_date = dt_parse(content['sDate']).date()
        win_rate_exist = WinRateDaily.query.filter_by(
            recommend_date=r_date, recommend_source_id=self.r_source_model.source_id
            ).first()
        # 如果不是当天数据或者数据已经抓取，则结束
        if r_date != dt.date.today() or win_rate_exist:
            return
        WinRateDaily.create(
            s_avg_increase=content['vtAvgIncrease'],
            s_succ_percent=content['vtSuccPercent'],
            recommend_source_id=self.r_source_model.id,
            recommend_date=r_date,
            )
        for stock in content['vtIntelliStock']:
            StockRecommended.create(
                recommend_source_id=self.r_source_model.id,
                recommend_date=r_date,
                stock=stock['sSecName'],
                code=stock['sDtSecCode'][4:],
                )

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO,
                        format='%(asctime)s %(name)s:%(funcName)s-%(lineno)d:%(levelname)s:%(message)s')
    intellistock_crawler_task()
