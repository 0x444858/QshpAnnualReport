import os
import sys
import json
import time
import shutil
from pathlib import Path


def main():
    if len(sys.argv) < 2:
        print("Usage: python enqueue_uids.py <uid1> [uid2] [uid3] ...", file=sys.stderr)
        sys.exit(1)

    # 解析并验证 UID
    uids = []
    for arg in sys.argv[1:]:
        try:
            uid = int(arg)
            if uid <= 0:
                raise ValueError("UID must be positive")
            uids.append(uid)
        except ValueError as e:
            print(f"Invalid UID '{arg}': {e}", file=sys.stderr)
            sys.exit(1)

    # 确保目录存在
    temp_dir = Path("data/temp")
    queue_dir = Path("data/queue")
    temp_dir.mkdir(parents=True, exist_ok=True)
    queue_dir.mkdir(parents=True, exist_ok=True)

    current_time = int(time.time())  # 当前时间戳

    for uid in uids:
        filename = str(uid)
        temp_path = temp_dir / filename
        queue_path = queue_dir / filename

        # 准备数据
        data = {
            "uid": uid,
            "create_time": current_time
        }

        # 写入临时文件（覆盖已存在）
        with open(temp_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, separators=(',', ':'))  # 紧凑格式，无空格

        # 移动到队列目录（覆盖目标）
        shutil.move(str(temp_path), str(queue_path))

        print(f"Enqueued UID {uid} -> {queue_path}")


if __name__ == "__main__":
    main()
