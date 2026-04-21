import sys
import argparse
from typing import TypedDict, Dict, Any, Optional
from pydantic import BaseModel, Field

from langgraph.graph import StateGraph, START, END
from langchain_ollama import ChatOllama
from langchain_core.messages import SystemMessage, HumanMessage
from langchain_core.messages.content import create_image_block, create_plaintext_block

# Import the data fetcher from the client interface we built
from client_interface import client_get_vision_context

# ==========================================
# 1. State & Schema Definitions
# ==========================================

class VerificationState(TypedDict, total=False):
    """The shared memory for the LangGraph agent."""
    task_to_verify: str
    images_base64: dict[str, str]
    motor_angles: dict[str, Any]
    is_success: bool
    reasoning: str
    error: Optional[str]

class VerificationOutput(BaseModel):
    """The strict JSON schema we force the VLM to return."""
    # reasoning: str = Field(description="A single sentence explaining what is visible in the cameras justifying the success or failure.")
    success: bool = Field(description="True if the robot successfully completed the task, False if it failed, missed, or dropped the item.")

# ==========================================
# 2. Initialize VLM
# ==========================================

# Note: Ensure you are using a vision-capable model in Ollama (e.g., llava, llama3.2-vision, or qwen-vl).
vlm = ChatOllama(
    model="qwen3.5:4b", # Kept from your example, though you may need a vision variant
    temperature=0.0
)

# Bind the Pydantic schema to force structured output
structured_vlm = vlm.with_structured_output(VerificationOutput)

# ==========================================
# 3. Define Graph Nodes (Tools/Logic)
# ==========================================

def fetch_robot_data(state: VerificationState) -> VerificationState:
    """Tool Node: Pulls the latest observation from the FastAPI microservice."""
    try:
        # Assuming client_get_vision_context returns raw base64 (no data URI header)
        b64_images, motors, current_api_task = client_get_vision_context()
        
        # If the graph was initialized with a specific task, use it. Otherwise, use what the API reports.
        target_task = state.get("task_to_verify") or current_api_task

        return {
            "task_to_verify": target_task,
            "images_base64": b64_images,
            "motor_angles": motors,
            "error": None
        }
    except Exception as e:
        return {"error": f"Failed to fetch context from robot API: {str(e)}"}

def perform_verification(state: VerificationState) -> VerificationState:
    """Reasoning Node: Constructs the multimodal prompt and queries the VLM."""
    if state.get("error"):
        return state # Skip reasoning if data fetching failed

    task = state["task_to_verify"]
    b64_images = state["images_base64"]

    # Build multimodal content blocks
    content_blocks = [
        {"type":"text","text":f"Please verify if the following physical task was successfully completed: '{task}'\nHere are the current camera views:"}
    ]
    
    # Dynamically append all available camera feeds
    for cam_name, b64_str in b64_images.items():
        content_blocks.append({"type":"text","text":(f"Camera: {cam_name}")})
        content_blocks.append(create_image_block(base64=b64_str, mime_type="jpeg"))

    messages = [
        SystemMessage(content="You are a robotic QA inspector. Your job is to look at the provided camera feeds and determine if the physical task was successfully executed by the robot. Be strict but fair. Focus on the end-effector (gripper) and the target object."),
        HumanMessage(content_blocks=content_blocks)
    ]

    try:
        # Invoke VLM and parse directly into our Pydantic model
        result: VerificationOutput = structured_vlm.invoke(messages)
        
        return {
            "is_success": result.success,
            # "reasoning": result.reasoning
        }
    except Exception as e:
        return {"error": f"VLM verification failed to parse: {str(e)}"}

# ==========================================
# 4. Build and Compile Graph
# ==========================================

workflow = StateGraph(VerificationState)

workflow.add_node("fetch_data", fetch_robot_data)
workflow.add_node("verify", perform_verification)

workflow.add_edge(START, "fetch_data")

# Conditional routing: End early if API is down
def route_after_fetch(state: VerificationState) -> str:
    if state.get("error"):
        return END
    return "verify"
    
workflow.add_conditional_edges("fetch_data", route_after_fetch)
workflow.add_edge("verify", END)

# This compiled agent is what you will import in your main orchestrator
verification_agent = workflow.compile()

# ==========================================
# 5. Runnable CLI Prototype
# ==========================================

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run the Visual Verification Agent.")
    parser.add_argument("--task", type=str, help="Specific task to verify. If omitted, pulls current_task from API.", default="")
    args = parser.parse_args()

    print("--- Starting Visual Verification Agent ---")
    
    # Initialize state
    initial_state = VerificationState()
    if args.task:
        initial_state["task_to_verify"] = args.task
        print(f"Target Task Override: '{args.task}'")

    # Execute the LangGraph state machine
    final_state = verification_agent.invoke(initial_state)

    if final_state.get("error"):
        print(f"\n[!] ERROR: {final_state['error']}")
        sys.exit(1)

    print("\n--- Verification Results ---")
    print(f"Task Verified: {final_state.get('task_to_verify')}")
    print(f"Success:       {'✅ YES' if final_state.get('is_success') else '❌ NO'}")
    print(f"Reasoning:     {final_state.get('reasoning')}")