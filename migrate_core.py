import os
import shutil
import glob

SRC_DIR = "/home/sarthak/HyprVoice/hyprvoice/core"
DST_DIR = "/home/sarthak/arova/arova/core"

def migrate_file(src, dst):
    with open(src, 'r') as f:
        content = f.read()
    
    # Replace hyprvoice.core with arova.core
    content = content.replace("hyprvoice.core", "arova.core")
    content = content.replace("hyprvoice.", "arova.")
    
    os.makedirs(os.path.dirname(dst), exist_ok=True)
    with open(dst, 'w') as f:
        f.write(content)

for root, _, files in os.walk(SRC_DIR):
    for file in files:
        if file.endswith(".py"):
            src = os.path.join(root, file)
            # Check exclusions
            if "plan_manager" in src or "agent" in src:
                continue
                
            rel = os.path.relpath(src, SRC_DIR)
            dst = os.path.join(DST_DIR, rel)
            
            # Avoid overwriting what we already created
            if os.path.exists(dst):
                continue
                
            migrate_file(src, dst)
            print(f"Migrated {rel}")
