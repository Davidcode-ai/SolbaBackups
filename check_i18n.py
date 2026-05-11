import re

with open('src/frontend/assets/js/app.js', 'r', encoding='utf-8') as f:
    content = f.read()

# Find all t('key') calls - only the standalone t() function (not set() or getElementById)
# Match t(' followed by an alphanumeric key ending with ')
t_calls = re.findall(r"\bt\('([a-zA-Z_][a-zA-Z0-9_]*)'\)", content)

# Find all keys defined in i18n dictionaries
# ES section keys
es_keys = set(re.findall(r"^\s+([a-zA-Z_][a-zA-Z0-9_]*):\s*\"", content, re.MULTILINE))
# Also quoted keys
es_keys |= set(re.findall(r'"([a-zA-Z_][a-zA-Z0-9_]+)":\s*"', content))

unique_calls = set(t_calls)
missing = sorted(k for k in unique_calls if k not in es_keys)

print(f"t() calls found: {len(t_calls)}")
print(f"Unique t() keys used: {len(unique_calls)}")
if missing:
    print(f"\nMISSING KEYS ({len(missing)}):")
    for k in missing:
        print(f"  - {k}")
else:
    print("\nAll keys are present! i18n is 100% complete.")
