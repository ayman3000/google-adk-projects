# MicroGPT Architecture and Implementation Details

`microgpt.py` is a minimal, dependency-free Python implementation of a GPT (Generative Pre-trained Transformer) model, created by Andrej Karpathy. It demonstrates the most atomic way to train and run inference for a GPT, stripping away all optimizations and external libraries like PyTorch or NumPy, keeping only the fundamental algorithm.

## Key Components

### 1. Data and Tokenization
- The dataset (`docs`) is a list of strings (e.g., names).
- It uses a character-level tokenizer. Unique characters in the dataset become the vocabulary.
- It includes a special Beginning of Sequence (BOS) token.
- `vocab_size` is the number of unique characters plus the BOS token.

### 2. Autograd Engine (`Value` class)
- A custom scalar-valued automatic differentiation engine.
- Tracks the computation graph using `_children` and `_local_grads`.
- Implements basic math operations (`+`, `*`, `**`, `log`, `exp`, `relu`) and backward pass (`backward()`) using topological sort and the chain rule.

### 3. Model Parameters (`state_dict`)
- Parameters are initialized using a Gaussian distribution (`random.gauss`).
- The architecture uses:
  - Token and Position Embeddings (`wte`, `wpe`).
  - Language Modeling Head (`lm_head`).
  - Transformer layers containing Multi-Head Attention and Multi-Layer Perceptron (MLP) weights.
- Parameters are flattened into a single list of `Value` objects for the optimizer.

### 4. Mathematical Operations
- `linear(x, w)`: Manual matrix multiplication (dot product of inputs and weights).
- `softmax(logits)`: Computes probabilities while mitigating numerical instability (subtracting the max value).
- `rmsnorm(x)`: Root Mean Square Normalization (a simplified alternative to LayerNorm).

### 5. The Transformer Block (`gpt` function)
- **Embeddings**: Joins token and positional embeddings, followed by RMSNorm.
- **Layers** (`n_layer` loops):
  - **Multi-Head Attention**: 
    - Applies `linear` layers to compute Queries (`q`), Keys (`k`), and Values (`v`).
    - Splits heads and computes scaled dot-product attention (`softmax(q_h * k_h / sqrt(head_dim)) * v_h`).
    - Concatenates head outputs and projects via `attn_wo`.
    - Includes a residual connection.
  - **MLP**:
    - Applies RMSNorm, a linear projection (`mlp_fc1`), ReLU activation, and a second linear projection (`mlp_fc2`).
    - Includes a residual connection.
- **Output**: Returns logits mapped to the vocabulary size via `lm_head`.

### 6. Training Loop
- **Adam Optimizer**: Manual implementation of Adam with first (`m`) and second (`v`) moment buffers, bias-correction (`m_hat`, `v_hat`), and linear learning rate decay.
- Computes Cross-Entropy loss on token sequences (predicting the next character).
- Performs a backward pass (`loss.backward()`) and updates parameters.

### 7. Inference
- Generates new text character-by-character.
- Uses a `temperature` parameter to scale logits before softmax, controlling the randomness or "creativity" of the output.
- Stops when it generates the BOS token (which doubles as an EOS token here) or reaches `block_size`.

## Summary
The script acts as an educational masterpiece, compressing the core mathematical and architectural concepts of modern Large Language Models into exactly 200 lines of pure Python, proving that understanding Transformers doesn't strictly require complex tensor frameworks.
