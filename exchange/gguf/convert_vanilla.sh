#!/usr/bin/env bash
# Offline GGUF Conversion ($0.00 cloud spend)
set -euo pipefail

echo "==> Running: python3 /opt/llama.cpp/convert_lora_to_gguf.py exchange/adapters/dpo --outtype f16 --outfile /Users/admin/magi_pact/exchange/gguf/adapter_lora.gguf"
python3 /opt/llama.cpp/convert_lora_to_gguf.py exchange/adapters/dpo --outtype f16 --outfile /Users/admin/magi_pact/exchange/gguf/adapter_lora.gguf

echo "==> Running: python3 /opt/llama.cpp/export_lora.py --base Qwen/Qwen2.5-Coder-7B-Instruct --lora exchange/adapters/dpo --outtype f16 --outfile /Users/admin/magi_pact/exchange/gguf/model_merged.gguf"
python3 /opt/llama.cpp/export_lora.py --base Qwen/Qwen2.5-Coder-7B-Instruct --lora exchange/adapters/dpo --outtype f16 --outfile /Users/admin/magi_pact/exchange/gguf/model_merged.gguf

echo "==> Running: /opt/llama.cpp/llama-quantize /Users/admin/magi_pact/exchange/gguf/model_merged.gguf /Users/admin/magi_pact/exchange/gguf/model.Q4_K_M.gguf Q4_K_M"
/opt/llama.cpp/llama-quantize /Users/admin/magi_pact/exchange/gguf/model_merged.gguf /Users/admin/magi_pact/exchange/gguf/model.Q4_K_M.gguf Q4_K_M

echo "==> Running: /opt/llama.cpp/llama-quantize /Users/admin/magi_pact/exchange/gguf/model_merged.gguf /Users/admin/magi_pact/exchange/gguf/model.Q8_0.gguf Q8_0"
/opt/llama.cpp/llama-quantize /Users/admin/magi_pact/exchange/gguf/model_merged.gguf /Users/admin/magi_pact/exchange/gguf/model.Q8_0.gguf Q8_0

