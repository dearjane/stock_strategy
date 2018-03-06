# -*- coding: utf-8 -*-
import os

db_file = os.path.join(os.path.dirname(__file__), 'data.db')
db_config = 'sqlite:///{}'.format(db_file)
