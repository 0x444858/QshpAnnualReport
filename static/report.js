/**
 * 渲染 GitHub 风格贡献绿墙
 * @param {number} year - 年份，如 2024
 * @param {Object} dataDict - 键为 "MM-dd"，值为数字（发帖量），未出现的日期视为 0
 * @returns {{ downloadSVG: Function }} - 包含下载函数的对象
 */

/*
调用示例：
const myData = {
  "01-01": 419,
  "01-03": 74
};
// 渲染 2024 年的绿墙
const { downloadSVG } = renderGreenWall(2024, myData);

// 绑定下载按钮
document.getElementById('download-btn').addEventListener('click', downloadSVG);
*/
function renderGreenWall(year, dataDict) {
  const container = document.getElementById('green_wall');
  if (!container) {
    console.error('Element #green_wall not found');
    return { downloadSVG: () => {} };
  }

  // === 配置 ===
  const CELL_SIZE = 11;
  const CELL_SPACING = 3;
  const MONTH_LABELS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun",
                        "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];
  const WEEKDAY_SHORT = ["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"]; // 左侧星期标签
  const COLORS = ["#ebedf0", "#9be9a8", "#40c463", "#30904e", "#216e39",
                             "#ffd700", "#daa520", "#b8860b",
                             "#ff0000", "#cd0000", "#8b0000"];

  // === 工具函数 ===
  function isLeapYear(y) {
    return (y % 4 === 0 && y % 100 !== 0) || y % 400 === 0;
  }

  function getColor(v) {
    // 白
    if (v === 0) return COLORS[0];
    // 绿
    if (v <= 10) return COLORS[1];
    if (v <= 20) return COLORS[2];
    if (v <= 30) return COLORS[3];
    if (v <= 50) return COLORS[4];
    // 黄
    if (v <= 100) return COLORS[5];
    if (v <= 150) return COLORS[6];
    if (v <= 200) return COLORS[7];
    // 红
    if (v <= 300) return COLORS[8];
    if (v <= 500) return COLORS[9];
    if (v <= 1000) return COLORS[10];
    // 黑
    return '#000000'
  }

  // === 1. 生成 year 年所有 UTC+8（CST）日历日的数据 ===
  const daysInYear = isLeapYear(year) ? 366 : 365;
  let maxValue = 0;
  const dailyData = [];

  for (let i = 0; i < daysInYear; i++) {
    // 构造 CST 的 year-01-01 + i 天，用 UTC 时间表示
    const utcDate = new Date(Date.UTC(year, 0, 1 + i));

    // 提取 MM-DD（用于匹配 dataDict）
    const mm = String(utcDate.getUTCMonth() + 1).padStart(2, '0');
    const dd = String(utcDate.getUTCDate()).padStart(2, '0');
    const mmdd = `${mm}-${dd}`;

    const value = dataDict[mmdd] || 0;
    if (value > maxValue) maxValue = value;

    // 存储：语义上这是 CST 的某一天
    dailyData.push({
      utcDate: utcDate,
      isoDate: `${utcDate.getUTCFullYear()}-${mm}-${dd}`,
      mmdd: mmdd,
      dayOfWeek: utcDate.getUTCDay(), // 0=Sun ... 6=Sat（CST 星期几）
      value: value
    });
  }

  // === 2. 补前导空格（使 1月1日落在正确的星期列）===
  const firstDayOfWeek = new Date(Date.UTC(year, 0, 1)).getUTCDay(); // Jan 1 是星期几（CST）
  const paddedData = [];

  // 前导空单元格（不属于该年）
  for (let i = 0; i < firstDayOfWeek; i++) {
    paddedData.push({
      utcDate: null,
      isoDate: null,
      mmdd: null,
      dayOfWeek: i,
      value: 0,
      isEmpty: true
    });
  }

  paddedData.push(...dailyData);

  // === 3. 按周分组（每7天一列）===
  const weeks = [];
  for (let i = 0; i < paddedData.length; i += 7) {
    let week = paddedData.slice(i, i + 7);
    // 补尾部（通常不需要，但安全）
    while (week.length < 7) {
      const nextIndex = i + week.length;
      week.push({
        utcDate: null,
        isoDate: null,
        mmdd: null,
        dayOfWeek: nextIndex % 7,
        value: 0,
        isEmpty: true
      });
    }
    weeks.push(week);
  }

  // === 4. 创建 SVG ===
  const svgNS = "http://www.w3.org/2000/svg";
  const leftMargin = 32;   // 给左侧星期标签留空间
  const topMargin = 20;    // 给顶部月份标签留空间
  const totalWidth = weeks.length * (CELL_SIZE + CELL_SPACING) + leftMargin + 10;
  const totalHeight = 7 * (CELL_SIZE + CELL_SPACING) + topMargin + 10;

  const svg = document.createElementNS(svgNS, "svg");
  svg.setAttribute("width", totalWidth);
  svg.setAttribute("height", totalHeight);
  svg.setAttribute("viewBox", `0 0 ${totalWidth} ${totalHeight}`);
  svg.setAttribute("style", "font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Helvetica, Arial, sans-serif;");

  // === 5. 渲染单元格 ===
  weeks.forEach((week, colIndex) => {
    week.forEach(cell => {
      const x = colIndex * (CELL_SIZE + CELL_SPACING) + leftMargin;
      const y = cell.dayOfWeek * (CELL_SIZE + CELL_SPACING) + topMargin;

      const rect = document.createElementNS(svgNS, "rect");
      rect.setAttribute("x", x);
      rect.setAttribute("y", y);
      rect.setAttribute("width", CELL_SIZE);
      rect.setAttribute("height", CELL_SIZE);
      rect.setAttribute("fill", getColor(cell.value));
      rect.setAttribute("shape-rendering", "crispEdges");

      // 悬停提示（仅真实数据）
      if (!cell.isEmpty) {
        const title = document.createElementNS(svgNS, "title");
        title.textContent = `${cell.isoDate}: ${cell.value} posts`;
        rect.appendChild(title);
      }

      svg.appendChild(rect);
    });
  });

  // === 6. 月份标签（顶部）===
  let lastMonth = -1;
  weeks.forEach((week, colIndex) => {
    const firstValid = week.find(c => !c.isEmpty);
    if (!firstValid) return;

    const month = firstValid.utcDate.getUTCMonth();
    if (month !== lastMonth) {
      const text = document.createElementNS(svgNS, "text");
      text.setAttribute("x", colIndex * (CELL_SIZE + CELL_SPACING) + leftMargin);
      text.setAttribute("y", 12);
      text.setAttribute("font-size", "10");
      text.setAttribute("fill", "#666");
      text.textContent = MONTH_LABELS[month];
      svg.appendChild(text);
      lastMonth = month;
    }
  });

  // === 7. 星期标签（左侧，全部7行）===
  for (let row = 0; row < 7; row++) {
    const text = document.createElementNS(svgNS, "text");
    text.setAttribute("x", leftMargin - 6);
    text.setAttribute("y", row * (CELL_SIZE + CELL_SPACING) + topMargin + CELL_SIZE / 2 + 3);
    text.setAttribute("font-size", "9");
    text.setAttribute("fill", "#666");
    text.setAttribute("text-anchor", "end");
    text.textContent = WEEKDAY_SHORT[row];
    svg.appendChild(text);
  }

  // === 8. 渲染到页面 ===
  container.innerHTML = '';
  container.appendChild(svg);

  // === 9. 生成 SVG 字符串（用于下载）===
  // 注意：必须序列化当前 DOM 中的 svg，确保与显示一致
  const svgString = new XMLSerializer().serializeToString(svg);

  // === 10. 下载函数 ===
  function downloadSVG(filename = `green-wall-${year}.svg`) {
    const blob = new Blob([svgString], { type: "image/svg+xml;charset=utf-8" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = filename;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
  }

  return { downloadSVG };
}

function isLeapYear(y) {
    return (y % 4 === 0 && y % 100 !== 0) || y % 400 === 0;
}

function getDaysInYear(y) {
    return isLeapYear(y) ? 366 : 365;
}

function set_element(element_id, str){
    const element = document.getElementById(element_id);
    if (element) element.textContent = str;
}

function set_link(element_id, str, link){
    const element = document.getElementById(element_id);
    if (element) {
        element.textContent = str;
        element.href = link;
    }
}

function get_thread_link(tid){
    return `https:\/\/bbs.uestc.edu.cn/thread/${tid}`;
}

function get_post_link(pid){
    return `https:\/\/bbs.uestc.edu.cn/goto/${pid}`;
}

function get_user_link(username){
    return `https:\/\/bbs.uestc.edu.cn/user/name/${username}`;
}

function get_forum_link(fid){
    return `https:\/\/bbs.uestc.edu.cn/forum/${fid}`;
}

// 生成报告
function generate_report(data){
    // 数据准备
    year = data.year;
    user = data.user;
    summary = data.summary;
    first_and_last = data.first_and_last;
    support_and_oppose = data.support_and_oppose;
    popularity = data.popularity;
    personal_favorite = data.personal_favorite;
    rank = data.rank;
    task = data.task;
    s = set_element;
    l = set_link;

    // 填入数据

    // 元数据
    s('report_apply_time', new Date(task.create_time * 1000).toLocaleString());
    s('get_data_start', new Date(task.get_data_start * 1000).toLocaleString());
    s('get_data_stop', new Date(task.get_data_stop * 1000).toLocaleString());
    s('get_data_time', task.get_data_stop - task.get_data_start);
    s('meta_tid_count', task.tid_count);
    s('report_generate_time', new Date(task.generate_report * 1000).toLocaleString());

    // 用户信息
    s('username', user.username);
    s('uid', user.uid);
    s('group_title', user.group_title);
    if (user.group_subtitle) s('group_subtitle', '(' + user.group_subtitle + ')');
    const registerDate = new Date(user.register_time * 1000);
    const now = new Date();
    const registerDay = new Date(registerDate.getFullYear(), registerDate.getMonth(), registerDate.getDate());
    const currentDay = new Date(now.getFullYear(), now.getMonth(), now.getDate());
    const diffDays = Math.floor((currentDay.getTime() - registerDay.getTime()) / (1000 * 60 * 60 * 24)) + 1;
    s('days_from_register', diffDays);

    // 摘要
    s('summary_thread', summary.thread);
    s('summary_reply', summary.reply);
    s('summary_all', summary.all);
    s('sofa_count', summary.sofa_count);
    s('summary_post_days', summary.post_days);
    if (getDaysInYear(year) - summary.post_days < 90){
        const summary_reward_message = document.getElementById('summary_reward_message');
        if (summary_reward_message) summary_reward_message.style.display = 'inline';
        if (getDaysInYear() - summary.post_days == 0) s('summary_reward', '全勤奖');
        else if (getDaysInYear() - summary.post_days <= 15) s('summary_reward', '差点全勤奖');
        else if (getDaysInYear() - summary.post_days <= 45) s('summary_reward', '活跃奖');
        else s('summary_reward', '水水奖');
    }
    s('post_most_days', summary.post_most_days.map(item => item.d).join('，'));
    s('summary_post_days_max', summary.post_most_days[0].c);
    const { downloadSVG } = renderGreenWall(year, summary.post_count_per_day);
    const download_btn = document.getElementById('download_green_wall');
    download_btn.onclick = () => {downloadSVG(`清水河畔uid${user.uid}的2025年发帖热力图.svg`);};

    // 第一个与最后一个
    l('first_thread_link', first_and_last.first_thread[4], get_thread_link(first_and_last.first_thread[2]));
    l('last_thread_link', first_and_last.last_thread[4], get_thread_link(first_and_last.last_thread[2]));
    l('first_reply_thread_link', first_and_last.first_reply[4], get_thread_link(first_and_last.first_reply[2]));
    l('first_reply_number', first_and_last.first_reply[0], get_post_link(first_and_last.first_reply[3]));
    l('last_reply_thread_link', first_and_last.last_reply[4], get_thread_link(first_and_last.last_reply[2]));
    l('last_reply_number', first_and_last.last_reply[0], get_post_link(first_and_last.last_reply[3]));

    // 赞与踩
    s('total_support', support_and_oppose.total_support);
    s('total_oppose', support_and_oppose.total_oppose);
    const thread_most_support_link_area = document.getElementById('thread_most_support_link_area');
    if (thread_most_support_link_area) {
        list = support_and_oppose.thread_most_support;
        for (let i = 0; i < list.length; i++) {
            let a = document.createElement('a');
            a.href = get_thread_link(list[i][0]);
            a.textContent = list[i][2];
            thread_most_support_link_area.appendChild(a);
            if (i+1 < list.length) {
                let sep = document.createElement('span');
                sep.textContent = '，';
                thread_most_support_link_area.appendChild(sep);
            }
        }
    }
    s('thread_most_support_count', support_and_oppose.thread_most_support[0][5]);
    const thread_most_oppose_link_area = document.getElementById('thread_most_oppose_link_area');
    if (thread_most_oppose_link_area) {
        list = support_and_oppose.thread_most_oppose;
        for (let i = 0; i < list.length; i++) {
            let a = document.createElement('a');
            a.href = get_thread_link(list[i][0]);
            a.textContent = list[i][2];
            thread_most_oppose_link_area.appendChild(a);
            if (i+1 < list.length) {
                let sep = document.createElement('span');
                sep.textContent = '，';
                thread_most_oppose_link_area.appendChild(sep);
            }
        }
    }
    s('thread_most_oppose_count', support_and_oppose.thread_most_oppose[0][5]);
    const reply_most_support_link_area = document.getElementById('reply_most_support_link_area');
    if (reply_most_support_link_area) {
        list = support_and_oppose.reply_most_support;
        for (let i = 0; i < list.length; i++) {
            let a = document.createElement('a');
            a.href = get_thread_link(list[i][0]);
            a.textContent = list[i][3];
            reply_most_support_link_area.appendChild(a);
            let zd = document.createElement('span');
            zd.textContent = '中的第';
            reply_most_support_link_area.appendChild(zd);
            a = document.createElement('a');
            a.href = get_post_link(list[i][1]);
            a.textContent = list[i][2];
            reply_most_support_link_area.appendChild(a);
            let fl = document.createElement('span');
            fl.textContent = '楼';
            reply_most_support_link_area.appendChild(fl);
            if (i+1 < list.length) {
                let sep = document.createElement('span');
                sep.textContent = '，';
                reply_most_support_link_area.appendChild(sep);
            }
        }
    }
    s('reply_most_support_count', support_and_oppose.reply_most_support[0][6]);
    const reply_most_oppose_link_area = document.getElementById('reply_most_oppose_link_area');
    if (reply_most_oppose_link_area) {
        list = support_and_oppose.reply_most_oppose;
        for (let i = 0; i < list.length; i++) {
            let a = document.createElement('a');
            a.href = get_thread_link(list[i][0]);
            a.textContent = list[i][3];
            reply_most_oppose_link_area.appendChild(a);
            let zd = document.createElement('span');
            zd.textContent = '中的第';
            reply_most_oppose_link_area.appendChild(zd);
            a = document.createElement('a');
            a.href = get_post_link(list[i][1]);
            a.textContent = list[i][2];
            reply_most_oppose_link_area.appendChild(a);
            let fl = document.createElement('span');
            fl.textContent = '楼';
            reply_most_oppose_link_area.appendChild(fl);
            if (i+1 < list.length) {
                let sep = document.createElement('span');
                sep.textContent = '，';
                reply_most_oppose_link_area.appendChild(sep);
            }
        }
    }
    s('reply_most_oppose_count', support_and_oppose.reply_most_oppose[0][6]);
    let reply_thread_most_link_area = document.getElementById('reply_thread_most_link_area');
    if (reply_thread_most_link_area) {
        list = popularity.reply_thread_most;
        for (let i = 0; i < list.length; i++) {
            let a = document.createElement('a');
            a.href = get_thread_link(list[i][0]);
            a.textContent = list[i][1];
            reply_thread_most_link_area.appendChild(a);
            if (i+1 < list.length) {
                let sep = document.createElement('span');
                sep.textContent = '，';
                reply_thread_most_link_area.appendChild(sep);
            }
        }
    }
    // popularity
    s('reply_thread_most_count', popularity.reply_thread_most[0][2]);
    let thread_replies_most_link_area = document.getElementById('thread_replies_most_link_area');
    if (thread_replies_most_link_area) {
        list = popularity.thread_replies_most;
        for (let i = 0; i < list.length; i++) {
            let a = document.createElement('a');
            a.href = get_thread_link(list[i][0]);
            a.textContent = list[i][1];
            thread_replies_most_link_area.appendChild(a);
            if (i+1 < list.length) {
                let sep = document.createElement('span');
                sep.textContent = '，';
                thread_replies_most_link_area.appendChild(sep);
            }
        }
    }
    s('thread_replies_most_count', popularity.thread_replies_most[0][2]);
    let thread_views_most_link_area = document.getElementById('thread_views_most_link_area');
    if (thread_views_most_link_area) {
        list = popularity.thread_views_most;
        for (let i = 0; i < list.length; i++) {
            let a = document.createElement('a');
            a.href = get_thread_link(list[i][0]);
            a.textContent = list[i][1];
            thread_views_most_link_area.appendChild(a);
            if (i+1 < list.length) {
                let sep = document.createElement('span');
                sep.textContent = '，';
                thread_views_most_link_area.appendChild(sep);
            }
        }
    }
    s('thread_views_most_count', popularity.thread_views_most[0][2]);
    let thread_favorite_most_link_area = document.getElementById('thread_favorite_most_link_area');
    if (thread_favorite_most_link_area) {
        list = popularity.thread_favorite_most;
        for (let i = 0; i < list.length; i++) {
            let a = document.createElement('a');
            a.href = get_thread_link(list[i][0]);
            a.textContent = list[i][1];
            thread_favorite_most_link_area.appendChild(a);
            if (i+1 < list.length) {
                let sep = document.createElement('span');
                sep.textContent = '，';
                thread_favorite_most_link_area.appendChild(sep);
            }
        }
    }
    s('thread_favorite_most_count', popularity.thread_favorite_most[0][2]);
    // 个人喜好
    let forum_most_favorite_link_area = document.getElementById('forum_most_favorite_link_area');
    if (forum_most_favorite_link_area) {
        list = personal_favorite.forum_most_favorite;
        for (let i = 0; i < list.length; i++) {
            let a = document.createElement('a');
            a.href = get_forum_link(list[i][0]);
            a.textContent = list[i][2];
            forum_most_favorite_link_area.appendChild(a);
            if (i+1 < list.length) {
                let sep = document.createElement('span');
                sep.textContent = '，';
                thread_favorite_most_link_area.appendChild(sep);
            }
        }
    }
    s('forum_most_favorite_count', personal_favorite.forum_most_favorite[0][1]);
    let reply_user_most_link_area = document.getElementById('reply_user_most_link_area');
    if (reply_user_most_link_area) {
        list = personal_favorite.reply_user_most;
        for (let i = 0; i < list.length; i++) {
            let a = document.createElement('a');
            a.href = get_user_link(list[i][0]);
            a.textContent = list[i][0];
            reply_user_most_link_area.appendChild(a);
            if (i+1 < list.length) {
                let sep = document.createElement('span');
                sep.textContent = '，';
                thread_favorite_most_link_area.appendChild(sep);
            }
        }
    }
    s('reply_user_most_count', personal_favorite.reply_user_most[0][1]);
    // 排行榜


    // 将数据设为可见
    let search_report_div = document.getElementById('search_report');
    if (search_report_div) search_report.style.display = 'none';
    let report_main_div = document.getElementById('report_main');
    if (report_main_div) report_main.style.display = 'block';
}

// 获取数据
document.addEventListener('DOMContentLoaded', async () => {
    const container = document.getElementById('search_report');
    if (!container) {
        alert('DOM结构异常：请尝试刷新网页');
        return;
    }
    try {
        // 校验 UID
        const params = new URLSearchParams(window.location.search);
        const uidStr = params.get('uid');
        if (!uidStr) {
            throw new Error('未找到 UID 参数');
        }
        const uid = Number(uidStr);
        if (!Number.isInteger(uid) || uid <= 0) {
            throw new Error('UID 必须为正整数');
        }
        // api 请求
        const response = await fetch(`/AnnualReport/api/get_report?uid=${encodeURIComponent(uid)}`);
        let result;
        let parsedJson = false;
        try {
            result = await response.json();
            parsedJson = true;
        } catch (e) {
            // JSON 解析失败
            if (!response.ok) {
                throw new Error(`错误: ${response.status} ${response.statusText}`);
            } else {
                throw new Error('服务器返回了非 JSON 内容');
            }
        }
        if (parsedJson && typeof result === 'object' && result !== null) {
            if ('code' in result) {
                if (result.code === 0) {
                    // 成功
                    if (!result.data) {
                        throw new Error('API 返回成功，但缺少 data 字段');
                    }
                    generate_report(result.data);
                    return; // 正常结束
                } else {
                    throw new Error(result.message || '未知 API 错误');
                }
            }
        }
        throw new Error('API 返回的数据格式无效');

    } catch (error) {
        // 统一错误展示
        container.innerHTML = `<h1 style="color: #ff2121; margin: 1em 0;">错误: ${error.message}</h1>`;
    }
});