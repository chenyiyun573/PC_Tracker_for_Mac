On MacOS
Because of tkinter, we need to create the venv using System Python
```
/usr/bin/python3 -m venv .venv
source .venv/bin/activate
python3 -m pip install -r requirements.txt
```


20250105 0938 PT
The screenshots contains a lot of problem when using Quartz, so we changed to use pyautogui. 
Also, due to some errors troublesome to fix, we delete tkinter related GUI code. 
This version of code is saved as 1.0.0.