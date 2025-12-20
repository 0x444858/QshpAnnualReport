import sqlite3
import os
import json


def get_conn(uid: int) -> sqlite3.Connection:
    os.makedirs(f'data/user/{uid}', exist_ok=True)
    return sqlite3.connect(f'data/user/{uid}/post.db')


def init_db(conn: sqlite3.Connection):
    """初始化数据库：创建 user_info 和 posts 表"""
    cursor = conn.cursor()

    # 创建 user_info 表
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS user_info (
            uid INTEGER PRIMARY KEY,
            info TEXT
        )
    ''')

    # 创建 posts 表
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS posts (
            tid INTEGER NOT NULL,
            pid INTEGER PRIMARY KEY NOT NULL,
            fid INTEGER NOT NULL,
            reply_pid INTEGER DEFAULT 0,
            reply_user TEXT,
            position INTEGER NOT NULL,
            subject TEXT,
            message TEXT,
            dateline INTEGER NOT NULL,
            views INTEGER DEFAULT 0,
            replies INTEGER DEFAULT 0,
            support INTEGER DEFAULT 0,
            oppose INTEGER DEFAULT 0,
            favorite INTEGER DEFAULT 0
        )
    ''')

    conn.commit()


def insert_user_info(conn: sqlite3.Connection, uid: int, info: str):
    """插入用户摘要信息"""
    cursor = conn.cursor()
    cursor.execute('INSERT INTO user_info (uid, info) VALUES (?, ?)'
                   'ON CONFLICT(uid) DO UPDATE SET info = excluded.info', (uid, info))
    conn.commit()


def insert_posts(conn: sqlite3.Connection, posts: list[dict]):
    """批量插入帖子信息"""
    if not posts:
        return

    keys = [
        'thread_id', 'post_id', 'forum_id', 'reply_pid', 'reply_user', 'position', 'subject', 'message', 'dateline',
        'views', 'replies', 'support', 'oppose', 'favorite'
    ]

    data = [
        tuple(post.get(k) for k in keys)
        for post in posts
    ]
    cursor = conn.cursor()
    cursor.executemany(
        'INSERT OR REPLACE INTO posts (tid, pid, fid, reply_pid, reply_user, position, subject, message, dateline,'
        'views, replies, support, oppose, favorite) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)',
        data)
    conn.commit()


def get_user_info(conn: sqlite3.Connection, uid: int) -> dict:
    """获取用户摘要信息"""
    cursor = conn.cursor()
    cursor.execute('SELECT info FROM user_info WHERE uid = ?', (uid,))
    result = cursor.fetchone()
    if result:
        return json.loads(result[0])
    else:
        return {}
