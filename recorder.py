import os
import json
import multiprocessing
from PIL import Image, ImageDraw
from fs import ensure_folder, hide_folder, delete_file
from utils import get_current_time, print_debug
from capturer import RecentScreen

MARK_IMAGE = False

class Recorder:
    """
    Buffers events (each with screenshot + action).
    Writes them to JSON lines. Also can generate MD.
    """
    def __init__(self, directory="events"):
        self.pool = multiprocessing.Pool()
        self.directory = directory
        self.screenshot_dir = os.path.join(directory, "screenshot")
        self.buffer = []  # list of (event_dict, rect)
        self.saved_cnt = 0
        self.timestamp_str = get_current_time().replace(":", "").replace("-", "_")

        ensure_folder(self.directory)
        ensure_folder(self.screenshot_dir)
        hide_folder(self.directory)

        prefix = "non_task"
        self.event_filename = os.path.join(
            self.directory, f"{prefix}_{self.timestamp_str}.jsonl"
        )
        self.md_filename = os.path.join(
            self.directory, f"{prefix}_{self.timestamp_str}.md"
        )

        self.recent_screen = RecentScreen()
        self.screenshot_f_list = []

    def get_event(self, action=None):
        timestamp = get_current_time()
        shot = self.recent_screen.get()  # (bits, w, h)
        event = {
            'timestamp': timestamp,
            'action': action,       # Action object or string
            'screenshot': shot,
        }
        return event

    def record_event(self, event, rect=None):
        """Append an (event_dict, rect) to our in-memory buffer."""
        self.buffer.append((event, rect))

    def record_action(self, action, rect=None):
        evt = self.get_event(action)
        self.record_event(evt, rect)

    def get_last_action(self):
        """
        Return the last action object from the buffer (or None if empty).
        """
        if self.buffer:
            event_dict, _ = self.buffer[-1]
            return event_dict.get('action', None)
        return None

    def change_last_action(self, new_action):
        """
        Replaces the 'action' field of the last event in the buffer
        with 'new_action'. This is used for turning a single click into
        a double click, etc.
        """
        if self.buffer:
            event_dict, rect = self.buffer.pop()
            event_dict['action'] = new_action
            self.buffer.append((event_dict, rect))

    def wait(self):
        """Flush the buffer to disk, then close the process pool."""
        for e, r in self.buffer:
            self._save(e, r)
        self.buffer.clear()
        self.pool.close()
        self.pool.join()

    def generate_md(self):
        if not os.path.exists(self.event_filename):
            return
        with open(self.event_filename, 'r', encoding='utf-8') as f:
            lines = f.readlines()

        md = ["# Non-Task Mode (Mac) Record\n\n"]
        prompt = "What would you do next?\n\n"

        for line in lines:
            data = json.loads(line)
            ts = data.get("timestamp", "")
            action = data.get("action", "")
            screenshot_path = data.get("screenshot", "")
            rel_path = "/".join(screenshot_path.split("/")[1:])

            md.append(f"### {ts}\n")
            md.append(f"**Input:**\n\n{prompt}\n")
            md.append(f"![Screenshot]({rel_path})\n\n")
            md.append(f"**Output:** {action}\n\n")

        with open(self.md_filename, 'w', encoding='utf-8') as out:
            out.writelines(md)

    def discard(self):
        delete_file(self.event_filename)
        delete_file(self.md_filename)
        for s in self.screenshot_f_list:
            delete_file(s)
        self.screenshot_f_list.clear()

    def _save(self, event, rect):
        self.saved_cnt += 1
        ts_str = event['timestamp'].replace(':','').replace('-','')
        action = event.get('action')
        shot = event.get('screenshot')  # (bits, w, h)

        screenshot_filename = os.path.join(
            self.screenshot_dir,
            f"{ts_str}_{self.saved_cnt}.png"
        )

        # Save the screenshot asynchronously
        self.pool.apply_async(
            save_screenshot, (screenshot_filename, shot)
        )

        # Convert the action to a string
        event['screenshot'] = screenshot_filename
        event['action'] = str(action) if action else "None"

        with open(self.event_filename, 'a', encoding='utf-8') as f:
            json.dump(event, f, ensure_ascii=False)
            f.write('\n')

        self.screenshot_f_list.append(screenshot_filename)

def save_screenshot(save_filename, shot_tuple):
    from PIL import Image, ImageDraw
    bits, w, h = shot_tuple
    img = Image.frombytes(
        'RGBA',
        (w, h),
        bits,
        'raw'
    )
    if MARK_IMAGE:
        draw = ImageDraw.Draw(img)
        draw.rectangle([0, 0, 50, 50], outline="red", width=3)
    img.save(save_filename)
