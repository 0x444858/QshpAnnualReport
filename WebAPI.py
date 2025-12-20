import requests
import time


class HepanException(Exception):
    """
    当因为论坛自身限制，导致函数失败时，会抛出此异常
    """

    def __init__(self, message):
        self.message = message

    def __str__(self):
        return self.message


class WebAPI:
    pre = 'https://bbs.uestc.edu.cn/'
    api_pre = f'{pre}_/'
    auto_relog = 3600
    auto_update_auth = 3600
    timeout = 5

    def __init__(self, username: str, password: str, loginField='username', autoLogin: bool = True):
        if not username or not password:
            raise ValueError(f'用户名或密码为空。当前用户名: {username}，密码: {password}')
        self.username: str = username
        self.password: str = password
        self.loginField: str = loginField
        self.lastLogin: int = 0
        self.lastUpdateAuth: int = 0
        self.user: dict = {}
        self.session = requests.session()
        if autoLogin:
            self.login()

    def login(self):
        url = f'{self.pre}member.php?mod=logging&action=login&loginsubmit=yes&inajax=1'
        data = {'loginfield': self.loginField, 'username': self.username, 'password': self.password}
        try:
            r = self.session.post(url, data=data, timeout=self.timeout)
            r.raise_for_status()
        except Exception as e:
            print(e)
            return False
        if '欢迎您回来' in r.text:
            self.lastLogin = time.time()
            return True and self.update_authorization()
        else:
            raise HepanException(
                f'登录失败 username={self.username}, password={self.password}, loginField={self.loginField}\n{r.text}')

    def update_authorization(self):
        """
        更新 authorization

        :return:
            bool: 成功 True，失败 False
        """
        url = f'{self.api_pre}auth/adoptLegacyAuth'
        headers = {'X-Uestc-Bbs': '1'}
        try:
            r = self.session.post(url, headers=headers, timeout=self.timeout)
            r.raise_for_status()
            authorization = r.json()['data']['authorization']
            self.session.headers.update({"Authorization": authorization})
            self.lastUpdateAuth = int(time.time())
            return True
        except Exception as e:
            print(e)
            return False

    def _request_api(self, method: str, short_url: str, args: dict = None, data=None):
        if time.time() - self.lastLogin > self.auto_relog:
            self.login()
        if time.time() - self.lastUpdateAuth > self.auto_update_auth:
            self.update_authorization()
        url = f'{self.api_pre}{short_url}'
        try:
            return self._request_once(method, url, args, data)
        except Exception as e:
            print(e)
            self.login()
            return self._request_once(method, url, args, data)

    def _request_once(self, method: str, full_url: str, args: dict, data=None):
        r = self.session.request(method, full_url, params=args, data=data, timeout=self.timeout)
        r.raise_for_status()
        j = r.json()
        if j['code']:
            raise HepanException(j['message'])
        self.user = j['user'] | {'time': int(time.time())}
        return j['data']

    def get_user_info(self, uid: int, user_summary: bool = False, visitors: bool = False) -> dict:
        """
        获取用户信息

        :param uid: UID
        :param user_summary: 是否获取摘要
        :param visitors: 是否获取访客记录
        """
        short_url = f'user/{uid}/profile'
        args = {'user_summary': int(user_summary), 'visitors': int(visitors)}
        return self._request_api('get', short_url, args)

    def get_user_threads(self, uid: int, page: int = 1, user_summary: bool = False, visitors: bool = False,
                         additional='removevlog') -> dict:
        """
        获取用户帖子

        :param uid: UID
        :param page: 页码
        :param user_summary: 是否获取摘要
        :param visitors: 是否获取访客记录
        :param additional:是否隐藏访问记录，可选removevlog
        """
        short_url = f'user/{uid}/threads'
        args = {'page': page, 'user_summary': int(user_summary), 'visitors': int(visitors), 'additional': additional}
        return self._request_api('get', short_url, args)

    def get_user_replies(self, uid: int, page: int = 1, user_summary: bool = False, visitors: bool = False,
                         additional='removevlog') -> dict:
        """
        获取用户回复

        :param uid: UID
        :param page: 页码
        :param user_summary: 是否获取摘要
        :param visitors: 是否获取访客记录
        :param additional:是否隐藏访问记录，可选removevlog
        """
        short_url = f'user/{uid}/replies'
        args = {'page': page, 'user_summary': int(user_summary), 'visitors': int(visitors), 'additional': additional}
        return self._request_api('get', short_url, args)

    def find_point(self, pid: int) -> tuple[int, int]:
        """
        :param pid: PID

        :return:
        tid, position
        """
        short_url = f'post/find'
        args = {'pid': pid}
        r = self._request_api('get', short_url, args)
        return r['thread_id'], r['position']

    def get_thread_reply_page(self, tid: int, page: int = 1, thread_details=0) -> dict:
        """
        获取帖子回复

        :param tid: TID
        :param page: 页码
        :param thread_details: 主题信息
        """
        short_url = 'post/list'
        args = {'thread_id': tid, 'page': page, 'thread_details': thread_details}
        return self._request_api('get', short_url, args)
