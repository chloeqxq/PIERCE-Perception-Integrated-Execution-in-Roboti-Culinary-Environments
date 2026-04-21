
from langchain_ollama import ChatOllama
from langchain.messages import SystemMessage,HumanMessage,ImageContentBlock
from langchain.chat_models import init_chat_model
from langchain_core.messages.content import create_image_block
from langchain_core.messages import ChatMessage
from PIL import Image 
from io import BytesIO
import cv2
import sys
import base64
def pil_to_base64(image, format="PNG"):
    # Create an in-memory bytes buffer
    buffered = BytesIO()
    
    # Save the PIL image into the buffer in the specified format
    image.save(buffered, format=format)
    
    # Get the byte data from the buffer
    img_bytes = buffered.getvalue()
    
    # Encode the bytes to Base64 and decode to a UTF-8 string
    base64_string = base64.b64encode(img_bytes).decode('utf-8')
    
    return base64_string

def get_camera_frame(path="/dev/video0"):
    path = "/dev/video0"
    print(f"trying to read from {path}")
    cap = cv2.VideoCapture(path, cv2.CAP_V4L2)
    fourcc = cv2.VideoWriter_fourcc(*'MJPG')
    cap.set(cv2.CAP_PROP_FOURCC, fourcc)
    cap.set(cv2.CAP_PROP_FPS, 30)
    print("starting stream capture")

    #buffer
    for _ in range (5):
        cap.read()

    ret, frame = cap.read()

    if not ret:
        print("Can't receive frame (stream end?). Exiting...")
    else:
        print("Frame recieved")
        
    # Display the resulting frame
    # cv2.imshow('Webcam Feed', frame)

    cap.release()

    #convert cv2 image to PIL
    color_coverted = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
    pil_frame = Image.fromarray(color_coverted)

    return pil_frame


# model = init_chat_model(
#     model="qwen3.5:4b",
#     model_provider="ollama",
#     reasoning
# ) 

model = ChatOllama(
    model="qwen3.5:4b",
    # temperature=0
    reasoning=False
)


# List of standard content blocks
# cat_image = Image.open("/home/guff/PIERCE-Perception-Integrated-Execution-in-Roboti-Culinary-Environments/image.png")
human_message = HumanMessage(content_blocks=[
    create_image_block(base64=pil_to_base64(get_camera_frame()),mime_type="PNG"),])

conversation = [
    SystemMessage("you are an image captioning agent. You are concise and minimize unnecessary yapping."),
    human_message
]

result = model.invoke(conversation)