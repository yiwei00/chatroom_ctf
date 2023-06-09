import argparse
import tempfile
import os
import signal
from server import ChatServer
from log4py import Log4py
from datetime import datetime

# a simple multi-threaded socket chat server

def main(**kwargs):
    host = kwargs['host']
    port = kwargs['port']
    logfile = kwargs['log']
    log_dir = kwargs['log_dir']
    #region setting up the log file
    if logfile is None:
        prog_name = os.path.basename(__file__)
        prog_name = os.path.splitext(prog_name)[0]
        date = datetime.now().strftime('%Y-%m-%d')
        logfile = f'{prog_name}-{date}.log'
        logpath = os.path.join(log_dir, logfile)
        n = 0
        while os.path.exists(logpath):
            n += 1
            logfile = f'{prog_name}-{date}({n}).log'
            logpath = os.path.join(log_dir, logfile)
    logpath = os.path.join(log_dir, logfile)
    logger = Log4py(logpath)
    #endregion
    server = ChatServer(host=host, port=port, logger=logger)
    signal.signal(signal.SIGINT, lambda sig, frame: server.stop())
    signal.signal(signal.SIGTERM, lambda sig, frame: server.stop())
    server.run()


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('-a', '--addr', type=str, default='0.0.0.0', help='listening address')
    parser.add_argument('-p', '--port', type=int, default=5000, help='listening port')
    parser.add_argument('-l', '--log', type=str, default= None, help='log file name, defaults to chatroom-YYYY-MM-DD.log')
    parser.add_argument('--log-dir', type=str, default=tempfile.gettempdir(), help='directory to store log files, defaults to system temp dir')
    main(
        host=parser.parse_args().addr,
        port=parser.parse_args().port,
        log=parser.parse_args().log,
        log_dir=parser.parse_args().log_dir
    )