from pynput import keyboard

pressed_keys = set()

def on_press(key):
    if key in pressed_keys:
        return  # ignore repeat while held

    pressed_keys.add(key)

    if key == keyboard.Key.space:
        print("stopping motors")
        return

    try:
        if key.char == '1':
            print("picking up foam ball")

        elif key.char == '2':
            print("skewering foam ball")

        elif key.char == '3':
            print("moving to ready position")

    except AttributeError:
        pass


def on_release(key):
    pressed_keys.discard(key)


with keyboard.Listener(
        on_press=on_press,
        on_release=on_release) as listener:
    listener.join()