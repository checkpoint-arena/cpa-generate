# Checkpoint-arena image and metadata generator script

import glob
import json
import os
import shutil
import time
from itertools import product
from urllib import request
from subprocess import Popen
from datetime import datetime

# absolute path to ComfyUI output directory, *needs to be configured*
output_dir = "C:/dev/ai/ComfyUI/output"

starting_seed = 42
imgs_per_prompt = 6
# the number per batch has a huge performance impact, should probably be tuned for each target HW
imgs_per_batch = 2

# loading and customizing the ComfyUI prompt 

with open("comfy_ui_input.json", 'r') as file:
    prompt_text = file.read()

json_prompt = json.loads(prompt_text)

def get_pos_prompt():
    return json_prompt["16"]["inputs"]["text"]

def set_pos_prompt(text):
    json_prompt["16"]["inputs"]["text"] = text

def get_neg_prompt():
    return json_prompt["7"]["inputs"]["text"]

def set_neg_prompt(text):
    json_prompt["7"]["inputs"]["text"] = text

def set_checkpoint(ckpt):
    json_prompt["4"]["inputs"]["ckpt_name"] = ckpt

def set_output_prefix(prefix):
    json_prompt["26"]["inputs"]["filename_prefix"] = prefix

def set_batch_size(sz):
    json_prompt["5"]["inputs"]["batch_size"] = sz

def set_seed(seed):
    json_prompt["3"]["inputs"]["seed"] = seed
    json_prompt["22"]["inputs"]["seed"] = seed

# queuing a prompt to ComfyUI (locally at default port)

def queue_prompt(prompt):
    p = {"prompt": prompt}
    data = json.dumps(p).encode('utf-8')
    req =  request.Request("http://127.0.0.1:8188/prompt", data=data)
    handler = request.urlopen(req)
    print(handler.status, end=' ', flush=True)

# actual image generation

from data import * # import checkpoint / prompt / etc input data

default_neg_prompt = get_neg_prompt()

checkpoint_map = {}
prompt_map = {}
category_map = { "anime": [], "other": [], "photo": [] }
gen_img_count = 0

for checkpoint_data, prompt_data, neg_prompt_setting in product(checkpoints, prompts, neg_prompt_options):
    checkpoint, checkpoint_id, category, checkpoint_name, url = checkpoint_data
    prompt, prompt_id = prompt_data

    sfw = neg_prompt_setting == "sfw"
    no_neg = neg_prompt_setting == "none"

    pos_prompt_string = "({}:1.1){}".format(prompt, extra_prompt_mapping[category])
    print("+ : " + pos_prompt_string)
    set_pos_prompt(pos_prompt_string)

    neg_prompt_string = ""
    if not no_neg:
        neg_prompt_string = default_neg_prompt
    if sfw:
        neg_prompt_string += sfw_extra_neg_prompt
    print("- : " + neg_prompt_string)
    set_neg_prompt(neg_prompt_string)
    
    checkpoint_fn = "{}.safetensors".format(checkpoint)
    print(checkpoint_fn)
    set_checkpoint(checkpoint_fn)

    output_prefix = "{}_{}".format(prompt_id, checkpoint_id)
    if no_neg:
        output_prefix += "_noneg"
    if sfw:
        output_prefix += "_sfw"
    print(output_prefix)
    set_output_prefix(output_prefix)

    expected_fn = "{}_{:05d}.png".format(output_prefix, 6)
    expected_path = os.path.join(output_dir, expected_fn)
    print(expected_path)

    if not os.path.exists(expected_path):
        imgs_generated = 0
        set_batch_size(imgs_per_batch)
        while imgs_generated < imgs_per_prompt:
            set_seed(starting_seed + imgs_generated)
            queue_prompt(json_prompt)
            imgs_generated += imgs_per_batch
        while not os.path.exists(expected_path):
            time.sleep(0.1)
        print("")
    else:
        print("exists, skipping")

    checkpoint_map[checkpoint_id] = { 
        'checkpoint': checkpoint,
        'checkpoint_name': checkpoint_name,
        'category': category,
    }
    prompt_map[prompt_id] = prompt
    if checkpoint_id not in category_map[category]:
        category_map[category].append(checkpoint_id)

    gen_img_count += imgs_per_prompt
    print("-----")

# store the results in JSON files

with open('out/checkpoint_map.json', 'w', newline='\n') as file:
    json.dump(checkpoint_map, file, indent=2)
with open('out/prompt_map.json', 'w', newline='\n') as file:
    json.dump(prompt_map, file, indent=2)
with open('out/category_map.json', 'w', newline='\n') as file:
    json.dump(category_map, file, indent=2)
with open('out/meta_info.json', 'w', newline='\n') as file:
    json.dump({ "gen_time": datetime.now().isoformat(), "total_imgs": gen_img_count }, file, indent=2)

repo_dir = os.getcwd()

# convert any new full-size pngs to avif and copy to repo

def convert_to_avif_and_copy(quality, target_path):
    print("avif conversion ...")
    os.system('npx avif --input="*.png" --quality {} --effort 5'.format(quality))
    print("copy ...")    
    os.makedirs(target_path, exist_ok=True)
    for aviffn in glob.glob("*.avif"):
        shutil.copy(aviffn, target_path)

FULL_AVIF_QUALITY=85
os.chdir(output_dir)
avif_repo_dir = os.path.join(repo_dir, "avif")
convert_to_avif_and_copy(FULL_AVIF_QUALITY, avif_repo_dir)

# generate thumbnails

THUMBNAIL_AVIF_QUALITY=65
THUMBNAIL_SIZE=256
THUMBNAIL_DIR='thumb'
PARALLELISM=16
print("thumbnails:", end='')
# this would be 3 lines in Ruby
pnglist = glob.glob("*.png")
for i in range(0, len(pnglist), PARALLELISM):
    chunk = pnglist[i:i+PARALLELISM]
    procs = []
    for pngfn in chunk:
        target = os.path.join(THUMBNAIL_DIR, pngfn)
        if not os.path.exists(target):
            procs.append(Popen('magick {0} -resize {1}x{1} {2}'.format(pngfn, THUMBNAIL_SIZE, target)))
    for p in procs:
        p.wait()
    print(".", end='', flush=True)
print("")

# convert any new thumbnail pngs to avif and copy to repo

os.chdir(THUMBNAIL_DIR)
repo_thumb_dir = os.path.join(avif_repo_dir, THUMBNAIL_DIR)
convert_to_avif_and_copy(THUMBNAIL_AVIF_QUALITY, repo_thumb_dir)
