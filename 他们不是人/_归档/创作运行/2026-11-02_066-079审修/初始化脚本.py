from pathlib import Path
p = Path(__file__).parent / '执行修订.py'
s = p.read_text(encoding='utf-8').replace('20261101', '20261102').replace('2026-11-01', '2026-11-02')
s = s.replace('LABELS = {', "LABELS = {66: ['065次晨整理薄本'],67: ['候车时接水并收整票据'],")
s = s.replace('RESOURCES = {', "RESOURCES = {'当前存在': ['本人票证、包和水瓶'],")
s = s.replace("voice_marker = '常年占座的老头' if name == '窗边老头' else name", "voice_marker = '这行只记用途' if name == '当前存在' else name")
s = s.replace("    (folder / 'candidate.md').write_text(text, encoding='utf-8')", "    for old, new in cfg.get('text_replacements', []):\n        assert old in text, old\n        text = text.replace(old, new)\n    (folder / 'candidate.md').write_text(text, encoding='utf-8')")
p.write_text(s, encoding='utf-8')
