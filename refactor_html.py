import re
from pathlib import Path

index_path = Path(r"c:\Escritorio\BackUp-Solba\src\frontend\index.html")

content = index_path.read_text(encoding="utf-8")

replacements = {
    r'\bbg-surface-950\b': 'bg-slate-50 dark:bg-surface-950',
    r'\bbg-surface-900\b': 'bg-white dark:bg-surface-900',
    r'\bbg-surface-800\b': 'bg-slate-100 dark:bg-surface-800',
    r'\bhover:bg-surface-800\b': 'hover:bg-slate-100 dark:hover:bg-surface-800',
    r'\btext-white\b': 'text-slate-900 dark:text-white',
    r'\bhover:text-white\b': 'hover:text-slate-900 dark:hover:text-white',
    r'\btext-slate-400\b': 'text-slate-500 dark:text-slate-400',
    r'\btext-slate-300\b': 'text-slate-600 dark:text-slate-300',
    r'\btext-slate-500\b': 'text-slate-400 dark:text-slate-500',
    r'\btext-slate-200\b': 'text-slate-700 dark:text-slate-200',
    r'\bborder-slate-800\b': 'border-slate-200 dark:border-slate-800',
    r'\bborder-slate-700\b': 'border-slate-300 dark:border-slate-700',
    r'\bborder-slate-600\b': 'border-slate-400 dark:border-slate-600',
    r'\bbg-slate-800\b': 'bg-slate-200 dark:bg-slate-800',
    r'\bfrom-surface-950\b': 'from-slate-50 dark:from-surface-950',
    r'\bto-surface-900\b': 'to-white dark:to-surface-900',
}

def replace_classes(match):
    cls_str = match.group(1)
    for old, new in replacements.items():
        if old.replace(r'\b', '') in cls_str:
            cls_str = re.sub(old, new, cls_str)
    return f'class="{cls_str}"'

new_content = re.sub(r'class="([^"]+)"', replace_classes, content)

index_path.write_text(new_content, encoding="utf-8")
print("Refactoring complete.")
