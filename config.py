"""
ETF预测系统配置
"""
import os

# 项目路径
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# 数据库配置
DATABASE_PATH = os.path.join(BASE_DIR, 'data', 'etf.db')
WATCHLIST_PATH = os.path.join(BASE_DIR, 'data', 'watchlist_etfs.json')
WEIGHTS_PATH = os.path.join(BASE_DIR, 'optimized_weights')

# API配置
API_HOST = '0.0.0.0'
API_PORT = 8001  # 使用8001端口避免与原系统冲突
API_TITLE = 'ETF预测系统API'
API_VERSION = '1.0.0'

# Tushare配置（可选，用于数据更新）
TUSHARE_TOKEN = '5c778b0f7d4a69893ae98c6d3b6ef5637875125daee6205b435e9d20e9b4'

# Minishare配置（用于实时行情数据）
MINISHARE_TOKEN = os.getenv('MINISHARE_TOKEN', '6xH3v19jLi9AZ4N2m7Qsn98hur2Mle9ock6RT9Dnt7Ys3GAPMf00H0gl3d5355fd')

# ETF列表（52个ETF）
ETF_LIST = [
    {'code': '510330.SH', 'name': '沪深300ETF', 'sector': '宽基'},
    {'code': '159672.SZ', 'name': '创业板ETF', 'sector': '宽基'},
    {'code': '159647.SZ', 'name': '中药ETF', 'sector': '中药'},
    {'code': '159928.SZ', 'name': '消费ETF', 'sector': '主要消费'},
    {'code': '513050.SH', 'name': '中概互联网ETF易方达', 'sector': '互联网'},
    {'code': '516910.SH', 'name': '物流ETF', 'sector': '交通运输'},
    {'code': '515980.SH', 'name': '人工智能ETF', 'sector': '人工智能'},
    {'code': '515220.SH', 'name': '煤炭ETF', 'sector': '传统能源'},
    {'code': '516560.SH', 'name': '养老ETF', 'sector': '健康'},
    {'code': '515790.SH', 'name': '光伏ETF', 'sector': '光伏'},
    {'code': '159611.SZ', 'name': '电力ETF', 'sector': '公用事业'},
    {'code': '512660.SH', 'name': '军工ETF', 'sector': '军工'},
    {'code': '159825.SZ', 'name': '农业ETF', 'sector': '农业'},
    {'code': '159870.SZ', 'name': '化工ETF', 'sector': '化工'},
    {'code': '512170.SH', 'name': '医疗ETF', 'sector': '医疗'},
    {'code': '159929.SZ', 'name': '医药ETF', 'sector': '医药'},
    {'code': '512760.SH', 'name': '芯片ETF', 'sector': '半导体'},
    {'code': '159936.SZ', 'name': '可选消费ETF', 'sector': '可选消费'},
    {'code': '510170.SH', 'name': '大宗商品ETF', 'sector': '商品'},
    {'code': '159959.SZ', 'name': '央企ETF', 'sector': '国企'},
    {'code': '510050.SH', 'name': '上证50ETF', 'sector': '宽基'},
    {'code': '562910.SH', 'name': '高端制造ETF易方达', 'sector': '工业其他'},
    {'code': '159745.SZ', 'name': '建材ETF', 'sector': '建材'},
    {'code': '516950.SH', 'name': '基建ETF银华', 'sector': '建筑'},
    {'code': '512770.SH', 'name': '战略新兴ETF', 'sector': '成长'},
    {'code': '512200.SH', 'name': '房地产ETF', 'sector': '房地产'},
    {'code': '515700.SH', 'name': '新能车ETF', 'sector': '新能源'},
    {'code': '513520.SH', 'name': '日经ETF', 'sector': '日股'},
    {'code': '518880.SH', 'name': '黄金ETF', 'sector': '有色金属'},
    {'code': '159886.SZ', 'name': '机械ETF', 'sector': '机械'},
    {'code': '159944.SZ', 'name': '材料ETF', 'sector': '材料其他'},
    {'code': '515030.SH', 'name': '新能源车ETF', 'sector': '汽车'},
    {'code': '512980.SH', 'name': '传媒ETF', 'sector': '消费服务'},
    {'code': '513660.SH', 'name': '恒生ETF', 'sector': '港股'},
    {'code': '512580.SH', 'name': '环保ETF', 'sector': '环保'},
    {'code': '562860.SH', 'name': '疫苗ETF嘉实', 'sector': '生物'},
    {'code': '159625.SZ', 'name': '绿色电力ETF嘉实', 'sector': '电力'},
    {'code': '159997.SZ', 'name': '电子ETF', 'sector': '电子'},
    {'code': '515000.SH', 'name': '科技ETF', 'sector': '科技其他'},
    {'code': '515080.SH', 'name': '中证红利ETF', 'sector': '红利'},
    {'code': '159941.SZ', 'name': '纳指ETF', 'sector': '美股'},
    {'code': '159930.SZ', 'name': '能源ETF', 'sector': '能源其他'},
    {'code': '159378.SZ', 'name': '通用航空ETF', 'sector': '航空航天'},
    {'code': '512720.SH', 'name': '计算机ETF', 'sector': '计算机'},
    {'code': '512880.SH', 'name': '证券ETF', 'sector': '证券'},
    {'code': '512750.SH', 'name': '基本面50ETF嘉实', 'sector': '质量'},
    {'code': '515880.SH', 'name': '通信ETF', 'sector': '通信'},
    {'code': '159985.SZ', 'name': '豆粕ETF', 'sector': '金融其他'},
    {'code': '515210.SH', 'name': '钢铁ETF', 'sector': '钢铁'},
    {'code': '512800.SH', 'name': '银行ETF', 'sector': '银行'},
    {'code': '515170.SH', 'name': '食品饮料ETF', 'sector': '食品饮料'},
    {'code': '516800.SH', 'name': '智能制造ETF', 'sector': '高端装备'},
]

# 策略配置
STRATEGIES = {
    'macd_aggressive': 'MACD激进策略',
    'optimized_t_trading': '优化做T策略',
    'multifactor': '多因子量化策略'
}

# 回测默认参数
DEFAULT_INITIAL_CAPITAL = 2000
DEFAULT_POSITIONS = 10
DEFAULT_START_DATE = '20240101'

# 支持的交易所
EXCHANGES = ['SH', 'SZ']
