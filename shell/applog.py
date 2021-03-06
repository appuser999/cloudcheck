import os, time
class Applog :
    def __init__(self):
        logfile = os.getcwd() + "\\log\\" + time.strftime("%Y%m%d", time.localtime()) + ".log"
        self.fp = open(logfile, 'a')
        return

    def addLog(self, log):
        log = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime()) + "  " + log
        print(log)
        self.fp.write(log + '\n')
        self.fp.flush()
        return

    def closeLofile(self):
        self.fp.close()
        return

def logRun(file):
    def decorator(fun):
        def wrapper(*args, **kwargs):
            file.addLog(fun.__name__)
            return fun(*args)
        return wrapper
    return decorator
