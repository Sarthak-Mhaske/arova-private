with open("arova/core/runtime.py", "r") as f:
    lines = f.readlines()

for i in range(275, 344):
    if lines[i].startswith("        "):
        lines[i] = lines[i][4:]

with open("arova/core/runtime.py", "w") as f:
    f.writelines(lines)
