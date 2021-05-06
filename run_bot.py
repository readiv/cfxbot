#!/usr/bin/env python3
from datetime import datetime
from func import get_api, time2float
import logger, csv, config, confluxscan, func
from nicehash import Nice

log = logger.get_logger(__name__)

if __name__ == "__main__":
    log.info("===========+============= Start ============+=============")         
    while True:
        diff = confluxscan.get_difficulty()
        state = {"state":"down",
                "diff": diff,
                "time_start":datetime.now(),
                "deadline":0}   # down up_2m up down_2m 
        if diff != 0:
            break
    print(diff)

    nice = Nice()

    with open('log-order.csv', 'w', newline='') as csvfile:
        csvwriter = csv.writer(csvfile, delimiter=',')
        row = ["time","diff","max_price","p_n_EU","p_o_EU","p_n_EU_N","p_o_EU_N","p_n_USA","p_o_USA","p_n_USA_E","p_o_USA_E"]
        csvwriter.writerow(row)
        
        while True:
            diff_now = confluxscan.get_difficulty()
            if diff_now == 0:
                log.error(f"id={diff_now} difficulty = 0")
                continue #Сложность не может быть равна нулю
            time_now = datetime.now() #2021-03-24 19:41:07.198087                   
  
            price_BTC = get_api("https://conflux.herominers.com/api/get_market?tickers%5B%5D=CFX-BTC")[0]["price"]
            if price_BTC is not None:
                price_BTC = float(price_BTC)
            else:
                continue #Курс тоже не может быть равен нулю

            max_profit_price = round( price_BTC * 172800 * 1000000000000 / diff_now - 0.0005, 3)
            row = [time2float(time_now), diff_now, max_profit_price]

            if (state["state"] == "down" or state["state"] == "up") and diff_now > config.k_down_up * state["diff"]: #Сложность повысилась
                state["state"] = "up_2m"
                state["time_start"] = time_now
                state["deadline"] = config.time_2m # Действует секунд
                log.info(f"new state = {state['state']} diff_old = {state['diff']} diff_new = {diff_now} state = up_2m")
                # log.info(f"id={cfx_data[i][0]} Stop All Orders")
                # nice.stop_all_orders(price_BTC)

            if state["state"] == "up_2m": 
                if time_now > state["time_start"] + datetime.timedelta(seconds=state["deadline"]):
                    state["state"] = "up"
                    state["time_start"] = time_now
                    state["deadline"] = config.time_start_order
                    nice.avg_reset()
                    log.info(f"new state = {state['state']} diff_old = {state['diff']} diff_new = {diff_now} state = up")
    
            if (state["state"] == "down" or state["state"] == "up") and diff_now < config.k_up_down * state["diff"]: #Сложность упала
                state["state"] = "down_2m"
                state["time_start"] = time_now
                state["deadline"] = config.time_2m # Действует time_2m секунд
                log.info(f"new state = {state['state']} diff_old = {state['diff']} diff_new = {diff_now} state = down_2m") 

            if state["state"] == "down_2m": 
                if time_now > state["time_start"] + datetime.timedelta(seconds=state["deadline"]):
                    state["state"] = "down"
                    state["time_start"] = time_now
                    state["deadline"] = 0 # Действует time_2m секунд
                    log.info(f"new state = {state['state']} diff_old = {state['diff']} diff_new = {diff_now} state = down")

            if state["state"] == "up" and time_now < state["time_start"] + datetime.timedelta(seconds=state["deadline"]):
                for k in range(0,len(config.market_lists)): #Накапливаем среднюю цену
                    p_avg_001 = nice.avg.get(k) 
                    p_nh_001 = nice.get_price_nh(config.market_lists[k], 0.001)
                    if p_avg_001 != -1 and p_nh_001 != 0:         
                        if p_nh_001 > config.k_avg * p_avg_001:
                            state["deadline"] = (time_now - state["time_start"]).seconds
                    nice.avg.add(k, p_nh_001)

            if state["state"] == "up" and time_now > state["time_start"] + datetime.timedelta(seconds=state["deadline"]): 
                for k in range(0,len(config.market_lists)): #Начинаем выставлять ордера.
                    p_nh_001 = nice.get_price_nh(config.market_lists[k], 0.001)
                    if p_nh_001 !=0:
                        nice.start_order_market(config.market_lists[k], diff_now, 
                                                max_profit_price = max_profit_price, 
                                                k_price_estimated = config.k_price_estimated)
            
            nice.update_from_nicehash()
            nice.check_and_add_amount() #Пополняем ордера

            for k in range(0,len(config.market_lists)): #Формируем row для csv файл 
                row.append(nice.get_price_nh(config.market_lists[k], 0.001))
                row.append(nice.get_price_order(config.market_lists[k]))

            # Всё время проверяем выставленые ордера и если есть более выгодеый - переустанавливаем
            if len(nice.orders) != 0: #как то неэфективно получилось 
                for k in range(0,len(config.market_lists)):
                    p_nh_001 = nice.get_price_nh(config.market_lists[k], 0.001)
                    if p_nh_001 !=0:
                        nice.start_order_market(config.market_lists[k], diff_now, 
                                                max_profit_price = max_profit_price, 
                                                k_price_estimated = config.k_price_estimated,
                                                reorder=True,
                                                course = price_BTC,
                                                k_percrnt=1.0) 
            
            # Проверяем все ордера и если какой-то невыгодный по diff - стопаем его
            # if ((state["state"] == "up" and time_now <= state["time_start"] + datetime.timedelta(seconds=state["deadline"])) or
            #     (state["state"] == "down")):
            #     nice.check_and_stop_diff(float(cfx_data[i][2]), config.k_diff_order_stop, price_BTC)

            # Проверяем все ордера и если какой-то невыгодный по цене - стопаем его
            if ((state["state"] == "up" and time_now <= state["time_start"] + datetime.timedelta(seconds=state["deadline"])) or
                (state["state"] == "down")):
                nice.check_and_stop_price(max_profit_price, config.k_price_order_stop, price_BTC)

            if diff_now != state["diff"]:
                log.info(f"diff_old = {state['diff']} diff_new = {diff_now}")
                state["diff"] = diff_now

            csvwriter.writerow(row)
