#!/system/bin/sh
# 模块卸载时由 KernelSU 执行：停掉守护、清掉锁与日志、把快跳的内存优先级恢复成默认。
#
# 卸载本模块**不影响快跳本体** —— 快跳照常跳过广告，只是不再有自动修复。
PKG=com.laopeng.autoskip

for p in $(pgrep -f 'autoskip_guard/bin/guard.sh'); do
  kill "$p" 2>/dev/null
done

# 把还在锁着的那档位放回去（0 = 默认）
for p in $(pidof $PKG); do
  printf '%s\n' 0 > /proc/$p/oom_score_adj 2>/dev/null
done

rm -f /data/adb/autoskip_guard.lock
rm -f /data/adb/autoskip_guard.log
