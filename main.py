# main.py
import multiprocessing

from monitor import Monitor

def main():
    print("====== PCTracker Mac CLI (Non-Task Mode, with Typing/ScrollBuffer) ======")
    print("Recording starts now. Press ENTER to stop at any time.")
    print("Perform mouse/keyboard actions. Press ENTER in this console to finish.\n")

    mon = Monitor()
    mon.start()

    try:
        input()  # wait for user to press enter
    except KeyboardInterrupt:
        pass

    print("\nStop capturing. Do you want to save or discard? [save/discard]")
    choice = input("Choice: ").strip().lower()
    if choice.startswith('s'):
        mon.save()
        print("Saved. Check './events' folder for output.")
    else:
        mon.discard()
        print("Discarded all events.")

if __name__ == "__main__":
    multiprocessing.freeze_support()
    main()
