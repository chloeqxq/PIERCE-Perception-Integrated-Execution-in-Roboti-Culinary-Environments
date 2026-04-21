## Base Rotation Example
curl -X POST "http://localhost:/base"      -H "Content-Type: application/json"      -d '{"steps": -100}'
## Enable Arms Example
curl -X POST "http://localhost:/allow_act"      -H "Content-Type: application/json"      -d '{"allow_act":true}'
## Update Subtask Example
curl -X POST "http://localhost:/task" \
     -H "Content-Type: application/json" \
     -d '{"task": "make a foam ball skewer"}'

##

vllm serve Qwen/Qwen3.5-2B --reasoning-parser qwen3 --port 5000