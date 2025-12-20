import os
import json
from pathlib import Path
import shutil


def init_folder():
    """初始化文件夹"""
    os.makedirs('data/user', exist_ok=True)
    os.makedirs('data/queue', exist_ok=True)
    os.makedirs('data/read', exist_ok=True)


def get_next_task() -> dict | None:
    """获取下一个任务

    从 'data/queue' 目录中：
      - 找到所有纯数字命名的文件（无后缀）
      - 按 **修改时间（mtime）从早到晚** 排序
      - 取最早的一个，解析为 JSON
      - 将该文件移入 'data/read'（无论成功与否）
      - 返回解析结果

    异常处理：
      - 若目录不存在或为空 → 返回 None
      - 若文件名非纯数字 → 跳过（不处理）
      - 若 JSON 解析失败 → 移动文件到 read，返回 None
      - 若解析结果不是 dict[str, int] → 移动文件到 read，返回 None
    """
    queue_dir = Path("data/queue")
    read_dir = Path("data/read")

    # 确保 read 目录存在
    read_dir.mkdir(parents=True, exist_ok=True)

    if not queue_dir.exists():
        return None

    # 收集所有“纯数字命名”的文件
    numeric_files = []
    for f in queue_dir.iterdir():
        if f.is_file() and f.name.isdigit():
            try:
                # 获取修改时间（用于排序）
                mtime = f.stat().st_mtime
                numeric_files.append((f, mtime))
            except OSError:
                # 如果无法获取 stat（如文件被删除），跳过
                continue

    if not numeric_files:
        return None

    # 按修改时间升序排序（最早的时间在前）
    numeric_files.sort(key=lambda x: x[1])
    first_file = numeric_files[0][0]
    target_path = read_dir / first_file.name

    try:
        # 读取并解析 JSON
        with open(first_file, 'r', encoding='utf-8') as f:
            data = json.load(f)

        # 验证类型：必须是 dict[str, int]
        if isinstance(data, dict):
            for k, v in data.items():
                if not (isinstance(k, str) and isinstance(v, int)):
                    raise ValueError("Not dict[str, int]")
        else:
            raise ValueError("Not a dict")

        # 成功解析后，移动文件到 read
        shutil.move(str(first_file), str(target_path))
        return data

    except (json.JSONDecodeError, ValueError, OSError, UnicodeDecodeError) as e:
        # 任何错误都移动坏文件到 read（避免重复处理）
        try:
            shutil.move(str(first_file), str(target_path))
        except (OSError, shutil.Error):
            # 如果移动失败（如目标已存在），尝试删除原文件
            first_file.unlink(missing_ok=True)
        return None


def get_reply_pid_and_username(post: dict):
    if post['position'] == 1:
        return None
    form = post['format']
    match form:
        case 0:
            message = post['message']
            if message.startswith('[quote][size=2][url=forum.php?mod=redirect&goto=findpost'):
                try:
                    _ = message.removeprefix('[quote][size=2][url=forum.php?mod=redirect&goto=findpost&pid=')
                    reply_pid = _.split('&')[0]
                    username = _.split('][color=#999999]')[1].split(' 发表于 ')[0]
                    return reply_pid, username
                except ValueError:
                    return None
        case 2:
            message = post['message']
            if message.startswith('> ') and ' 发表于 [' in message and '](/goto/' in message:
                try:
                    _ = message.split('](/goto/')
                    reply_pid = int(_[1].split(')\n> ')[0])
                    username = _[0][2:].split(' 发表于')[0]
                    return reply_pid, username
                except ValueError:
                    return None
    return None


def save_task_metadata(uid: int, task: dict):
    with open(f'data/user/{uid}/task.json', 'w', encoding='utf-8') as f:
        json.dump(task, f, ensure_ascii=False, separators=(',', ':'))


def set_page(tid_position_dict: dict[int, list[int]], page_size: int = 20) -> dict[int, dict[int, list[int]]]:
    """
    根据 position 的数值范围分页（每页包含 page_size 个连续位置）

    例如 page_size=20:
        position 1~20   → page 1
        position 21~40  → page 2
        position 41~60  → page 3
        ...

    输入: {tid: [pos1, pos2, ...]} （列表应已排序）
    输出: {tid: {page_num: [pos_in_this_page_range]}}
    """
    result = {}

    for tid, positions in tid_position_dict.items():
        # 跳过空列表
        if not positions:
            result[tid] = {}
            continue

        # 按页码分组
        pages = {}
        for pos in positions:
            # 计算 position 所属页码（从 1 开始）
            page_num = (pos - 1) // page_size + 1

            if page_num not in pages:
                pages[page_num] = []
            pages[page_num].append(pos)

        result[tid] = pages

    return result


def get_fid_name(fid: int) -> str:
    mapping = {
        "1": "站务管理",
        "2": "站务公告",
        "17": "同城同乡",
        "20": "学术交流",
        "25": "水手之家",
        "42": "经典图吧",
        "44": "时政要闻",
        "45": "情感专区",
        "46": "站务综合",
        "55": "视觉艺术",
        "61": "二手专区",
        "66": "电子数码",
        "70": "程序员之家",
        "74": "音乐空间",
        "95": "科技学术",
        "109": "成电轨迹",
        "111": "店铺专区",
        "114": "文人墨客",
        "115": "军事国防",
        "118": "体坛风云",
        "121": "IC电设",
        "134": "外语学习",
        "140": "动漫时代",
        "146": "清水书院",
        "149": "影视天地",
        "156": "篮球部落",
        "157": "天下足球",
        "159": "版主申请",
        "162": "古典文字",
        "174": "就业创业",
        "183": "兼职信息发布栏",
        "199": "保研考研",
        "201": "生活信息",
        "203": "休闲娱乐",
        "207": "原创翻唱",
        "208": "社团交流中心",
        "214": "招聘信息发布栏",
        "216": "家族专区",
        "219": "出国留学",
        "222": "评优专区",
        "225": "交通出行",
        "236": "校园热点",
        "237": "毕业感言",
        "244": "成电骑迹",
        "248": "论坛周年庆活动专版",
        "255": "房屋租赁",
        "256": "Matlab技术交流",
        "259": "海外成电",
        "260": "交换学习\\u0026CSC",
        "261": "资源汇总",
        "262": "飞跃阁",
        "263": "职场交流",
        "267": "非技术岗位",
        "273": "成电校园",
        "305": "失物招领",
        "308": "LaTeX技术交流",
        "309": "成电锐评",
        "312": "跑步家园",
        "313": "鹊桥",
        "316": "自然科学",
        "326": "新生专区",
        "334": "情系舞缘",
        "370": "吃喝玩乐",
        "371": "密语",
        "378": "晾晒专栏",
        "382": "考试专区",
        "383": "驾校考试",
        "387": "招生信息",
        "388": "抢楼活动版块",
        "389": "实习信息发布栏",
        "391": "拼车同行",
        "395": "藏经阁",
        "403": "部门直通车",
        "405": "电子科技大学医院",
        "410": "研究生院",
        "415": "后勤保障部",
        "420": "党委保卫部",
        "423": "党委学生工作部",
        "427": "前程似锦",
        "430": "公考选调",
        "433": "校团委（创新创业学院）",
        "434": "信息中心",
        "435": "大学生文化素质教育中心",
        "436": "体育部",
        "888": "投资理财",
        "889": "合作发展部",
        "891": "沙河校区管理办公室",
        "1024": "开发者专区"
    }
    return mapping.get(str(fid), f"未知({fid})")
