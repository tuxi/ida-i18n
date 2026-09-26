# -*- coding: utf-8 -*-
"""在 IDA 里运行，导出全部 action 名称 + 英文标签到 tools/actions_reference.txt。

用途: IDA 升级后（例如 9.3 -> 9.4），用新版本重新导出这份全表，
      和旧版 `git diff` 对比即可知道哪些 action 新增/改名，只补差异词条。

用法（任选其一）:
    * IDA 菜单 File -> Script file... 选择本文件
    * Python 控制台: exec(open("/path/to/tools/dump_actions_reference.py").read())

注意: 必须在 IDA 进程内运行（需要 ida_kernwin），不是系统 python3。
"""
import os

import ida_kernwin

try:
    _HERE = os.path.dirname(os.path.abspath(__file__))
except NameError:  # 通过控制台 exec 时可能没有 __file__
    _HERE = os.getcwd()

OUT = os.path.join(_HERE, "actions_reference.txt")


def main():
    acts = ida_kernwin.get_registered_actions() or []
    rows = []
    for name in acts:
        try:
            label = ida_kernwin.get_action_label(name)
        except Exception:
            label = None
        rows.append("%s\t%s" % (name, label))
    with open(OUT, "w", encoding="utf-8") as f:
        f.write("\n".join(rows))
    ida_kernwin.msg("[ida_i18n] wrote %s (%d actions)\n" % (OUT, len(rows)))
    print("[ida_i18n] wrote %s (%d actions)" % (OUT, len(rows)))


main()
