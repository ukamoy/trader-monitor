# encoding: UTF-8

import sys

# 判断操作系统
import platform
system = platform.system()

# vn.trader模块
from vnpy.event import EventEngine
from vnpy.trader.vtEngine import MainEngine
from vnpy.trader.uiQt import createQApp

# 加载底层接口
from vnpy.trader.gateway import okexGateway

# 加载上层应用
# from vnpy.trader.app import ctaStrategy

# 当前目录组件
from uiCryptoWindow import MainWindow

#----------------------------------------------------------------------
def main():
    """主程序入口"""
    # 创建Qt应用对象
    qApp = createQApp()

    # 创建事件引擎
    ee = EventEngine()

    # 创建主引擎
    me = MainEngine(ee)
    me.addGateway(okexGateway)

    # 添加上层应用
    # me.addApp(ctaStrategy)
    
    # 创建主窗口
    mw = MainWindow(me, ee)
    mw.showMaximized()

    # 在主线程中启动Qt事件循环
    sys.exit(qApp.exec_())

if __name__ == '__main__':
    main()
