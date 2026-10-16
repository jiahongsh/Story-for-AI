#!/usr/bin/env python3
"""Build a read-only, source-bound CORE foreshadow index for selected chapters.

The index is deliberately narrower than a complete foreshadow audit. An absent
entry means not yet audited, never "none". It never writes to tracking or prose.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path


HERE = Path(__file__).resolve().parent
BOOK = HERE.parents[2]
MASTER = BOOK / "大纲" / "伏笔总表.md"
STATE = BOOK / "追踪" / "_tracking-state.json"
BODY = BOOK / "正文"
MANIFEST = HERE / "source_manifest.json"
OUTPUT_JSON = HERE / "早期伏笔逐章.json"
OUTPUT_MD = HERE / "早期伏笔索引.md"
CHAPTERS = list(range(1, 51)) + list(range(96, 100))

# A line number plus a literal substring is an intentional reviewed anchor.
# Claims stay within what that particular line and the CORE master jointly allow.
EVIDENCE = [
    (10, "F11", "方法前置（未构成猫眼角色首埋）", "守钟人要求保留冲突版本；这是方法意识，尚未立住猫眼的纸质版本习惯。", [(125, "别删"), (151, "先把不同版本留下")]),
    (11, "F09", "首埋", "镜辞将旧名对应的原芽材料与当前存在的后续选择分页，并给当前存在留空白姓名栏。", [(13, "来源完全不同"), (23, "右页写"), (25, "当前存在"), (27, "空着")]),
    (17, "F11", "角色基础首埋", "猫眼把纸件、缓存、当前页并排，抢存被替换页面，打印校验值；其版本保存原则在行动中成立。", [(95, "纸件扫描"), (139, "版本刚被替换"), (223, "文件校验值")]),
    (19, "F11", "推进", "猫眼明确关页面不能代替证据，镜辞继续保留未被修掉的版本。", [(85, "关页面不算证据"), (197, "版本留下来")]),
    (32, "F01", "首埋", "许棠人工恢复的门禁权限次晨失效，页面出现02:17同步记录；原因尚未证明。", [(301, "人工恢复的权限已经被覆盖"), (303, "同步记录"), (307, "02:17")]),
    (33, "F01", "推进", "四份日志证明上游同步覆盖人工修正；502永久家庭成员字段又在停用后重新签发下游凭证。", [(29, "上游关系数据同步"), (31, "本地人工修改覆盖"), (131, "四份记录"), (205, "重新签发移动通行凭证")]),
    (38, "F11", "推进", "猫眼用带导出时间、校验值的两版截图比较字段，限定自己只比版本，不断言来源。", [(137, "导出时间和校验值"), (145, "我只比了版本")]),
    (39, "F04", "前兆／正式四分工未埋", "徐师傅保留502四年前换锁旧件和存根，形成“锁”一路的现实边界证据；旧值班册与四分工未在此出现。", [(49, "票据存根"), (99, "东西留在我这儿"), (141, "旧件及票据存根")]),
    (42, "F09", "推进", "空白姓名页影响镜辞的方法选择；眼前存在拒借旧同学群替他查照片并主动取消旧称呼留位，关系后果落实。", [(95, "空白姓名页"), (107, "留着位子"), (113, "不留位了"), (115, "草稿也被他取消")]),
    (43, "F02", "前兆／正式指标未埋", "物业自动说明与住户推断形成统一社会口径，但正文没有“关系说明口径一致率”正式考核指标。", [(3, "物业自动说明"), (7, "不需要注明来源的前情"), (33, "普通而完整的传播路径")]),
    (45, "F01", "推进", "物业立起人工“身份／关系争议中”状态并保存纸页；02:17上游同步仍在队列。", [(69, "身份／关系争议中"), (117, "下一次上游同步任务"), (121, "02:17")]),
    (45, "F11", "推进", "猫眼要求分开保存三份材料，物业另留离线副本与纸页，维持版本独立。", [(109, "离线副本"), (113, "分开存"), (115, "打印两份")]),
    (46, "F01", "推进", "02:17把人工争议页与门禁限制顶回正常，纸页和本地日志保住已存在的争议状态。", [(11, "争议中"), (15, "02:17"), (23, "黄色状态确实存在过")]),
    (50, "F01", "推进", "另两处记录也显示02:17覆盖人工异议，后续工单出现恒泰设施；发起来源仍未知。", [(113, "两组版本记录"), (115, "发起任务的真实来源")]),
    (50, "F11", "推进", "猫眼并列提供跨社区的版本记录，却没有从同名维护单位推断同一制造者。", [(113, "两组版本记录"), (115, "没有说三起事件由同一方制造")]),
    (96, "F03", "八年材料推进（承第095章嫌疑）", "猫眼带入周衡八年履历纸档；过整的早期履历只构成疑问，不证明伪造者或身份结论。", [(17, "纸质旧版本"), (21, "整齐还不能证明")]),
    (96, "F11", "推进", "猫眼仍优先摊开带出处和校验的纸质旧版，再讨论屏幕版本。", [(17, "校验和出处")]),
    (97, "F03", "推进", "独立旧版与现系统冲突，最早三年存在回填痕迹；实施者和当年事实仍待核。", [(5, "后来版本里被改写或回填"), (7, "哪些事当时真发生过"), (13, "实施者未知")]),
    (97, "F11", "推进", "旧纸表、交接本、缓存等互不隶属的版本被保留并与近年材料分开。", [(5, "纸质住户汇总表"), (31, "冲突页与近五年的材料分开收好")]),
    (98, "F03", "推进", "近五年留下分散的现实关系后果；正文明确把早期回填与后五年选择并列，身份结论继续开放。", [(5, "材料散在聊天"), (9, "这题仍空着"), (11, "两条并排")]),
    (98, "F11", "推进", "猫眼及镜辞把旧冲突页与近五年的独立关系材料分开保存，不让一个版本吞掉另一版。", [(3, "近五年"), (11, "两页纸分开压好")]),
    (99, "F03", "边界维持", "周衡到店修表，近距观察仍未见缝；正常维修发生，但无法据此判定身份。", [(21, "近距首触，接缝未立"), (25, "维修单")]),
]


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def rel(path: Path) -> str:
    return path.relative_to(BOOK).as_posix()


def chapter_path(number: int) -> Path:
    matches = sorted(BODY.glob(f"第{number:03d}章*.md"))
    if len(matches) != 1:
        raise ValueError(f"第{number:03d}章期望唯一活动正文，实际 {len(matches)}：{matches}")
    return matches[0]


def capture_manifest() -> dict:
    state = json.loads(STATE.read_text(encoding="utf-8-sig"))
    if state.get("state_revision") != 175:
        raise ValueError(f"仅为 r175 冻结来源；当前是 r{state.get('state_revision')}")
    return {
        "schema": "early-core-foreshadow-source-manifest-v1",
        "authority_note": "本文件仅为辅助阅读索引的来源指纹，不是伏笔状态正史。",
        "core_master": {"path": rel(MASTER), "sha256": sha(MASTER)},
        "tracking": {"path": rel(STATE), "revision": 175, "sha256": sha(STATE)},
        "chapters": {
            f"{ch:03d}": {"path": rel(chapter_path(ch)), "sha256": sha(chapter_path(ch))}
            for ch in CHAPTERS
        },
    }


def verify_manifest(manifest: dict) -> None:
    if manifest.get("schema") != "early-core-foreshadow-source-manifest-v1":
        raise ValueError("来源清单 schema 不匹配")
    for label, path in (("CORE总表", MASTER), ("追踪状态", STATE)):
        key = "core_master" if label == "CORE总表" else "tracking"
        binding = manifest[key]
        if binding["path"] != rel(path) or binding["sha256"] != sha(path):
            raise ValueError(f"{label}来源变化；本索引须重审，不能静默重建")
    state = json.loads(STATE.read_text(encoding="utf-8-sig"))
    if state.get("state_revision") != manifest["tracking"]["revision"]:
        raise ValueError("追踪修订号与来源清单不一致")
    if list(manifest["chapters"]) != [f"{ch:03d}" for ch in CHAPTERS]:
        raise ValueError("章节覆盖范围不符")
    for ch in CHAPTERS:
        binding = manifest["chapters"][f"{ch:03d}"]
        path = chapter_path(ch)
        if binding["path"] != rel(path) or binding["sha256"] != sha(path):
            raise ValueError(f"第{ch:03d}章活动正文变化；本索引须重审")


def build(manifest: dict) -> tuple[dict, str]:
    verify_manifest(manifest)
    master_lines = MASTER.read_text(encoding="utf-8-sig").splitlines()
    section_lines = {}
    for i, line in enumerate(master_lines, 1):
        match = re.match(r"^## (F\d{2})｜", line)
        if match:
            section_lines[match.group(1)] = i
    for core in {entry[1] for entry in EVIDENCE}:
        if core not in section_lines:
            raise ValueError(f"CORE总表缺少 {core} 节")

    per_chapter = {}
    for ch in CHAPTERS:
        binding = manifest["chapters"][f"{ch:03d}"]
        per_chapter[f"{ch:03d}"] = {
            "chapter": ch,
            "prose_path": binding["path"],
            "prose_sha256": binding["sha256"],
            "coverage": "限定证据已核；本章其他CORE项仍待逐条核对",
            "core_evidence": [],
        }
    for ch, core, phase, claim, anchors in EVIDENCE:
        binding = manifest["chapters"][f"{ch:03d}"]
        lines = (BOOK / binding["path"]).read_text(encoding="utf-8-sig").splitlines()
        refs = []
        for lineno, fragment in anchors:
            if not 1 <= lineno <= len(lines) or fragment not in lines[lineno - 1]:
                raise ValueError(f"正文锚点失效：{ch:03d} {core} L{lineno} {fragment!r}")
            refs.append({"line": lineno, "exact_prose_line": lines[lineno - 1]})
        per_chapter[f"{ch:03d}"]["core_evidence"].append({
            "namespace": "CORE",
            "core_id": core,
            "phase": phase,
            "limited_claim": claim,
            "prose_sha256": binding["sha256"],
            "prose_refs": refs,
            "core_master_sha256": manifest["core_master"]["sha256"],
            "core_master_section_line": section_lines[core],
            "tracking_r175_sha256": manifest["tracking"]["sha256"],
        })
    for entry in per_chapter.values():
        if not entry["core_evidence"]:
            entry["coverage"] = "未逐条核对（未知；不等于无伏笔）"

    state = json.loads(STATE.read_text(encoding="utf-8-sig"))
    track_sample = {}
    for track_id in ("F001", "F009", "F046", "F049"):
        item = state["foreshadow"][track_id]
        track_sample[track_id] = {
            "namespace": "TRACK",
            "id": track_id,
            "summary": item.get("summary"),
            "status": item.get("status"),
            "planted_chapter": item.get("planted_chapter"),
        }

    doc = {
        "schema": "early-core-foreshadow-index-v1",
        "scope": "活动正文第001—050、096—099章；只索引CORE总表与活动正文共同支持的限定证据。",
        "authority": "辅助阅读视图；规划生命周期见大纲/伏笔总表.md，已发生见活动正文，追踪当前状态见追踪/_tracking-state.json。",
        "not_a_complete_audit": True,
        "no_historic_transaction_inferred": True,
        "source_manifest": "创作运行/2026-10-06_第六批早期验收修复/早期伏笔索引/source_manifest.json",
        "core_master": manifest["core_master"],
        "tracking": manifest["tracking"],
        "namespace_rule": "CORE F01…F12 与 TRACK F001… 是独立编号空间，数字近似不构成映射；本索引不改追踪伏笔状态。",
        "track_examples": track_sample,
        "chapters": per_chapter,
    }

    rows = []
    for ch in CHAPTERS:
        item = per_chapter[f"{ch:03d}"]
        evs = item["core_evidence"]
        codes = "；".join(f"{ev['core_id']} {ev['phase']}" for ev in evs) if evs else "待核"
        rows.append(f"| {ch:03d} | {codes} | `{item['prose_sha256']}` |")
    detail = []
    for ch in CHAPTERS:
        item = per_chapter[f"{ch:03d}"]
        for ev in item["core_evidence"]:
            loc = "、".join(f"L{ref['line']}" for ref in ev["prose_refs"])
            detail.append(
                f"| {ch:03d} | {ev['core_id']} | {ev['phase']} | {ev['limited_claim']} | "
                f"`{item['prose_path']}:{loc}`；总表 L{ev['core_master_section_line']} |"
            )
    md = "\n".join([
        "# 早期 CORE 伏笔来源索引（r175）",
        "",
        "> 辅助阅读视图，不是第二份正史。只登记当前活动正文与《伏笔总表》共同支持的限定证据；未列项、未核章一律是“待核”，不能读成“无伏笔”。不补造历史追踪事务。",
        "",
        f"- CORE总表：`{manifest['core_master']['path']}`；SHA-256 `{manifest['core_master']['sha256']}`。",
        f"- 追踪状态：`{manifest['tracking']['path']}`；r175；SHA-256 `{manifest['tracking']['sha256']}`。",
        "- 每章正文 SHA-256 与每条证据的精确行文、行号均在 [早期伏笔逐章.json](早期伏笔逐章.json)；下表也列全量正文哈希。",
        "- 本目录运行 `python build_early_foreshadow_index.py --check` 可校验来源、证据锚点与派生文件；若正文、总表或追踪有变更，检查会失败，须人工重审并重新冻结来源。",
        "",
        "## 编号与状态边界",
        "",
        "`CORE F01…F12` 是《伏笔总表》的跨卷结构编号；`TRACK F001…` 是追踪系统内的逐章承诺编号。不能因数字相似而合并：例如 CORE F09 是眼前存在的空白姓名栏，TRACK F009 则是陈屿问南岸和502后的待回收承诺。CORE F01 与 TRACK F001 都涉及02:17，也仍是两个不同的账本项。",
        "",
        "本索引只判“在该章有何可指认的文本证据”。总表已确定 CORE F02、F04 在本区间分别只有第043、039章前兆，**正式指标与四分工仍未埋**；CORE F03 的第095章初起嫌疑在本索引范围外，第096—099章记录后续纸档和边界。CORE F05—F08、F10、F12 在001—050尚未逐条复核，不从本索引推断未出现。",
        "",
        "## 逐章覆盖与正文指纹",
        "",
        "| 章 | 本索引已核限定证据（其余项仍待核） | 活动正文 SHA-256 |",
        "|---:|---|---|",
        *rows,
        "",
        "## 已核证据与位置",
        "",
        "| 章 | CORE | 限定阶段 | 只由正文支持的结论 | 正文位置／总表位置 |",
        "|---:|---|---|---|---|",
        *detail,
        "",
        "## 留存的核对缺口",
        "",
        "1. 本索引只覆盖总表已明确重算的 F01、F02、F04、F09、F11 及第096—099章的 F03。其他 CORE 项不能用本索引判“无”。",
        "2. 未命中证据的章节记录为“待核”；有证据章节也未穷尽所有小型、局部伏笔。逐章紧凑记录中“伏笔变化：无”不能替代这项查验。",
        "3. 第095章 F03 嫌疑、第051—095章 F09 等推进、第100—103章锁定正文不在本次逐章范围；引用它们应重新读对应活动正文与来源版本。",
        "4. 此索引本身只读；已核F01/F09/F11里程碑已由独立的17次历史修订事务提交。其余未核项不能据此认定完成，不把历史读者知识反推为人物当时所知。",
        "",
    ])
    return doc, md


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--freeze", action="store_true", help="首次冻结当前 r175 来源；已存在时拒绝覆盖")
    parser.add_argument("--build", action="store_true", help="从已冻结来源生成 JSON 与 Markdown")
    parser.add_argument("--check", action="store_true", help="验证来源和现有派生文件；不写任何文件")
    args = parser.parse_args()
    if sum((args.freeze, args.build, args.check)) != 1:
        parser.error("必须且只能指定 --freeze / --build / --check")
    if args.freeze:
        if MANIFEST.exists():
            raise SystemExit("来源清单已存在；禁止静默覆盖。先人工重审，再显式归档旧清单。")
        MANIFEST.write_text(json.dumps(capture_manifest(), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print("source_manifest.json frozen at r175")
        return
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    doc, md = build(manifest)
    json_text = json.dumps(doc, ensure_ascii=False, indent=2) + "\n"
    if args.check:
        if not OUTPUT_JSON.exists() or OUTPUT_JSON.read_text(encoding="utf-8") != json_text:
            raise SystemExit("早期伏笔逐章.json 缺失或不是确定性派生结果")
        if not OUTPUT_MD.exists() or OUTPUT_MD.read_text(encoding="utf-8") != md:
            raise SystemExit("早期伏笔索引.md 缺失或不是确定性派生结果")
        print(f"PASS r175; {len(CHAPTERS)} chapter bindings; {len(EVIDENCE)} reviewed CORE evidence rows")
        return
    OUTPUT_JSON.write_text(json_text, encoding="utf-8")
    OUTPUT_MD.write_text(md, encoding="utf-8")
    print(f"built r175; {len(CHAPTERS)} chapter bindings; {len(EVIDENCE)} reviewed CORE evidence rows")


if __name__ == "__main__":
    main()
