import os
from concurrent.futures import ThreadPoolExecutor, as_completed
import WebAPI
import config
import util
import time
import db
import json
from collections import defaultdict
from typing import Dict, List, Tuple
import datetime


def fetch_valid_thread_tids_in_pages(uid: int, page_start: int, page_end: int):
    """
    返回 (tids: List[int], should_stop: bool)
    """
    tids = []
    should_stop = False

    with ThreadPoolExecutor(max_workers=max_workers_thread) as executor:
        futures = {
            executor.submit(api.get_user_threads, uid, p): p
            for p in range(page_start, page_end + 1)
        }
        page_results = {}
        for future in as_completed(futures):
            try:
                resp = future.result()
                page_results[future] = resp.get('rows', [])
            except Exception as e:
                print(f"[Thread] Page error: {e}")
                page_results[future] = []

    for rows in page_results.values():
        if not rows:
            should_stop = True
            continue
        for th in rows:
            dl = th['dateline']
            if dl > start_time:
                continue
            elif dl < stop_time:
                should_stop = True
                break
            else:
                tids.append(th['thread_id'])
    return tids, should_stop


def fetch_valid_reply_positions_in_pages(uid: int, page_start: int, page_end: int):
    """
    返回 (tid_positions: Dict[tid, List[position]], should_stop: bool)
    内部对 find_point 使用多线程加速
    """
    valid_post_ids = []
    should_stop = False

    # === 第一阶段：拉取 pages，收集有效 post_id ===
    with ThreadPoolExecutor(max_workers=max_workers_reply) as executor:
        futures = {
            executor.submit(api.get_user_replies, uid, p): p
            for p in range(page_start, page_end + 1)
        }
        page_results = {}
        for future in as_completed(futures):
            try:
                resp = future.result()
                page_results[future] = resp.get('rows', [])
            except Exception as e:
                print(f"[Reply] Page error: {e}")
                page_results[future] = []

    for rows in page_results.values():
        if not rows:
            should_stop = True
            continue
        for reply in rows:
            dl = reply['dateline']
            if dl > start_time:
                continue
            elif dl < stop_time:
                should_stop = True
                break
            else:
                valid_post_ids.append(reply['post_id'])

    # === 第二阶段：并发调用 find_point 获取 (tid, pos) ===
    tid_positions = defaultdict(list)

    if valid_post_ids:
        with ThreadPoolExecutor(max_workers=max_workers_position) as executor:  # 可更高，视 API 限流而定
            future_to_pid = {
                executor.submit(api.find_point, pid): pid
                for pid in valid_post_ids
            }
            for future in as_completed(future_to_pid):
                try:
                    tid, pos = future.result()
                    if tid and pos:  # 防御性检查
                        tid_positions[tid].append(pos)
                except Exception as e:
                    pid = future_to_pid[future]
                    print(f"[find_point] post_id={pid} failed: {e}")
                    # 可选：记录失败或跳过

    return dict(tid_positions), should_stop


def get_user_thread_position_dict(uid) -> dict[int, list[int]]:
    result = defaultdict(list)
    BATCH_SIZE = 10

    # --- Threads: position = 1 ---
    page = 1
    while True:
        end_page = page + BATCH_SIZE - 1
        tids, stop = fetch_valid_thread_tids_in_pages(uid, page, end_page)
        for tid in tids:
            result[tid].append(1)
        if stop:
            global_info['thread_end_page'] = end_page
            break
        page = end_page + 1

    # --- Replies: 并发获取 position ---
    page = 1
    while True:
        end_page = page + BATCH_SIZE - 1
        tid_pos_dict, stop = fetch_valid_reply_positions_in_pages(uid, page, end_page)
        for tid, positions in tid_pos_dict.items():
            result[tid].extend(positions)
        if stop:
            global_info['reply_end_page'] = end_page
            break
        page = end_page + 1

    return dict(result)


# def get_user_thread_position_dict_old(uid) -> dict[int, list[int]]:
#     """
#     获取指定uid在本年的主题帖tid列表
#
#     返回示例:
#     {111:[1,3],222:[2,4]}
#     格式{tid:[positions],...}
#     """
#     result = defaultdict(list)
#     page = 1
#     stop = False
#     while True:
#         if page % 10 == 0:
#             print(f'[{time.asctime()}] thread 进度 {page}', end='\r')
#         r = api.get_user_threads(uid, page)
#         rows = r.get('rows', [])
#         if not rows:
#             break
#         for thread in rows:
#             if thread['dateline'] < stop_time:
#                 stop = True
#                 break
#             result[thread['thread_id']].append(1)
#         if stop or len(rows) < 20 or r['total'] <= page * 20:
#             break
#         page += 1
#     print(f'[{time.asctime()}] thread 终止页 {page}')
#     global_info['thread_end_page'] = page
#     page = 1
#     stop = False
#     while True:
#         if page % 10 == 0:
#             print(f'[{time.asctime()}] reply 进度 {page}', end='\r')
#         r = api.get_user_replies(uid, page)
#         rows = r.get('rows', [])
#         if not rows:
#             break
#         for reply in rows:
#             if reply['dateline'] < stop_time:
#                 stop = True
#                 break
#             tid, position = api.find_point(reply['post_id'])
#             result[tid].append(position)
#         if stop or len(rows) < 20 or r['total'] <= page * 20:
#             break
#         page += 1
#     print(f'[{time.asctime()}] reply 终止页 {page}')
#     global_info['reply_end_page'] = page
#     return result


# def get_posts_old(tid: int, page_and_position: dict[int, list[int]]) -> list:
#     result = []
#     r = api.get_thread_reply_page(tid, 1, 1)
#     thread_info = r.get('thread', {})
#     rows = r.get('rows', [])
#     t_pid = rows[0]['post_id']
#     t_user = rows[0]['author']
#     t_subject = thread_info['subject']
#     for page, positions in page_and_position.items():
#         if page == 1 and 1 in positions:
#             for post in rows:
#                 if post['position'] == 1:
#                     post['views'] = thread_info.get('views')
#                     post['replies'] = thread_info.get('replies')
#                     post['favorite'] = thread_info.get('favorite_times')
#                 if post['position'] in positions:
#                     if post['position'] != 1:
#                         _ = util.get_reply_pid_and_username(post)
#                         post['reply_pid'], post['reply_user'] = (t_pid, t_user) if _ is None else _
#                         post['subject'] = t_subject
#                     result.append(post)
#         else:
#             r = api.get_thread_reply_page(tid, page)
#             rows = r.get('rows', [])
#             for post in rows:
#                 if post['position'] in positions:
#                     if post['position'] != 1:
#                         _ = util.get_reply_pid_and_username(post)
#                         post['reply_pid'], post['reply_user'] = (t_pid, t_user) if _ is None else _
#                         post['subject'] = t_subject
#                     result.append(post)
#     return result


def fetch_all_posts_parallel(tid_page_position_dict: Dict[int, Dict[int, List[int]]]) -> List[dict]:
    """
    并发拉取所有需要的帖子内容，每个 (tid, page) 作为独立任务。
    """
    # 扁平化任务
    tasks: List[Tuple[int, int, List[int]]] = []
    for tid, page_pos in tid_page_position_dict.items():
        for page, positions in page_pos.items():
            tasks.append((tid, page, positions))

    all_posts = []

    with ThreadPoolExecutor(max_workers=max_workers_posts) as executor:
        # 提交所有任务
        future_to_task = {
            executor.submit(_fetch_tid_page_posts, tid, page, positions): (tid, page)
            for (tid, page, positions) in tasks
        }

        # 收集结果
        for future in as_completed(future_to_task):
            tid, page = future_to_task[future]
            try:
                posts = future.result()
                all_posts.extend(posts)
            except Exception as e:
                print(f"[ERROR] Failed to fetch tid={tid}, page={page}: {e}")

    return all_posts


def _fetch_tid_page_posts(tid: int, page: int, positions: List[int]) -> List[dict]:
    """
    拉取指定 tid 的某一页，并筛选出 positions 中的帖子，注入必要字段。
    """
    # 关键：thread_details=1 → 任意页都能拿到 thread 信息！
    resp = api.get_thread_reply_page(tid, page=page, thread_details=1)

    thread_info = resp.get('thread', {})
    rows = resp.get('rows', [])

    # 找到主帖（position=1）的 post_id 和 author
    main_post_id = None
    for post in rows:
        if post.get('position') == 1:
            main_post_id = post['post_id']
            break

    main_author = thread_info.get('author')
    subject = thread_info.get('subject', '')

    result = []
    for post in rows:
        pos = post.get('position')
        if pos not in positions:
            continue

        post = post.copy()  # 避免副作用

        if pos == 1:
            # 主帖：注入统计信息
            post['views'] = thread_info.get('views')
            post['replies'] = thread_info.get('replies')
            post['favorite'] = thread_info.get('favorite_times')  # 如果 API 不返回，就是 None
        else:
            # 回复：注入引用信息
            _ = util.get_reply_pid_and_username(post)
            post['reply_pid'], post['reply_user'] = (
                (main_post_id, main_author) if _ is None else _
            )
            post['subject'] = subject

        result.append(post)

    return result


def main():
    while True:
        task = util.get_next_task()
        if task is None:
            print(f'[{time.asctime()}] 无事', end='\r')
            time.sleep(60)
            continue
        uid = task['uid']
        print(f'[{time.asctime()}] 开始处理uid: {uid}')
        task['get_data_start'] = int(time.time())
        db_conn = db.get_conn(uid)
        db.init_db(db_conn)
        user_info = api.get_user_info(uid, True)
        db.insert_user_info(db_conn, uid, json.dumps(user_info, ensure_ascii=False, separators=(',', ':')))
        tid_position_dict = get_user_thread_position_dict(uid)
        tid_count = len(tid_position_dict)
        print(f'[{time.asctime()}] 获取到相关tid数: {tid_count}')
        global_info['tid_count'] = tid_count
        tid_page_position_dict = util.set_page(tid_position_dict)
        all_posts = fetch_all_posts_parallel(tid_page_position_dict)
        db.insert_posts(db_conn, all_posts)
        db_conn.close()
        task['get_data_stop'] = int(time.time())
        task |= global_info
        print(f'[{time.asctime()}] 完成uid: {uid}')
        util.save_task_metadata(uid, task)
        os.system(f'python generate_report.py {uid}')
        print(f'[{time.asctime()}] 报告生成完成: {uid}')


if __name__ == '__main__':
    max_workers_thread = 10
    max_workers_reply = 10
    max_workers_position = 10
    max_workers_posts = 10
    target_year = config.year
    tz_utc8 = datetime.timezone(datetime.timedelta(hours=8))
    start_time = int(datetime.datetime(target_year, 12, 31, 23, 59, 59, tzinfo=tz_utc8).timestamp())
    stop_time = int(datetime.datetime(target_year, 1, 1, 0, 0, 0, tzinfo=tz_utc8).timestamp())
    api: WebAPI.WebAPI = WebAPI.WebAPI(config.username, config.password)
    util.init_folder()
    global_info = {}
    main()
