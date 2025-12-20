import requests
import json
import time
from urllib.parse import quote


class HepanException(Exception):

    def __init__(self, message):
        self.message = message

    def __str__(self):
        return self.message


class MobcentAPI:

    def __init__(self, username: str, password: str, autoLogin: bool = True):
        if not username or not password:
            raise HepanException('账号或密码为空')
        self.username = username
        self.password = password
        self.accessToken = ''
        self.accessSecret = ''
        self.uid = 0
        self.base_url = 'https://bbs.uestc.edu.cn/mobcent/app/web/index.php'
        self.session = requests.Session()
        self.timeout = 10
        self.session.headers.update({'Content-Type': 'application/x-www-form-urlencoded;charset=UTF-8'})
        if autoLogin:
            s, e = self.login()
            if not s:
                raise HepanException(f'登陆失败: {e} 传入的账号为"{username}"，密码为"{password}"')

    def login(self) -> tuple[bool, str]:
        """
        :return:
            (是否成功, 提示信息)
        """
        params = {'r': 'user/login', 'type': 'login',
                  'username': self.username, 'password': self.password}
        self.session.params = {}
        r = self.session.get(self.base_url, params=params, timeout=self.timeout)
        try:
            r.raise_for_status()
            j = r.json()
            if j['rs']:
                self.accessToken = j['token']
                self.accessSecret = j['secret']
                self.uid = j['uid']
                self.session.params = {'accessToken': self.accessToken, 'accessSecret': self.accessSecret}
                return True, f"登录{j['userName']}成功，UID{j['uid']}"
            else:
                return False, j['head']['errInfo']
        except requests.HTTPError as e:
            return False, f"HTTP错误: {str(e)}"
        except requests.JSONDecodeError as e:
            return False, f"JSON解析错误: {str(e)}"
        except Exception as e:
            return False, f"错误: {e}"

    def send_pm(self, uid: int, message: str, msg_type: str = 'text') -> tuple[bool, str]:
        """
        :param uid: 对方uid
        :param message: 要发送的文本消息 / 图片url / 音频url
        :param msg_type: 消息类型，可选 text, image, audio

        :return:
            (是否成功, 提示信息)

        :warning:
            为避免您的账号被利用给其他人发私信，更推荐使用接收用户私信的方式来验证。
        """
        if uid == self.uid:
            return False, '您不能给自己发短消息'
        if uid <= 0:
            return False, 'UID必须是正整数'
        sj = {
            "action": "send",
            "toUid": uid,
            "msg": {"type": msg_type, "content": quote(message)}
        }
        params = {'r': 'message/pmadmin'}
        r = self.session.post(self.base_url, params=params, data={'json': json.dumps(sj)}, timeout=self.timeout)
        try:
            r.raise_for_status()
            j = r.json()
            if j['rs']:
                return True, j['head']['errInfo']
            else:
                return False, j['head']['errInfo']
        except requests.HTTPError as e:
            return False, f"HTTP错误: {str(e)}"
        except requests.JSONDecodeError as e:
            return False, f"JSON解析错误: {str(e)}"
        except Exception as e:
            return False, f"错误: {e}"

    def get_last_pm_dict(self, uids: int | list[int], time_limit: int = None) -> tuple[
        bool, str | dict[int, dict | None]]:
        """
        获取指定用户最新一条私信

        :param uids: uid或uid列表
        :param time_limit: 从多久以前开始，默认180秒（3分钟）

        :return:
            (是否成功，错误信息或uid对dict的(dict或None))
        :note:
            示例返回：
            True, {
                287813: {
                    "sender": 287813,
                    "mid": 4896695,
                    "content": "test pm message",
                    "type": "text",
                    "time": "1764411289000"
                },
                287814: None
            }
        """
        if time_limit is None:
            time_limit = 180
        params = {'r': 'message/pmlist'}
        if isinstance(uids, int):
            uids = [uids]
        pmLimit = min(int(time_limit / 15), 10)
        sj = {
            "body": {
                "externInfo": {"onlyFromUid": 1},  # 只返回收到的消息（不包括自己发出去的消息）
                "pmInfos": [{
                    "startTime": int(time.time() - time_limit) * 1000,
                    # 开始时间（以毫秒为单位）。startTime 和 stopTime 均为 0 表示获取最新（未读）消息，如果要获取历史消息指定一个较早的时间
                    "stopTime": 0,  # 结束时间（以毫秒为单位），为零表示获取晚于 startTime 的所有消息
                    "cacheCount": 1,
                    "fromUid": uid,
                    "pmLimit": pmLimit  # 最多返回几条结果
                } for uid in uids]
            }
        }
        r = self.session.post(self.base_url, params=params, data={'pmlist': json.dumps(sj)}, timeout=self.timeout)
        try:
            r.raise_for_status()
            j: dict = r.json()
            if j['rs']:
                pm_list = j['body']['pmList']
                rtd = {int(i['fromUid']): i['msgList'][-1] if i['msgList'] else None for i in pm_list}
                return True, rtd
            else:
                return False, j['head']['errInfo']
        except requests.HTTPError as e:
            return False, f"HTTP错误: {str(e)}"
        except requests.JSONDecodeError as e:
            return False, f"JSON解析错误: {str(e)}"
        except Exception as e:
            return False, f"错误: {e}"

    def get_last_pm_text(self, uids: int | list[int], time_limit: int = None) -> tuple[
        bool, str | dict[int, str | None]]:
        """
        获取指定用户最新一条私信的文本
        :param uids: uid或uid列表
        :param time_limit: 从多久以前开始，默认600秒

        :return:
            (是否成功，错误信息或uid对str的(str或None))
        :note:
            示例返回
            True, {
                287813: "test pm message",
                287814: None
            }
        """
        s, e = self.get_last_pm_dict(uids, time_limit)
        if not s:
            return s, e
        return s, {k: v['content'] if v else None for k, v in e.items()}

    def check_pm(self, d: dict[int, str], time_limit: int = 600) -> tuple[bool, str | dict[int, bool]]:
        """
        检查指定用户最新一条私信是否为指定内容
        :param d: uid对str的dict
        :param time_limit: 从多久以前开始，默认600秒

        :return:
            (是否成功，错误信息或uid对bool的dict)
        :note:
            示例返回
            True, {
                287813: True,
                287814: False
            }
        """
        s, e = self.get_last_pm_text(list(d.keys()), time_limit)
        if not s:
            return s, e
        """
        对判断中使用 endswith 而不是 == 的解释：
        当用户在旧版网页浏览帖子时，通过左边的“发消息”按钮发送到私信会默认带上一个标识来源的前缀，干扰判断。
        并且，判断后缀其实已经足够了。
        
        以下是真实返回的结果，来自get_last_pm_text函数：
        {
            "287813": " 关于您在“帖子编辑测试”的帖子 https://bbs.uestc.edu.cn/forum.php?mod=redirect&goto=findpost&pid=39742652&ptid=2290822 \nmessage in old web version",
            "287814": null
        }
        """
        return s, {k: v.endswith(d[k]) if v else False for k, v in e.items()}

    def get_user_info(self, uid: int) -> tuple[bool, str | dict]:
        """
        获取用户信息
        :param uid: uid

        :return:
            (是否成功，提示信息或信息dict)
        """
        params = {'r': 'user/userinfo', 'userId': uid}
        r = self.session.post(self.base_url, params=params, timeout=self.timeout)
        try:
            r.raise_for_status()
            j: dict = r.json()
            if j['rs']:
                return True, j
            else:
                return False, j['head']['errInfo']
        except requests.HTTPError as e:
            return False, f"HTTP错误: {str(e)}"
        except requests.JSONDecodeError as e:
            return False, f"JSON解析错误: {str(e)}"
        except Exception as e:
            return False, f"错误: {e}"

    def check_user_info(self, uid: int, username: str):
        s, j = self.get_user_info(uid)
        if not s:
            return s, j
        if j['name'] == username:
            return True, 'uid与用户名验证通过'
        else:
            return False, 'uid与用户名验证不通过'
