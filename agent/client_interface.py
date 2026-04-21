import requests
import base64
import cv2
import numpy as np

# Base URL of the robot microservice
VLA_API_URL = "http://localhost:8000"

# --- Node Implementation Examples ---

def client_dispatch_task(task_string: str):
    """
    Used in [Node: dispatch_vla].
    Sends the new text prompt to the VLA and ensures motors are active.
    """    
    # 1. Update the target text prompt
    task_response = requests.post(
        f"{VLA_API_URL}/task", 
        json={"task": task_string}
    )
    task_response.raise_for_status()
    
    # 2. Ensure the motors are allowed to move
    motor_response = requests.post(
        f"{VLA_API_URL}/allow_act", 
        json={"allow_act": True}
    )
    motor_response.raise_for_status()
    
    return True

def client_rotate_base(steps=0):
    response = requests.post(
        f"{VLA_API_URL}/base", 
        json={"steps": steps}
    )
    response.raise_for_status()
    data = response.json()
    return data['base_goal']

def client_pause_robot():
    """
    Used before heavy MLLM reasoning.
    Freezes the robot so it doesn't drift while the agent is 'thinking'.
    """
    response = requests.post(
        f"{VLA_API_URL}/allow_act", 
        json={"allow_act": False}
    )
    response.raise_for_status()
    return True

def client_get_vision_context(convert = False):
    """
    Used in [Node: deep_vision_verification].
    Pulls the latest observation and formats it for the LangChain VLM.
    """
    response = requests.get(f"{VLA_API_URL}/observation")
    response.raise_for_status()
    
    data = response.json()
    base64_strings = data["images_base64"]
    motor_angles = data["motor_angles"]
    current_task = data["current_task"]
    
    # FORMATTING FOR LANGCHAIN:
    # LangChain Multimodal messages accept standard base64 strings
    # directly in the image_url field, just like we mocked up earlier!
    if convert:
        base64_strings = {k:f"data:image/jpeg;base64,{base64_string}" for k,base64_string in base64_strings.items()}

    return base64_strings, motor_angles, current_task

# --- Optional Debugging Helper ---

def decode_image(base64_string: str):
    """Decodes the base64 string back into an OpenCV window."""
    img_bytes = base64.b64decode(base64_string)
    np_arr = np.frombuffer(img_bytes, np.uint8)
    img_bgr = cv2.imdecode(np_arr, cv2.IMREAD_COLOR)
    return img_bgr

# --- Example Execution Flow ---
if __name__ == "__main__":
    # 1. Send the command
    # client_dispatch_task("skewer the banana")
    
    # 2. Freeze the robot to check its work
    client_pause_robot()
    
    # 3. Pull the visual data
    while cv2.waitKey(1):
        b64_images, motors, task = client_get_vision_context()
        img_bgr = decode_image(b64_images['right_wrist'])
        cv2.imshow("Agent POV", img_bgr)
    cv2.destroyAllWindows()
