import logging, os, datetime as dt

def setup_logger():
    os.makedirs("logs", exist_ok=True)
    ts = dt.datetime.now().strftime("%Y%m%d-%H%M%S")
    logfile = f"logs/run-{ts}.log"
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(levelname)s | %(message)s",
        handlers=[
            logging.FileHandler(logfile, encoding="utf-8"),
            logging.StreamHandler()
        ],
    )
    return logging.getLogger("runner"), logfile
