# -*- coding: utf-8 -*-
import time
import json
import logging
import datetime as dt
from concurrent.futures import ThreadPoolExecutor

import requests
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
