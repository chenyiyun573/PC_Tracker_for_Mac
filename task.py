# task.py
import json
import os

def find_tasks_json():
    start_dir = os.path.abspath(".")
    for root, dirs, files in os.walk(start_dir):
        if 'tasks.json' in files:
            return os.path.join(root, 'tasks.json')
    return None

def find_task_cnt_json():
    start_dir = os.path.abspath(".")
    for root, dirs, files in os.walk(start_dir):
        if 'task_cnt.json' in files:
            return os.path.join(root, 'task_cnt.json')
    return None

tasks_path = find_tasks_json()
task_cnt_path = find_task_cnt_json()
task_cnt = 0

class Task:
    def __init__(self, description, id, level, file_input=None, category="other", finished=False, is_bad=False):
        self.description = description
        self.level = level
        self.id = id
        self.category = category
        self.file_input = file_input
        self.finished = finished
        self.is_bad = is_bad

def from_json(task_json, task_id) -> Task:
    return Task(
        description=task_json['task'],
        id=task_id,
        level=task_json['level'],
        file_input=task_json['file_input'],
        category=task_json['category'],
        finished=task_json['finished']
    )

def free_task():
    return Task("free task", 0, "easy")

def load_task_cnt():
    if not task_cnt_path:
        return (0, 0)
    with open(task_cnt_path, 'r') as file:
        data = json.load(file)
        return data.get('given_task', 0), data.get('free_task', 0)

def load_given_tasks():
    global task_cnt
    if not tasks_path:
        return [free_task()]
    tasks = []
    with open(tasks_path, 'r') as file:
        data = json.load(file)
        for t in data:
            task_cnt += 1
            tasks.append(from_json(t, task_cnt))
    return tasks

def update_given_tasks(given_tasks):
    if not tasks_path:
        return
    to_save = []
    for tk in given_tasks:
        if not tk.is_bad:
            to_save.append({
                'task': tk.description,
                'level': tk.level,
                'file_input': tk.file_input,
                'category': tk.category,
                'finished': tk.finished
            })
    with open(tasks_path, 'w') as file:
        json.dump(to_save, file, indent=2)

def update_task_cnt(finished_given_cnt, finished_free_cnt):
    if not task_cnt_path:
        return
    with open(task_cnt_path, 'w') as file:
        json.dump({
            'given_task': finished_given_cnt,
            'free_task': finished_free_cnt
        }, file, indent=2)
