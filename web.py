from pathlib import Path
from flask import Flask, request, jsonify
import os
import json
import config
import mobcentAPI
import time
import shutil

app = Flask(__name__, static_folder='static', static_url_path='/AnnualReport/static')


@app.route('/AnnualReport/')
def index():
    return app.send_static_file('index.html')


@app.route('/AnnualReport/user_status/')
def user_status():
    return app.send_static_file('user_status.html')


@app.route('/AnnualReport/report/')
def report():
    return app.send_static_file('report.html')


@app.route('/AnnualReport/api/user_status')
def user_status_api():
    uid = request.args.get('uid')

    if not uid:
        return jsonify({
            "code": 1,
            "message": "缺少 uid 参数",
            "status": "错误"
        }), 400

    try:
        uid_int = int(uid)
        uid_str = str(uid_int)
    except (ValueError, TypeError):
        return jsonify({
            "code": 1,
            "message": "uid 必须为整数",
            "status": "错误"
        }), 400

    user_dir = os.path.join('data', 'user', uid_str)
    post_db_path = os.path.join(user_dir, 'post.db')
    report_json_path = os.path.join(user_dir, 'report.json')
    task_json_path = os.path.join(user_dir, 'task.json')
    queue_file_path = os.path.join('data', 'queue', uid_str)

    # 获取 post.db 的大小（如果存在），否则为 0
    size = os.path.getsize(post_db_path) if os.path.exists(post_db_path) else 0

    # 1. 已完成？
    if os.path.exists(report_json_path):
        task_data = {}
        if os.path.exists(task_json_path):
            try:
                with open(task_json_path, 'r', encoding='utf-8') as f:
                    task_data = json.load(f)
            except (json.JSONDecodeError, OSError):
                task_data = {}

        return jsonify({
            "code": 0,
            "message": "年度报告已生成完成",
            "status": "完成",
            "size": size,
            "task": task_data
        })

    # 2. 正在获取数据？
    if os.path.exists(post_db_path):
        return jsonify({
            "code": 0,
            "message": "正在获取用户数据，请稍候",
            "status": "正在获取数据",
            "size": size
        })

    # 3. 在队列中？
    queue_dir = Path("data/queue")
    if os.path.isfile(queue_file_path):
        if queue_dir.exists() and queue_file_path.startswith(str(queue_dir)):
            # 收集所有纯数字命名的文件，并按 mtime 排序
            queue_files = []
            for f in queue_dir.iterdir():
                if f.is_file() and f.name.isdigit():
                    try:
                        mtime = f.stat().st_mtime
                        queue_files.append((f.name, mtime))
                    except OSError:
                        continue  # 跳过无法访问的文件

            # 按修改时间升序排序
            queue_files.sort(key=lambda x: x[1])

            # 查找当前 uid 的排名（从 1 开始）
            rank = None
            for idx, (fname, _) in enumerate(queue_files, start=1):
                if fname == uid_str:
                    rank = idx
                    break

            return jsonify({
                "code": 0,
                "message": "用户已在生成队列中",
                "status": "队列",
                "size": 0,
                "queue": rank
            })

    # 4. 未生成
    return jsonify({
        "code": 0,
        "message": "用户年度报告尚未生成",
        "status": "未生成",
        "size": 0
    })


@app.route('/AnnualReport/api/get_report')
def get_report_api():
    uid = request.args.get('uid')

    if not uid:
        return jsonify({
            "code": 1,
            "message": "缺少 uid 参数"
        }), 400

    try:
        uid = int(uid)
    except (ValueError, TypeError):
        return jsonify({
            "code": 1,
            "message": "uid 必须为整数"
        }), 400

    report_path = os.path.join('data', 'user', str(uid), 'report.json')

    if not os.path.exists(report_path):
        return jsonify({
            "code": 2,
            "message": "年度报告尚未生成或不存在"
        }), 404

    try:
        with open(report_path, 'r', encoding='utf-8') as f:
            report_data = json.load(f)
        return jsonify({
            "code": 0,
            "message": "成功",
            "data": report_data
        })
    except (json.JSONDecodeError, OSError) as e:
        return jsonify({
            "code": 3,
            "message": f"读取报告文件失败: {str(e)}"
        }), 500


@app.route('/AnnualReport/api/new_task', methods=['POST'])
def new_task_api():
    # 1. 检查请求是否为 JSON
    if not request.is_json:
        return jsonify({
            "code": 1,
            "message": "请求体必须是 JSON 格式"
        }), 400

    data = request.get_json()
    if not isinstance(data, dict):
        return jsonify({
            "code": 1,
            "message": "请求体必须是一个 JSON 对象"
        }), 400

    # 2. 提取并验证 uid 和 auth
    uid_raw = data.get('uid')
    auth = data.get('auth')

    try:
        uid = int(uid_raw)
        if uid <= 0:
            raise ValueError
    except (ValueError, TypeError):
        return jsonify({
            "code": 1,
            "message": "uid 必须是正整数"
        }), 400

    if not isinstance(auth, str) or not auth.strip():
        return jsonify({
            "code": 1,
            "message": "auth 必须是非空字符串"
        }), 400

    auth = auth.strip()

    # 3. 验证私信认证
    d = {uid: auth}
    success, result = m_api.check_pm(d, time_limit=600)

    if not success:
        return jsonify({
            "code": 4,
            "message": result or "私信验证失败"
        }), 400

    if not result.get(uid, False):
        return jsonify({
            "code": 5,
            "message": "未在最近 600 秒内收到包含指定认证字符串的私信"
        }), 400

    # 4. 检查是否已在队列中（防止重复）
    queue_dir = Path("data/queue")
    task_in_queue = queue_dir / str(uid)
    if task_in_queue.exists():
        return jsonify({
            "code": 6,
            "message": "该用户已在生成队列中，请勿重复提交"
        }), 409

    # 5. 准备目录
    temp_dir = Path("data/temp")
    queue_dir.mkdir(parents=True, exist_ok=True)
    temp_dir.mkdir(parents=True, exist_ok=True)

    temp_file = temp_dir / f"{uid}.tmp"
    final_file = queue_dir / str(uid)

    # 6. 先写入 temp 目录
    task_data = {
        "uid": uid,
        "create_time": int(time.time())
    }

    try:
        with open(temp_file, 'w', encoding='utf-8') as f:
            json.dump(task_data, f, ensure_ascii=False)
            f.flush()  # 确保写入缓冲区
            os.fsync(f.fileno())  # 强制落盘（可选，增强可靠性）
    except OSError as e:
        # 清理临时文件（如果存在）
        temp_file.unlink(missing_ok=True)
        return jsonify({
            "code": 2,
            "message": f"写入临时文件失败: {e}"
        }), 500

    # 7. 原子移动到 queue 目录
    try:
        shutil.move(str(temp_file), str(final_file))
    except (OSError, shutil.Error) as e:
        # 移动失败，清理残留
        temp_file.unlink(missing_ok=True)
        final_file.unlink(missing_ok=True)
        return jsonify({
            "code": 2,
            "message": f"移动任务文件到队列失败: {e}"
        }), 500

    # 8. 成功
    return jsonify({
        "code": 0,
        "message": "任务已成功加入队列",
        "uid": uid
    })


@app.route('/AnnualReport/api/get_user_total/')
def get_user_total_api():
    user_count = len([f for f in os.listdir('data/user') if os.path.isdir(os.path.join('data/user', f))])
    return jsonify({"year": config.year, "user_count": user_count})


if __name__ == '__main__':
    m_api = mobcentAPI.MobcentAPI(config.username, config.password)
    app.run('127.0.0.1', 9595, debug=False)
