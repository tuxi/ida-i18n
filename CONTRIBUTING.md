# 贡献指南

感谢愿意帮忙！这个项目最需要的是**补词条**和**多平台验证**，两者都不需要读懂插件代码。

## 一、补词条（最容易上手）

词典就是「英文原文 → 中文」，文件是 `ida_i18n_zh_CN.json`。

1. 在 IDA 里找到没被翻译的文本，**照抄英文原文**（含结尾的 `...` 也照抄）；
2. 加进 `ida_i18n_zh_CN.json`（键写原文，`&` / `~` / 结尾 `...` 可省）：

   ```json
   "Load file": "加载文件",
   "Produce file": "生成文件"
   ```

3. 在 IDA 里点 `Options → 重载汉化词典` 自测；
4. 提交 PR，附一张截图更好。

**不用改** `tools/` 下的生成器，除非你想批量补；直接改 json 即可。

> 提交前请先看 README 的「已知限制」：内核输出窗口、状态栏、
> chooser 列头（如 `Function name`）等属于当前**无法覆盖**的部分，不用报。

## 二、平台验证（当前待办）

| 平台 | 状态 |
|---|---|
| macOS (arm64) | ✅ 已在 IDA 9.3.251224 实测通过 |
| Windows | ❌ **未验证**（作者没有 Windows 机器） |
| Linux | ❌ **未验证** |

如果你有 Windows / Linux 环境，帮忙确认一下（不用改代码）：

1. 按 README「安装」把 `ida_i18n.py` + `ida_i18n_zh_CN.json` 放进
   `%APPDATA%\Hex-Rays\IDA Pro\plugins\`（Windows）或 `~/.idapro/plugins/`；
2. 把 `idapythonrc.py` 放到用户目录（与 `plugins/` 同级）；
3. 重启 IDA，看 `Options` 菜单里是否出现 **中文汉化** / **重载汉化词典**；
4. 开个 issue 说明结果（成功/失败），成功的话会更新上表与 README 徽章。

失败时请把 `ida_i18n.py` 里的 `_LOG` 改成 `True` 后重启，附上
`ida_i18n.log` 内容——通常能直接定位。

## 三、适配新版本（例如 9.4）的 checklist

IDA 升级后插件代码一般不用动，主要是补词典。按顺序做，**别漏了末尾三条同步项**：

**适配**

- [ ] 在新版本 IDA 里 `File → Script file...` 运行 `tools/dump_actions_reference.py`，
      然后 `git diff tools/actions_reference.txt` 找出新增/改名的 action
- [ ] `python3 tools/extract_dialog_strings.py --binary "<新版本可执行文件>" --outdir /tmp/ida_new`
      提取新的对话框候选文案
- [ ] 把新增/变化的英文补进 `ida_i18n_zh_CN.json`
- [ ] 如需批量补，更新 `tools/build_actions_dict.py` / `tools/build_dialog_dict.py` 后重新生成
- [ ] 在目标版本实测：主菜单、右键菜单、`Options` 各对话框、启动窗口（Quick start）
- [ ] 确认 `Options → 中文汉化 / 重载汉化词典` 两个开关仍在
- [ ] 若新版本改了控件结构，在 `ida_i18n.py` 的 `translate_object()` 里补对应控件类型

**版本同步（三处必须一起改，否则文档会自相矛盾）**

- [ ] README 顶部「**支持版本**」那行文字
- [ ] README 徽章 `IDA_Pro-9.3` → 新版本号
- [ ] `CHANGELOG.md` 增加新版本条目（功能 / 已知限制 / 支持版本）

**收尾**

- [ ] 更新本文件「平台验证」表（如在新平台验证过）
- [ ] 打 tag 并建 Release：`git tag -a v1.1.0 -m "..."` + `git push --tags`
- [ ] 在 GitHub 上用 `CHANGELOG.md` 对应段落作为 Release notes

## 四、提交规范

- 提交信息遵循 [Conventional Commits](https://www.conventionalcommits.org/zh-hans/)：
  `feat: ...` / `fix: ...` / `docs: ...` / `chore: ...`
- PR 尽量小而聚焦：一个 PR 只做一类事（补词条、修 bug、文档）
- 词典改动请说明来源（哪个界面看到、或 IDA 版本）

## 五、不要提交的内容

- ❌ 任何 IDA 程序文件、安装包、授权文件（`idapro.hexlic`）、keygen / 破解脚本
- ❌ 含本机用户名、项目路径的截图（提交前请打码）
- 这些会让仓库涉及侵权，请务必避免。
