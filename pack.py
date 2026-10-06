#!/usr/bin/env python3
"""把本目录打包成 KernelSU / Magisk 可刷入的模块 zip。

zip 顶层必须**直接**是 module.prop —— 不能套一层目录，否则 KernelSU 认不出来。
所以这里用显式白名单，而不是「把目录整个塞进去」，免得 .git / README / pack.py 自己也进包。

用法：
    python pack.py
产物：
    autoskip_guard-v<version>.zip      # version 取自 module.prop
"""
import os
import re
import sys
import zipfile

HERE = os.path.dirname(os.path.abspath(__file__))

# 进包的文件（相对本目录）；EXEC 里的带 0755，其余 0644
FILES = ["module.prop", "service.sh", "uninstall.sh", "bin/guard.sh"]
EXEC = {"service.sh", "uninstall.sh", "bin/guard.sh"}
DIRS = ["bin"]

# 固定时间戳，保证同样的输入产出同样的 zip（便于核对 md5）
STAMP = (2026, 10, 6, 12, 0, 0)


def read_version():
    with open(os.path.join(HERE, "module.prop"), "r", encoding="utf-8") as f:
        for line in f:
            m = re.match(r"^version\s*=\s*(\S+)\s*$", line)
            if m:
                return m.group(1)
    return "unknown"


def add(zf, arcname, path, is_dir=False):
    zi = zipfile.ZipInfo(arcname + ("/" if is_dir else ""))
    zi.date_time = STAMP
    mode = 0o755 if (is_dir or arcname in EXEC) else 0o644
    # 权限位放高 16 位：KernelSU 解包时按这个还原
    zi.external_attr = (mode | (0o040000 if is_dir else 0o100000)) << 16
    if is_dir:
        zf.writestr(zi, b"")
    else:
        with open(path, "rb") as f:
            zf.writestr(zi, f.read())


def main():
    version = read_version()
    out = os.path.join(HERE, "autoskip_guard-%s.zip" % version)
    if os.path.exists(out):
        os.remove(out)

    missing = [f for f in FILES if not os.path.isfile(os.path.join(HERE, f))]
    if missing:
        sys.exit("缺文件，拒绝打包: " + ", ".join(missing))

    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as zf:
        for d in DIRS:
            add(zf, d, os.path.join(HERE, d), is_dir=True)
        for f in FILES:
            add(zf, f, os.path.join(HERE, f))

    print("已生成: %s  (%d 字节, 版本 %s)" % (out, os.path.getsize(out), version))
    with zipfile.ZipFile(out) as zf:
        for i in zf.infolist():
            print("  %-20s %6d B  mode=%o" % (i.filename, i.file_size, (i.external_attr >> 16) & 0o777))
        names = zf.namelist()
    # 顶层就是 module.prop 才算合格
    if "module.prop" not in names:
        sys.exit("!! 打包结果不合格：顶层没有 module.prop")


if __name__ == "__main__":
    main()
