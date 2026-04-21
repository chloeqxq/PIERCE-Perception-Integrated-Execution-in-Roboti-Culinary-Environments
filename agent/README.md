## Starting Robot MicroService
conda activate lerobot && python3 robot_service.py

### Debug Dashboard
conda activate base && python3 dashboard.py

## Starting vLLM server (prereq for agent)
conda activate vllm && vllm serve Qwen/Qwen3.5-4B --port 5000 --served-model-name vlm
or
conda activate vllm && vllm serve google/gemma-4-E2B-it --port 5000 --served-model-name vlm --gpu-memory-utilization 0.7

### Note:
recommend run this in tmux for background persistence.
vLLM only needs to be started once, check first if it's already up.

## Run the verifier agent (requires vLLM and Robot Service)
conda activate lerobot && python3 visual_verifier.py
the llm must 

