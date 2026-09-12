# -*- coding: utf-8 -*-
"""append_problems_entry.py — 安全地向 PROBLEMS.md 追加登记项（PROBLEMS 只进 git、纯人工账本）

为什么需要一个脚本：`PROBLEMS.md` 是 CRLF 文件（`git ls-files --eol` 显示 `i/lf w/crlf`），
而任何普通文本编辑器都可能把它整份改写成 LF，diff 会变成全文重写、真实改动被淹没。
本脚本**只按 `"\\r\\n"` 切分与拼回**，写前断言全文没有裸 LF，写后断言行数恰好增加 N。

用法
    python audit/append_problems_entry.py --fragment <片段文件>            # 追加
    python audit/append_problems_entry.py --fragment <片段文件> --dry-run   # 只看会写什么
    python audit/append_problems_entry.py --fragment <片段文件> --replace-row 58   # 改写第 58 条

片段文件是一份 UTF-8 文本，每行是**一条完整的表格行**（`| 编号 | 现象 | 处置 |`），
不带换行符分隔之外的东西；脚本会把它的各行依次追加到表尾。
脚本不生成内容、不做判断——编号与文字由人（或调用它的 agent）写死在片段里。
`--replace-row` 用于既有条目状态变化（例如「未修」改成「已修」）：同样按 `"\r\n"` 切分整份
文件，只换掉编号匹配的那一行，其余行逐字节不动。
"""
import argparse
import io
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LEDGER = os.path.join(ROOT, "PROBLEMS.md")


def load_crlf(path):
    raw = io.open(path, "rb").read()
    if b"\n" in raw.replace(b"\r\n", b""):
        sys.exit("%s 里有裸 LF——账本必须是纯 CRLF，拒绝在它上面动手" % path)
    return raw.decode("utf-8").split("\r\n")


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--fragment", required=True)
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--replace-row", type=int,
                    help="改写编号等于该值的既有条目行（片段只给这一行）")
    ap.add_argument("--set-disposition", type=int,
                    help="只改写该编号条目的「处置」一格（片段给处置正文，不带竖线）")
    a = ap.parse_args()

    lines = load_crlf(LEDGER)
    frag = io.open(a.fragment, "rb").read().decode("utf-8")
    new_lines = [l for l in frag.replace("\r\n", "\n").split("\n") if l.strip()]
    if not new_lines:
        sys.exit("片段是空的")

    if a.replace_row is not None:
        if len(new_lines) != 1:
            sys.exit("--replace-row 只接受片段里恰好一行")
        marker = "| %d |" % a.replace_row
        idx = [i for i, l in enumerate(lines) if l.startswith(marker)]
        if len(idx) != 1:
            sys.exit("编号 %d 在账本里出现 %d 次，拒绝改" % (a.replace_row, len(idx)))
        i = idx[0]
        print("改第 %d 行（原 %d 字符 -> 新 %d 字符）：" % (i + 1, len(lines[i]), len(new_lines[0])))
        print("  旧：" + lines[i][:200] + "…")
        print("  新：" + new_lines[0][:200] + "…")
        if a.dry_run:
            print("--dry-run：未写。")
            return
        lines[i] = new_lines[0]
        data = ("\r\n".join(lines)).encode("utf-8")
        io.open(LEDGER + ".tmp", "wb").write(data)
        os.replace(LEDGER + ".tmp", LEDGER)
        assert len(load_crlf(LEDGER)) == len(lines), "行数变了，别提交"
        print("已改写第 %d 条（纯 CRLF，行数不变）" % a.replace_row)
        return

    if a.set_disposition is not None:
        text = io.open(a.fragment, "rb").read().decode("utf-8")
        text = " ".join(text.replace("\r\n", "\n").split("\n")).strip()
        if not text:
            sys.exit("片段是空的")
        marker = "| %d |" % a.set_disposition
        idx = [i for i, l in enumerate(lines) if l.startswith(marker)]
        if len(idx) != 1:
            sys.exit("编号 %d 在账本里出现 %d 次，拒绝改" % (a.set_disposition, len(idx)))
        i = idx[0]
        parts = lines[i].split(" | ")
        if len(parts) != 3 or not parts[2].rstrip().endswith("|"):
            sys.exit("第 %d 条不是 `| 号 | 现象 | 处置 |` 三段式（实际 %d 段），拒绝改——"
                     "不要按 | 硬切，先在片段里手写整行再用 --replace-row" % (a.set_disposition, len(parts)))
        old_disp = parts[2]
        lines[i] = " | ".join([parts[0], parts[1], text + " |"])
        print("第 %d 条处置：%d 字符 -> %d 字符" % (a.set_disposition, len(old_disp), len(text) + 2))
        print("  旧：" + old_disp[:200] + "…")
        print("  新：" + text[:200] + "…")
        if a.dry_run:
            print("--dry-run：未写。")
            return
        data = ("\r\n".join(lines)).encode("utf-8")
        io.open(LEDGER + ".tmp", "wb").write(data)
        os.replace(LEDGER + ".tmp", LEDGER)
        assert len(load_crlf(LEDGER)) == len(lines), "行数变了，别提交"
        print("已改写第 %d 条的处置（纯 CRLF，行数不变）" % a.set_disposition)
        return

    # 追加前先把表尾现状打出来：编号是否接得上，看这一行
    tail = [l for l in lines if l.startswith("| ") and l.strip().endswith("|")]
    print("现有登记项 %d 条，最后一条：" % (len(tail) - 1))
    print("  " + (tail[-1][:160] if tail else "(无)"))
    print("将追加 %d 行：" % len(new_lines))
    for l in new_lines:
        print("  " + l[:200] + ("…" if len(l) > 200 else ""))
    if a.dry_run:
        print("--dry-run：未写。")
        return

    out = lines + new_lines
    data = ("\r\n".join(out)).encode("utf-8")
    io.open(LEDGER + ".tmp", "wb").write(data)
    os.replace(LEDGER + ".tmp", LEDGER)

    after = load_crlf(LEDGER)
    assert len(after) == len(lines) + len(new_lines), "行数没对上，别提交"
    print("已写入 %s（%d 行 -> %d 行，纯 CRLF）" % (LEDGER, len(lines), len(after)))


if __name__ == "__main__":
    sys.exit(main())
