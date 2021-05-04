import logging, sys, inspect, os, datetime, config, time

class Profiler(object):
    def __enter__(self):
        self._startTime = time.time()
              
    def __exit__(self, type, value, traceback):
        # print("Elapsed time: {:.3f} sec".format(time.time() - self._startTime))
        pass

def get_script_dir(follow_symlinks=True):
    if getattr(sys, 'frozen', False): # py2exe, PyInstaller, cx_Freeze
        path = os.path.abspath(sys.executable)
    else:
        path = inspect.getabsfile(get_script_dir)
    if follow_symlinks:
        path = os.path.realpath(path)
    return os.path.dirname(path)

_log_format = f"%(asctime)s - [%(levelname)s] - (%(filename)s).%(funcName)s(%(lineno)d) - %(message)s"

def get_file_handler():
    file_handler = logging.FileHandler(str(get_script_dir()) + f"/logs/{datetime.datetime.now().strftime(config.log_name_template)}.log")
    file_handler.setLevel(logging.INFO)
    file_handler.setFormatter(logging.Formatter(_log_format))
    return file_handler

def get_stream_handler():
    stream_handler = logging.StreamHandler()
    stream_handler.setLevel(logging.INFO)
    stream_handler.setFormatter(logging.Formatter(_log_format))
    return stream_handler

def get_logger(name):
    logger = logging.getLogger(name)
    logger.setLevel(logging.WARNING)
    # logger.setLevel(logging.INFO)
    logger.addHandler(get_file_handler())
    logger.addHandler(get_stream_handler())
    return logger

if __name__ == "__main__":
    print(str(get_script_dir()))