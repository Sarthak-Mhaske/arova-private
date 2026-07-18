with open("arova/core/runtime.py", "r") as f:
    lines = f.readlines()

init_end = 257  # the line index just before def _persist_runtime(self):
block_start = 278 # index of '# Wire Memory and Intent events'
block_end = 346 # index up to 'def shutdown(self):'

block = lines[block_start:block_end]
for i in range(len(block)):
    block[i] = "    " + block[i] # add 4 spaces to make it 8 spaces

# Remove the block from its current position
del lines[block_start:block_end]

# Insert it before _persist_runtime
for i, line in enumerate(block):
    lines.insert(init_end + i, line)

with open("arova/core/runtime.py", "w") as f:
    f.writelines(lines)
