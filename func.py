import datetime, requests
from config import private_api, algorithm, time_order

import logger
log = logger.get_logger(__name__)

def int2time(time:int):
    time_since = datetime.datetime(1970, 1, 1, 1) + datetime.timedelta(seconds=time)
    return time_since

def time2int(time: datetime):
    return int((time - datetime.datetime(1970, 1, 1, 1)).total_seconds())

def time2float(time: datetime):
    return float((time - datetime.datetime(1970, 1, 1, 1)).total_seconds())

def reward2float(reward:str):
    while len(reward)<19:
        reward = "0" + reward
    reward = reward[:1] + "." + reward[1:9]
    return float(reward)

def get_api(url:str, wallet:str=""):
    url = url.replace(":wallet",wallet)

    response = requests.get(url, params={"format":"json"})

    if response.status_code != 200:
        log.info(f"Error. response.status_code = {response.status_code}")
        return None

    try:
        result = response.json()
        return result
    except:
        log.info(f"Error convert json. response.text = {response.text}")
        return None

def get_power(x1,y1,x2,y2,max_price,market,depth):
    x = (x1 + x2) / 2
    y = float(private_api.get_hashpower_fixedprice(market, algorithm, x )["fixedPrice"])
    if y == 0:
        return 0
    if depth == 0:
        return x
    if y <= max_price:
        return get_power(x,y,x2,y2,max_price,market,depth - 1)
    else:
        return get_power(x1,y1,x,y,max_price,market,depth - 1)

def calc_order_param(max_price, market, balance_available):
    """ Возвращает price, limit, amount для рынка market, что бы цена не превысила max_price """
    temp = private_api.get_hashpower_fixedprice(market, algorithm, 0.001) 
    x1 = 0.001
    x2 = 0.95*float(temp["fixedMax"])
    y1 = float(temp["fixedPrice"])
    y2 = float(private_api.get_hashpower_fixedprice(market, algorithm, x2)["fixedPrice"])
    if x2 == 0 or y1 == 0 or y2 == 0 or y1 > max_price:
        log.error(f"Error: x2:{x2} == 0 or y1:{y1} == 0 or y2:{y2} == 0 or y1:{y1} > max_price:{max_price}")
        return None, None, None
    if y2 < max_price:
        limit_power = 2 * x2 / 3 # 2/3 от расчетной
    else:
        limit_power = round(2*get_power(x1,y1,x2,y2,max_price,market,5)/3,3)
    if limit_power == 0:
        log.error(f"limit_power:{limit_power} == 0")
        return None, None, None

    price_power = float(private_api.get_hashpower_fixedprice(market, algorithm, limit_power)["fixedPrice"])
    if price_power == 0:
        log.error(f"price_power:{price_power} == 0")
        return None, None, None

    # log.info(f"it should be: power={power}. price_power={price_power} amount{power * price_power * 3 / 24}")
    # power = 0.001 #пока ограничим мощьность
    # price_power = float(private_api.get_hashpower_fixedprice(market, config.algorithm, power)["fixedPrice"])
    
    amount = limit_power * price_power * time_order / 24 #Из рассчета что бы хватило на time_order часа

    if amount<0.001:
        amount = 0.001
    if balance_available < 0.001: 
        log.error(f"Balance is close to zero. amount= {amount} balance_available = {balance_available}")
        return None, None, None
    if amount > balance_available:
        limit_power = round(0.99 * (limit_power * balance_available - 0.0005) / amount,3)
        if limit_power < 0:
            return None, None, None
        price_power = float(private_api.get_hashpower_fixedprice(market, algorithm, limit_power)["fixedPrice"])
    return price_power, limit_power, amount 

def get_pool_id(market):
    try:
        pools = private_api.get_my_pools("page", 100)["list"]
        for pool in pools:
            if pool["algorithm"] == algorithm:
                if pool["name"].split(":")[0] == market:
                    return pool["id"]
    except Exception as e:
        log.error(str(e))
    return None