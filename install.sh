#!/bin/sh
# ida-i18n 一键安装（macOS / Linux）
#
# 用法:
#   ./install.sh              # 安装到 ~/.idapro
#   IDAUSER=/path ./install.sh  # 自定义 IDA 用户目录
#
# 做两件事:
#   1. 复制插件到 $IDAUSER/plugins/
#   2. 确保 $IDAUSER/idapythonrc.py 会加载插件（不存在则创建，存在则追加）
set -eu

HERE=$(cd "$(dirname "$0")" && pwd)
IDAUSER=${IDAUSER:-"$HOME/.idapro"}
PLUGDIR="$IDAUSER/plugins"
RC="$IDAUSER/idapythonrc.py"
MARK="# ida-i18n loader"

echo "IDA user dir: $IDAUSER"
mkdir -p "$PLUGDIR"

cp "$HERE/ida_i18n.py" "$PLUGDIR/ida_i18n.py"
cp "$HERE/ida_i18n_zh_CN.json" "$PLUGDIR/ida_i18n_zh_CN.json"
echo "installed plugin -> $PLUGDIR"

BLOCK='import os, sys
sys.path.insert(0, os.path.join(os.path.expanduser("~"), ".idapro", "plugins"))
import ida_i18n'

if [ -f "$RC" ] && grep -qF "$MARK" "$RC"; then
    echo "idapythonrc.py already configured, skipped"
elif [ -f "$RC" ]; then
    printf '\n%s\n%s\n' "$MARK" "$BLOCK" >> "$RC"
    echo "appended loader to existing $RC"
else
    printf '# -*- coding: utf-8 -*-\n%s\n%s\n' "$MARK" "$BLOCK" > "$RC"
    echo "created $RC"
fi

echo "done. 重启 IDA 生效。"
