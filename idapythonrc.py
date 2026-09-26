# -*- coding: utf-8 -*-
# IDA 每次启动（IDAPython 初始化后）都会执行本文件。
# 用它确定性地加载 ida_i18n 汉化插件，不依赖 IDA 的插件自动发现
# （实测发现 IDA 9.3 对用户 plugins/ 目录里独立 .py 的自动加载不可靠）。
#
# 安装：把本文件放到 ~/.idapro/idapythonrc.py（Windows:
# %APPDATA%\Hex-Rays\IDA Pro\idapythonrc.py）。
try:
    import os
    import sys
    import traceback

    _plugdir = os.path.join(os.path.expanduser("~"), ".idapro", "plugins")
    if os.path.isdir(_plugdir) and _plugdir not in sys.path:
        sys.path.insert(0, _plugdir)
    import ida_i18n  # 模块导入即完成初始化
except Exception:
    try:
        import os
        import traceback
        _log = os.path.join(os.path.expanduser("~"), ".idapro", "plugins", "ida_i18n.log")
        with open(_log, "a", encoding="utf-8") as f:
            f.write("idapythonrc: load failed\n" + traceback.format_exc())
    except Exception:
        pass
