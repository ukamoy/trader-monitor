# encoding: UTF-8
'''
vnpy.api.okex的gateway接入
Contributor：ipqhjjybj 大佳
'''
from __future__ import print_function

import time
import os
import json
from datetime import datetime
from time import sleep
from copy import copy, deepcopy
from threading import Condition
from queue import Queue, Empty
from threading import Thread
from time import sleep
from vnpy.trader.vtEngine import MainEngine
from vnpy.api.okex import OkexSpotApi, OkexFuturesApi, OKEX_SPOT_HOST, OKEX_FUTURES_HOST

from vnpy.trader.vtGateway import *
from vnpy.trader.vtFunction import getJsonPath


# 价格类型映射
# 买卖类型： 限价单（buy/sell） 市价单（buy_market/sell_market）
priceTypeMap = {}
priceTypeMap['buy'] = (DIRECTION_LONG, PRICETYPE_LIMITPRICE)
priceTypeMap['buy_market'] = (DIRECTION_LONG, PRICETYPE_MARKETPRICE)
priceTypeMap['sell'] = (DIRECTION_SHORT, PRICETYPE_LIMITPRICE)
priceTypeMap['sell_market'] = (DIRECTION_SHORT, PRICETYPE_MARKETPRICE)  ###原版现货下单映射
priceTypeMapReverse = {v: k for k, v in priceTypeMap.items()} 

futureOrderTypeMap = {}
futureOrderTypeMap['1'] = (DIRECTION_LONG,OFFSET_OPEN)               ##买开
futureOrderTypeMap['2'] = (DIRECTION_SHORT,OFFSET_OPEN)             ##卖开
futureOrderTypeMap['3'] = (DIRECTION_SHORT,OFFSET_CLOSE)              #卖平  
futureOrderTypeMap['4'] = (DIRECTION_LONG,OFFSET_CLOSE)               #买平

futureOrderTypeMapReverse = {v: k for k, v in futureOrderTypeMap.items()} 

# 委托状态印射
statusMap = {}
statusMap[-1] = STATUS_CANCELLED
statusMap[0] = STATUS_NOTTRADED
statusMap[1] = STATUS_PARTTRADED
statusMap[2] = STATUS_ALLTRADED
statusMap[4] = STATUS_CANCELINPROGRESS
statusMap[5] = STATUS_CANCELLING

# Restful 下单返回错误映射
orderErrorMap = {}
orderErrorMap['20001'] = u"用户不存在"
orderErrorMap['20002'] = u"用户被冻结"
orderErrorMap['20003'] = u"用户被爆仓冻结"
orderErrorMap['20004'] = u"合约账户被冻结"
orderErrorMap['20005'] = u"用户合约账户不存在"
orderErrorMap['20006'] = u"必填参数为空"
orderErrorMap['20007'] = u"参数错误"
orderErrorMap['20008'] = u"合约账户余额为空"
orderErrorMap['20009'] = u"虚拟合约状态错误"
orderErrorMap['20010'] = u"合约风险率信息不存在"
orderErrorMap['20011'] = u"10倍/20倍杠杆开BTC前保证金率低于90%/80%，10倍/20倍杠杆开LTC前保证金率低于80%/60%"
orderErrorMap['20012'] = u"10倍/20倍杠杆开BTC后保证金率低于90%/80%，10倍/20倍杠杆开LTC后保证金率低于80%/60%"
orderErrorMap['20013'] = u"暂无对手价"
orderErrorMap['20014'] = u"系统错误"
orderErrorMap['20015'] = u"订单信息不存在"
orderErrorMap['20016'] = u"平仓数量是否大于同方向可用持仓数量"
orderErrorMap['20017'] = u"非本人操作"
orderErrorMap['20018'] = u"下单价格高于前一分钟的103%或低于97%"
orderErrorMap['20019'] = u"该IP限制不能请求该资源"
orderErrorMap['20020'] = u"密钥不存在"
orderErrorMap['20021'] = u"指数信息不存在"
orderErrorMap['20022'] = u"接口调用错误（全仓模式调用全仓接口，逐仓模式调用逐仓接口）"
orderErrorMap['20023'] = u"逐仓用户"
orderErrorMap['20024'] = u"sign签名不匹配"
orderErrorMap['20025'] = u"杠杆比率错误"
orderErrorMap['20026'] = u"API鉴权错误"
orderErrorMap['20027'] = u"无交易记录"
orderErrorMap['20028'] = u"合约不存在"
orderErrorMap['20029'] = u"转出金额大于可转金额"
orderErrorMap['20030'] = u"账户存在借款"
orderErrorMap['20038'] = u"根据相关法律，您所在的国家或地区不能使用该功能。"
orderErrorMap['20049'] = u"用户请求接口过于频繁"
orderErrorMap['20061'] = u"合约相同方向只支持一个杠杆，若有10倍多单，就不能再下20倍多单"
orderErrorMap['21020'] = u"合约交割中，无法下单"
orderErrorMap['21021'] = u"合约清算中，无法下单"
orderErrorMap['HTTP错误码403'] = u"用户请求过快，IP被屏蔽"
orderErrorMap['Ping不通'] = u"用户请求过快，IP被屏蔽"

KlinePeriodMap = {}
KlinePeriodMap['1min'] = '1min'
KlinePeriodMap['5min'] = '5min'
KlinePeriodMap['15min'] = '15min'
KlinePeriodMap['30min'] = '30min'
KlinePeriodMap['60min'] = '1hour'
KlinePeriodMap['1day'] = 'day'
KlinePeriodMap['1week'] = 'week'
KlinePeriodMap['4hour'] = '4hour'


okex_all_symbol_pairs = ['ref_usdt', 'soc_usdt', 'light_usdt', 'avt_usdt', 
'of_usdt', 'brd_usdt', 'ast_usdt', 'int_usdt', 'zrx_usdt', 'ctr_usdt', 'dgd_usdt', 
'aidoc_usdt', 'wtc_usdt', 'swftc_usdt', 'wrc_usdt', 'sub_usdt', 'dna_usdt', 'knc_usdt', 
'kcash_usdt', 'mdt_usdt', 'theta_usdt', 'ppt_usdt', 'utk_usdt', 'qvt_usdt', 'salt_usdt', 
'la_usdt', 'itc_usdt', 'fair_usdt', 'yee_usdt', '1st_usdt', 'fun_usdt', 'iost_usdt', 'mkr_usdt', 
'tio_usdt', 'req_usdt', 'ubtc_usdt', 'icx_usdt', 'tct_usdt', 'san_usdt', 'lrc_usdt', 'icn_usdt', 
'cvc_usdt', 'eth_usdt', 'poe_usdt', 'xlm_usdt', 'iota_usdt', 'eos_usdt', 'nuls_usdt', 'mot_usdt', 
'neo_usdt', 'gnx_usdt', 'dgb_usdt', 'evx_usdt', 'ltc_usdt', 'mda_usdt', 'etc_usdt', 'dpy_usdt', 
'tnb_usdt', 'nas_usdt', 'btc_usdt', 'smt_usdt', 'ssc_usdt', 'oax_usdt', 'yoyo_usdt', 'snc_usdt', 
'sngls_usdt', 'bch_usdt', 'mana_usdt', 'mof_usdt', 'mco_usdt', 'vib_usdt', 'topc_usdt', 'pra_usdt', 
'bnt_usdt', 'xmr_usdt', 'edo_usdt', 'snt_usdt', 'eng_usdt', 'stc_usdt', 'qtum_usdt', 'key_usdt', 
'ins_usdt', 'rnt_usdt', 'bcd_usdt', 'amm_usdt', 'lend_usdt', 'btm_usdt', 'elf_usdt', 'xuc_usdt', 
'cag_usdt', 'snm_usdt', 'act_usdt', 'dash_usdt', 'zec_usdt', 'storj_usdt', 'pay_usdt', 'vee_usdt', 
'show_usdt', 'trx_usdt', 'atl_usdt', 'ark_usdt', 'ost_usdt', 'gnt_usdt', 'dat_usdt', 'rcn_usdt', 
'qun_usdt', 'mth_usdt', 'rct_usdt', 'read_usdt', 'gas_usdt', 'btg_usdt', 'mtl_usdt', 'cmt_usdt', 
'xrp_usdt', 'spf_usdt', 'aac_usdt', 'can_usdt', 'omg_usdt', 'hsr_usdt', 'link_usdt', 'dnt_usdt', 
'true_usdt', 'ukg_usdt', 'xem_usdt', 'ngc_usdt', 'lev_usdt', 'rdn_usdt', 'ace_usdt', 'ipc_usdt', 
'ugc_usdt', 'viu_usdt', 'mag_usdt', 'hot_usdt', 'pst_usdt','ref_btc', 'soc_btc', 'light_btc', 
'avt_btc', 'of_btc', 'brd_btc', 'ast_btc', 'int_btc', 'zrx_btc', 'ctr_btc', 'dgd_btc', 'aidoc_btc', 
'wtc_btc', 'swftc_btc', 'wrc_btc', 'sub_btc', 'dna_btc', 'knc_btc', 'kcash_btc', 'mdt_btc', 
'theta_btc', 'ppt_btc', 'utk_btc', 'qvt_btc', 'salt_btc', 'la_btc', 'itc_btc', 'fair_btc', 
'yee_btc', '1st_btc', 'fun_btc', 'iost_btc', 'mkr_btc', 'tio_btc', 'req_btc', 'ubtc_btc', 
'icx_btc', 'tct_btc', 'san_btc', 'lrc_btc', 'icn_btc', 'cvc_btc', 'eth_btc', 'poe_btc', 'xlm_btc', 
'iota_btc', 'eos_btc', 'nuls_btc', 'mot_btc', 'neo_btc', 'gnx_btc', 'dgb_btc', 'evx_btc', 
'ltc_btc', 'mda_btc', 'etc_btc', 'dpy_btc', 'tnb_btc', 'nas_btc', 'btc_btc', 'smt_btc', 'ssc_btc', 
'oax_btc', 'yoyo_btc', 'snc_btc', 'sngls_btc', 'bch_btc', 'mana_btc', 'mof_btc', 'mco_btc', 
'vib_btc', 'topc_btc', 'pra_btc', 'bnt_btc', 'xmr_btc', 'edo_btc', 'snt_btc', 'eng_btc', 'stc_btc', 
'qtum_btc', 'key_btc', 'ins_btc', 'rnt_btc', 'bcd_btc', 'amm_btc', 'lend_btc', 'btm_btc', 
'elf_btc', 'xuc_btc', 'cag_btc', 'snm_btc', 'act_btc', 'dash_btc', 'zec_btc', 'storj_btc', 
'pay_btc', 'vee_btc', 'show_btc', 'trx_btc', 'atl_btc', 'ark_btc', 'ost_btc', 'gnt_btc', 
'dat_btc', 'rcn_btc', 'qun_btc', 'mth_btc', 'rct_btc', 'read_btc', 'gas_btc', 'btg_btc', 
'mtl_btc', 'cmt_btc', 'xrp_btc', 'spf_btc', 'aac_btc', 'can_btc', 'omg_btc', 'hsr_btc', 
'link_btc', 'dnt_btc', 'true_btc', 'ukg_btc', 'xem_btc', 'ngc_btc', 'lev_btc', 'rdn_btc', 
'ace_btc', 'ipc_btc', 'ugc_btc', 'viu_btc', 'mag_btc', 'hot_btc', 'pst_btc']


########################################################################
class OkexGateway(VtGateway):
    """OKEX交易接口"""
    
    #----------------------------------------------------------------------
    def __init__(self, eventEngine, gatewayName='OKEX'):
        """Constructor"""
        super(OkexGateway, self).__init__(eventEngine, gatewayName)
        
        self.spotApi = SpotApi(self)     
        self.futuresApi = FuturesApi(self)
        
        self.leverage = 0
        self.connected = False
        self.fileName = self.gatewayName + '_connect.json'
        self.filePath = getJsonPath(self.fileName, __file__)     

    #----------------------------------------------------------------------
    def connect(self):
        """连接"""
        # 载入json文件
        try:
            f = open(self.filePath)
        except IOError:
            log = VtLogData()
            log.gatewayName = self.gatewayName
            log.logContent = u'读取连接配置出错，请检查'
            self.onLog(log)
            return
        
        # 解析json文件
        setting = json.load(f)
        try:
            apiKey = str(setting['apiKey'])
            secretKey = str(setting['secretKey'])
            trace = setting['trace']
            symbols = setting['symbols']
            contracts = setting['contracts']

        except KeyError:
            log = VtLogData()
            log.gatewayName = self.gatewayName
            log.logContent = u'连接配置缺少字段，请检查'
            self.onLog(log)
            return            
        
        # 初始化接口
        self.futuresApi.init(apiKey, secretKey, trace, contracts)
        # self.spotApi.init(apiKey, secretKey, trace, symbols)


    #----------------------------------------------------------------------
    def subscribe(self, subscribeReq):
        """订阅行情"""
        pass
        
    #----------------------------------------------------------------------
    def sendOrder(self, orderReq):
        """发单"""
        pass
    #----------------------------------------------------------------------
    def cancelOrder(self, cancelOrderReq):
        """撤单"""
        pass
    #----------------------------------------------------------------------
    def qryAccount(self):
        """查询账户资金"""
        pass

    #----------------------------------------------------------------------
    def qryPosition(self):
        """查询持仓"""
        # self.futuresApi.futuresUserInfo()
        pass
    #------------------------------------------------
    def qryAllOrders(self, vtSymbol, order_id, status= None):
        pass

    def batchCancelOrder(cancelOrderReqList):
        pass

    def loadHistoryBar(self, vtSymbol, type_, size= None, since = None):
        """策略初始化时下载历史数据"""
        pass

    #------------------------------------------------
    def initPosition(self,vtSymbol):
        """策略初始化时查询策略的持仓"""
        symbol= vtSymbol.split(':')[0]
        contractType = symbol[4:]
        if 'quarter' in contractType or 'week' in contractType:
            symbol = vtSymbol[:3]
            self.futuresApi.rest_futures_position(symbol,contractType)
        else:
            symbol = symbol
            self.spotApi.rest_spot_posotion(symbol)
    #----------------------------------------------------------------------
    def close(self):
        """关闭"""
        self.futuresApi.close()
        self.spotApi.close()
        
    #----------------------------------------------------------------------
    def initQuery(self):
        """初始化连续查询"""
        if self.qryEnabled:
            # 需要循环的查询函数列表
            self.qryFunctionList = [self.qryPosition]
            
            self.qryCount = 0           # 查询触发倒计时
            self.qryTrigger = 2         # 查询触发点
            self.qryNextFunction = 0    # 上次运行的查询函数索引
            
            self.startQuery()  
    
    #----------------------------------------------------------------------
    def query(self, event):
        """注册到事件处理引擎上的查询函数"""
        self.qryCount += 1
        
        if self.qryCount > self.qryTrigger:
            # 清空倒计时
            self.qryCount = 0
            
            # 执行查询函数
            function = self.qryFunctionList[self.qryNextFunction]
            function()
            
            # 计算下次查询函数的索引，如果超过了列表长度，则重新设为0
            self.qryNextFunction += 1
            if self.qryNextFunction == len(self.qryFunctionList):
                self.qryNextFunction = 0
                
    #----------------------------------------------------------------------
    def startQuery(self):
        """启动连续查询"""
        self.eventEngine.register(EVENT_TIMER, self.query)
    
    #----------------------------------------------------------------------
    def setQryEnabled(self, qryEnabled):
        """设置是否要启动循环查询"""
        self.qryEnabled = qryEnabled

    def writeLog(self, content):
        """快速记录日志"""
        log = VtLogData()
        log.gatewayName = self.gatewayName
        log.logContent = content
        self.onLog(log)

class FuturesApi(OkexFuturesApi):
    """OKEX的期货API实现"""
    def __init__(self, gateway):
        """Constructor"""
        super(FuturesApi, self).__init__()
        self.gateway = gateway                  # gateway对象
        self.gatewayName = gateway.gatewayName  # gateway对象名称

        self.cbDict = {}
        self.tickDict = {}
        self.orderDict = {}
        self.channelSymbolMap = {}
        self.channelcontractTypeMap = {}
        
        self.localNo = 0                # 本地委托号
        self.localNoQueue = Queue()     # 未收到系统委托号的本地委托号队列
        self.localNoDict = {}           # key为本地委托号，value为系统委托号
        self.localOrderDict = {}        # key为本地委托号, value为委托对象
        self.orderIdDict = {}           # key为系统委托号，value为本地委托号
        self.cancelDict = {}            # key为本地委托号，value为撤单请求
        self.strategyDict = {}

        self.contractidDict = {}        # 用于持仓信息中, 对应rest查询的合约和ws查询的合约，获取品种信息
        self.filledList =[]
        self.tradetick = 0
        self.accountdata = None
        self.prebalanceDict = {}

        self.recordOrderId_BefVolume = {}       # 记录的之前处理的量

        self.cache_some_order = {}
        self.minute_temp = 0
        self.tradeID = 0
        self.symbolSizeDict = {}        # 保存合约代码和合约大小的印射关系
    #----------------------------------------------------------------------
    def onMessage(self, data):
        """信息推送""" 
        channel = data.get('channel', '')
        if not channel:
            return

        if channel in self.cbDict:
            callback = self.cbDict[channel]
            callback(data)

    #----------------------------------------------------------------------
    def onError(self, data):
        """错误推送"""
        error = VtErrorData()
        error.gatewayName = self.gatewayName
        error.errorMsg = str(data)
        self.gateway.onError(error)
        
    #----------------------------------------------------------------------
    def onClose(self):
        """接口断开"""
        self.gateway.connected = False
        self.writeLog(u'期货服务器连接断开')
    
    #----------------------------------------------------------------------
    def onOpen(self):       
        """连接成功"""
        self.gateway.connected = True
        
        self.login()
        self.writeLog(u'期货服务器连接成功')
        
        # 推送合约数据
        for symbol in self.contracts:
            contract = VtContractData()
            contract.gatewayName = self.gatewayName

            contract.symbol = symbol
            contract.exchange = EXCHANGE_OKEX
            contract.contractType = symbol[4:]
            contract.vtSymbol = ':'.join([contract.symbol, contract.gatewayName])
            contract.name = symbol
            contract.size = 0.00001
            contract.priceTick = 0.00001
            contract.productClass = PRODUCT_FUTURES
            self.gateway.onContract(contract)
    #----------------------------------------------------------------------
    def initCallback(self):
        """初始化回调函数"""
        for symbol in self.contracts:
            # channel和symbol映射
            contractType = symbol[4:]
            symbol = symbol[:3]
            self.channelSymbolMap["ok_sub_futureusd_%s_ticker_%s" %(symbol,contractType)] = symbol
            # self.channelSymbolMap["ok_sub_futureusd_%s_kline_this_week_week" %(symbol)] = symbol  ## WS并不会给历史K线，提供的是实时数据
            # self.channelSymbolMap["ok_sub_futureusd_%s_depth_%s_10" %(symbol,contractType)] = symbol
            # self.channelSymbolMap["ok_sub_futureusd_%s_trade_%s" %(symbol, contractType)] = symbol

            self.channelcontractTypeMap["ok_sub_futureusd_%s_ticker_%s" %(symbol,contractType)] = contractType
            # self.channelcontractTypeMap["ok_sub_futureusd_%s_depth_%s_10" %(symbol,contractType)] = contractType
            # self.channelcontractTypeMap["ok_sub_futureusd_%s_trade_%s" %(symbol, contractType)] = contractType

            # channel和callback映射
            self.cbDict["ok_sub_futureusd_%s_ticker_%s" % (symbol,contractType)] = self.onTicker
            # self.cbDict["ok_sub_futureusd_%s_depth_%s_10" % (symbol,contractType)] = self.onDepth
            # # self.cbDict["ok_sub_futureusd_%s_order" % symbol] = self.onSubFuturesOrder
            # self.cbDict["ok_sub_futureusd_%s_trade_%s" %(symbol, contractType)] = self.onSubFuturesTrades
            
        self.cbDict["ok_sub_futureusd_userinfo"] = self.onSubFuturesBalance
        self.cbDict['ok_futureusd_userinfo'] = self.onFuturesUserInfo
        self.cbDict['ok_futureusd_orderinfo'] = self.onFuturesOrderInfo
        # self.cbDict['ok_futureusd_trade'] = self.onSubFuturesOrderError 
        # self.cbDict['ok_sub_futureusd_trades'] = self.onFuturesOrderInfo
        # self.cbDict['ok_futureusd_order'] = self.onFuturesOrder
        # self.cbDict['ok_futureusd_cancel_order'] = self.onFuturesCancelOrder
        self.cbDict['ok_sub_futureusd_positions'] = self.onSubFuturesPosition
        # self.cbDict['ok_sub_futureusd_userinfo'] = self.subscribeFuturesUserInfo
        self.cbDict['login'] = self.onLogin
     #----------------------------------------------------------------------
    def onLogin(self, data):
        """"""
        # 查询持仓
        self.futuresUserInfo()
        # self.subscribeFuturesPositions()   # 没用，Websocket初始查询不给持仓信息

        # 订阅推送
        for symbol in self.contracts:
            contractType = symbol[4:]
            symbol = symbol[:3]
            self.subscribe(symbol,contractType)
            
            symbol = symbol[:3]+'_usd'
            self.rest_futures_position(symbol,contractType)  # 初始化后使用restful查询持仓信息
        self.contactOrders()
        self.writeLog(u'期货服务器登录成功')
    #----------------------------------------------------------------------
    def onTicker(self, data):
        """
        {'high': '724.306', 'limitLow': '693.093', 'vol': '852082', 'last': '714.333', 
        'low': '677.024', 'buy': '714.448', 'hold_amount': '599090', 'sell': '715.374', 
        'contractId': 201807060050052, 'unitAmount': '10', 'limitHigh': '735.946'}
        """
        channel = data['channel']
        # print('gw on tick',datetime.now(),data['data']['last'])
        symbol = self.channelSymbolMap[channel]
        contractType = self.channelcontractTypeMap[channel]
        symbol = symbol+'_'+contractType                         # 从回报获取品种名称
        d = data['data']
        self.contractidDict[str(d['contractId'])] =symbol

    #---------------------------------------------------
    def onFuturesUserInfo(self, data):
        """期货账户资金推送"""  
        #{'binary': 0, 'channel': 'ok_futureusd_userinfo', 'data': {'result': True, 

        # 'info': {'btc': {'balance': 0.00524741, 'rights': 0.00524741, 
        # 'contracts': [{'contract_type': 'this_week', 'freeze': 0, 'balance': 5.259e-05, 'contract_id':201807060000013, 
        # 'available': 0.00524741, 'profit': -5.259e-05, 'bond': 0, 'unprofit': 0}, 
        # {'contract_type': 'next_week', 'freeze': 0, 'balance': 0, 'contract_id': 201807130000034, 'available': 0.00524741, 
        # 'profit': 0, 'bond': 0, 'unprofit': 0}]}, 

        # 'eos': {'balance': 0, 'rights': 0, 'contracts': []}, 
        # 'ltc': {'balance': 0, 'rights': 0, 'contracts': []}}}}


        #    {'binary': 0, 'channel': 'ok_futureusd_userinfo', 'data': {'result': True, 
        #    'info': {'btc': {'risk_rate': 10000, 'account_rights': 0.00080068, 'profit_unreal': 0, 'profit_real': 0, 'keep_deposit': 0}, 
        #    'btg': {'risk_rate': 10000, 'account_rights': 0, 'profit_unreal': 0, 'profit_real': 0, 'keep_deposit': 0}, 
        #    'etc': {'risk_rate': 10000, 'account_rights': 0, 'profit_unreal': 0, 'profit_real': 0, 'keep_deposit': 0}, 
        #    'bch': {'risk_rate': 10000, 'account_rights': 0.07406406, 'profit_unreal': 0, 'profit_real': 0.00017953, 'keep_deposit': 0}, 
        #    'xrp': {'risk_rate': 10000, 'account_rights': 0, 'profit_unreal': 0, 'profit_real': 0, 'keep_deposit': 0}, 
        #    'eth': {'risk_rate': 10000, 'account_rights': 0, 'profit_unreal': 0, 'profit_real': 0, 'keep_deposit': 0}, 
        #    'eos': {'risk_rate': 10000, 'account_rights': 0, 'profit_unreal': 0, 'profit_real': 0, 'keep_deposit': 0}, 
        #    'ltc': {'risk_rate': 10000, 'account_rights': 0, 'profit_unreal': 0, 'profit_real': 0, 'keep_deposit': 0}}}}

        if self.checkDataError(data):
            return
        # print(data,"持仓的币种")
        contracts = data['data']['info']
        flag = 0
        # 帐户信息
        for symbol in contracts.keys():
            fund = contracts[symbol]

            if 'account_rights' in fund.keys():
                balance= float(fund['account_rights'])
                if balance:                   ##过滤掉没有持仓的币种
                    account = VtAccountData()
                    account.gatewayName = self.gatewayName
                    account.accountID = symbol + '_usd'
                    account.vtAccountID = ':'.join([account.gatewayName, account.accountID])
                    account.risk_rate = fund['risk_rate']
                    account.balance = balance
                    account.closeProfit = float(fund['profit_real'])
                    account.positionProfit = fund['profit_unreal']
                    account.margin =  fund['keep_deposit']
                    if not account.preBalance:
                        account.preBalance = account.balance
                    self.gateway.onAccount(account)    
                    flag = 1
                
            elif 'balance' in fund.keys():
                balance= float(fund['balance'])
                if balance:                     ##过滤掉没有持仓的币种
                    account = VtAccountData()
                    account.gatewayName = self.gatewayName
                    account.accountID = symbol + '_usd'
                    account.vtAccountID = ':'.join([account.gatewayName, account.accountID])
                    account.available = fund['rights']
                    account.balance = balance
                    self.gateway.onAccount(account)    
                self.writeLog(u'期货账户信息查询成功, 该账户是逐仓模式')
        if flag:
            self.writeLog(u'期货账户信息查询成功, 该账户是全仓模式')
    #----------------------------------------------------------------------
    def onFuturesOrderInfo(self, data):
        # print(data)
        """委托信息查询回调
        {'lever_rate': 10.0, 'amount': 1.0, 'orderid': 1018500247351296, 'contract_id': 201807060050052, 
        'fee': 0.0, 'contract_name': 'BCH0706', 'unit_amount': 10.0, 'price_avg': 0.0, 'type': 1, 
        'deal_amount': 0.0, 'contract_type': 'this_week', 'user_id': ********, 'system_type': 0, 
        'price': 654.977, 'create_date_str': '2018-06-29 20:58:00', 'create_date': 1530277080437, 'status': 0}
        """
        if self.checkDataError(data):
            return
        rawData = data['data']
        name = rawData['contract_name'][:3]
        contract_type = rawData['contract_type']
        symbol = str.lower(name) + '_' + contract_type

        order = VtOrderData()
        order.symbol = symbol
        order.gatewayName = self.gatewayName
        order.vtSymbol = ':'.join([order.symbol, order.gatewayName])
        order.exchange = EXCHANGE_OKEX
        order.price = rawData['price']
        order.price_avg = rawData['price_avg']
        order.direction, order.offset = futureOrderTypeMap[str(rawData['type'])]
        order.totalVolume = rawData['amount']    
        order.user_id = rawData['user_id']
        order.gatewayName = self.gatewayName
        order.createDate  = datetime.fromtimestamp(float(rawData['create_date'])/1e3)
        
        order.deliverTime = datetime.now()
        order.status = statusMap[rawData['status']] 
        order.fee = rawData['fee']
        order.tradedVolume = float(rawData['deal_amount'])
        self.gateway.onOrder(copy(order))

    #----------------------------------------------------------------------
    def onSubFuturesBalance(self, data):
        """
        {'binary': 0, 'channel': 'ok_sub_futureusd_userinfo', 
        'data': {'symbol': 'eth_usd', 'balance': 0.03080528, 'unit_amount': 10.0, 
        'profit_real': 0.00077335, 'keep_deposit': 0.002298829}}
        """
        if self.checkDataError(data):
            return
        rawData = data['data']

        # 帐户信息更新
        account = VtAccountData()
        account.gatewayName = self.gatewayName
        account.accountID = rawData['symbol']
        account.vtAccountID = ':'.join([account.gatewayName, account.accountID])
        account.balance = float(rawData['balance'])
        account.closeProfit = float(rawData['profit_real'])
        account.margin = float(rawData['keep_deposit'])

        today = datetime.today().strftime('%Y%m%d')
        if not self.prebalanceDict:
            account.preBalance = account.balance
            self.prebalanceDict[today] = account.preBalance
            account.dailyPnL = 0
            return

        if today in self.prebalanceDict.keys():
            account.preBalance = self.prebalanceDict[today]
            account.dailyPnL = account.balance / account.preBalance - 1

        else:
            account.preBalance = self.accountdata.balance    # 从缓存获取前一个balance
            del self.prebalanceDict
            self.prebalanceDict = {}
            self.prebalanceDict[today] = account.preBalance
            account.dailyPnL = account.balance / account.preBalance - 1

        self.accountdata = account
        self.gateway.onAccount(account)  
        # self.writeLog(u'期货账户信息更新成功')
    
    #--------------------------------------------------------------------
    def onSubFuturesPosition(self,data):
        # print(data)
        """
        {'binary': 0, 'channel': 'ok_sub_futureusd_positions', 
        'data': {'symbol': 'bch_usd', 'user_id': ***********, 
        'positions': [{'bondfreez': 0.0, 'margin': 0.0, 'avgprice': 660.97060244,'eveningup': 0.0, 
        'contract_id': 201807130050065, 'hold_amount': 0.0, 'contract_name': 'BCH0713','realized': -0.00316062, 
        'position': 1, 'costprice': 660.97060244, 'position_id': 1017505776168960}
        , {'bondfreez': 0.0, 'margin': 0.0, 'avgprice': 659.89775978, 'eveningup': 2.0, 'contract_id': 2018
        07130050065, 'hold_amount': 2.0, 'contract_name': 'BCH0713', 'realized': -0.00316062, 'position': 2
        , 'costprice': 659.89775978, 'position_id': 1017505776168960}]}}        
        """
        if self.checkDataError(data):
            return
        # if not self.contract_id:   #判断REST的持仓信息是否已经推送
        #     return
            
        symbol = data['data']['symbol']
        position = data['data']['positions']
        sid = str(position[0]['contract_id'])
        
        if sid in self.contractidDict.keys():
            symbol = self.contractidDict[sid]
        else:
            self.writeLog('can\'t identify trading symbol, msg discharged,contract_id = %s'%sid)
            return
        pos = VtPositionData()
        pos.gatewayName = self.gatewayName
        pos.symbol = symbol
        pos.vtSymbol = ':'.join([pos.symbol, pos.gatewayName])
        pos.exchange = EXCHANGE_OKEX

        pos.vtPositionName = pos.vtSymbol
        pos.Longposition = position[0]['hold_amount']
        pos.Shortposition = position[1]['hold_amount']
        pos.LongpositionProfit = position[0]['realized']
        pos.ShortpositionProfit = position[1]['realized']
        pos.Longprice =  position[0]['avgprice']
        pos.Shortprice =  position[1]['avgprice']
        pos.Longfrozen = pos.Longposition - position[0]['eveningup']
        pos.Shortfrozen = pos.Shortposition - position[1]['eveningup']
        if pos.Longposition or pos.Shortposition:
            self.gateway.onPosition(pos)
    #----------------------------------------------------------------------
    def init(self, apiKey, secretKey, trace, contracts):
        """初始化接口"""

        self.contracts = contracts
        self.initCallback()
        self.connect(OKEX_FUTURES_HOST, apiKey, secretKey, trace)
        if not apiKey:
            self.writeLog(u'请添加apiKey和对应的密钥')
            return
        self.writeLog(u'期货接口初始化成功')
    #----------------------------------------
    def generateDateTime(self, s):
        """生成时间"""
        dt = datetime.fromtimestamp(float(s)/1e3)
        time = dt.strftime("%H:%M:%S.%f")
        date = dt.strftime("%Y%m%d")
        return date, time
    #----------------------------------------------------------------------
    def writeLog(self, content):
        """快速记录日志"""
        log = VtLogData()
        log.gatewayName = self.gatewayName
        log.logContent = content
        self.gateway.onLog(log)
    #----------------------------------------------------------------------
    def checkDataError(self, data):
        """检查回报是否存在错误"""
        rawData = data['data']
        if 'error_code' not in rawData:
            return False
        else:
            error = VtErrorData()
            error.gatewayName = self.gatewayName
            error.errorID = rawData['error_code']
            error.errorMsg = u'请求失败，功能：%s' %data['channel']
            self.writeLog("from_error_msg:%s"%data)
            self.gateway.onError(error)
            return True

    #----------------------------------------------------------------------
    def subscribe(self, symbol,contractType):
        """订阅行情"""
        self.subsribeFuturesTicker(symbol,contractType)
        # self.subscribeFuturesKline(symbol,"this_week","30min")  # 订阅推送K线数据
        self.subscribeFuturesDepth(symbol,contractType)
        self.subscribeFuturesTrades(symbol,contractType)
        # self.subscribeFuturesUserInfo()
    #------------------------------------------------------
    #Restful 配置

    def rest_futures_position(self, symbol,contractType):
        try:
            data = self.future_position(symbol,contractType)
        except:
            return ''
        """
        {'result': True, 
        'holding': [
            {'buy_price_avg': 653.83300536, 'symbol': 'bch_usd', 'lever_rate': 10, 'buy_available': 0, 
            'contract_id': 201807060050052, 'buy_amount': 0, 'buy_profit_real': -0.0011777, 
            'contract_type': 'this_week', 'sell_amount': 0, 'sell_price_cost': 655.176, 
            'buy_price_cost': 653.83300536, 'create_date': 1529979371000,'sell_price_avg': 655.176, 
            'sell_profit_real': -0.0011777, 'sell_available': 0}], 'force_liqu_price': '0.000'}
        """
        # print("restonFuturesPosition",data)
        if data['result']:
            if not data['holding']:
                return
            position = data['holding'][0]
            pos = VtPositionData()
            pos.gatewayName = self.gatewayName
            pos.exchange = EXCHANGE_OKEX
            symbol = position['symbol'][:3]
            contract_type = position['contract_type']
            pos.symbol = symbol + '_' + contract_type
            pos.vtSymbol = ':'.join([pos.symbol, pos.gatewayName])
            self.contractidDict[str(position['contract_id'])] =pos.symbol
            pos.vtPositionName = pos.vtSymbol
            pos.Longposition = position['buy_amount']
            pos.Shortposition = position['sell_amount']
            pos.LongpositionProfit = position['buy_profit_real']
            pos.ShortpositionProfit = position['sell_profit_real']
            pos.Longprice =  position['buy_price_avg']
            pos.Shortprice =  position['sell_price_avg']
            pos.Longfrozen = pos.Longposition - position['buy_available']
            pos.Shortfrozen = pos.Shortposition - position['sell_available']
            if pos.Longposition or pos.Shortposition:
                self.gateway.onPosition(pos)
        else:
            # {'result': False, 'error_code': 20022, 'interface': '/api/v1/future_position_4fix'}
            return data['error_code']