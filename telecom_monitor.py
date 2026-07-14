#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# Repo: https://github.com/Cp0204/ChinaTelecomMonitor
# Modify: 2026-05-28 (修复语法错误 + 生成 usage.json + 修正流量单位)

import os
import sys
import json
import datetime
import calendar

try:
    from telecom_class import Telecom
except:
    print("正在尝试自动安装依赖...")
    os.system("pip3 install pycryptodome requests &> /dev/null")
    from telecom_class import Telecom


CONFIG_DATA = {}
NOTIFYS = []
CONFIG_PATH = sys.argv[1] if len(sys.argv) > 1 else "telecom_config.json"
TELECOM_FLUX_PACKAGE = os.environ.get("TELECOM_FLUX_PACKAGE", "true").lower() != "false"
TELECOM_ONLY_WARN = os.environ.get("TELECOM_ONLY_WARN", "false").lower() == "true"


def send_notify(title, body):
    try:
        import notify
        if CONFIG_DATA.get("push_config"):
            notify.push_config.update(CONFIG_DATA["push_config"])
            notify.push_config["CONSOLE"] = notify.push_config.get("CONSOLE", True)
        notify.send(title, body)
    except Exception as e:
        if e:
            print("发送通知消息失败！")


def add_notify(text):
    global NOTIFYS
    NOTIFYS.append(text)
    print("📢", text)
    return text


def usage_status_icon(used, total):
    if total <= 0:
        return "⚫"
    if used >= total:
        return "🔴"
    today = datetime.date.today()
    _, days_in_month = calendar.monthrange(today.year, today.month)
    time_progress = today.day / days_in_month
    usage_progress = used / total
    if usage_progress > time_progress * 1.5:
        return "🟠"
    elif usage_progress > time_progress:
        return "🟡"
    else:
        return "🟢"


def main():
    global CONFIG_DATA
    start_time = datetime.datetime.now()
    print(f"===============程序开始===============")
    print(f"⏰ 执行时间: {start_time.strftime('%Y-%m-%d %H:%M:%S')}")
    print()
    
    if os.path.exists(CONFIG_PATH):
        print(f"⚙️ 正从 {CONFIG_PATH} 文件中读取配置")
        with open(CONFIG_PATH, "r", encoding="utf-8") as file:
            CONFIG_DATA = json.load(file)
    if not CONFIG_DATA.get("user"):
        CONFIG_DATA["user"] = {}

    telecom = Telecom()

    def auto_login():
        if TELECOM_USER := os.environ.get("TELECOM_USER"):
            phonenum, password = TELECOM_USER[:11], TELECOM_USER[11:]
        elif TELECOM_USER := CONFIG_DATA.get("user", {}):
            phonenum, password = TELECOM_USER.get("phonenum", ""), TELECOM_USER.get("password", "")
        else:
            exit("自动登录：未设置账号密码，退出")
        if not phonenum.isdigit():
            exit("自动登录：手机号设置错误，退出")
        print(f"自动登录：{phonenum}")
        
        login_fail_time = CONFIG_DATA.get("loginFailTime", 0)
        if login_fail_time < 5:
            data = telecom.do_login(phonenum, password)
            if data.get("responseData", {}).get("resultCode") == "0000":
                print(f"自动登录：成功")
                login_info = data["responseData"]["data"]["loginSuccessResult"]
                login_info["phonenum"] = phonenum
                login_info["createTime"] = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                CONFIG_DATA["login_info"] = login_info
                CONFIG_DATA["loginFailTime"] = 0
                telecom.set_login_info(login_info)
            else:
                # 修复第102行：处理loginFailTime可能是字符串的情况
                login_fail_time_value = data.get("responseData", {}).get("data", {}).get("loginFailResult", {}).get("loginFailTime", login_fail_time + 1)
                try:
                    # 如果是字符串日期格式，则累加失败次数；否则直接转换为int
                    if isinstance(login_fail_time_value, str):
                        login_fail_time = login_fail_time + 1
                    else:
                        login_fail_time = int(login_fail_time_value)
                except (ValueError, TypeError):
                    login_fail_time = login_fail_time + 1
                CONFIG_DATA["loginFailTime"] = login_fail_time
                update_config()
                add_notify(f"自动登录：已连续失败{login_fail_time}次，程序退出")
                exit(data)
        else:
            print(f"自动登录：已连续失败{login_fail_time}次，为避免风控不再执行")
            exit()

    login_info = CONFIG_DATA.get("login_info", {})
    if login_info and login_info.get("phonenum"):
        print(f"尝试使用缓存登录：{login_info['phonenum']}")
        telecom.set_login_info(login_info)
    else:
        auto_login()

    important_data = telecom.qry_important_data()
    if important_data.get("responseData"):
        print(f"获取主要信息：成功")
    elif important_data["headerInfos"]["code"] == "X201":
        print(f"获取主要信息：失败 {important_data['headerInfos']['reason']}")
        auto_login()
        important_data = telecom.qry_important_data()

    try:
        summary = telecom.to_summary(important_data["responseData"]["data"])
    except Exception as e:
        exit(f"简化主要信息出错：{e}")

    if summary:
        print(f"简化主要信息：{summary}")
        CONFIG_DATA["summary"] = summary

    flux_package_str = ""
    if TELECOM_FLUX_PACKAGE:
        user_flux_package = telecom.user_flux_package()
        if user_flux_package:
            print("获取流量包明细：成功")
            packages = user_flux_package["responseData"]["data"]["productOFFRatable"]["ratableResourcePackages"]
            for package in packages:
                package_icon = "🇨🇳" if "国内" in package["title"] else "📺" if "专用" in package["title"] else "🌎"
                flux_package_str += f"\n{package_icon}{package['title']}\n"
                for product in package["productInfos"]:
                    if product["infiniteTitle"]:
                        flux_package_str += f"🔹[{product['title']}]{product['infiniteTitle']}{product['infiniteValue']}{product['infiniteUnit']}/无限\n"
                    else:
                        flux_package_str += f"🔹[{product['title']}]{product['leftTitle']}{product['leftHighlight']}{product['rightCommon']}\n"

    common_str = (
        f"{telecom.convert_flow(summary['commonUse'],'GB',2)} / {telecom.convert_flow(summary['commonTotal'],'GB',2)} GB"
        if summary["flowOver"] == 0
        else f"-{telecom.convert_flow(summary['flowOver'],'GB',2)} / {telecom.convert_flow(summary['commonTotal'],'GB',2)} GB"
    )
    status_icon = usage_status_icon(summary["commonUse"], summary["commonTotal"])
    common_str = f"{common_str} {status_icon}"
    special_str = f"{telecom.convert_flow(summary['specialUse'], 'GB', 2)} / {telecom.convert_flow(summary['specialTotal'], 'GB', 2)} GB" if summary["specialTotal"] > 0 else ""

    # 修复语法错误：不要在外层 f-string 内部使用单引号包裹字典键
    voice_part = f' / {summary["voiceTotal"]}' if summary["voiceTotal"] > 0 else ''
    notify_str = f"""
📱 手机：{summary['phonenum']}
💰 余额：{round(summary['balance']/100,2)}
📞 通话：{summary['voiceUsage']}{voice_part} min
🌐 总流量
  - 通用：{common_str}{f'{chr(10)}  - 专用：{special_str}' if special_str else ''}"""

    if TELECOM_FLUX_PACKAGE:
        notify_str += f"\n\n【流量包明细】\n\n{flux_package_str.strip()}"
    notify_str += f"\n\n查询时间：{summary['createTime']}"
    add_notify(notify_str.strip())

    if NOTIFYS:
        print(f"===============推送通知===============")
        if TELECOM_ONLY_WARN and status_icon == "🟢":
            print("流量使用在均匀范围内，跳过通知")
        else:
            notify_body = "\n".join(NOTIFYS)
            send_notify("【电信套餐用量监控】", notify_body)

    # ========== 生成供手机读取的 usage.json ==========
    # 注意：summary 中的 commonUse / commonTotal 单位是 KB，需要转换为 GB（二进制 1024*1024）
    flow_used_gb = round(summary['commonUse'] / 1024 / 1024, 2)
    flow_total_gb = round(summary['commonTotal'] / 1024 / 1024, 2)
    
    # 获取 GMT+8 时间（北京时间）
    now_utc = datetime.datetime.utcnow()
    now_gmt8 = now_utc + datetime.timedelta(hours=8)
    update_time_gmt8 = now_gmt8.strftime("%Y-%m-%d %H:%M:%S")

    usage_json = {
        "balance": round(summary['balance'] / 100, 2),
        "flowUsed": flow_used_gb,
        "flowTotal": flow_total_gb,
        "voiceUsed": summary['voiceUsage'],
        "voiceTotal": summary['voiceTotal'] if summary['voiceTotal'] > 0 else 0,
        "updateTime": update_time_gmt8,
        "statusIcon": status_icon
    }
    try:
        with open("usage.json", "w", encoding="utf-8") as f:
            json.dump(usage_json, f, ensure_ascii=False, indent=2)
        print("✅ 已生成 usage.json 文件，供手机小组件读取")
    except Exception as e:
        print(f"⚠️ 生成 usage.json 失败: {e}")

    update_config()


def update_config():
    with open(CONFIG_PATH, "w", encoding="utf-8") as file:
        json.dump(CONFIG_DATA, file, ensure_ascii=False, indent=2)


if __name__ == "__main__":
    main()
