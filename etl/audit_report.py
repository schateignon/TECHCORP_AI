import json
from common.db import database
from common.indicators import indicators

if __name__ == "__main__":
    with database("etl") as conn:
        print(json.dumps(indicators(conn), default=str, ensure_ascii=False, indent=2))
