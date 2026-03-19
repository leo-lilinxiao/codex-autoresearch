# Environment Awareness

Phase 0 probe that detects hardware, resources, and toolchain capabilities. Hypothesis generation uses this data to filter infeasible approaches before wasting iterations.

## Probe Sequence

Run these probes once at the start of a run, before the first iteration.

### 1. Compute Resources

| Probe | Command | Fallback |
|-------|---------|----------|
| CPU cores | `nproc 2>/dev/null \|\| sysctl -n hw.ncpu 2>/dev/null` | assume 2 |
| RAM (MB) | `free -m 2>/dev/null \| awk '/Mem:/{print $2}'` or `sysctl -n hw.memsize 2>/dev/null` | assume 4096 |
| Disk free (MB) | `df -m . 2>/dev/null \| awk 'NR==2{print $4}'` | assume 10240 |

### 2. GPU Detection

| Probe | Command | Interpretation |
|-------|---------|----------------|
| NVIDIA count | `nvidia-smi --query-gpu=name,memory.total --format=csv,noheader 2>/dev/null` | GPU names, VRAM, **count lines for total devices** |
| CUDA version | `nvcc --version 2>/dev/null \| grep release` | CUDA toolkit version |
| Ascend NPU count | `npu-smi info 2>/dev/null` | Huawei Ascend detected, **parse device count** |
| CANN version | `cat /usr/local/Ascend/ascend-toolkit/latest/version.cfg 2>/dev/null` | CANN toolkit version |
| ROCm count | `rocm-smi 2>/dev/null` | AMD GPU detected, **parse device count** |
| Apple Silicon | `sysctl -n machdep.cpu.brand_string 2>/dev/null \| grep -i apple` | MPS available (1 device) |
| No accelerator | all above fail | CPU-only environment |

**Device count is critical** for parallel experiment planning. Store the total number of accelerator devices in the environment profile so `references/parallel-experiments-protocol.md` can calculate `max_workers = floor(total_devices / devices_per_experiment)`.

### 3. Toolchain Detection

| Probe | Command |
|-------|---------|
| Python | `python3 --version 2>/dev/null \|\| python --version 2>/dev/null` |
| Node.js | `node --version 2>/dev/null` |
| Go | `go version 2>/dev/null` |
| Rust | `rustc --version 2>/dev/null` |
| Java | `java --version 2>/dev/null` |
| Package managers | check for `pip`, `npm`, `yarn`, `pnpm`, `cargo`, `go`, `mvn`, `gradle` |

### 4. Container Detection

| Probe | Command | Interpretation |
|-------|---------|----------------|
| Docker | `cat /proc/1/cgroup 2>/dev/null \| grep -q docker` | inside Docker |
| Kubernetes | `test -f /var/run/secrets/kubernetes.io/serviceaccount/token` | inside K8s pod |
| Sandbox | check for read-only filesystems, restricted network | sandboxed environment |

### 5. Network Availability

| Probe | Command | Interpretation |
|-------|---------|----------------|
| Outbound HTTP | `curl -s --max-time 3 -o /dev/null -w '%{http_code}' https://httpbin.org/get 2>/dev/null` | web search available |
| Git remote | `git remote -v 2>/dev/null` | push/pull possible |

## Environment Profile

Store the probe results as an internal environment profile:

```
[environment]
cpu_cores = 8
ram_mb = 16384
disk_free_mb = 52000
gpu = NVIDIA A100 (40GB)
gpu_count = 8
cuda = 12.2
accelerator_type = nvidia
python = 3.11.5
node = 20.10.0
container = docker
network = available
```

## Hypothesis Filtering

### Hard Constraints

Do not attempt hypotheses that require resources the environment lacks:

| Missing Resource | Blocked Hypotheses |
|------------------|-------------------|
| No GPU | CUDA kernel optimization, GPU memory management, mixed precision training |
| No Ascend NPU | CANN operator optimization, Ascend-specific kernels |
| RAM < 2GB | Large model loading, full dataset processing |
| Disk < 1GB | Build artifact generation, large file operations |
| No network | Package installation, web search, remote API calls |
| Read-only FS | Any file modification (hard blocker for entire run) |

### Soft Constraints

Adjust hypothesis parameters based on available resources:

| Resource Level | Adjustment |
|---------------|------------|
| CPU cores <= 2 | Avoid parallelism-dependent optimizations |
| RAM < 8GB | Prefer streaming over in-memory approaches |
| Disk < 5GB | Warn about large build artifacts |
| Slow verify (>60s) | Prefer smaller, more targeted changes |

## Plan Mode Integration

When generating a launch-ready config in plan mode:

1. Run environment probes before suggesting verify/guard commands.
2. Only suggest commands that are executable in the detected environment.
3. If the goal requires unavailable resources, warn the user during the wizard phase.
4. Suggest resource-appropriate verify commands (e.g., smaller test datasets for low-RAM environments).

## Logging

Include environment summary in the first line of the results log comments:

```tsv
# environment: cpu=8 ram=16384MB gpu=A100(40GB) python=3.11 container=docker
# metric_direction: lower
```

## Refresh Policy

- Full probe: once per run start.
- Disk free: re-check every 10 iterations (part of health check).
- GPU state: re-check if a `crash` status mentions GPU/CUDA/memory errors.
- Do not re-probe CPU, RAM, or toolchains mid-run.
