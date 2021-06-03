import logger, config, nicehash_api, func
log = logger.get_logger(__name__)
from config import private_api, public_api

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
        """ Конструктор. Инициализация начальных значений """
        self.n = [0,0,0,0]
        self.p = [0,0,0,0]

    def add(self, i:int, price:float):
        """ Добавляет один элемент для подсчета среднего"""
        if i<0 or i>4:
            return
        if price != 0:
            self.n[i] += 1
            self.p[i] += price

    def get(self, i):
        """ Возвращает среднее арифмитическое значение. 
            Либо -1 в если его невозможно посчитать """
        if self.n[i] == 0:
            return -1
        return self.p[i]/self.n[i]

    def reset(self):
        """ Сброс всех средних в ноль. Начинаем считать всё заново """
        self.n = [0,0,0,0]
        self.p = [0,0,0,0]

class Order(object):

    def __init__(self, market:str, diff:int, price_BTC_TH_day, limit_TH_s, amount_BTC):
        """Constructor"""
        self.market = market
        self.diff = diff
        # self.timer = 0
        self.price_BTC_TH_day = price_BTC_TH_day
        self.limit_TH_s = limit_TH_s
        # self.start_BTC =  amount_BTC
        self.amount_BTC = config.commission_nicehash * amount_BTC - 0.00001 #3,8 процента комиссия nicehash
        # self.amount_CFX = 0.0
        self.estimateDurationInSeconds = 24 * 60 *60 #Перепишеться на реальное значение при вызове update_from_nicehash
        pool_id = func.get_pool_id(market)
        self.order_id = self.start(market, config.type_order, config.algorithm, pool_id, price_BTC_TH_day, limit_TH_s, amount_BTC)

    def update_from_nicehash(self):
        """ Возвращает True, если всё ok. Иначе False. """
        try:
            if self.order_id == None:
                return False
            req_json = private_api.get_order_details(self.order_id) #Эта ошибка обошлась в 350 евро.
            self.amount_BTC = float(req_json["availableAmount"])
            self.estimateDurationInSeconds = int(req_json["estimateDurationInSeconds"])
            if req_json["status"]["code"] not in ["PENDING", "ACTIVE"]: #Статус неверный. Останавливаем ордер.
                self.order_id = None
                raise(f"order_id = {self.order_id} status = {req_json['status']['code']}")
            return True
        except Exception as e:
            log.error(str(e))
            return False

    def start(self, market, type_order, algorithm, pool_id, price, limit, amount):
        if pool_id is None:
            return None
        try:
            algo_response = public_api.get_algorithms()
            log.info(f"market={market}, pool_id={pool_id}")
            if config.no_order:
                return None
            response = private_api.create_hashpower_order(market, type_order, algorithm, price, limit, amount, pool_id, algo_response)
            order_id = response["id"]
            return order_id
        except Exception as e:
            log.error(str(e))
            return None
        
    def is_market(self, market:str):
        return self.market == market

    # def mine(self, diff:int, time_s:float):
    #     self.timer += time_s
    #     if self.amount_BTC == 0:
    #         return
    #     delta_CFX = 172800 * (1000000000000 * self.limit_TH_s / (diff)) * (time_s / (24 * 60 * 60))
    #     delta_BTC = (self.price_BTC_TH_day / (24 * 60 * 60)) * self.limit_TH_s * time_s
    #     if delta_BTC > self.amount_BTC:
    #         delta_CFX = delta_CFX * self.amount_BTC / delta_BTC
    #         delta_BTC = self.amount_BTC
    #     self.amount_CFX = self.amount_CFX + delta_CFX
    #     self.amount_BTC = self.amount_BTC - delta_BTC
    #     # log.info(f"{self.market} BTC = {self.amount_BTC} CFX = {self.amount_CFX}")

    def add_amount(self, amount_BTC):
        private_api.refill_hashpower_order(self.order_id, amount_BTC)

    def get_time_live(self):
        return self.estimateDurationInSeconds

    # def stop_and_exchange(self, course:float):
    #     self.amount_BTC = self.amount_BTC / config.commission_nicehash + course * self.amount_CFX
    #     self.limit_TH_s = 0
    #     self.amount_CFX = 0

    def __del__(self): #При удалении ордера остановить его на nicehash
        if not config.no_order and self.order_id is not None:
            log.info(f"The order stoped. order_id = {self.order_id} market = {self.market} amount_BTC = {self.amount_BTC}")
            private_api.cancel_hashpower_order(self.order_id)

class Nice(object):
    def __init__(self):
        """Constructor"""
        self.balance_BTC = config.start_balance
        self.start_balance_BTC = 0
        # self.minimum_balance_BTC = config.start_balance
        # self.balance_CFX = 0
        # self.balance_BTC_prev = balance_BTC
        self.orders = []
        self.avg = Avg_price()
        self.update_from_nicehash()
        

    def market_is_present_in_orders(self, market):
        result = False
        for order in self.orders:
            if order.market == market:
                result = True
                break
        return result

    def update_from_nicehash(self):
        """ Обновить с nh информациб об ордерах. Грохнуть те, которых уже нет на nh """
        try:
            self.balance_BTC = float(private_api.get_accounts_for_currency(config.currency)["available"])
            if self.start_balance_BTC == 0: #Вызов из конструктора
                self.start_balance_BTC = self.balance_BTC
        except Exception as e:
            log.error(str(e)) 
        k = 0
        while k < len(self.orders):
            if not self.orders[k].update_from_nicehash():
                self.stop_order_n(k)
            else: 
                k += 1

    def avg_reset(self):
        self.avg.reset()

    def get_price_order(self, market):
        price = 0.0
        for order in self.orders:
            if order.market == market:
                return order.price_BTC_TH_day
        return price

    def get_price_nh(self, market, limit_TH_s):
        try:
            return float(private_api.get_hashpower_fixedprice(market, config.algorithm, 0.001)["fixedPrice"])
        except:
            return 0.0

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
            self.orders.append(Order(market, diff, price_BTC_TH_day, limit_TH_s, amount_BTC))
            # self.balance_BTC = self.balance_BTC - amount_BTC
            log.info(f"Start order = {market} max_profit_price = {max_profit_price} price_BTC_TH_day={price_BTC_TH_day} limit_TH_s = {limit_TH_s} amount_BTC = {amount_BTC}")
            return True
        return False

    def stop_order_n(self, n:int):
        # self.orders[n].stop_and_exchange(course)
        # self.balance_BTC = self.balance_BTC + self.orders[n].amount_BTC
        self.orders.pop(n)

    def stop_order(self, market:str):
        for k in range(len(self.orders)):
            if self.orders[k].market == market: #Оцениваем новый ордер. Цена на k_percrnt меньше - перевыставляем               
                self.stop_order_n(k)
                break

    def start_order_market(self, market:str, diff:int, max_profit_price:float, k_price_estimated:float, 
                           reorder = False, course:float = 0, k_percrnt = 1.0):
        present = self.market_is_present_in_orders(market) 

        if (present and not reorder) or (not present and reorder): #Если ордер уже есть то не выставлять
            return False

        #Определить максимальнуб цену
        max_price = max_profit_price * k_price_estimated   
        price, limit_TH_s, amount_BTC = func.calc_order_param(max_price, market, self.balance_BTC)  
        if price is None or price == 0 or limit_TH_s == 0 or amount_BTC == 0:
            # log.error(f"price = {price} limit_TH_s = {limit_TH_s} amount_BTC = {amount_BTC}")
            return False
        if not reorder: #Выставить новый ордер start_order_one
            if self.start_order_one(market, diff, price, limit_TH_s, amount_BTC, max_profit_price):
                log.info(f"The order was launched successfully. price_BTC_TH_day = {max_price} limit_TH_s = {limit_TH_s} amount_BTC = {amount_BTC}")
            else:
                log.info(f"Order start error. price_BTC_TH_day = {max_price} limit_TH_s = {limit_TH_s} amount_BTC = {amount_BTC}")
        else:
            flag_start = False
            for k in range(len(self.orders)):
                order = self.orders[k]
                if order.market == market: #Оцениваем новый ордер. Цена на k_percrnt меньше - перевыставляем            
                    if  ((k_percrnt * price < order.price_BTC_TH_day) and
                        (limit_TH_s > 0.9 * order.limit_TH_s)):
                        flag_start = True
                        diff_old_order = order.diff #Сохраняем сложность от ордера, который надо перевыставить
                        # log.warning(f"Reorder stop {market} price_BTC_TH_day = {order.price_BTC_TH_day} limit_TH_s = {order.limit_TH_s} amount_BTC = {order.amount_BTC}")
                        self.stop_order_n(k)
                        # time.sleep(config.time_2m) #Ждем пока цена на найсхэш устаканиться
                        break
            if flag_start:
                if self.start_order_one(market, diff_old_order, price, limit_TH_s, amount_BTC, max_profit_price):
                    log.info(f"Successful order restart. price_BTC_TH_day = {max_price} limit_TH_s = {limit_TH_s} amount_BTC = {amount_BTC}")
                else:
                    log.info(f"Reorder start error. price_BTC_TH_day = {max_price} limit_TH_s = {limit_TH_s} amount_BTC = {amount_BTC}")

    def check_and_stop_diff(self, diff:float, k_diff_order_stop : float, course:float):
        k = 0
        while k < len(self.orders):
            if diff > k_diff_order_stop * self.orders[k].diff:
                self.stop_order_n(k)
            else: 
                k += 1

    def check_and_stop_price(self, price:float, k_price_order_stop : float, course:float):
        k = 0
        while k < len(self.orders):
            if k_price_order_stop * price < self.orders[k].price_BTC_TH_day:
                self.stop_order_n(k)
            else: 
                k += 1

    # def check_and_stop(self, course:float):
    #     """ Остановка при 0 балансе, либот по времени 24 часа """
    #     k = 0
    #     while k < len(self.orders):
    #         if self.orders[k].amount_BTC == 0 or self.orders[k].timer > 24 * 60 * 60:
    #             self.stop_order_n(k , course)
    #         else: 
    #             k += 1

    def check_and_add_amount(self):
        """ Пополняем ордер 1 час если ему осталось жить 30 минут = 1800 секунд """
        for order in self.orders:
            time_live = order.get_time_live()
            if time_live < 1800:
                time_amount = config.time_order * 60 * 60
                amount_BTC = round(order.limit_TH_s * order.price_BTC_TH_day * time_amount / 24 / 60 / 60 + 0.0005, 3)
                if amount_BTC > self.balance_BTC:
                    amount_BTC = self.balance_BTC
                order.add_amount(amount_BTC)
                self.balance_BTC -= amount_BTC

        
    # def mine(self, diff:int, time_s:float):
    #     if self.balance_BTC < self.minimum_balance_BTC:
    #         self.minimum_balance_BTC = self.balance_BTC
    #     for order in self.orders:
    #         order.mine(diff,time_s)

    # def exchange_CFX(self, course:float, amount_CFX_for_exchange):
    #     for order in self.orders:
    #         self.balance_CFX += order.amount_CFX
    #         order.amount_CFX = 0
    #     if self.balance_CFX > amount_CFX_for_exchange:
    #         self.balance_BTC = self.balance_BTC + course * self.balance_CFX #* 0.991 - 0.00056
    #         # log.warning("Exchange")
    #         self.balance_CFX = 0

    def stop_all_orders(self, course:float):
        while len(self.orders) != 0:
            self.stop_order_n(0)

if __name__ == "__main__":
    nice = Nice()



