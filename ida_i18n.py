# -*- coding: utf-8 -*-
"""
ida_i18n -- IDA Pro 9.x UI 汉化插件
=====================================

目标：在不修改 IDA 任何二进制、不破坏代码签名、不改变功能的前提下，
把 IDA 图形界面上能改的英文文本替换为中文。

原理：
  * 菜单/动作(Action)标签：走 IDA 官方 Python API
    (get_registered_actions / get_action_label / update_action_label)。
  * 菜单栏标题、菜单项、对话框标题、按钮、标签、Tab、下拉框、右键菜单等：
    在 Qt 层遍历控件树直接改文本（PySide6，IDA 自带）。
  * 运行时动态弹出的窗口/菜单：安装 QApplication 事件过滤器 + 兜底定时器。

局限（设计如此，不是 bug）：
  * 内核输出窗口(Output)、状态栏、libida.dylib 生成的错误/提示串
    属于编译期内核字符串，此插件无法覆盖（除非 patch 二进制）。
  * 词典按“英文原文 -> 中文”精确匹配，IDA 升级导致原文变化时需补词。

配置：
  * 词典：同目录 ida_i18n_zh_CN.json
  * 开关状态：同目录 ida_i18n.conf.json（自动生成）

安装：
  1) 把本文件与 ida_i18n_zh_CN.json 一起放入 IDA 用户插件目录：
         ~/.idapro/plugins/                       (macOS / Linux)
         %APPDATA%\\Hex-Rays\\IDA Pro\\plugins\\    (Windows)
  2) 让 ~/.idapro/idapythonrc.py 加载它（必需）。这一步不能省：实测 IDA 9.3
     对用户 plugins/ 目录里独立 .py 的自动发现不可靠，有时会完全跳过。
     若同仓库带了 idapythonrc.py，直接复制到用户目录即可；否则把下面几行
     追加到你已有的 idapythonrc.py：
         import os, sys
         sys.path.insert(0, os.path.join(os.path.expanduser("~"), ".idapro", "plugins"))
         import ida_i18n
  重启 IDA。菜单 Options 下会出现 “中文汉化” 两个开关。
"""

import json
import os
import sys
import time
import traceback

PLUGIN_DIR = os.path.dirname(os.path.abspath(__file__))
DICT_PATH = os.path.join(PLUGIN_DIR, "ida_i18n_zh_CN.json")
CONF_PATH = os.path.join(PLUGIN_DIR, "ida_i18n.conf.json")
LOG_PATH = os.path.join(PLUGIN_DIR, "ida_i18n.log")

ACT_TOGGLE = "ida_i18n:toggle"
ACT_RELOAD = "ida_i18n:reload"

# 进程级"已初始化"标记，挂在 sys 上，避免同一进程内重复初始化
_BOOT_FLAG = "_ida_i18n_booted"

# 调为 True 可把日志同时打到 Output 窗口
_DEBUG = False

# 调为 True 才写诊断日志到 ida_i18n.log（排障用，平时保持 False）
_LOG = False


def logf(msg):
    if not _LOG:
        return
    try:
        with open(LOG_PATH, "a", encoding="utf-8") as f:
            f.write("%s %s\n" % (time.strftime("%H:%M:%S"), msg))
    except Exception:
        pass


def log(*a):
    if _DEBUG:
        print("[ida_i18n]", *a)
        logf(" ".join(str(x) for x in a))


# 模块级日志：能确定 IDA 到底有没有导入本文件
logf("module import: begin pid=%d" % os.getpid())

try:
    import ida_idaapi
    import ida_kernwin
    logf("module import: ida modules ok")
except Exception as e:
    logf("module import: ida modules FAILED: %r" % (e,))
    raise

try:
    from PySide6 import QtCore, QtGui, QtWidgets
    _QT_OK = True
    logf("module import: PySide6 ok")
except Exception as e:  # 无 GUI（idat）或 Qt 不可用
    _QT_OK = False
    logf("module import: PySide6 failed: %r" % (e,))


# --------------------------------------------------------------------------- #
# 词典
# --------------------------------------------------------------------------- #
DICT = {}      # normalized en -> zh
REV = {}       # normalized zh -> en
_enabled = True


def norm_key(s):
    """去掉加速键标记、结尾省略号，用于查表。"""
    if not s:
        return ""
    s = s.replace("&", "").replace("~", "").strip()
    if s.endswith("..."):
        s = s[:-3].rstrip()
    elif s.endswith("\u2026"):   # …
        s = s[:-1].rstrip()
    return s


def _has_ellipsis(s):
    s = s.rstrip()
    return s.endswith("...") or s.endswith("\u2026")


def translate_text(raw):
    """英文 -> 中文；匹配不到返回 None。"""
    if not raw or not _enabled:
        return None
    k = norm_key(raw)
    if not k:
        return None
    zh = DICT.get(k)
    if zh is None:
        return None
    if norm_key(zh) == k:
        # 译文与原文相同（如专有名词）：不动它，保留原有加速键
        return None
    if _has_ellipsis(raw) and not _has_ellipsis(zh):
        zh = zh + "..."
    return zh


def restore_text(raw):
    """中文 -> 英文（用于关闭汉化时还原）。匹配不到返回 None。"""
    if not raw:
        return None
    k = norm_key(raw)
    en = REV.get(k)
    if en is None:
        return None
    if _has_ellipsis(raw) and not _has_ellipsis(en):
        en = en + "..."
    return en


def load_dict():
    global DICT, REV
    d = {}
    rev = {}
    try:
        with open(DICT_PATH, "r", encoding="utf-8") as f:
            raw = json.load(f)
        for k, v in raw.items():
            if not isinstance(v, str) or k.startswith("_"):
                continue
            nk = norm_key(k)
            if not nk:
                continue
            d[nk] = v
            rev.setdefault(norm_key(v), nk)
    except Exception as e:
        log("dictionary load failed:", repr(e))
    DICT = d
    REV = rev
    log("dictionary loaded:", len(d), "entries")


def load_conf():
    global _enabled
    try:
        with open(CONF_PATH, "r", encoding="utf-8") as f:
            _enabled = bool(json.load(f).get("enabled", True))
    except Exception:
        _enabled = True


def save_conf():
    try:
        with open(CONF_PATH, "w", encoding="utf-8") as f:
            json.dump({"enabled": _enabled}, f, ensure_ascii=False, indent=2)
    except Exception as e:
        log("conf save failed:", repr(e))


# --------------------------------------------------------------------------- #
# Qt 控件翻译
# --------------------------------------------------------------------------- #
QT_TOPLEVEL = (QtWidgets.QWidget,) if _QT_OK else ()


def _apply_text(text, setter, tr=translate_text):
    zh = tr(text)
    if zh is not None and zh != text:
        try:
            setter(zh)
            return True
        except Exception:
            pass
    return False


def translate_object(obj, seen, tr=translate_text):
    """递归翻译一个 QObject / QWidget 子树。"""
    if not _QT_OK or obj is None:
        return
    oid = id(obj)
    if oid in seen:
        return
    seen.add(oid)

    try:
        if isinstance(obj, QtGui.QAction):
            _apply_text(obj.text(), obj.setText, tr)
        elif isinstance(obj, QtWidgets.QMenu):
            _apply_text(obj.title(), obj.setTitle, tr)
        elif isinstance(obj, QtWidgets.QGroupBox):
            _apply_text(obj.title(), obj.setTitle, tr)
        elif isinstance(obj, QtWidgets.QAbstractButton):
            _apply_text(obj.text(), obj.setText, tr)
        elif isinstance(obj, QtWidgets.QLabel):
            _apply_text(obj.text(), obj.setText, tr)
        elif isinstance(obj, QtWidgets.QWidget):
            # 窗口标题：顶层窗口、停靠面板、标签页都靠它
            _apply_text(obj.windowTitle(), obj.setWindowTitle, tr)
    except Exception:
        pass

    # 列表/表格的列头（chooser 的 “Function name / Address” 等）
    if isinstance(obj, QtWidgets.QAbstractItemView):
        try:
            model = obj.model()
            hh = obj.horizontalHeader()
            if model is not None and hh is not None:
                for i in range(hh.count()):
                    txt = model.headerData(
                        i, QtCore.Qt.Horizontal, QtCore.Qt.DisplayRole)
                    if isinstance(txt, str) and txt:
                        zh = tr(txt)
                        if zh is not None:
                            model.setHeaderData(
                                i, QtCore.Qt.Horizontal, zh,
                                QtCore.Qt.DisplayRole)
        except Exception:
            pass

    # Tab 页
    if isinstance(obj, QtWidgets.QTabWidget):
        try:
            for i in range(obj.count()):
                _apply_text(obj.tabText(i),
                            lambda t, i=i, o=obj: o.setTabText(i, t), tr)
        except Exception:
            pass

    # 下拉框
    if isinstance(obj, QtWidgets.QComboBox):
        try:
            for i in range(obj.count()):
                _apply_text(obj.itemText(i),
                            lambda t, i=i, o=obj: o.setItemText(i, t), tr)
        except Exception:
            pass

    # 关联的 QAction
    try:
        for a in obj.actions():
            translate_object(a, seen, tr)
    except Exception:
        pass

    # 子对象
    try:
        for c in obj.children():
            if isinstance(c, (QtWidgets.QWidget, QtGui.QAction, QtCore.QObject)):
                translate_object(c, seen, tr)
    except Exception:
        pass


def translate_all(tr=translate_text):
    if not _QT_OK:
        return
    app = QtWidgets.QApplication.instance()
    if app is None:
        return
    seen = set()
    try:
        titles = []
        for w in app.topLevelWidgets():
            try:
                t = w.windowTitle()
            except RuntimeError:
                t = ""
            if t:
                titles.append(t)
            if not _LOG_STATE["welcome"] and "Quick start" in (t or ""):
                _LOG_STATE["welcome"] = True
                logf("saw welcome form title=%r visible=%s" % (t, w.isVisible()))
            translate_object(w, seen, tr)
        if _LOG_STATE["n"] < 5:
            logf("translate_all#%d toplevels=%d titles=%r"
                 % (_LOG_STATE["n"], len(app.topLevelWidgets()),
                    [t for t in titles if t][:8]))
            _LOG_STATE["n"] += 1
    except Exception as e:
        log("translate_all error:", repr(e))


# --------------------------------------------------------------------------- #
# Action 标签翻译（IDA API）
# --------------------------------------------------------------------------- #
_ORIG_ACTIONS = {}   # action name -> 原始英文标签（首次汉化前快照）
_busy = False        # 重入保护：update_action_label 会再次触发 updated_actions


def translate_actions():
    global _busy
    if not _enabled or _busy:
        return
    try:
        names = ida_kernwin.get_registered_actions()
    except Exception:
        return
    if not names:
        return
    _busy = True
    changed = 0
    try:
        for name in names:
            try:
                lb = ida_kernwin.get_action_label(name)
            except Exception:
                continue
            if not lb:
                continue
            zh = translate_text(lb)
            if zh is None or zh == lb:
                continue
            _ORIG_ACTIONS.setdefault(name, lb)
            try:
                if ida_kernwin.update_action_label(name, zh):
                    changed += 1
            except Exception:
                pass
    finally:
        _busy = False
    log("actions translated:", changed)


def restore_actions():
    for name, lb in list(_ORIG_ACTIONS.items()):
        try:
            ida_kernwin.update_action_label(name, lb)
        except Exception:
            pass
    _ORIG_ACTIONS.clear()


# --------------------------------------------------------------------------- #
# Qt 事件过滤器 / 定时器
# --------------------------------------------------------------------------- #
class _EventFilter(QtCore.QObject if _QT_OK else object):
    def eventFilter(self, obj, ev):
        try:
            if _enabled and isinstance(obj, QtWidgets.QWidget):
                t = ev.type()
                if t == QtCore.QEvent.Show:
                    translate_object(obj, set())
                    # 有些控件 Show 之后才填充子项，下一轮事件循环再翻一次
                    QtCore.QTimer.singleShot(
                        0, lambda o=obj: translate_object(o, set()))
                elif t in (QtCore.QEvent.Polish, QtCore.QEvent.LayoutRequest):
                    if obj.isWindow() or isinstance(obj, QtWidgets.QMenu):
                        translate_object(obj, set())
        except Exception:
            pass
        return False


_filter = None
_timer = None
_hooks = None
_installed = False
_boot_timer = None
_LOG_STATE = {"n": 0, "welcome": False}


def _install_qt_hooks():
    global _filter, _timer, _installed
    if not _QT_OK:
        return
    app = QtWidgets.QApplication.instance()
    if app is None:
        return
    if _filter is None:
        _filter = _EventFilter()
    if not _installed:
        try:
            app.installEventFilter(_filter)
            _installed = True
        except Exception as e:
            log("install filter failed:", repr(e))
    if _timer is None:
        _timer = QtCore.QTimer()
        _timer.setInterval(600)
        _timer.timeout.connect(lambda: _enabled and translate_all())
    _timer.start()
    logf("qt hooks installed (filter=%s)" % (_installed,))


def _remove_qt_hooks():
    global _filter, _timer, _installed
    if not _QT_OK:
        return
    app = QtWidgets.QApplication.instance()
    if app is not None and _filter is not None and _installed:
        try:
            app.removeEventFilter(_filter)
        except Exception:
            pass
        _installed = False
    if _timer is not None:
        try:
            _timer.stop()
        except Exception:
            pass
    log("qt hooks removed")


# --------------------------------------------------------------------------- #
# UI_Hooks：等界面就绪后统一翻译
# --------------------------------------------------------------------------- #
logf("module import: reached _bootstrap_qt")


def _bootstrap_qt(*_args):
    """尽早安装 Qt 钩子。

    IDA 的启动窗口（如 Quick start）在任何数据库加载之前就弹出，此时
    ready_to_run 还没触发。这里在插件 init 阶段就尝试安装；若 QApplication
    尚未就绪，则用 IDAPython 定时器轮询重试，直到装上为止。
    """
    global _boot_timer
    if not _enabled:
        return 0
    app_ready = _QT_OK and QtWidgets.QApplication.instance() is not None
    if app_ready:
        _install_qt_hooks()
        translate_actions()
        translate_all()
        if _boot_timer is not None:
            try:
                ida_kernwin.unregister_timer(_boot_timer)
            except Exception:
                pass
            _boot_timer = None
        logf("bootstrap done")
    return 0


logf("module import: before _UIHooks")


class _UIHooks(ida_kernwin.UI_Hooks):
    def ready_to_run(self):
        # 界面就绪：翻译已注册的 action，并整体走一遍控件树
        _install_qt_hooks()
        translate_actions()
        translate_all()

    def updated_actions(self):
        # 菜单重建 / action 状态刷新后，补翻
        if _enabled:
            translate_actions()

    def widget_visible(self, widget):
        # 兜底：钩子还没装上时，借窗口可见事件补装一次（装好就不再重复）
        if _enabled and not _installed:
            _install_qt_hooks()
            translate_all()


# --------------------------------------------------------------------------- #
# 开关
# --------------------------------------------------------------------------- #
def set_enabled(on):
    global _enabled
    _enabled = bool(on)
    save_conf()
    if _enabled:
        _install_qt_hooks()
        translate_actions()
        translate_all()
    else:
        _remove_qt_hooks()
        restore_actions()
        # 还原当前可见控件文本
        translate_all(tr=restore_text)
    _refresh_action_icon()
    ida_kernwin.msg("[ida_i18n] 汉化已%s\n" % ("开启" if _enabled else "关闭"))


def toggle():
    set_enabled(not _enabled)


def reload_dict():
    load_dict()
    if _enabled:
        translate_actions()
        translate_all()
    ida_kernwin.msg("[ida_i18n] 词典已重载：%d 条\n" % len(DICT))


# --------------------------------------------------------------------------- #
# Action 注册
# --------------------------------------------------------------------------- #
logf("module import: before _ToggleHandler")


class _ToggleHandler(ida_kernwin.action_handler_t):
    def activate(self, ctx):
        toggle()
        return 1

    def update(self, ctx):
        return ida_kernwin.AST_ENABLE_ALWAYS


class _ReloadHandler(ida_kernwin.action_handler_t):
    def activate(self, ctx):
        reload_dict()
        return 1

    def update(self, ctx):
        return ida_kernwin.AST_ENABLE_FOR_IDB


_actions_registered = False


def _register_actions():
    global _actions_registered
    if _actions_registered:
        return
    _actions_registered = True
    try:
        if ida_kernwin.register_action(ida_kernwin.action_desc_t(
                ACT_TOGGLE, "中文汉化", _ToggleHandler(),
                None, "开启/关闭界面汉化")):
            ida_kernwin.attach_action_to_menu(
                "Options/", ACT_TOGGLE, ida_kernwin.SETMENU_APP)

        if ida_kernwin.register_action(ida_kernwin.action_desc_t(
                ACT_RELOAD, "重载汉化词典", _ReloadHandler(),
                None, "重新读取 ida_i18n_zh_CN.json")):
            ida_kernwin.attach_action_to_menu(
                "Options/", ACT_RELOAD, ida_kernwin.SETMENU_APP)
    except Exception as e:
        log("register actions failed:", repr(e))


def _refresh_action_icon():
    """开关状态用文字后缀反映（无图标资源，简单起见改 help）。"""
    try:
        ida_kernwin.update_action_label(
            ACT_RELOAD, "重载汉化词典")
    except Exception:
        pass


# --------------------------------------------------------------------------- #
# 插件入口
# --------------------------------------------------------------------------- #
logf("module import: before I18nPlugin")


class I18nPlugin(ida_idaapi.plugin_t):
    flags = ida_idaapi.PLUGIN_KEEP
    comment = "IDA UI Chinese localization (ida_i18n)"
    help = "在 Options 菜单中开关界面汉化"
    wanted_name = "ida_i18n"
    wanted_hotkey = ""

    def init(self):
        logf("init: called")
        _auto_start()
        return ida_idaapi.PLUGIN_KEEP

    def run(self, arg):
        toggle()

    def term(self):
        global _hooks, _boot_timer
        _remove_qt_hooks()
        if _boot_timer is not None:
            try:
                ida_kernwin.unregister_timer(_boot_timer)
            except Exception:
                pass
            _boot_timer = None
        if _hooks is not None:
            try:
                _hooks.unhook()
            except Exception:
                pass
            _hooks = None


logf("module import: before PLUGIN_ENTRY")


def PLUGIN_ENTRY():
    return I18nPlugin()


# --------------------------------------------------------------------------- #
# 兜底：实测发现某些情况下 IDA 会 *导入* 本模块却不调用 PLUGIN_ENTRY()/init()。
# 既然导入必定发生，这里在导入完成时幂等初始化一次，保证汉化一定生效。
# --------------------------------------------------------------------------- #
logf("module import: complete")


def _auto_start():
    """幂等初始化。带进程级互斥：无论由 idapythonrc、插件自动加载还是
    init() 触发，整个进程只真正初始化一次。"""
    global _hooks, _boot_timer
    if getattr(sys, _BOOT_FLAG, False):
        logf("auto_start: skipped (already booted)")
        return
    logf("auto_start: begin")
    ok = True
    try:
        load_conf()
        load_dict()
        _register_actions()
        if ida_kernwin.get_action_label(ACT_TOGGLE) is None:
            ok = False
            logf("auto_start: actions not registered")
        if _hooks is None:
            try:
                _hooks = _UIHooks()
                _hooks.hook()
            except Exception as e:
                ok = False
                logf("auto_start: hooks failed %r" % (e,))
        if _enabled and _QT_OK:
            if QtWidgets.QApplication.instance() is not None:
                _bootstrap_qt()
            else:
                try:
                    _boot_timer = ida_kernwin.register_timer(200, _bootstrap_qt)
                    logf("auto_start: register_timer -> %r" % (_boot_timer,))
                except Exception as e:
                    logf("auto_start: register_timer failed %r" % (e,))
        if ok:
            try:
                setattr(sys, _BOOT_FLAG, True)
            except Exception:
                pass
        logf("auto_start: done ok=%s" % ok)
    except Exception:
        logf("auto_start: FAILED\n" + traceback.format_exc())


try:
    _auto_start()
except Exception:
    logf("auto_start: crashed\n" + traceback.format_exc())
