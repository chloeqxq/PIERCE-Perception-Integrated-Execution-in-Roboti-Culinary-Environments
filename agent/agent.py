
from langchain_ollama import ChatOllama
from langchain.messages import SystemMessage,HumanMessage,ImageContentBlock,ToolMessage
from langchain.chat_models import init_chat_model
from langchain_core.messages.content import create_image_block,create_plaintext_block
from langchain_core.messages import ChatMessage
from PIL import Image 
from io import BytesIO
import cv2
import sys
import base64
from client_interface import *

model = ChatOllama(
    model="qwen3.5:4b",
    # temperature=0
    reasoning=False
)

base64_strings, motor_angles, current_task = client_get_vision_context()
content_blocks = []
for k in base64_strings.keys():
    # content_blocks.append(create_plaintext_block(f"{k}_camera:"))
    content_blocks.append(create_image_block(base64=base64_strings[k],mime_type="jpg"))

# List of standard content blocks
# cat_image = Image.open("/home/guff/PIERCE-Perception-Integrated-Execution-in-Roboti-Culinary-Environments/image.png")
human_message = HumanMessage(content_blocks=content_blocks)

conversation = [
    SystemMessage("you are a robotics perception module. you take in the camera observations and describe the current scene and state."),
    human_message
]

result = model.invoke(conversation)
print(result.content)