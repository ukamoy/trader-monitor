# encoding: UTF-8

from __future__ import print_function

import hashlib
import json
import traceback
from threading import Thread, Event, Timer
from time import sleep
import pandas as  pd
import requests
from urllib.error import HTTPError
import datetime
import ssl
import websocket    

# 常量定义
OKEX_SPOT_HOST = 'wss://real.okex.com:10440/websocket'
OKEX_FUTURES_HOST = 'wss://real.okex.com:10440/websocket/okexapi'
# OKEX_SPOT_HOST = 'wss://okexcomreal.bafang.com:10441/websocket'
# OKEX_FUTURES_HOST = 'wss://okexcomreal.bafang.com:10441/websocket/okexapi'

SPOT_CURRENCY = ["usdt",
                 "btc",
                 "ltc",
                 "eth",
                 "etc",
                 "bch"]

SPOT_SYMBOL = ["ltc_btc",
               "eth_btc",
               "etc_btc",
               "bch_btc",
               "btc_usdt",
               "eth_usdt",
               "ltc_usdt",
               "etc_usdt",
               "bch_usdt",
               "etc_eth",
               "bt1_btc",
               "bt2_btc",
               "btg_btc",
               "qtum_btc",
               "hsr_btc",
               "neo_btc",
               "gas_btc",
               "qtum_usdt",
               "hsr_usdt",
               "neo_usdt",
               "gas_usdt"]

KLINE_PERIOD = ["1min",
                "3min",
                "5min",
                "15min",
                "30min",
                "1hour",
                "2hour",
                "4hour",
                "6hour",
                "12hour",
                "day",
                "3day",
                "week"]

########################################################################
class OkexApi(object):    
    """交易接口"""
    reconnect_timeout = 10 # 重连超时时间

    #----------------------------------------------------------------------
    def __init__(self):
        """Constructor"""
        self.host = ''          # 服务器
        self.apiKey = ''        # 用户名
        self.secretKey = ''     # 密码
  
        self.active = False     # 工作状态
        self.ws = None          # websocket应用对象
        self.wsThread = None    # websocket工作线程
        
        self.heartbeatCount = 0         # 心跳计数
        self.heartbeatThread = None     # 心跳线程
        self.heartbeatReceived = True   # 心跳是否收到
        
        self.connectEvent = Event() # 表示是否连接
        self.reconnecting = False       # 重新连接中
        self.reconnectTimer = None
    
    #----------------------------------------------------------------------
    def heartbeat(self):
        """"""
        while self.active:
            self.connectEvent.wait()
            self.heartbeatCount += 1
            if self.heartbeatCount < 10:
                sleep(1)
            else:
                self.heartbeatCount = 0
                
                if not self.heartbeatReceived:
                    self.reconnect()
                else:
                    self.heartbeatReceived = False
                    d = {'event': 'ping'}
                    j = json.dumps(d)
                    
                    try:                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                      
                        self.ws.send(j) 
                    except:
                        msg = traceback.format_exc()
                        self.onError(msg)
                        self.reconnect()

    #----------------------------------------------------------------------
    def reconnect(self):
        """重新连接"""
        if not self.reconnecting:
            self.reconnecting = True
            self.closeWebsocket()  # 首先关闭之前的连接
            print('OKEX_API断线重连')
            self.reconnectTimer = Timer(self.reconnect_timeout, self.connectEvent.set)
            self.connectEvent.clear() # 设置未连接上
            self.initWebsocket()
            self.reconnectTimer.start()
            self.heartbeatReceived = True # avoid too frequent reconnect
            self.reconnecting = False
        
    #----------------------------------------------------------------------
    def connect(self, host, apiKey, secretKey, trace=False):
        """连接"""
        self.host = host
        self.apiKey = apiKey
        self.secretKey = secretKey
        websocket.enableTrace(trace)
        
        self.initWebsocket()
        self.active = True
        self.heartbeatReceived = True
        print('OKEX_API初始化连接')
        
    #----------------------------------------------------------------------
    def initWebsocket(self):
        """"""
        self.ws = websocket.WebSocketApp(self.host,
                                         on_message=self.onMessageCallback,
                                         on_error=self.onErrorCallback,
                                         on_close=self.onCloseCallback,
                                         on_open=self.onOpenCallback,
                                        )        
        
        self.wsThread = Thread(target=self.ws.run_forever,kwargs=dict(
            sslopt = {"cert_reqs": ssl.CERT_NONE, "check_hostname": False},
        ))
        self.wsThread.start()

    #----------------------------------------------------------------------
    def readData(self, evt):
        """解码推送收到的数据"""
        data = json.loads(evt)
        # print(data)
        return data

    #----------------------------------------------------------------------
    def closeHeartbeat(self):
        """关闭接口"""
        if self.heartbeatThread and self.heartbeatThread.isAlive():
            self.active = False
            self.heartbeatThread.join()
        self.heartbeatThread = None

    #----------------------------------------------------------------------
    def closeWebsocket(self):
        """关闭WS"""
        if self.wsThread and self.wsThread.isAlive():
            self.ws.close()
            self.wsThread.join(2)
    
    #----------------------------------------------------------------------
    def close(self):
        """"""
        self.closeHeartbeat()
        self.closeWebsocket()
        
    #----------------------------------------------------------------------
    def onMessage(self, data):
        """信息推送""" 
        print('onMessage')
        
    #----------------------------------------------------------------------
    def onError(self, data):
        """错误推送"""
        print('onError')
        
    #----------------------------------------------------------------------
    def onClose(self):
        """接口断开"""
        print('onClose')
        
    #----------------------------------------------------------------------
    def onOpen(self):
        """接口打开"""
        print('onOpen')
    
    #----------------------------------------------------------------------
    def onMessageCallback(self, ws, evt):
        """""" 
        data = self.readData(evt)
        if 'event' in data:
            self.heartbeatReceived = True
        else:
            self.onMessage(data[0])
        
    #----------------------------------------------------------------------
    def onErrorCallback(self, ws, evt):
        """"""
        self.onError(evt)
        
    #----------------------------------------------------------------------
    def onCloseCallback(self, ws):
        """"""
        self.onClose()
        
    #----------------------------------------------------------------------
    def onOpenCallback(self, ws):
        """"""
        self.connectEvent.set() # 设置为连接上
        if self.reconnectTimer:
            self.reconnectTimer.cancel()
        self.heartbeatReceived = True
        if not self.heartbeatThread:
            self.heartbeatThread = Thread(target=self.heartbeat)
            self.heartbeatThread.start()
        self.onOpen()
        
    #----------------------------------------------------------------------
    def generateSign(self, params):
        """生成签名"""
        l = []
        for key in sorted(params.keys()):
            l.append('%s=%s' %(key, params[key]))
        l.append('secret_key=%s' %self.secretKey)
        sign = '&'.join(l)
        return hashlib.md5(sign.encode('utf-8')).hexdigest().upper()

    #----------------------------------------------------------------------
    def sendRequest(self, channel, params=None):
        """发送请求"""
        # 生成请求
        d = {}
        d['event'] = 'addChannel'
        d['channel'] = channel        
        
        # 如果有参数，在参数字典中加上api_key和签名字段
        if params is not None:
            params['api_key'] = self.apiKey
            params['sign'] = self.generateSign(params)
            d['parameters'] = params
        
        # 使用json打包并发送
        j = json.dumps(d)
        # 若触发异常则重连
        try:
            self.ws.send(j)
            return True
        except websocket.WebSocketConnectionClosedException:
            self.reconnect()
            return False

    #----------------------------------------------------------------------
    def login(self):
        params = {}
        params['api_key'] = self.apiKey
        params['sign'] = self.generateSign(params)
        
        # 生成请求
        d = {}
        d['event'] = 'login'
        d['parameters'] = params
        j = json.dumps(d)
        # 若触发异常则重连
        try:
            self.ws.send(j)
            return True
        except websocket.WebSocketConnectionClosedException:
            self.reconnect()
            return False

    ###Rest 接口的sign方法------------------------------
    def rest_sign(self, dictionary):   
        data = self._chg_dic_to_sign(dictionary)
        signature = self.__md5(data)
        return signature.upper()
    
    def _chg_dic_to_sign(self, dictionary):
        keys = list(dictionary.keys())
        if "self" in keys:
            keys.remove("self")
        keys.sort()
        strings = []
        for key in keys:
            if dictionary[key] != None:
                if not isinstance(dictionary[key], str):
                    strings.append(key + "=" + str(dictionary[key]))
                    continue
                strings.append(key + "=" + dictionary[key])
        strings.append("secret_key" + "=" + self.secretKey)
        return "&".join(strings)

    def __md5(self, string):
        m = hashlib.md5()
        m.update(string.encode("utf-8"))
        return m.hexdigest()


########################################################################
class OkexFuturesApi(OkexApi):
    """期货交易接口
    
    交割推送信息：
    [{
        "channel": "btc_forecast_price",
        "timestamp":"1490341322021",
        "data": "998.8"
    }]
    data(string): 预估交割价格
    timestamp(string): 时间戳
    
    无需订阅，交割前一小时自动返回
    """

    #----------------------------------------------------------------------
    def __init__(self):
        """Constructor"""
        super(OkexFuturesApi, self).__init__()

    #----------------------------------------------------------------------
    def subsribeFuturesTicker(self, symbol, contractType):
        """订阅期货行情   #不停推送
        [{'binary': 0, 
        'channel': 'ok_sub_futureusd_btc_ticker_this_week', 
        'data': {'high': '6810.9', 'limitLow': '6541.07', 'vol': '1563798', 
        'last': '6743.24', 'low': '6600', 'buy': '6739.08', 'hold_amount': '1251968', 
        'sell': '6742.14', 'contractId': 201806220000013, 'unitAmount': '100', 'limitHigh': '6945.78'}}
        """
        channel ='ok_sub_futureusd_%s_ticker_%s' %(symbol, contractType)
        self.sendRequest(channel)

    #----------------------------------------------------------------------
    def subscribeFuturesKline(self, symbol, contractType, period):
        """订阅期货K线""" # 建议使用RESTFUL取历史的数据, WEBSOCKET只返回并推送当前K线
        channel = 'ok_sub_futureusd_%s_kline_%s_%s' %(symbol, contractType, period)
        self.sendRequest(channel)

    #----------------------------------------------------------------------
    def futuresUserInfo(self):
        """查询期货账户   #只在查询时返回一次
        [{'binary': 0, 'channel': 'ok_futureusd_userinfo', 
        'data': {'result': True, 
        'info': {
        'btc': {'risk_rate': 10000, 'account_rights': 0, 'profit_unreal': 0, 'profit_real': 0, 'keep_deposit': 0}, 
        'bch': {'risk_rate': 43.5473, 'account_rights': 0.06191271, 'profit_unreal': 3.471e-05, 
        'profit_real': -0.00030754, 'keep_deposit': 0.001418476},
        ...省略其他品种}}}]
        """
        channel = 'ok_futureusd_userinfo'
        self.sendRequest(channel, {})

    #----------------------------------------------------------------------
    def futuresOrderInfo(self, symbol, orderid, contractType, status, current_page, page_length=10):
        """查询期货委托
        查询指令: futuresOrderInfo("bch_usd" , "978694112964608" , "this_week" , '0', '1'  , '10')
        返回信息: 
        [{'binary': 0, 'channel': 'ok_futureusd_orderinfo', 
        'data': {'result': True, 
        'orders': [{'symbol': 'bch_usd', 'lever_rate': 10, 'amount': 1, 'fee': -6.23e-06, 
        'contract_name': 'BCH0629', 'unit_amount': 10, 'type': 1, 'price_avg': 802.254, 
        'deal_amount': 1, 'price': 802.254, 'create_date': 1529669687000, 
        'order_id': 978694112964608, 'status': 2}]}}]
        """
        params = {}
        params['symbol'] = str(symbol)
        params['order_id'] = str(orderid)
        params['contract_type'] = str(contractType)
        params['status'] = str(status)
        params['current_page'] = str(current_page)
        params['page_length'] = str(page_length)
        
        channel = 'ok_futureusd_orderinfo'
        
        self.sendRequest(channel, params)

    #----------------------------------------------------------------------
    def subscribeFuturesUserInfo(self):
        """订阅期货账户信息"""            #只在变动时, 即交易时返回
        """
        [{'binary': 0, 'channel': 'ok_sub_futureusd_userinfo', 
        'data': {'symbol': 'bch_usd', 'balance': 0.06218554, 'unit_amount': 10.0, 
        'profit_real': -7.104e-05, 'keep_deposit': 0.00124909}}]
        """
        channel = 'ok_sub_futureusd_userinfo' 
        self.sendRequest(channel, {})
        
    #----------------------------------------------------------------------
    def subscribeFuturesPositions(self):
        """订阅期货持仓信息      #只在持仓变动时, 即下单时返回, 这里的持仓信息为上一笔成交的信息。直接查询不返回。
        1、全仓模式
        [{'binary': 0, 
        'channel': 'ok_sub_futureusd_positions', 
        'data': {
        'symbol': 'bch_usd', 
        'user_id': 8182562, 
        'positions': [
        {'bondfreez': 0.00124909, 'margin': 0.0, 'avgprice': 800.702, 'eveningup': 0.0,   #eveningup 可平仓量
        'contract_id': 201807060050052, 'hold_amount': 0.0, 'contract_name': 'BCH0706',   #hold_amount 持仓量
        'realized': 6.006e-05, 'position': 1, 'costprice': 800.702, 'position_id': 978565225741312}, 
        {'bondfreez': 0.00124909, 'margin': 0.0, 'avgprice': 0.0, 'eveningup': 0.0, 
        'contract_id': 201807060050052, 'hold_amount': 0.0, 'contract_name': 'BCH0706', 
        'realized': 6.006e-05, 'position': 2, 'costprice': 0.0, 'position_id': 978565225741312}]}}]
        # position: 仓位 1多仓 2空仓, bondfreez: 当前合约冻结保证金, margin: 固定保证金
        2、逐仓模式
        forcedprice(string): 强平价格，balance(string): 合约账户余额 ，fixmargin(double): 固定保证金
        lever_rate(double): 杠杆倍数

        """
        channel = 'ok_sub_futureusd_positions' 
        self.sendRequest(channel, {})    
    
    # RESTFUL 接口
    def _post_url_func(self, url):
        # return 'https://okexcomweb.bafang.com/api' + "/" + "v1" + "/" + url + ".do"
        return 'https://www.okex.com/api' + "/" + "v1" + "/" + url + ".do"
    
    def _get_url_func(self, url, params=""):
        # return 'https://okexcomweb.bafang.com/api' + "/" + "v1" + "/" + url + params
        return 'https://www.okex.com/api' + "/" + "v1" + "/" + url + params
    
    def _chg_dic_to_str(self, dictionary):
        keys = list(dictionary.keys())
        keys.remove("self")
        keys.sort()
        strings = []
        for key in keys:
            if dictionary[key] != None:
                if not isinstance(dictionary[key], str):
                    strings.append(key + "=" + str(dictionary[key]))
                    continue
                strings.append(key + "=" + dictionary[key])

        return ".do?" + "&".join(strings)
        
    def future_userinfo(self):
        params = {}
        params['api_key'] = self.apiKey
        params['sign'] = self.rest_sign(params)
        url = self._post_url_func("future_userinfo")
        # print(url)
        r = requests.post(url, data=params, timeout=30)
        return r.json()
    
    def future_position(self, symbol, contract_type):
        api_key = self.apiKey
        data = {"api_key": api_key, "sign": self.rest_sign(locals()), "symbol": symbol, "contract_type": contract_type}
        url = self._post_url_func("future_position")
        # print(url)
        r = requests.post(url, data=data, timeout=30)
        return r.json()