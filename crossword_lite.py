#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
crossword-lite —— 迷你英文填字游戏

纯标准库实现：内置词库 → 自动生成交叉填字布局 → 回溯求解器演示 → 交互填词。

用法：
    python -m crossword_lite                  # 交互填词（中文提示）
    python -m crossword_lite --auto --games 3 --seed 42
    python -m crossword_lite --solve --seed 7  # 展示一次"生成→求解"全过程
"""

import argparse
import random
import sys
import time

VERSION = "1.0.0"

# ---------------------------------------------------------------------------
# 内置词库：常见英文单词（全部大写，去重，长度 3~8）
# ---------------------------------------------------------------------------
WORDS = list(dict.fromkeys([
    # 3 字母
    "CAT", "DOG", "SUN", "BUS", "CAR", "BOX", "KEY", "CUP", "PEN", "MAP",
    "ANT", "BEE", "EGG", "OAK", "ASH", "IVY", "PIG", "HEN", "FOX", "OWL",
    # 4 字母
    "FISH", "BIRD", "BOOK", "TREE", "STAR", "MOON", "LAKE", "SHIP", "BALL",
    "DOOR", "WALL", "ROOF", "CAKE", "MILK", "RICE", "BEAR", "WOLF", "LION",
    "TIGER", "SNAKE", "FROG", "DUCK", "KITE", "DOLL", "GAME", "SONG",
    # 5 字母
    "APPLE", "PEARL", "GRAPE", "LEMON", "MELON", "BREAD", "HOUSE", "WATER",
    "MUSIC", "DANCE", "CLOUD", "RIVER", "HORSE", "SHEEP", "MOUSE", "TRAIN",
    "PLANE", "CLOCK", "PHONE", "TABLE", "CHAIR", "QUEEN", "TULIP",
    # 6 字母
    "COFFEE", "JUICE", "BANANA", "ORANGE", "FLOWER", "FOREST", "RABBIT",
    "PLANET", "ROCKET", "SOCCER", "TENNIS", "PENCIL", "WINDOW",
    "GARDEN", "BRIDGE", "DESERT", "JUNGLE",
    # 7 字母
    "CHICKEN", "HAMSTER", "DOLPHIN", "PIANO", "VIOLIN", "TRUMPET",
    "SUNSET", "RAINBOW", "VOLCANO", "GLACIER", "MEADOW", "PIRATE",
    # 8 字母
    "TELEPHONE", "COMPUTER", "FOOTBALL", "BICYCLE", "AIRPLANE", "PYTHON",
]))

# 部分单词的中文释义（用于出题时的提示；没有释义的只提示字母数）
DEFINITIONS = {
    "CAT": "猫", "DOG": "狗", "SUN": "太阳", "MOON": "月亮", "STAR": "星星",
    "TREE": "树", "FISH": "鱼", "BIRD": "鸟", "BOOK": "书", "PEN": "钢笔",
    "CUP": "杯子", "BOX": "盒子", "KEY": "钥匙", "MAP": "地图", "BUS": "公交车",
    "CAR": "汽车", "SHIP": "船", "TRAIN": "火车", "PLANE": "飞机",
    "APPLE": "苹果", "GRAPE": "葡萄", "LEMON": "柠檬", "MELON": "瓜",
    "BREAD": "面包", "RICE": "米饭", "CAKE": "蛋糕", "MILK": "牛奶",
    "EGG": "鸡蛋", "COFFEE": "咖啡", "JUICE": "果汁",
    "WATER": "水", "WIND": "风", "RAIN": "雨", "SNOW": "雪",
    "CLOUD": "云", "RIVER": "河", "LAKE": "湖", "SEA": "海",
    "FOREST": "森林", "FLOWER": "花",
    "HORSE": "马", "SHEEP": "绵羊", "PIG": "猪", "TIGER": "老虎",
    "LION": "狮子", "BEAR": "熊", "WOLF": "狼", "SNAKE": "蛇", "FROG": "青蛙",
    "RABBIT": "兔子", "MOUSE": "老鼠", "HOUSE": "房子", "DOOR": "门",
    "WINDOW": "窗户", "WALL": "墙", "TABLE": "桌子", "CHAIR": "椅子",
    "CLOCK": "时钟", "PHONE": "电话", "MUSIC": "音乐", "SONG": "歌曲",
    "DANCE": "舞蹈", "GAME": "游戏", "BALL": "球", "KITE": "风筝",
    "QUEEN": "王后", "PIANO": "钢琴", "TRUMPET": "小号",
}

DIRS = {"across": (0, 1), "down": (1, 0)}
DIR_ZH = {"across": "横向", "down": "纵向"}


class Crossword:
    """填字布局：grid 存字母（"" 表示空格），placements 记录单词摆放。"""

    def __init__(self, size=15):
        self.size = size
        self.grid = [["" for _ in range(size)] for _ in range(size)]
        self.placements = []  # [{word, row, col, dir}]

    def can_place(self, word, row, col, direction):
        """检查单词能否摆放在 (row, col) 沿 direction，且至少交叉一个已有字母。"""
        dr, dc = DIRS[direction]
        n = len(word)
        cells = [(row + dr * i, col + dc * i) for i in range(n)]
        for (r, c) in cells:
            if not (0 <= r < self.size and 0 <= c < self.size):
                return False
        # 单词两端沿线方向的格子必须为空（或出界）
        for (r, c) in ((row - dr, col - dc), (row + dr * n, col + dc * n)):
            if 0 <= r < self.size and 0 <= c < self.size and self.grid[r][c]:
                return False
        touches = 0
        pr, pc = DIRS["down" if direction == "across" else "across"]
        for i, (r, c) in enumerate(cells):
            cur = self.grid[r][c]
            if cur:
                if cur != word[i]:
                    return False
                touches += 1
            else:
                # 新格子的垂直邻格必须为空，避免意外并排
                for (nr, nc) in ((r + pr, c + pc), (r - pr, c - pc)):
                    if 0 <= nr < self.size and 0 <= nc < self.size and self.grid[nr][nc]:
                        return False
        if self.placements and touches == 0:
            return False
        return True

    def place(self, word, row, col, direction):
        dr, dc = DIRS[direction]
        for i, ch in enumerate(word):
            self.grid[row + dr * i][col + dc * i] = ch
        self.placements.append({"word": word, "row": row, "col": col, "dir": direction})


def generate(word_list, size=15, max_words=12, seed=0):
    """生成填字布局：首词居中横放，其余词随机找交叉点放入。"""
    rng = random.Random(seed)
    cw = Crossword(size)
    cands = [w for w in word_list if len(w) <= size]
    if not cands:
        return cw
    first = max(cands, key=len)
    cw.place(first, size // 2, (size - len(first)) // 2, "across")
    placed = {first}
    remaining = [w for w in cands if w not in placed]
    rng.shuffle(remaining)
    progress = True
    while progress and len(cw.placements) < max_words:
        progress = False
        for w in list(remaining):
            spots = []
            for p in cw.placements:
                pdr, pdc = DIRS[p["dir"]]
                perp = "down" if p["dir"] == "across" else "across"
                dr, dc = DIRS[perp]
                for i, ch in enumerate(p["word"]):
                    cr, cc = p["row"] + pdr * i, p["col"] + pdc * i
                    for j, wc in enumerate(w):
                        if wc != ch:
                            continue
                        sr, sc = cr - dr * j, cc - dc * j
                        if cw.can_place(w, sr, sc, perp):
                            spots.append((sr, sc, perp))
            if spots:
                sr, sc, perp = rng.choice(spots)
                cw.place(w, sr, sc, perp)
                placed.add(w)
                remaining.remove(w)
                progress = True
                if len(cw.placements) >= max_words:
                    break
    return cw


def number_grid(cw):
    """标准填字编号：某格是横向/纵向单词起点则编号（从左上到右下）。"""
    starts = {}
    n = 1
    for r in range(cw.size):
        for c in range(cw.size):
            if not cw.grid[r][c]:
                continue
            start_across = (c == 0 or not cw.grid[r][c - 1]) and c + 1 < cw.size and cw.grid[r][c + 1]
            start_down = (r == 0 or not cw.grid[r - 1][c]) and r + 1 < cw.size and cw.grid[r + 1][c]
            if start_across or start_down:
                starts[(r, c)] = n
                n += 1
    return starts


def slots_of(cw):
    """把每个摆放转成"题槽"：编号、方向、格子坐标、长度、答案（生成时已知）。"""
    starts = number_grid(cw)
    slots = []
    for p in cw.placements:
        dr, dc = DIRS[p["dir"]]
        cells = [(p["row"] + dr * i, p["col"] + dc * i) for i in range(len(p["word"]))]
        slots.append({
            "num": starts.get((p["row"], p["col"])),
            "dir": p["dir"],
            "cells": cells,
            "length": len(p["word"]),
            "answer": p["word"],
        })
    slots.sort(key=lambda s: (s["num"] or 0, s["dir"]))
    return slots


def clue_text(slot):
    zh = DIR_ZH[slot["dir"]]
    defi = DEFINITIONS.get(slot["answer"])
    if defi:
        return "%s：%s（%d 个字母）" % (zh, defi, slot["length"])
    return "%s：%d 个字母的英文单词" % (zh, slot["length"])


def render(cw, fill=None, show_letters=False):
    """文本棋盘。fill 为用户已填字母；show_letters=True 显示答案。"""
    starts = number_grid(cw)
    lines = []
    for r in range(cw.size):
        parts = []
        for c in range(cw.size):
            ch = cw.grid[r][c]
            if not ch:
                parts.append("   ")
            elif show_letters:
                parts.append(" %s " % ch)
            else:
                f = fill[r][c] if fill else ""
                num = starts.get((r, c))
                if f:
                    parts.append(" %s " % f)
                elif num:
                    parts.append("%2d·" % num)
                else:
                    parts.append(" · ")
        lines.append("".join(parts).rstrip())
    return "\n".join(lines)


def solve_puzzle(cw, word_list, node_limit=200000):
    """回溯求解器：只用题槽+词库（不看答案），MRV 启发式。

    返回 (assignment 或 None, 搜索节点数)。assignment 为 {slot_index: word}。
    """
    slots = slots_of(cw)
    by_len = {}
    for w in dict.fromkeys(word_list):
        by_len.setdefault(len(w), []).append(w)
    assign = {}
    letters = {}
    nodes = [0]
    aborted = [False]

    def candidates(i):
        s = slots[i]
        out = []
        for w in by_len.get(s["length"], []):
            ok = True
            for k, cell in enumerate(s["cells"]):
                if cell in letters and letters[cell] != w[k]:
                    ok = False
                    break
            if ok:
                out.append(w)
        return out

    def bt():
        nodes[0] += 1
        if nodes[0] > node_limit:
            aborted[0] = True
            return None
        if len(assign) == len(slots):
            return dict(assign)
        best, best_c = -1, None
        for i in range(len(slots)):
            if i in assign:
                continue
            c = candidates(i)
            if not c:
                return False
            if best_c is None or len(c) < len(best_c):
                best, best_c = i, c
                if len(c) == 1:
                    break
        for w in best_c:
            assign[best] = w
            added = []
            for k, cell in enumerate(slots[best]["cells"]):
                if cell not in letters:
                    letters[cell] = w[k]
                    added.append(cell)
            r = bt()
            if aborted[0]:
                return None
            if r:
                return r
            del assign[best]
            for cell in added:
                del letters[cell]
        return False

    result = bt()
    return (None if aborted[0] else result), nodes[0]


# ---------------------------------------------------------------------------
# 演示 / 交互
# ---------------------------------------------------------------------------

def auto_demo(games, seed, size, max_words):
    for g in range(games):
        s = seed + g
        cw = generate(WORDS, size=size, max_words=max_words, seed=s)
        slots = slots_of(cw)
        t0 = time.time()
        sol, nodes = solve_puzzle(cw, WORDS)
        dt = time.time() - t0
        print("=== 第 %d/%d 局（seed=%d）===" % (g + 1, games, s))
        print("单词数：%d，棋盘：%dx%d" % (len(slots), size, size))
        if sol is None:
            print("求解：节点超限未完成（%d 节点）" % nodes)
        else:
            ok = len(sol) == len(slots)
            print("求解：%s（%d 节点，用时 %.2fs）" % ("成功" if ok else "失败", nodes, dt))
        print(render(cw, show_letters=True))
        print()


def solve_demo(seed, size, max_words):
    cw = generate(WORDS, size=size, max_words=max_words, seed=seed)
    slots = slots_of(cw)
    print("【待填棋盘】（数字为题号）")
    print(render(cw))
    print("\n【题面】")
    for s in slots:
        tag = "A" if s["dir"] == "across" else "D"
        print("  %d%s  %s" % (s["num"], tag, clue_text(s)))
    t0 = time.time()
    sol, nodes = solve_puzzle(cw, WORDS)
    dt = time.time() - t0
    print("\n【求解器】节点 %d，用时 %.2fs" % (nodes, dt))
    if sol is None:
        print("节点超限，未求出完整解。")
        return
    for i in sorted(sol):
        s = slots[i]
        tag = "A" if s["dir"] == "across" else "D"
        mark = "✓" if sol[i] == s["answer"] else "(原答案 %s)" % s["answer"]
        print("  %d%s = %s %s" % (s["num"], tag, sol[i], mark))
    print("\n【答案棋盘】")
    print(render(cw, show_letters=True))


def play_interactive(seed, size, max_words):
    cw = generate(WORDS, size=size, max_words=max_words, seed=seed)
    slots = slots_of(cw)
    if not slots:
        print("生成失败，请换个 seed 再试。")
        return 1
    fill = [["" for _ in range(size)] for _ in range(size)]
    slot_done = [False] * len(slots)
    slot_by_key = {}
    for i, s in enumerate(slots):
        key = "%d%s" % (s["num"], "A" if s["dir"] == "across" else "D")
        slot_by_key[key.upper()] = i

    print("=== 迷你填字游戏 ===")
    print("输入如 `3A APPLE` 填词（题号 + A横向/D纵向 + 单词），`show` 看答案，`q` 退出。\n")
    while True:
        print(render(cw, fill=fill))
        print("\n【题面】")
        for i, s in enumerate(slots):
            key = "%d%s" % (s["num"], "A" if s["dir"] == "across" else "D")
            flag = " ✓" if slot_done[i] else ""
            print("  %s%s  %s" % (key, flag, clue_text(s)))
        if all(slot_done):
            print("\n🎉 全部填完，通关！")
            return 0
        try:
            cmd = input("\n> ").strip()
        except EOFError:
            print()
            return 0
        if not cmd:
            continue
        if cmd.lower() in ("q", "quit"):
            print("已退出。")
            return 0
        if cmd.lower() == "show":
            print(render(cw, show_letters=True))
            return 0
        parts = cmd.upper().split()
        if len(parts) != 2 or parts[0] not in slot_by_key:
            print("格式不对，示例：3A APPLE")
            continue
        i = slot_by_key[parts[0]]
        s = slots[i]
        word = parts[1]
        if len(word) != s["length"]:
            print("长度不对，这题要 %d 个字母。" % s["length"])
            continue
        if not word.isalpha():
            print("只能填英文字母。")
            continue
        if word not in WORDS:
            print("词库里没有这个词（本题只接受内置词库中的单词）。")
            continue
        conflict = False
        for k, (r, c) in enumerate(s["cells"]):
            if fill[r][c] and fill[r][c] != word[k]:
                conflict = True
                break
        if conflict:
            print("与已填的交叉字母冲突。")
            continue
        for k, (r, c) in enumerate(s["cells"]):
            fill[r][c] = word[k]
        slot_done[i] = True
        print("%s 填入成功！" % parts[0])


def main(argv=None):
    ap = argparse.ArgumentParser(description="crossword-lite：迷你英文填字游戏（生成/求解/交互）")
    ap.add_argument("--auto", action="store_true", help="自动演示：生成 N 局并求解")
    ap.add_argument("--games", type=int, default=3, help="--auto 的局数（默认 3）")
    ap.add_argument("--solve", action="store_true", help="展示一次 生成→求解 全过程")
    ap.add_argument("--seed", type=int, default=42, help="随机种子（默认 42）")
    ap.add_argument("--size", type=int, default=15, help="棋盘边长（默认 15）")
    ap.add_argument("--max-words", type=int, default=12, help="最多单词数（默认 12）")
    args = ap.parse_args(argv)

    if args.auto:
        auto_demo(args.games, args.seed, args.size, args.max_words)
        return 0
    if args.solve:
        solve_demo(args.seed, args.size, args.max_words)
        return 0
    if not sys.stdin.isatty():
        print("交互模式需要终端；请加 --auto 或 --solve 使用非交互演示。")
        return 2
    return play_interactive(args.seed, args.size, args.max_words)


if __name__ == "__main__":
    sys.exit(main())
