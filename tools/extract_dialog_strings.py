# -*- coding: utf-8 -*-
"""从 IDA 主程序可执行文件里提取候选界面文案（对话框/表单标签）。

类别1: 带 Qt 加速键 "&X" 的标签（几乎必是界面控件文本）
类别2: 标题型短语（对话框标题、分组框）

用法:
    python3 extract_dialog_strings.py \
        --binary "/Applications/IDA Professional 9.3.app/Contents/MacOS/ida" --outdir .

产出（写入 --outdir）:
    _dlg_mnemonic.txt   带加速键的标签
    _dlg_title.txt      标题型短语
    _dlg_final.txt      过滤后的合并候选（供人工翻译）

注意: 本脚本只读取你自己机器上已安装的 IDA 可执行文件，不包含任何 IDA 内容。
"""
import argparse
import os
import re

DEFAULT_BIN = "/Applications/IDA Professional 9.3.app/Contents/MacOS/ida"

BAD = set("%#\\{}<>@*|\t\"~`^")
ALNUM_SP = re.compile(r"^[A-Za-z0-9 &()\[\]{}/.,'\-+*:;!?=]+$")


def load_strings(path):
    b = open(path, "rb").read()
    out = set()
    for r in re.findall(rb"[ -~]{2,90}", b):
        out.add(r.decode("ascii", "ignore").strip())
    return out


def readable(s):
    if not (4 <= len(s) <= 60):
        return False
    if any(ch in BAD for ch in s):
        return False
    if not ALNUM_SP.match(s):
        return False
    if sum(c.isalpha() for c in s) < 3:
        return False
    good = sum(c.isalpha() or c == " " for c in s)
    return good / len(s) >= 0.80


def extract(strings):
    mnemonic = set()
    for s in strings:
        if re.search(r"&[A-Za-z]", s):
            n = s.replace("&", "").strip()
            if readable(n) and " " in n and not n.endswith("."):
                mnemonic.add(n)

    title = set()
    pat = re.compile(r"^[A-Z][A-Za-z0-9 ,'()/.:+\-]{2,40}$")
    for s in strings:
        if "&" in s or not pat.match(s) or s.endswith(".") or " " not in s:
            continue
        if len(s.split()) > 6 or not readable(s):
            continue
        title.add(s)

    STOP = ("AUTOHIDE", "ACTION ", "BUTTON ", "ICON ", "STARTITEM", "ACCEPT",
            "CHECKBOX", "RADIO", "GROUPBOX", "SEPARATOR", "ENDITEM", "NONE")
    MSG = (" is ", " are ", " was ", " were ", "cannot", "can not", "can't",
           "failed", "invalid", "expected", " error", "must ", "should ",
           "unable", "not found", "instead of", "deprecated")

    def ok_title(s):
        if s.isupper() or any(s.startswith(t) for t in STOP):
            return False
        low = " " + s.lower() + " "
        if any(m in low for m in MSG):
            return False
        return not any(len(w) > 2 and w.isupper() for w in s.split())

    title = {s for s in title if ok_title(s)}
    mnemonic -= title
    final = sorted(mnemonic | title)
    return mnemonic, title, final


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--binary", default=DEFAULT_BIN,
                    help="IDA 主程序可执行文件路径")
    ap.add_argument("--outdir", default=".",
                    help="输出目录（默认当前目录）")
    args = ap.parse_args()

    if not os.path.exists(args.binary):
        raise SystemExit("找不到文件: %s（用 --binary 指定）" % args.binary)

    strings = load_strings(args.binary)
    mnemonic, title, final = extract(strings)
    os.makedirs(args.outdir, exist_ok=True)
    for name, data in [("_dlg_mnemonic.txt", sorted(mnemonic)),
                       ("_dlg_title.txt", sorted(title)),
                       ("_dlg_final.txt", final)]:
        with open(os.path.join(args.outdir, name), "w", encoding="utf-8") as f:
            f.write("\n".join(data))
    print("strings: %d  mnemonic: %d  title: %d  final: %d"
          % (len(strings), len(mnemonic), len(title), len(final)))


if __name__ == "__main__":
    main()
