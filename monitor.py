# monitor.py
import time
import threading
from enum import Enum
from pynput import keyboard, mouse
from pynput.keyboard import Key
from utils import get_current_time, print_debug, get_capslock_state, get_element_info_at_position
from recorder import Recorder

WAIT_INTERVAL = 6     # 6s per wait
DOUBLE_CLICK_INTERVAL = 0.5

# We adapt the Windows code to mac, ignoring Windows-only hotkeys. 
# Or you can define your own mac relevant hotkeys if desired.
HOT_KEY = [
    ["cmd", "space"],  # e.g. Spotlight
]

def switch_caption(char):
    """If caps lock is on, invert the case. This logic is the same as Windows."""
    if char.isalpha() and get_capslock_state() == 1:
        return char.swapcase()
    return char

class ActionType(Enum):
    CLICK = "click"
    RIGHT_CLICK = "right click"
    DOUBLE_CLICK = "double click"
    MOUSE_DOWN = "press"
    DRAG = "drag to"
    SCROLL = "scroll"
    KEY_DOWN = "press key"
    HOTKEY = "hotkey"
    TYPE = "type text"
    WAIT = "wait"
    FINISH = "finish"
    FAIL = "fail"

class Action:
    def __init__(self, action_type: ActionType, **kwargs):
        self.action_type = action_type
        self.kwargs = kwargs

    def __str__(self):
        """How it's stored in the JSON or MD output."""
        out = f"{self.action_type.value}"
        if self.action_type in [ActionType.CLICK, ActionType.RIGHT_CLICK, ActionType.MOUSE_DOWN, ActionType.DOUBLE_CLICK]:
            out += f" ({self.kwargs.get('x')}, {self.kwargs.get('y')})"
        elif self.action_type == ActionType.DRAG:
            out += f" ({self.kwargs.get('x')}, {self.kwargs.get('y')})"
        elif self.action_type == ActionType.SCROLL:
            out += f" ({self.kwargs.get('dx')}, {self.kwargs.get('dy')})"
        elif self.action_type == ActionType.KEY_DOWN:
            out += f" {self.kwargs.get('key')}"
        elif self.action_type == ActionType.HOTKEY:
            out += f" ({self.kwargs.get('key1')}, {self.kwargs.get('key2')})"
        elif self.action_type == ActionType.TYPE:
            out += f": {self.kwargs.get('text')}"
        return out

    def get_element(self):
        """Used if we want to store element name or coords."""
        return self.kwargs.get('name', 'Unknown')

class Monitor:
    """
    High-level monitor that orchestrates KeyboardMonitor + MouseMonitor,
    plus the TypeBuffer, ScrollBuffer, and Timer logic.
    """
    def __init__(self):
        self.recorder = Recorder()
        self.type_buffer = TypeBuffer(self.recorder)
        self.timer = Timer(self.recorder, self.type_buffer)
        self.scroll_buffer = ScrollBuffer(self.recorder)

        self.keyboard_monitor = KeyboardMonitor(self.recorder, self.type_buffer, self.timer, self.scroll_buffer)
        self.mouse_monitor = MouseMonitor(self.recorder, self.type_buffer, self.timer, self.scroll_buffer)
        self.running = False

    def start(self):
        if not self.running:
            self.running = True
            self.keyboard_monitor.start()
            self.mouse_monitor.start()
            self.type_buffer.reset()
            self.timer.reset()

    def stop(self):
        if self.running:
            self.running = False
            self.keyboard_monitor.stop()
            self.mouse_monitor.stop()
            self.timer.stop()
            self.recorder.wait()

    def save(self):
        """Stop + generate MD."""
        self.stop()
        self.recorder.generate_md()

    def discard(self):
        """Stop + discard everything."""
        self.stop()
        self.recorder.discard()

class Timer:
    """Triggers a WAIT action after WAIT_INTERVAL seconds of no input."""
    def __init__(self, recorder, type_buffer):
        self.recorder = recorder
        self.type_buffer = type_buffer
        self.timer_inner = None

    def reset(self):
        if self.timer_inner:
            self.timer_inner.cancel()
        self.timer_inner = threading.Timer(WAIT_INTERVAL, self._on_wait)
        self.timer_inner.start()

    def stop(self):
        if self.timer_inner:
            self.timer_inner.cancel()

    def _on_wait(self):
        # Only record WAIT if we are not in the middle of typing
        if not self.type_buffer.last_action_is_typing:
            act = Action(ActionType.WAIT)
            self.recorder.record_action(act)
        self.reset()

class TypeBuffer:
    """Groups consecutive typed chars into a single TYPE action."""
    def __init__(self, recorder):
        self.recorder = recorder
        self.text = ""
        self.is_typing = False
        self.last_action_is_typing = False
        self.last_action_is_shift = False
        self.pre_saved_type_event = None
        self.events_buffer = []

    def pre_save_type_event(self):
        self.pre_saved_type_event = self.recorder.get_event()

    def reset(self):
        # If we were typing, store that TYPE action
        if self.is_typing and self.text:
            if self.pre_saved_type_event:
                type_act = Action(ActionType.TYPE, text=self.text)
                self.pre_saved_type_event["action"] = type_act
                self.recorder.record_event(self.pre_saved_type_event)
        else:
            # flush all events_buffer as normal
            for e in self.events_buffer:
                self.recorder.record_event(e)

        self.text = ""
        self.is_typing = False
        self.last_action_is_typing = False
        self.last_action_is_shift = False
        self.pre_saved_type_event = None
        self.events_buffer.clear()

    def append(self, char):
        self.text += char
        if not self.is_typing:
            # We store the "press key" for this char in events_buffer
            press_act = Action(ActionType.KEY_DOWN, key=char)
            evt = self.recorder.get_event(press_act)
            self.events_buffer.append(evt)

    def backspace(self):
        # If there's text in our buffer, remove last char
        if self.text:
            self.text = self.text[:-1]
            # If not in "typing" mode yet, just buffer the backspace
            if not self.is_typing:
                backspace_act = Action(ActionType.KEY_DOWN, key="backspace")
                evt = self.recorder.get_event(backspace_act)
                self.events_buffer.append(evt)
        else:
            # If buffer is empty, flush everything
            self.reset()
            # Then record an actual backspace
            backspace_act = Action(ActionType.KEY_DOWN, key="backspace")
            self.recorder.record_action(backspace_act)

    def add_type_related_action(self):
        # If we have typed at least 2 chars, unify into a TYPE action
        if len(self.text) >= 2 and not self.is_typing:
            self.is_typing = True
            # Clear out older KEY_DOWN events in the buffer
            self.events_buffer.clear()

    def is_empty(self):
        return len(self.text) == 0

    def set_last_action_is_typing(self):
        self.last_action_is_typing = True

    def reset_last_action_is_typing(self):
        self.last_action_is_typing = False

    def set_last_action_is_shift(self):
        self.last_action_is_shift = True

    def reset_last_action_is_shift(self):
        self.last_action_is_shift = False

class ScrollBuffer:
    """Accumulates multiple scroll deltas into one action if needed."""
    def __init__(self, recorder):
        self.recorder = recorder
        self.dx = 0
        self.dy = 0
        self.pre_saved_event = None

    def is_empty(self):
        return (self.pre_saved_event is None)

    def reset(self):
        if self.pre_saved_event and (self.dx != 0 or self.dy != 0):
            scroll_act = Action(ActionType.SCROLL, dx=self.dx, dy=self.dy)
            self.pre_saved_event["action"] = scroll_act
            self.recorder.record_event(self.pre_saved_event)
        self.dx = 0
        self.dy = 0
        self.pre_saved_event = None

    def new(self, dx, dy):
        self.dx = dx
        self.dy = dy
        self.pre_saved_event = self.recorder.get_event()

    def add_delta(self, dx, dy):
        self.dx += dx
        self.dy += dy

class KeyboardMonitor:
    """Captures keystrokes, merges them into typing or hotkeys."""
    def __init__(self, recorder, type_buffer, timer, scroll_buffer):
        self.recorder = recorder
        self.type_buffer = type_buffer
        self.timer = timer
        self.scroll_buffer = scroll_buffer
        self.listener = keyboard.Listener(on_press=self.on_press, on_release=self.on_release)

        # track pressed keys to avoid repeated on_press
        self.currently_pressed_keys = set()

    def start(self):
        self.listener.start()

    def stop(self):
        self.listener.stop()
        self.listener.join()

    def on_press(self, key):
        # If key is already pressed, ignore
        if key in self.currently_pressed_keys:
            return
        self.currently_pressed_keys.add(key)

        # Reset timer + scroll buffer
        self.timer.reset()
        self.scroll_buffer.reset()

        # Check if key relates to typing
        if is_related_to_type(key):
            self.type_buffer.set_last_action_is_typing()
            self.type_buffer.add_type_related_action()
        else:
            self.type_buffer.reset_last_action_is_typing()

        # Shift handling
        if key == Key.shift:
            self.type_buffer.set_last_action_is_shift()
        else:
            self.type_buffer.reset_last_action_is_shift()

        # If it's a typed character
        if is_related_to_type(key):
            if key == Key.backspace:
                self.type_buffer.backspace()
            elif key == Key.space:
                self.type_buffer.append(" ")
            elif hasattr(key, 'char') and key.char:
                # Possibly switch caps
                c = switch_caption(key.char)
                self.type_buffer.append(c)
                if len(self.type_buffer.text) == 1:
                    # We prepare to unify typed text if more chars come
                    self.type_buffer.pre_save_type_event()
            return

        # Otherwise it's not a typed char, flush the typed text
        self.type_buffer.reset()

        # For hotkey detection, not super relevant on mac 
        # but we keep the structure from Windows code
        # We'll do a basic approach: if it's "cmd + something"
        # you'll see separate events anyway. We'll skip complex hotkey detection.

        # If it's a normal key press
        key_str = get_key_str(key)
        press_act = Action(ActionType.KEY_DOWN, key=key_str)
        self.recorder.record_action(press_act)

    def on_release(self, key):
        if key in self.currently_pressed_keys:
            self.currently_pressed_keys.remove(key)

class MouseMonitor:
    """Captures mouse clicks, double-click detection, drag, scroll, etc."""
    def __init__(self, recorder, type_buffer, timer, scroll_buffer):
        self.recorder = recorder
        self.type_buffer = type_buffer
        self.timer = timer
        self.scroll_buffer = scroll_buffer
        self.listener = mouse.Listener(on_click=self.on_click, on_scroll=self.on_scroll, on_move=self.on_move)

        self.last_click_time = 0
        self.last_click_x = None
        self.last_click_y = None

        # For drag detection
        self.pre_saved_drag_event = None

    def start(self):
        self.listener.start()

    def stop(self):
        self.listener.stop()
        self.listener.join()

    def on_click(self, x, y, button, pressed):
        self.timer.reset()
        self.type_buffer.reset_last_action_is_typing()
        self.type_buffer.reset_last_action_is_shift()
        self.scroll_buffer.reset()

        if not pressed:
            # handle release for possible drag
            if self.pre_saved_drag_event:
                # see if the mouse moved
                old_x, old_y = self.last_click_x, self.last_click_y
                if (x != old_x or y != old_y):
                    # we have a drag
                    # the last action might be "CLICK", turn it into "MOUSE_DOWN"
                    last_act = self.recorder.get_last_action()
                    if last_act and last_act.action_type == ActionType.CLICK:
                        press_act = Action(ActionType.MOUSE_DOWN, x=old_x, y=old_y, name=last_act.kwargs.get('name'))
                        self.recorder.change_last_action(press_act)
                        # record the drag
                        drag_act = Action(ActionType.DRAG, x=x, y=y)
                        self.pre_saved_drag_event["action"] = drag_act
                        self.recorder.record_event(self.pre_saved_drag_event)
            return

        # Pressed
        self.type_buffer.reset()  # flush typed text
        now = time.time()
        dt = now - self.last_click_time
        if (self.last_click_x == x and self.last_click_y == y and dt < DOUBLE_CLICK_INTERVAL):
            # double click
            last_act = self.recorder.get_last_action()
            if last_act and last_act.action_type == ActionType.CLICK:
                double_click_act = Action(ActionType.DOUBLE_CLICK, x=x, y=y, name=last_act.kwargs.get('name'))
                self.recorder.change_last_action(double_click_act)
        else:
            # single click
            element = get_element_info_at_position(x, y)
            if button == mouse.Button.left:
                click_act = Action(ActionType.CLICK, x=x, y=y, name=element["name"])
                evt = self.recorder.get_event(click_act)
                self.recorder.record_event(evt)
                self.pre_saved_drag_event = evt
            elif button == mouse.Button.right:
                rc_act = Action(ActionType.RIGHT_CLICK, x=x, y=y, name=element["name"])
                evt = self.recorder.get_event(rc_act)
                self.recorder.record_event(evt)
                self.pre_saved_drag_event = evt

        self.last_click_time = now
        self.last_click_x = x
        self.last_click_y = y

    def on_scroll(self, x, y, dx, dy):
        self.timer.stop()
        self.type_buffer.reset_last_action_is_typing()
        self.type_buffer.reset_last_action_is_shift()
        self.type_buffer.reset()

        if self.scroll_buffer.is_empty():
            self.scroll_buffer.new(dx, dy)
        else:
            self.scroll_buffer.add_delta(dx, dy)

    def on_move(self, x, y):
        # no-op
        pass

def is_related_to_type(key):
    """Check if key is relevant for typed text."""
    if isinstance(key, Key):
        return key in [Key.shift, Key.space, Key.backspace, Key.caps_lock]
    elif isinstance(key, keyboard.KeyCode):
        # A normal ASCII char. 
        return key.char is not None and ord(key.char) > 31
    return False

def get_key_str(key):
    """Convert a Key/KeyCode into a string like 'ctrl', 'shift', 'a'."""
    if isinstance(key, Key):
        s = str(key)
        # e.g. Key.ctrl -> 'ctrl', Key.shift -> 'shift', Key.cmd -> 'cmd'
        # or Key.enter -> 'enter'
        if 'ctrl' in s: 
            return 'ctrl'
        if 'shift' in s:
            return 'shift'
        if 'alt' in s:
            return 'alt'
        if 'cmd' in s:
            return 'cmd'
        return s.replace('Key.', '')  # e.g. Key.enter -> 'enter'
    elif isinstance(key, keyboard.KeyCode):
        if key.char:
            return key.char
    return 'unknown'
