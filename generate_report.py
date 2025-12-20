import sys
import time
import db
import json
import util
from datetime import datetime
import config


def get_yearly_post_counts(db_conn, year: int):
    """
    获取指定自然年的每日发帖量（仅返回 >0 的天）

    返回: dict { "MM-DD": count }
    """
    # 构造该年 1月1日 00:00:00 和 下一年 1月1日 00:00:00 的时间戳（东八）
    start_dt = datetime(year, 1, 1)
    end_dt = datetime(year + 1, 1, 1)

    start_ts = int(start_dt.timestamp())
    end_ts = int(end_dt.timestamp())

    cursor = db_conn.cursor()
    cursor.execute("""
        SELECT 
            strftime('%m-%d', datetime(dateline, 'unixepoch', 'localtime')) AS mm_dd,
            COUNT(*) AS count
        FROM posts
        WHERE dateline >= ? AND dateline < ?
        GROUP BY mm_dd
        ORDER BY mm_dd
    """, (start_ts, end_ts))

    # 只返回有发帖的日期（COUNT >= 1）
    return {row[0]: row[1] for row in cursor.fetchall()}


def get_all_top_tied(ranked_list):
    """
    从已降序排序的列表中取出所有并列第一的项。
    每个元素是 list/tuple，最后一个元素是排序值（数值）。

    返回: list of items（若输入为空则返回空 list）
    """
    if not ranked_list:
        return []

    max_value = ranked_list[0][-1]  # 第一个的排序值就是最大值
    result = []
    for item in ranked_list:
        if item[-1] == max_value:
            result.append(item)
        else:
            break  # 因为已排序，一旦小于就不用继续了
    return result


def main():
    report = {
        'user': {},
        'summary': {},
        'first_and_last': {},
        'support_and_oppose': {},
        'popularity': {},
        'personal_favorite': {},
        'rank': {}
    }
    db_conn = db.get_conn(uid)
    cursor = db_conn.cursor()
    user_info = db.get_user_info(db_conn, uid)
    user_summary = user_info['user_summary']
    report['user']['uid'] = uid
    report['user']['username'] = user_summary['username']
    report['user']['group_title'] = user_summary['group_title']
    report['user']['group_subtitle'] = user_summary['group_subtitle']
    report['user']['register_time'] = user_info['register_time']
    # 主题总数，回复总数
    cursor.execute("""
            SELECT 
                SUM(CASE WHEN position = 1 THEN 1 ELSE 0 END) AS count_pos_1,
                SUM(CASE WHEN position != 1 THEN 1 ELSE 0 END) AS count_pos_not_1
            FROM posts
        """)
    row = cursor.fetchone()
    report['summary']['thread'] = row[0] or 0
    report['summary']['reply'] = row[1] or 0
    report['summary']['all'] = report['summary']['thread'] + report['summary']['reply']
    # 最早的主题帖
    cursor.execute("""
            SELECT position, dateline, tid, pid, subject, message
            FROM posts
            WHERE position = 1
            ORDER BY dateline ASC
            LIMIT 1
        """)
    report['first_and_last']['first_thread'] = cursor.fetchone()
    # 最晚的主题帖
    cursor.execute("""
            SELECT position, dateline, tid, pid, subject, message
            FROM posts
            WHERE position = 1
            ORDER BY dateline DESC
            LIMIT 1
        """)
    report['first_and_last']['last_thread'] = cursor.fetchone()
    # 最早的回复
    cursor.execute("""
            SELECT position, dateline, tid, pid, subject, message
            FROM posts
            WHERE position != 1
            ORDER BY dateline ASC
            LIMIT 1
        """)
    report['first_and_last']['first_reply'] = cursor.fetchone()
    # 最晚的回复
    cursor.execute("""
            SELECT position, dateline, tid, pid, subject, message
            FROM posts
            WHERE position != 1
            ORDER BY dateline DESC
            LIMIT 1
        """)
    report['first_and_last']['last_reply'] = cursor.fetchone()
    # 点赞总计/点踩总计
    cursor.execute("""
            SELECT 
                COALESCE(SUM(support), 0) AS total_support,
                COALESCE(SUM(oppose), 0) AS total_oppose
            FROM posts
        """)
    row = cursor.fetchone()
    report['support_and_oppose']['total_support'] = row[0]
    report['support_and_oppose']['total_oppose'] = row[1]
    # 主题帖点赞排行
    cursor.execute("""
            SELECT tid, pid, subject, message, dateline, support
            FROM posts
            WHERE position = 1 AND support > 0
            ORDER BY support DESC
            LIMIT 20
        """)
    report['rank']['thread_support'] = cursor.fetchall()
    # 主题帖点踩排行
    cursor.execute("""
            SELECT tid, pid, subject, message, dateline, oppose
            FROM posts
            WHERE position = 1 AND oppose > 0
            ORDER BY oppose DESC
            LIMIT 20
        """)
    report['rank']['thread_oppose'] = cursor.fetchall()
    # 回复点赞排行
    cursor.execute("""
            SELECT tid, pid, position, subject, message, dateline, support
            FROM posts
            WHERE position != 1 AND support > 0
            ORDER BY support DESC
            LIMIT 20
        """)
    report['rank']['reply_support'] = cursor.fetchall()
    # 回复点踩排行
    cursor.execute("""
            SELECT tid, pid, position, subject, message, dateline, oppose
            FROM posts
            WHERE position != 1 AND oppose > 0
            ORDER BY oppose DESC
            LIMIT 20
        """)
    report['rank']['reply_oppose'] = cursor.fetchall()
    # 被 点赞/点踩 最多的主题帖/回复
    report['support_and_oppose']['thread_most_support'] = get_all_top_tied(report['rank']['thread_support'])
    report['support_and_oppose']['thread_most_oppose'] = get_all_top_tied(report['rank']['thread_oppose'])
    report['support_and_oppose']['reply_most_support'] = get_all_top_tied(report['rank']['reply_support'])
    report['support_and_oppose']['reply_most_oppose'] = get_all_top_tied(report['rank']['reply_oppose'])
    # 回复主题帖排行
    cursor.execute("""
            SELECT tid, subject, COUNT(*) AS reply_count
            FROM posts
            WHERE position != 1
            GROUP BY tid
            ORDER BY reply_count DESC
            LIMIT 20
        """)
    report['rank']['reply_thread'] = cursor.fetchall()
    # 被回复的主题帖排行
    cursor.execute("""
            SELECT tid, subject, replies
            FROM posts
            WHERE position = 1 AND replies > 0
            ORDER BY replies DESC
            LIMIT 20
        """)
    report['rank']['thread_replies'] = cursor.fetchall()
    # 主题帖浏览量排行
    cursor.execute("""
            SELECT tid, subject, views
            FROM posts
            WHERE position = 1 AND views > 0
            ORDER BY views DESC
            LIMIT 20
        """)
    report['rank']['thread_views'] = cursor.fetchall()
    # 主题帖收藏量排行
    cursor.execute("""
            SELECT tid, subject, favorite
            FROM posts
            WHERE position = 1 AND favorite > 0
            ORDER BY favorite DESC
            LIMIT 20
        """)
    report['rank']['thread_favorite'] = cursor.fetchall()
    # 回复最多的主题帖
    report['popularity']['reply_thread_most'] = get_all_top_tied(report['rank']['reply_thread'])
    # 被回复最多的主题帖
    report['popularity']['thread_replies_most'] = get_all_top_tied(report['rank']['thread_replies'])
    # 浏览量最多的帖子
    report['popularity']['thread_views_most'] = get_all_top_tied(report['rank']['thread_views'])
    # 被收藏最多的帖子
    report['popularity']['thread_favorite_most'] = get_all_top_tied(report['rank']['thread_favorite'])
    # 版块发帖排行
    cursor.execute("""
            SELECT fid, COUNT(*) AS post_count
            FROM posts
            WHERE fid IS NOT NULL
            GROUP BY fid
            ORDER BY post_count DESC
            LIMIT 20
        """)
    report['rank']['forum_post'] = cursor.fetchall()
    # 插入fid名称
    new_forum_post = []
    for item in report['rank']['forum_post']:
        new_forum_post.append((item[0], item[1], util.get_fid_name(item[0])))
    report['rank']['forum_post'] = new_forum_post
    # 最喜欢的分区（发表主题帖和回复总和）
    report['personal_favorite']['forum_most_favorite'] = get_all_top_tied(report['rank']['forum_post'])
    # 回复的人排行
    cursor.execute("""
            SELECT reply_user, COUNT(*) AS reply_count
            FROM posts
            WHERE position != 1 
              AND reply_user IS NOT NULL 
              AND reply_user != ''
            GROUP BY reply_user
            ORDER BY reply_count DESC
            LIMIT 20
        """)
    report['rank']['reply_user'] = cursor.fetchall()
    # 回复最多的人
    report['personal_favorite']['reply_user_most'] = get_all_top_tied(report['rank']['reply_user'])
    # 每天发帖量
    report['summary']['post_count_per_day'] = get_yearly_post_counts(db_conn, config.year)
    # 发帖天数
    report['summary']['post_days'] = len(report['summary']['post_count_per_day'])

    # 写入文件
    with open(f'data/user/{uid}/report.json', 'w', encoding='utf-8') as f:
        # json.dump(report, f, ensure_ascii=False, separators=(',', ':'))
        json.dump(report, f, ensure_ascii=False, indent=4)
    # 更新task文件
    with open(f'data/user/{uid}/task.json', 'r', encoding='utf-8') as f:
        task = json.load(f)
    task['generate_report'] = int(time.time())
    with open(f'data/user/{uid}/task.json', 'w', encoding='utf-8') as f:
        json.dump(task, f, ensure_ascii=False, separators=(',', ':'))


if __name__ == '__main__':
    argv = sys.argv[1:]
    if not argv:
        print('No uid')
        exit()
    try:
        uid = int(argv[0])
    except ValueError:
        print('Invalid uid')
        exit()
    main()
