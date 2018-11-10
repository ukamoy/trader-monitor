# encoding: UTF-8
'''
vnpy.api.okex的gateway接入
Contributor：ipqhjjybj 大佳
'''
from __future__ import print_function

import time
import os
import json
import csv
import random
 
from datetime import datetime,timedelta
from time import sleep
from copy import copy, deepcopy
from threading import Condition
from queue import Queue, Empty
from threading import Thread
from time import sleep
from vnpy.trader.vtEngine import MainEngine
from vnpy.api.okex import OkexFuturesApi, OKEX_FUTURES_HOST

from vnpy.trader.vtGateway import *
from vnpy.trader.vtFunction import getJsonPath

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
boringMap = [
    "好快！这就一分钟了","每分钟会怼账户状态",
    "每分钟我来更新一下",
    "底下不能有未成交",
    "未成交 ？ 不存在的",
    "让我们期待 2019",
    "更新好了,你快去快回",
    "是不是喜欢绿色了？",
    "为田总打 Call",
    "你干嘛盯着我看",
    "我就说这么几句话",
    "不一定显示全部订单",
    "看看持仓，成交会变",
    "呱呱 呱呱 呱呱",
    "瞧这满屏的绿色",
    "未成交>60秒有邮件",
    "亏超3%我会通知你",
    "定时看OKEX客户端",
    "先停策略再处理异常",
    "疑似单边要看待成交",
    "这个版本没有BUG",
    "每分钟更新 ↘ ↘ ↘",
    "有问题 找宗盛 ^_^",
    "发单间隔太久要看下",
    "你比上一分钟还帅",
    "EOS 年底 100 块"
]


########################################################################
class OkexGateway(VtGateway):
    """OKEX交易接口"""
    
    #----------------------------------------------------------------------
    def __init__(self, eventEngine, gatewayName='OKEX'):
        """Constructor"""
        super(OkexGateway, self).__init__(eventEngine, gatewayName)
        
        self.futuresApi = FuturesApi(self)
        self.flag = 0
        
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
            liquidation = setting['liquidation']

        except KeyError:
            log = VtLogData()
            log.gatewayName = self.gatewayName
            log.logContent = u'连接配置缺少字段，请检查'
            self.onLog(log)
            return            
        
        # 初始化接口
        self.futuresApi.init(apiKey, secretKey, trace, contracts,liquidation)

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

    def batchCancelOrder(self,cancelOrderReqList):
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
            #self.spotApi.rest_spot_posotion(symbol)
    #----------------------------------------------------------------------
    def close(self):
        """关闭"""
        self.futuresApi.close()
        
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
        self.subscribeList = []
        self.arbPair = {}

        self.contractidDict = {}        # 用于持仓信息中, 对应rest查询的合约和ws查询的合约，获取品种信息
        self.prebalanceDict = {}
        self.filledList =[]
        self.preTrade = None
        self.accountdata = None
        self.liquidation = 0
        self.recordPrevConnection = None

        self.recordOrderId_BefVolume = {}       # 记录的之前处理的量

        self.cache_some_order = {}
        self.minute_temp = 0
        self.tradeID = 0
        self.symbolDict = {}        # 保存合约代码和合约大小的印射关系
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
        
        temp = self.recordPrevConnection
        self.recordPrevConnection = datetime.now()
        if temp:
            if (self.recordPrevConnection-temp).seconds < 60:
                self.gateway.sendErrorMsg('%s, reconnect within 1 min'%self.gatewayName)
                sleep(10)
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
            # self.cbDict["ok_sub_futureusd_%s_order" % symbol] = self.onSubFuturesOrder
            # self.cbDict["ok_sub_futureusd_%s_trade_%s" %(symbol, contractType)] = self.onSubFuturesTrades
            
        self.cbDict["ok_sub_futureusd_userinfo"] = self.onSubFuturesBalance
        self.cbDict['ok_futureusd_userinfo'] = self.onFuturesUserInfo
        #self.cbDict['ok_futureusd_orderinfo'] = self.onFuturesOrderInfo
        # self.cbDict['ok_futureusd_trade'] = self.onSubFuturesOrderError 
        #self.cbDict['ok_sub_futureusd_trades'] = self.onFuturesOrderInfo
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
            self.subscribeList.append(symbol)
            contractType = symbol[4:]
            symbol = symbol[:3]
            self.subscribe(symbol,contractType)
            
            symbol = symbol[:3]+'_usd'
            self.rest_futures_position(symbol,contractType)  # 初始化后使用restful查询持仓信息
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

        now = datetime.now()

        if now.minute != self.minute_temp:
            self.minuteCheck()
            self.minute_temp = now.minute

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
        accountinfo = []
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
                    account.liq = self.liquidation
                    
                    check = self.loadPreBalance()

                    if not check:
                        account.preBalance = account.balance
                        self.preTrade = datetime.now().strftime('%Y%m%d %X')
                    else:
                        account.preBalance = check[account.accountID]
                    account.dailyPnL = account.balance / account.preBalance - 1
                    if account.margin:
                        self.preTrade = datetime.now().strftime('%Y%m%d %X')
                    
                    account.lastTrade = self.preTrade

                    accountinfo.append([account.accountID,account.balance,account.preBalance])
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
        self.saveAccountinfo(accountinfo)
        if flag:
            self.writeLog(u'期货账户信息查询成功, 该账户是全仓模式')
    #----------------------------------------------------------------------
    def pushOrder(self, rawData, symbol):
        """委托信息查询回调
        {'lever_rate': 10.0, 'amount': 1.0, 'orderid': 1018500247351296, 'contract_id': 201807060050052, 
        'fee': 0.0, 'contract_name': 'BCH0706', 'unit_amount': 10.0, 'price_avg': 0.0, 'type': 1, 
        'deal_amount': 0.0, 'contract_type': 'this_week', 'user_id': ********, 'system_type': 0, 
        'price': 654.977, 'create_date_str': '2018-06-29 20:58:00', 'create_date': 1530277080437, 'status': 0}
        """
        exid = str(rawData['order_id'])
        if exid in self.localNoDict.keys():
            self.localNo = self.localNoDict[exid]
        else:
            self.localNo +=1
            self.localNoDict[exid] = self.localNo
            self.symbolDict[exid] = symbol
        
        order = VtOrderData()
        order.orderID = str(self.localNo)

        order.vtOrderID = ':'.join([self.gatewayName,order.orderID])
        order.symbol = symbol
        order.gatewayName = self.gatewayName
        order.vtSymbol = ':'.join([order.symbol, order.gatewayName])
        order.price = rawData['price']
        order.price_avg = rawData['price_avg']
        order.direction, order.offset = futureOrderTypeMap[str(rawData['type'])]
        order.totalVolume = rawData['amount']    
        order.gatewayName = self.gatewayName
        date,time = self.generateDateTime(rawData['create_date'])
        order.createDate  = date + ' ' + time
        order.deliverTime = datetime.now().strftime('%Y%m%d %H:%M:%S')
        order.status = statusMap[rawData['status']] 
        order.tradedVolume = float(rawData['deal_amount'])
        self.gateway.onOrder(copy(order))
        if order.status in [STATUS_ALLTRADED,STATUS_CANCELLED]:
            if exid in self.localNoDict.keys():
                del self.localNoDict[exid]
            if exid in self.symbolDict.keys():
                del self.symbolDict[exid]
            return

        if 'cta' in self.gatewayName:   # 非套利策略
            return
        ordertime = datetime.strptime(order.createDate,'%Y%m%d %H:%M:%S')  
        minutenow = datetime.now()
        if (minutenow - ordertime).seconds > 60: # 超过1分钟
            content = u'超过60秒没有撤单 \n 网关：%s，合约：%s，\n 价格：%s，数量：%s，\n挂单时间：%s'%(
                self.gatewayName,symbol,order.price,order.totalVolume,order.createDate)
            self.gateway.sendErrorMsg(content)
            self.writeLog(content)
            
    #----------------------------------------------------------------------
    def onSubFuturesBalance(self, data):
        """
        {'binary': 0, 'channel': 'ok_sub_futureusd_userinfo', 
        'data': {'symbol': 'eth_usd', 'balance': 0.03080528, 'unit_amount': 10.0, 
        'profit_real': 0.00077335, 'keep_deposit': 0.002298829}}
        """
        # print(data)
        if self.checkDataError(data):
            return
        rawData = data['data']

        # 帐户信息更新
        account = VtAccountData()
        account.gatewayName = self.gatewayName
        account.accountID = rawData['symbol']
        account.vtAccountID = ':'.join([account.gatewayName, account.accountID])
        account.closeProfit = float(rawData['profit_real'])
        account.balance = float(rawData['balance']) + account.closeProfit
        account.margin = float(rawData['keep_deposit'])
        account.liq = self.liquidation

        today = datetime.today().strftime('%Y%m%d')
        if not self.prebalanceDict:
            account.preBalance = account.balance
            self.prebalanceDict[account.accountID] = account.preBalance
            account.dailyPnL = 0
            return

        if account.accountID in self.prebalanceDict.keys():
            account.preBalance = self.prebalanceDict[account.accountID]
            account.dailyPnL = account.balance / account.preBalance - 1

        self.accountdata = account

        if account.margin:
            self.preTrade = datetime.now().strftime('%Y%m%d %X')
        account.lastTrade = self.preTrade
        self.gateway.onAccount(account)  
        # self.writeLog(u'期货账户信息更新成功')
    def saveAccountinfo(self,data):    
        ##查询账户资金
        path = os.getcwd()
        vnTrader_dir = os.path.join(path, 'AccountInfo')# AccountInfo 所在路径
        if not os.path.isdir(vnTrader_dir):
            os.makedirs(vnTrader_dir)
        today = datetime.today().strftime('%Y%m%d')
        path = vnTrader_dir + '//'+self.gatewayName + today + '.csv'
        newdata = []
        for item in data:
            item.append(today)
            newdata.append(item)

        if not os.path.exists(path): # 如果文件不存在，需要写header
            with open(path, 'w',newline="") as f:
                w = csv.writer(f)
                w.writerow(['accountID','balance','prebalance','date'])
                w.writerows(newdata)
        else: 
            return    #如果文件存在不写入

    def loadPreBalance(self):
        path = os.getcwd()
        vnTrader_dir = os.path.join(path, 'AccountInfo')# AccountInfo 所在路径
        if not os.path.isdir(vnTrader_dir):
            return False
        # # 文件名称设置为今天名称, 每次只推送一条合约信息
        today = datetime.today().strftime('%Y%m%d')
        path = vnTrader_dir + '//'+self.gatewayName + today + '.csv'
        info =[]
        if not os.path.exists(path): # 如果文件不存在
            return False
        else:
            with open(path) as f:
                data = csv.DictReader(f)
                for d in data:
                    self.prebalanceDict[d['accountID']]=float(d['prebalance'])
            return self.prebalanceDict
    
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
        self.gateway.onPosition(pos)
        long1,short2 = self.arbPair[pos.symbol][0],self.arbPair[pos.symbol][1]
        self.arbPair[pos.symbol]=[pos.Longposition,pos.Shortposition]
        if long1!=pos.Longposition or short2 != pos.Shortposition:
            self.gateway.sendHeartBeat(u'账户%s，合约：%s，当前仓位：%s'%(
                self.gatewayName,symbol,self.arbPair[pos.symbol]))

    #----------------------------------------------------------------------
    def init(self, apiKey, secretKey, trace, contracts,liquidation):
        """初始化接口"""

        self.contracts = contracts
        self.liquidation = liquidation
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
        time = dt.strftime("%H:%M:%S")
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
    def minuteCheck(self):

        for exid in list(self.localNoDict.keys()):
            if exid in list(self.symbolDict.keys()):
                sym = self.symbolDict[exid]
            else:
                self.writeLog('no sym found in this order:(%s)'%exid)
                continue

            symbol = sym[:3]+'_usd'
            contract_type = sym[4:]
            data = self.future_order_info(symbol,contract_type,exid)  # 对收到的订单更新状态
            rawData = data['orders'][0]
            self.pushOrder(rawData,sym)


        num = random.randint(0,25)
        order = VtOrderData()
        order.vtOrderID = self.gatewayName+'0'
        order.orderID = '0'
        order.symbol = boringMap[num]
        num = random.randint(0,25)
        order.createDate = boringMap[num]
        order.deliverTime = datetime.now().strftime('%Y%m%d %H:%M:%S')
        order.gatewayName = self.gatewayName
        self.gateway.onOrder(order)      # 硬插入一行作为分隔符

        for sym in self.subscribeList:
            symbol = sym[:3]+'_usd'
            contract_type = sym[4:]
            data = self.future_order_info(symbol,contract_type,-1,1,1,10)  # 挂单查询
            if 'orders' in data.keys():
                for rawData in data['orders']:
                    self.pushOrder(rawData,sym)
            else:
                self.writeLog('somethingwrong %s'%data)


            
        # 查询账户信息
        data = self.future_userinfo()
        contracts = data['info']  
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
                    account.margin =  round(fund['keep_deposit'],3)
                    account.liq = self.liquidation
                    check = self.loadPreBalance()

                    if not check:
                        account.preBalance = account.balance
                        self.preTrade = datetime.now().strftime('%Y%m%d %X')
                    else:
                        account.preBalance = check[account.accountID]
                    if account.margin:
                        self.preTrade = datetime.now().strftime('%Y%m%d %X')
                    account.lastTrade = self.preTrade
                    account.dailyPnL = account.balance / account.preBalance - 1
                    self.writeLog(u'Account:%s, balance:%s, margin:%s'%(
                        account.accountID,balance,account.margin))
                    self.gateway.onAccount(account)
                    if account.dailyPnL<(-0.03):
                        self.gateway.sendErrorMsg(
                            u'日内亏损超过 0.03,需要干预使用当前账户的策略。\n账户：%s,净值：%s,昨净值：%s'%(
                                self.gatewayName,account.balance,account.preBalance))
                    if account.balance<account.liq:
                        self.gateway.sendErrorMsg(
                            u'强平线被触发，需要干预使用当前账户的策略。\n账户:%s，净值：%s'%(
                                self.gatewayName,account.balance))
                        

        for sym in self.subscribeList:
            symbol = sym[:3]+'_usd'
            contract_type = sym[4:]
            self.rest_futures_position(symbol,contract_type)
        # 判断是否头寸暴露
        if 'cta' in self.gatewayName:
            return
        arb = []
        for sym in self.arbPair.keys():
            pos = self.arbPair[sym]
            arb.append([pos,sym])
        
        if len(arb)==2:
            sym1 = arb[0][1]
            sym2 = arb[1][1]
            if arb[0][0][0] or arb[1][0][1]:
                if arb[0][0][0]==arb[1][0][1]:
                    content = u'---%s 双边持仓正常---%s %s：%s %s'%(self.gatewayName,sym1,arb[0][0][0],arb[1][0][1],sym2)
                    self.writeLog(content)
                else:
                    content = u'---%s 头寸暴露---\n--%s %s：%s %s'%(self.gatewayName,sym1,arb[0][0][0],arb[1][0][1],sym2)
                    self.writeLog(content)
                    self.gateway.sendErrorMsg(content)
            if arb[0][0][1] or arb[1][0][0]:
                if arb[0][0][1]==arb[1][0][0]:
                    content = u'---%s 双边持仓正常---%s %s：%s %s'%(self.gatewayName,sym1,arb[0][0][1],arb[1][0][0],sym2)
                    self.writeLog(content)
                else:
                    content = u'---%s 头寸暴露---\n--%s %s：%s %s'%(self.gatewayName,sym1,arb[0][0][1],arb[1][0][0],sym2)
                    self.writeLog(content)
                    self.gateway.sendErrorMsg(content)

            if (arb[0][0][1] + arb[1][0][0] + arb[0][0][0] + arb[1][0][1]) == 0:
                content = u'---%s 账户没有持仓---合约对%s,%s'%(self.gatewayName,sym1,sym2)
                self.writeLog(content)
            
    #----------------------------------------------------------------------
    def subscribe(self, symbol,contractType):
        """订阅行情"""
        self.subsribeFuturesTicker(symbol,contractType)
        self.subscribeFuturesUserInfo()
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
            self.gateway.onPosition(pos)
            self.arbPair[pos.symbol] = [pos.Longposition,pos.Shortposition]

        else:
            # {'result': False, 'error_code': 20022, 'interface': '/api/v1/future_position_4fix'}
            return data['error_code']