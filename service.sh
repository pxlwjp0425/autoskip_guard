#!/system/bin/sh
# KernelSU 在 late_start 阶段以 root 身份执行本脚本。
MODDIR=${0%/*}

# 等系统真的起来。无障碍服务属于系统服务，起太早写了设置也会被系统覆盖回去。
i=0
while [ "$(getprop sys.boot_completed)" != "1" ] && [ $i -lt 90 ]; do
  sleep 2
  i=$((i+1))
done
sleep 12

nohup sh $MODDIR/bin/guard.sh </dev/null >/dev/null 2>&1 &
