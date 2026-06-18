import json
import os
import shutil

dataset_dir = "/home/zengkun/GS-IR/datasets/TensoIR/lego/"
original_json_path = os.path.join(dataset_dir, "transforms_train.json")
backup_json_path = os.path.join(dataset_dir, "transforms_train_full.json")

def create_few_shot_json(shot=5):
    # 如果原始文件和备份文件都不存在，则报错
    if not os.path.exists(original_json_path) and not os.path.exists(backup_json_path):
        print(f"Error: Neither {original_json_path} nor {backup_json_path} found.")
        return
        
    # 如果备份文件不存在，则先执行备份
    if not os.path.exists(backup_json_path):
        print("Backing up original transforms_train.json to transforms_train_full.json...")
        shutil.copy2(original_json_path, backup_json_path)
    
    # 从备份文件（完整版）中读取数据，确保每次抽样基准都是 100-shot
    with open(backup_json_path, 'r') as f:
        data = json.load(f)
        
    frames = data.get('frames', [])
    num_frames = len(frames)
    
    if num_frames == 0:
        print("Error: No frames found in JSON.")
        return
        
    print(f"Original frames count: {num_frames}")
    
    # 均匀抽稀
    step = num_frames // shot
    sampled_frames = frames[::step][:shot]
    
    data['frames'] = sampled_frames
    
    # 覆盖写入 transforms_train.json
    with open(original_json_path, 'w') as f:
        json.dump(data, f, indent=4)
        
    print(f"Successfully sampled {len(sampled_frames)} frames and saved to {original_json_path}.")

if __name__ == "__main__":
    create_few_shot_json(shot=5)
