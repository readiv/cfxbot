from datetime import datetime
from time import mktime
from func import time2int

def get_epoch_ms_from_now():
    now = datetime.now()
    now_ec_since_epoch = mktime(now.timetuple()) + now.microsecond / 1000000.0
    return int(now_ec_since_epoch * 1000)

print(get_epoch_ms_from_now())
print(time2int(datetime.now()))