from pathlib import Path

book = Path(__file__).resolve().parents[2]
dest = Path(__file__).resolve().parent / "候选_096-099"
dest.mkdir(exist_ok=True)

notes = {
    96: "截至本章，周衡自然场景观察仍未见稳定接缝；猫眼把八年纸档带入店，姜霁接纳空结果。正文去掉作者章号回指与重复方法解释，纸档来源、风险和未见记录不变。",
    97: "旧纸表、旧交接本与现系统出现版本冲突，只证后来有回填，实施者和当年实际事件未知。近五年关系材料另核，不在本章认证周衡。正文压去落笔后重复解释。",
    98: "分散的近五年生活后果与前三年版本冲突并立。徐师傅按039旧业务送来旧锁芯，镜辞放铁盒隔层，100不重送。正文压去重复情绪解释，不添关系或身份结论。",
    99: "午前真实坏表入店、管钳归还、近距未见稳定接缝，维修单约明日取。正文把‘今晚’改回现场时点，缩减复述；100隔日取表并首次确定接缝。",
}

for number, note in notes.items():
    source = book / "大纲" / f"细纲_第{number:03d}章.md"
    value = source.read_text(encoding="utf-8-sig")
    if number in (96, 98, 99):
        value = value.replace("二轮施工目标。一轮稿若与本文件冲突，以本文件为准。", "活动正文映射。以已接纳正文为准。")
    if number == 97:
        value = value.replace("重新获得执行资格。", "活动正文映射。以已接纳正文为准。")
    value = value.rstrip() + f"\n\n## 2026-10-06 详细验收修订映射\n\n{note}\n"
    (dest / source.name).write_text(value, encoding="utf-8")
