#!/usr/bin/env bash
# Program: magi_pact - convert_abli.sh
# Programmer: Ethan-da-Tech-Wizard (written with Claude, an AI assistant)
# Last Modified: 2026-11-18
# Purpose: Offline pipeline that converts the DPO LoRA adapter to GGUF, merges it into the base model, and quantizes the abliterated variant to Q4_K_M and Q8_0.
# Offline GGUF Conversion ($0.00 cloud spend)
# Stop on the first error, on unset variables, and on failures inside pipes.
set -euo pipefail

# Step 1: convert the LoRA adapter folder to a standalone GGUF adapter file.
echo "==> Running: python3 /opt/llama.cpp/convert_lora_to_gguf.py exchange/adapters/dpo --outtype f16 --outfile /Users/admin/magi_pact/exchange/gguf/adapter_lora.gguf"
python3 /opt/llama.cpp/convert_lora_to_gguf.py exchange/adapters/dpo --outtype f16 --outfile /Users/admin/magi_pact/exchange/gguf/adapter_lora.gguf

# Step 2: merge the adapter into the base model, producing a full-precision GGUF.
echo "==> Running: python3 /opt/llama.cpp/export_lora.py --base Qwen/Qwen2.5-Coder-7B-Instruct --lora exchange/adapters/dpo --outtype f16 --outfile /Users/admin/magi_pact/exchange/gguf/model_abli_merged.gguf"
python3 /opt/llama.cpp/export_lora.py --base Qwen/Qwen2.5-Coder-7B-Instruct --lora exchange/adapters/dpo --outtype f16 --outfile /Users/admin/magi_pact/exchange/gguf/model_abli_merged.gguf

# Step 3: quantize the merged model to Q4_K_M.
echo "==> Running: /opt/llama.cpp/llama-quantize /Users/admin/magi_pact/exchange/gguf/model_abli_merged.gguf /Users/admin/magi_pact/exchange/gguf/model_abli.Q4_K_M.gguf Q4_K_M"
/opt/llama.cpp/llama-quantize /Users/admin/magi_pact/exchange/gguf/model_abli_merged.gguf /Users/admin/magi_pact/exchange/gguf/model_abli.Q4_K_M.gguf Q4_K_M

# Step 4: quantize the merged model to Q8_0.
echo "==> Running: /opt/llama.cpp/llama-quantize /Users/admin/magi_pact/exchange/gguf/model_abli_merged.gguf /Users/admin/magi_pact/exchange/gguf/model_abli.Q8_0.gguf Q8_0"
/opt/llama.cpp/llama-quantize /Users/admin/magi_pact/exchange/gguf/model_abli_merged.gguf /Users/admin/magi_pact/exchange/gguf/model_abli.Q8_0.gguf Q8_0

