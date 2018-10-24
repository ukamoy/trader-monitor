# encoding: UTF-8

import time
from threading import Timer
from vnpy.event import *

from vnpy.trader.vtEvent import *
from vnpy.trader.vtConstant import *
from vnpy.trader.vtObject import *
from vnpy.trader.vtGlobal import globalSetting
from datetime import datetime
import smtplib
from email.mime.text import MIMEText
from email.utils import formataddr


########################################################################
class VtGateway(object):
    """交易接口"""

    #----------------------------------------------------------------------
    def __init__(self, eventEngine, gatewayName):
        """Constructor"""
        self.eventEngine = eventEngine
        self.gatewayName = gatewayName
        self.temp=0
        
    #----------------------------------------------------------------------
    def onTick(self, tick):
        """市场行情推送"""
        # 通用事件
        event1 = Event(type_=EVENT_TICK)
        event1.dict_['data'] = tick
        self.eventEngine.put(event1)
        
        # 特定合约代码的事件
        event2 = Event(type_=EVENT_TICK+tick.vtSymbol)
        event2.dict_['data'] = tick
        self.eventEngine.put(event2)
    
    #----------------------------------------------------------------------
    def onTrade(self, trade):
        """成交信息推送"""
        # 通用事件
        event1 = Event(type_=EVENT_TRADE)
        event1.dict_['data'] = trade
        self.eventEngine.put(event1)
        
        # 特定合约的成交事件
        event2 = Event(type_=EVENT_TRADE+trade.vtSymbol)
        event2.dict_['data'] = trade
        self.eventEngine.put(event2)        
    
    #----------------------------------------------------------------------
    def onOrder(self, order):
        """订单变化推送"""
        # 通用事件
        event1 = Event(type_=EVENT_ORDER)
        event1.dict_['data'] = order
        self.eventEngine.put(event1)
        
        # 特定订单编号的事件
        event2 = Event(type_=EVENT_ORDER+order.vtOrderID)
        event2.dict_['data'] = order
        self.eventEngine.put(event2)
    
    #----------------------------------------------------------------------
    def onPosition(self, position):
        """持仓信息推送"""
        # 通用事件
        event1 = Event(type_=EVENT_POSITION)
        event1.dict_['data'] = position
        self.eventEngine.put(event1)
        
        # 特定合约代码的事件
        event2 = Event(type_=EVENT_POSITION+position.vtSymbol)
        event2.dict_['data'] = position
        self.eventEngine.put(event2)
    
    #----------------------------------------------------------------------
    def onAccount(self, account):
        """账户信息推送"""
        # 通用事件
        event1 = Event(type_=EVENT_ACCOUNT)
        event1.dict_['data'] = account
        self.eventEngine.put(event1)
        
        # 特定合约代码的事件
        if account.vtAccountID:
            event2 = Event(type_=EVENT_ACCOUNT+account.vtAccountID)
            event2.dict_['data'] = account
            self.eventEngine.put(event2)
    
    #----------------------------------------------------------------------
    def onError(self, error):
        """错误信息推送"""
        # 通用事件
        event1 = Event(type_=EVENT_ERROR)
        event1.dict_['data'] = error
        self.eventEngine.put(event1)    
        
    #----------------------------------------------------------------------
    def onLog(self, log):
        """日志推送"""
        # 通用事件
        event1 = Event(type_=EVENT_LOG)
        event1.dict_['data'] = log
        self.eventEngine.put(event1)
        
    #----------------------------------------------------------------------
    def onContract(self, contract):
        """合约基础信息推送"""
        # 通用事件
        event1 = Event(type_=EVENT_CONTRACT)
        event1.dict_['data'] = contract
        self.eventEngine.put(event1)        
    
    #----------------------------------------------------------------------
    def connect(self):
        """连接"""
        pass
    
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
        pass
    #-----------------------------------
    def qryOrder(self):
        """查询特定订单"""
        pass
    #----------------------------------------------------------------------
    def close(self):
        """关闭"""
        pass

    def sendHeartBeat(self,my_context):
        self.mail(my_context,'MONITOR Position')
        
    def sendErrorMsg(self,my_context):
        self.mail(my_context,'MONITOR 警报')

    def mail(self,my_context,title):
        mailaccount, mailpass = globalSetting['mailAccount'],globalSetting['mailPass']
        mailserver, mailport = globalSetting['mailServer'],globalSetting['mailPort']
        to_receiver = globalSetting['receiver']
        ret=True
        try:
            my_context= my_context.replace('\n','<br>')
            my_context = my_context +"<br><br> from monitor <br><br> Have a good day <br>"+ datetime.now().strftime("%Y%m%d %H:%M:%S")
            msg=MIMEText(my_context,'html','utf-8')
            msg['From']=formataddr(['VNPY_CryptoCurrency',mailaccount])
            msg['To']=formataddr(["收件人昵称",to_receiver])
            msg['Subject'] = title
    
            server=smtplib.SMTP_SSL(mailserver, mailport)
            server.login(mailaccount, mailpass)
            server.sendmail(mailaccount,[to_receiver],msg.as_string())
            server.quit()
            print(u" Send email successfully ...")
        except Exception:
            ret=False
            print(u" Send email failed ...")
        return ret

    
    
    
