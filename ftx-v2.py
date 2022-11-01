# coding=utf-8

import ccxt
import datetime
import time
import os
import sys
import simplejson as json
# import random
# import threading

COLOR_RESET = "\033[0;0m"
COLOR_GREEN = "\033[0;32m"
COLOR_RED = "\033[1;31m"
COLOR_BLUE = "\033[1;34m"
COLOR_WHITE = "\033[1;37m"
LOGFILE=""

def log(msg):
    timestamp = datetime.datetime.now().strftime("%b %d %Y %H:%M:%S ")
    s = "[%s] %s" % (timestamp, msg)
    print(s)
    try:
        f = open(LOGFILE, "a")
        f.write(s + "\n")
        f.close()
    except:
        pass

def read_setting(file):
        with open(file) as json_file:
            return json.load(json_file)


class Oreder_Info:
    def __init__(self):
        self.done=False
        self.side=None
        self.price = 0
        self.id=0

class Grid_trader:
    order_list=[]

    def __init__(self, exchange, symbol, grid_level=0, lower_price=0.0, upper_price=0.0, amount=0, currency='', target=''):
        self.symbol = symbol
        self.exchange=exchange
        #self.order_min_inteval= self.exchange.markets[self.symbol]["info"]["priceIncrement"]
        self.order_min_interval = 0.00001
        self.grid_level=grid_level
        self.upper_price=upper_price
        self.lower_price=lower_price
        self.amount=amount
        self.currency = currency
        self.target = target
        self.inteval_profit=(self.upper_price-self.lower_price) / self.grid_level
        self.buySellCnt = {'buy':0, 'sell':0}
        pass

    def check_balance(self):
        lp = self.exchange.fetch_ticker(self.symbol)['last']
        needUSD = 0
        needSymbol = 0
        myBalance = self.exchange.fetch_balance()
        USD = 0
        symbolBalance = 0
        if self.currency in myBalance:
            USD = float(myBalance[self.currency]['free'])
        if self.target in myBalance:
            symbolBalance = float(myBalance[self.target]['free'])

        for i in range(self.grid_level + 1):
            price = self.lower_price + i * self.inteval_profit
            if price > lp:
                needSymbol += self.amount
            elif price < lp:
                needUSD += self.amount * price
            else:
                needSymbol += self.amount
                needUSD += self.amount * price

        flag = True
        if USD < needUSD:
            print(self.currency + ' balance too low, need ' + str(needUSD),
                  ', Your Balance: ' + str(USD) + ', still need: ' + str(needUSD - USD))
            flag = False
        if symbolBalance < needSymbol:
            print(self.target + ' balance too low, need ' + str(needSymbol),
                  ', Your Balance: ' + str(symbolBalance) + ', still need: ' + str(needSymbol - symbolBalance))
            flag = False

        if not flag:
            return False
        else:
            return True

    def place_order_init(self):
        #start cal level and place grid oreder
        for i in range(self.grid_level + 1): #  n+1 lines make n grid
            price = self.lower_price + i * self.inteval_profit
            bid_price, ask_price = self.send_request("get_bid_ask_price")
            order = Oreder_Info()
            if  price < ask_price : 
                order.id = self.send_request("place_order","buy",price)
                order.side = 'buy'
                order.price = price
                log("place buy order id = " + str(order.id) + " in "+ str(round(price,8)))
            else:
                order.id = self.send_request("place_order","sell",price)
                order.side = 'sell'
                order.price = price
                log("place sell order id = " + str(order.id) + " in "+ str(round(price,8)))
            self.order_list.append(order)

    def getExistOrder(self, orders):
        orderIDs = []
        for order in orders:
            id = order['info']['id']
            orderIDs.append(id)
        return orderIDs
    
    def loop_job(self):
        order_info = self.send_request("get_openOrders", self.symbol)
        existOrders = self.getExistOrder(order_info)

        for theOrder in self.order_list:
            ID = theOrder.id
            foundInExist = False
            for order in existOrders:
                if ID == order:
                    foundInExist = True
                    break

            if not foundInExist:
                old_order_id = theOrder.id
                old_order_price = theOrder.price
                side = theOrder.side
                msg = side + " order id : " + str(old_order_id) + " : " + str(round(old_order_price, 8)) + " completed , put "

                if side == "buy":
                    self.buySellCnt['buy'] += 1
                    new_order_price = round(float(theOrder.price) + self.inteval_profit, 8)
                    theOrder.id = self.send_request("place_order", "sell", new_order_price)
                    theOrder.side = 'sell'
                    theOrder.price = new_order_price
                    msg = msg + "sell"
                else:
                    self.buySellCnt['sell'] += 1
                    new_order_price = round(float(theOrder.price) - self.inteval_profit, 8)
                    theOrder.side = 'buy'
                    theOrder.price = new_order_price
                    theOrder.id = self.send_request("place_order", "buy", new_order_price)
                    msg = msg + "buy"
                msg = msg + " order id : " + str(theOrder.id) + " : " + str(new_order_price) + "   " + str(self.buySellCnt)
                log(msg)

            else:
                pass

    def send_request(self,task,input1=None,input2=None):
        tries = 10
        for i in range(tries):
            try:
                if task == "get_bid_ask_price":
                    ticker =self.exchange.fetch_ticker(self.symbol)
                    return ticker["bid"],  ticker["ask"]

                elif task == "get_order":
                    return self.exchange.fetchOrder(input1)["info"]

                elif task == 'get_openOrders':
                    return self.exchange.fetchOpenOrders(input1)

                elif task == "place_order":
                    #send_request(self,task,input1=side,input2=price)
                    side = input1
                    price = input2
                    orderid=0
                    if side =="buy":
                        orderid = self.exchange.create_limit_buy_order(self.symbol,self.amount,price )["info"]["id"]
                    else:
                        orderid = self.exchange.create_limit_sell_order(self.symbol,self.amount,price )["info"]["id"]
                    return orderid

                else:
                    return None
            except ccxt.NetworkError as e:
                if i < tries - 1: # i is zero indexed
                    log("NetworkError , try last "+str(i) +"chances" + str(e))
                    time.sleep(2)
                    continue
                else:
                    log(str(e))
                    raise
            except ccxt.InsufficientFunds as e:
                if i < tries - 1:
                    log('no base ' + str(e))
                    time.sleep(2)
                    continue
                else:
                    log(str(e))
                    raise
            except ccxt.ExchangeError as e:
                if i < tries - 1: # i is zero indexed
                    log(str(e))
                    time.sleep(2)
                    continue
                else:
                    log(str(e))
                    raise

            except ccxt.base.errors.InsufficientFunds as e:
                if i < tries - 1:
                    log('base ' + str(e))
                    time.sleep(2)
                    continue
                else:
                    log(str(e))
                    raise
            break


if __name__ == '__main__':
    configFile = str(sys.argv[1])
    # print(configFile)
    config = read_setting(configFile)
    LOGFILE= config["LOGFILE"]

    exchange  = ccxt.ftx({
        'verbose': False,
        'apiKey': config["apiKey"],
        'secret': config["secret"],
        'enableRateLimit': True,
    })

    exchange_markets = exchange.load_markets()

    main_job = Grid_trader(exchange, config["symbol"], config["grid_level"], config["lower_price"], config["upper_price"],
                           config["amount"], config['currency'], config['target'])
    #balance = main_job.check_balance()
    balance = True
    if balance:
        while True:
            try:
                main_job.place_order_init()
                break
            except Exception as e:
                print(e)
                time.sleep(0.5)
        while True:
            print("Loop in :", datetime.datetime.now())
            main_job.loop_job()
            time.sleep(0.5)
