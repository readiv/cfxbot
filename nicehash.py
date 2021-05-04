import logger, config
log = logger.get_logger(__name__)

# def get_limit(x1,x2,y1,y2,y):
#     if y1 == 0:
#         y1 = 100000 * y
#     if y2 == 0:
#         y2 = 100000 * y
#     if y2 != y1:
#         x = x1 + (x2 - x1) * (y - y1) /(y2 - y1)
#     else:
#         if y2 < y:
#             x = x2
#         else:
#             x = 0
#     if x < x1 or x > x2:
#         x = 0                
#     return x

class Avg_price(object):
    def __init__(self):
        self.n = [0,0,0,0]
        self.p = [0,0,0,0]

    def add(self, i:int, price):
            if i<0 or i>4:
                return
            if price != 0:
                self.n[i] += 1
                self.p[i] += price

    def get(self, i):
        if self.n[i] == 0:
            return -1
        return self.p[i]/self.n[i]

class Order(object):
    def __init__(self, market:str, diff:int, price_BTC_TH_day, limit_TH_s, amount_BTC):
        """Constructor"""
        self.market = market
        self.diff = diff
        self.timer = 0
        self.price_BTC_TH_day = price_BTC_TH_day
        self.limit_TH_s = limit_TH_s
        self.start_BTC =  amount_BTC
        self.amount_BTC = config.commission_nicehash * amount_BTC - 0.00001 #3,8 процента комиссия nicehash
        self.amount_CFX = 0.0

    def is_market(self, market:str):
        return self.market == market

    def mine(self, diff:int, time_s:float):
        self.timer += time_s
        if self.amount_BTC == 0:
            return
        delta_CFX = 172800 * (1000000000000 * self.limit_TH_s / (diff)) * (time_s / (24 * 60 * 60))
        delta_BTC = (self.price_BTC_TH_day / (24 * 60 * 60)) * self.limit_TH_s * time_s
        if delta_BTC > self.amount_BTC:
            delta_CFX = delta_CFX * self.amount_BTC / delta_BTC
            delta_BTC = self.amount_BTC
        self.amount_CFX = self.amount_CFX + delta_CFX
        self.amount_BTC = self.amount_BTC - delta_BTC
        # log.info(f"{self.market} BTC = {self.amount_BTC} CFX = {self.amount_CFX}")

    def add_amount(self, amount_BTC):
        self.amount_BTC += config.commission_nicehash * amount_BTC #3,8 процента комиссия nicehash

    def get_time_live(self):
        return self.amount_BTC * 24 * 60 * 60 / self.limit_TH_s / self.price_BTC_TH_day 

    def stop_and_exchange(self, course:float):
        self.amount_BTC = self.amount_BTC / config.commission_nicehash + course * self.amount_CFX
        self.limit_TH_s = 0
        self.amount_CFX = 0

    def __del__(self): #Перед удалением обязательно вызвать stop_and_exchange(self, course:float):
        # p = 100 * (self.amount_BTC - self.start_BTC)/self.start_BTC
        # if p > 0:
        #     log.warning(f"Stop order {self.market} start={self.start_BTC:2.8f} end={self.amount_BTC:2.8f} percent = {p:3.3f}%")
        # else:
        #     log.error(f"Stop order {self.market} start={self.start_BTC:2.8f} end={self.amount_BTC:2.8f} percent = {p:3.3f}%")
        pass

class Nice(object):
    def __init__(self):
        """Constructor"""
        self.balance_BTC = config.start_balance
        self.start_balance_BTC = config.start_balance
        self.minimum_balance_BTC = config.start_balance
        self.balance_CFX = 0
        # self.balance_BTC_prev = balance_BTC
        self.orders = []
        self.avg = Avg_price()

    def market_is_present_in_orders(self, market):
        result = False
        for order in self.orders:
            if order.market == market:
                result = True
                break
        return result

    def get_price_order(self, market):
        price = 0.0
        for order in self.orders:
            if order.market == market:
                return order.price_BTC_TH_day
        return price

    def get_order(self, market):
        order_r = None
        for order in self.orders:
            if order.market == market:
                return order
        return order_r

    def start_order_one(self, market, diff, price_BTC_TH_day, limit_TH_s, amount_BTC, max_profit_price):
        if self.balance_BTC == 0:
            return False
        if amount_BTC > self.balance_BTC:
            amount_BTC = self.balance_BTC
        if not self.market_is_present_in_orders(market):
            self.orders.append( Order(market, diff, price_BTC_TH_day, limit_TH_s, amount_BTC))
            self.balance_BTC = self.balance_BTC - amount_BTC
            log.info(f"Start order = {market} max_profit_price = {max_profit_price} price_BTC_TH_day={price_BTC_TH_day} limit_TH_s = {limit_TH_s} amount_BTC = {amount_BTC}")
            return True
        return False

    def stop_order_n(self, n:int, course:float):
        self.orders[n].stop_and_exchange(course)
        self.balance_BTC = self.balance_BTC + self.orders[n].amount_BTC
        self.orders.pop(n)

    def stop_order(self, market:str, course:float):
        for k in range(len(self.orders)):
            if self.orders[k].market == market: #Оцениваем новый ордер. Цена на k_percrnt меньше - перевыставляем               
                self.stop_order_n(k,course)
                break

    def start_order_market(self, market:str, diff:int, max_profit_price:float, k_price_estimated:float, p_001:float, p_005:float, 
                           p_010:float, p_050:float, p_100:float, max_limit_TH_s:float, reorder = False, course:float = 0, k_percrnt = 1.0):
        present = self.market_is_present_in_orders(market) 

        if (present and not reorder) or (not present and reorder): #Если ордер уже есть то не выставлять
            return False

        #Определить максимальнуб цену
        max_price = max_profit_price * k_price_estimated

        #Определить масимальную мощьность limit_TH_s
        # limit_TH_s = 0
        # limit_TH_s = max([limit_TH_s, get_limit(0.001,0.005,p_001,p_005,max_price)])
        # limit_TH_s = max([limit_TH_s, get_limit(0.005,0.010,p_005,p_010,max_price)])
        # limit_TH_s = max([limit_TH_s, get_limit(0.010,0.050,p_010,p_050,max_price)])
        # limit_TH_s = max([limit_TH_s, get_limit(0.050,0.100,p_050,p_100,max_price)])
        # if max_price > p_100 and p_100 != 0:  
        #     limit_TH_s = 0.100
        # if limit_TH_s > 0.99 * max_limit_TH_s:
        #     limit_TH_s = 0.99 * max_limit_TH_s
        # limit_TH_s = round(limit_TH_s - 0.0005, 3)
        # if limit_TH_s < 0.001:
        #     return False

        limit_TH_s = 0
        price = 0
        if p_001 !=0 and p_001 < max_price and 0.001 < max_limit_TH_s:
            limit_TH_s = 0.001
            price = p_001
        if p_005 !=0 and p_005< max_price and 0.001 < max_limit_TH_s:
            limit_TH_s = 0.005
            price = p_005
        if p_010 !=0 and p_010 < max_price and 0.001 < max_limit_TH_s:
            limit_TH_s = 0.010
            price = p_010
        if p_050 !=0 and p_050 < max_price and 0.001 < max_limit_TH_s:
            limit_TH_s = 0.050
            price = p_050
        if p_100 !=0 and p_100 < max_price and 0.001 < max_limit_TH_s:
            limit_TH_s = 0.001
            price = p_100

        if limit_TH_s < 0.001:
            return False

        #Посчитать количество BTC на час amount_BTC = power * price_power * 3 / 24
        amount_BTC = round(limit_TH_s * price * config.time_order / 24 + 0.0005, 3)
        
        if not reorder: #Выставить новый ордер start_order_one
            self.start_order_one(market, diff, price, limit_TH_s, amount_BTC, max_profit_price)
        else:
            flag_start = False
            for k in range(len(self.orders)):
                order = self.orders[k]
                if order.market == market: #Оцениваем новый ордер. Цена на k_percrnt меньше - перевыставляем
                    # if (((1 + (k_percrnt//10) /100) * max_price < order.price_BTC_TH_day) and 
                    #     # (100 * (order.start_BTC - order.amount_BTC) / order.start_BTC > 2 * (k_percrnt % 10)) and
                    #     (1.05 * amount_BTC > order.amount_BTC)):                  
                    if  ((k_percrnt * price < order.price_BTC_TH_day) and
                        (limit_TH_s > 0.9 * order.limit_TH_s)):
                        flag_start = True
                        diff_old_order = order.diff #Сохраняем сложность от ордера, который надо перевыставить
                        # log.warning(f"Reorder stop {market} price_BTC_TH_day = {order.price_BTC_TH_day} limit_TH_s = {order.limit_TH_s} amount_BTC = {order.amount_BTC}")
                        self.stop_order_n(k,course)
                        break
            if flag_start:
                # log.warning(f"Reorder start price_BTC_TH_day = {max_price} limit_TH_s = {limit_TH_s} amount_BTC = {amount_BTC}")
                self.start_order_one(market, diff_old_order, price, limit_TH_s, amount_BTC, max_profit_price)

    def check_and_stop_diff(self, diff:float, k_diff_order_stop : float, course:float):
        k = 0
        while k < len(self.orders):
            if diff > k_diff_order_stop * self.orders[k].diff:
                self.stop_order_n(k , course)
            else: 
                k += 1

    def check_and_stop_price(self, price:float, k_price_order_stop : float, course:float):
        k = 0
        while k < len(self.orders):
            if k_price_order_stop * price < self.orders[k].price_BTC_TH_day:
                self.stop_order_n(k , course)
            else: 
                k += 1

    def check_and_stop(self, course:float):
        """ Остановка при 0 балансе, либот по времени 24 часа """
        k = 0
        while k < len(self.orders):
            if self.orders[k].amount_BTC == 0 or self.orders[k].timer > 24 * 60 * 60:
                self.stop_order_n(k , course)
            else: 
                k += 1

    def check_and_add_amount(self):
        """ Пополняем ордер 1 час если ему осталось жить 30 минут = 1800 секунд """
        for order in self.orders:
            time_live = order.get_time_live()
            if time_live < 1800 and order.timer + time_live < 24 * 60 * 60:
                time_amount = 24 * 60 * 60 - order.timer 
                if time_amount > config.time_order * 60 *60:
                    time_amount = config.time_order * 60 *60
                amount_BTC = round(order.limit_TH_s * order.price_BTC_TH_day * time_amount / 24 / 60 / 60 + 0.0005, 3)
                if amount_BTC > self.balance_BTC:
                    amount_BTC = self.balance_BTC
                order.add_amount(amount_BTC)
                self.balance_BTC -= amount_BTC

        
    def mine(self, diff:int, time_s:float):
        if self.balance_BTC < self.minimum_balance_BTC:
            self.minimum_balance_BTC = self.balance_BTC
        for order in self.orders:
            order.mine(diff,time_s)

    def exchange_CFX(self, course:float, amount_CFX_for_exchange):
        for order in self.orders:
            self.balance_CFX += order.amount_CFX
            order.amount_CFX = 0
        if self.balance_CFX > amount_CFX_for_exchange:
            self.balance_BTC = self.balance_BTC + course * self.balance_CFX #* 0.991 - 0.00056
            # log.warning("Exchange")
            self.balance_CFX = 0

    def stop_all_orders(self, course:float):
        while len(self.orders) != 0:
            self.stop_order_n(0, course)

if __name__ == "__main__":
    nice = Nice(0.1)

    log.info(f"1 BTC = {nice.balance_BTC}")
    nice.start_order_market("EU", 2786714681928, 1.51114716813653, 1.1, 1.6, 1.6462, 1.6868, 2.15, 0, 0.0591)
    nice.start_order_market("USA",2786714681928, 1.51114716813653, 1.1, 1.5, 1.5462, 1.5868, 1.75, 1.9, 0.0991)

    log.info(f"2 BTC = {nice.balance_BTC}")
    for _ in range(3600*24):
        nice.mine(1852417174249,1)
    nice.stop_all_orders(0.00001831)
    log.info(f"3 BTC = {nice.balance_BTC}")

    nice.start_order_market("EU", 2786714681928, 1.51114716813653, 1.1, 1.6, 1.6462, 0, 2.15, 0, 0.0591)
    nice.start_order_market("USA",2786714681928, 1.51114716813653, 1.1, 0, 1.5462, 1.5868, 1.75, 1.9, 0.0991)
    log.info(f"4 BTC = {nice.balance_BTC}")
    for _ in range(3600*24):
        nice.mine(2254080980003,1)
    nice.stop_all_orders(0.00001831)
    log.info(f"5 BTC = {nice.balance_BTC}")

    avg = Avg_price()
    avg.add(15,14,13,0)
    avg.add(11,11,11,12)
    print(avg.n,avg.p)
    for i in range(4):
        print(avg.get(i))


