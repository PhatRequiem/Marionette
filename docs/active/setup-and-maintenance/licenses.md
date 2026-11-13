# Active software and model licenses

The local runtime and application dependencies are free and open source. Terminal operation has no paid feature, subscription, vendor account, or license-server requirement; downloads require internet access during setup. Optional Discord access depends on Discord’s proprietary hosted service, an account, bot credentials, and internet access. No paid Discord feature is required for this text-DM integration. Model licensing is reviewed separately below.

## Runtime and setup

| Component | Verified version | License / evidence |
|---|---|---|
| llama.cpp, ggml, bundled server libraries | b12211, commit 7d7f02875 | MIT; bundled `~/AI Infrastructure/AI Apps/Inference Engines/Language Models/llama.cpp/b12211/llama-b12211/LICENSE`, [upstream](https://github.com/ggml-org/llama.cpp/blob/b12211/LICENSE) |
| Python (setup, manifest loading, terminal client, and log routing; Qwen-Agent environment for model requests and tool coordination) | 3.14.8 | PSF-2.0 |
| SQLite (Python standard-library storage binding) | 3.54.0 in system, agent, and Discord Python | [Public domain](https://sqlite.org/copyright.html); no separate service or pip dependency |
| util-linux (`script` recorder, `flock` locks) | 2.42.4 | util-linux package: BSD-2-Clause, BSD-3-Clause, BSD-4-Clause-UC, GPL-2.0-only, GPL-2.0-or-later, GPL-3.0-or-later, ISC, LGPL-2.1-or-later, public domain; installed license texts under `/usr/share/licenses/util-linux/` |
| xdg-terminal-exec (default terminal launcher) | 0.14.3 | GPL-3.0-or-later, verified in `/usr/bin/xdg-terminal-exec` |
| Kitty (configured log terminal) | 0.49.2 | GPL-3.0-only |
| GNU coreutils (tail, mktemp, date, mkdir, chmod, cp, tee) | 9.12 | GPL-3.0-or-later; package documentation GFDL-1.3-or-later |
| Bash (launcher) | 5.3.20 | GPL-3.0-or-later |
| Git (checkout and maintenance) | 2.56.0 | GPL-2.0-only |
| glibc | 2.44+r50+g1848099f063e | LGPL-2.1-or-later / GPL-2.0-or-later package components |
| GCC runtime, libstdc++, libgcc, libgomp | 16.2.1+r23+gd564253eb6c8 | GPL-3.0-or-later WITH GCC-exception-3.1; package documentation GFDL-1.3-or-later |
| OpenSSL | 3.6.5 | Apache-2.0 |
| zlib | 1.3.2 | Zlib |
| Brotli | 1.2.0 | MIT |
| Zstandard | 1.5.7 | BSD-3-Clause / GPL-2.0-only dual license |
| Vulkan loader | 1.4.363.0 | Apache-2.0 |
| Mesa RADV (`vulkan-radeon`) | 26.2.5 | MIT AND BSD-3-Clause AND SGI-B-2.0 package components |

System package versions and license identifiers were checked using `pacman -Qi`; installed license texts are under `/usr/share/licenses/` and package/upstream source distributions. Linked CLI/server libraries were inspected with `ldd`. These are the current host versions, not a frozen operating-system image. Mesa also uses system graphics/LLVM support libraries provided by the distribution; their package licenses apply.

## Model weights (separate from software)

[Qwen/Qwen3.5-4B](https://huggingface.co/Qwen/Qwen3.5-4B) uses [Apache-2.0](https://huggingface.co/Qwen/Qwen3.5-4B/blob/main/LICENSE), verified from the actual license text. The [Unsloth GGUF distribution](https://huggingface.co/unsloth/Qwen3.5-4B-GGUF/tree/e87f176479d0855a907a41277aca2f8ee7a09523) identifies that base model and the same Apache-2.0 license. We use Q4_K_M at that pinned revision; see the download manifest for its checksum. Unsloth training software is not installed or required. Preserve license and attribution obligations if redistributing weights. This repository does not redistribute weights or runtime binaries.

## Resolved system library inventory

Transitive shared-library package owners resolved with `ldd` and `pacman` for the server executable, Vulkan backend, and RADV driver on the verified host:

| Package | Installed version | Package license identifiers |
|---|---|---|
| brotli | 1.2.0-1 | MIT |
| expat | 2.9.0-1 | MIT |
| glibc | 2.44+r50+g1848099f063e-1 | GPL-2.0-or-later  LGPL-2.1-or-later |
| icu | 78.3-1 | LicenseRef-Unicode-3.0  BSD-2-Clause  BSD-3-Clause  NAIST-2003 |
| libdisplay-info | 0.3.0-1 | MIT |
| libdrm | 2.4.134-1 | MIT |
| libedit | 20260512_3.1-1 | BSD-3-Clause |
| libelf | 0.197-1 | GPL-2.0-or-later OR LGPL-3.0-or-later |
| libffi | 3.8.0-1 | MIT |
| libgcc | 16.2.1+r23+gd564253eb6c8-1 | GPL-3.0-or-later WITH GCC-exception-3.1  GFDL-1.3-or-later |
| libgomp | 16.2.1+r23+gd564253eb6c8-1 | GPL-3.0-or-later WITH GCC-exception-3.1  GFDL-1.3-or-later |
| libstdc++ | 16.2.1+r23+gd564253eb6c8-1 | GPL-3.0-or-later WITH GCC-exception-3.1  GFDL-1.3-or-later |
| libx11 | 1.8.14-1 | MIT AND X11 |
| libxau | 1.0.12-1 | MIT-open-group |
| libxcb | 1.17.0-1 | X11 |
| libxdmcp | 1.1.5-2 | MIT-open-group |
| libxml2 | 2.15.4-1 | MIT |
| libxshmfence | 1.3.3-1 | HPND-sell-variant |
| llvm-libs | 23.1.3-4 | Apache-2.0 WITH LLVM-exception |
| ncurses | 6.6-2 | MIT-open-group |
| openssl | 3.6.5-1 | Apache-2.0 |
| spirv-tools | 1:1.4.363.0-1 | Apache-2.0 |
| systemd-libs | 262.1-1 | LGPL-2.1-or-later  CC0-1.0  GPL-2.0-or-later WITH Linux-syscall-note |
| vulkan-icd-loader | 1.4.363.0-1 | Apache-2.0 |
| wayland | 1.26.0-1 | MIT |
| xcb-util-keysyms | 0.4.1-5 | X11-distribute-modifications-variant |
| zlib | 1:1.3.2-4 | Zlib |
| zstd | 1.5.7-3 | BSD-3-Clause  GPL-2.0-only |

## Optional Discord transport

`discord.py` is MIT licensed ([upstream license](https://github.com/Rapptz/discord.py/blob/v2.7.1/LICENSE)). It provides Gateway connectivity and HTTP rate-limit handling. This does not make Discord's hosted service open source. The optional transport can be removed without changing local inference or terminal chat.

Pinned dependencies and installed distribution license metadata/texts were checked in `runtime/discord/lib/python3.14/site-packages/`. The hash-locked installation list is `scripts/native-linux/discord-requirements.txt`.

| Package | Version | License |
|---|---|---|
| discord.py | 2.7.1 | MIT |
| aiohttp | 3.14.5 | Apache-2.0 AND MIT |
| aiohappyeyeballs | 2.7.1 | PSF-2.0 |
| aiosignal | 1.4.0 | Apache-2.0 |
| attrs | 26.1.0 | MIT |
| audioop-lts | 0.2.2 | PSF-2.0 |
| frozenlist | 1.8.0 | Apache-2.0 |
| idna | 3.20 | BSD-3-Clause |
| multidict | 7.2.1 | Apache-2.0 |
| propcache | 0.5.4 | Apache-2.0 |
| yarl | 1.25.1 | Apache-2.0 |
| uv (optional setup/lock maintenance) | 0.13.7 | MIT OR Apache-2.0; [upstream licenses](https://github.com/astral-sh/uv#license) |

`flock` comes from the already listed util-linux package; `tee` comes from GNU coreutils. No voice dependencies are requested; audioop-lts is an upstream dependency on this Python version.

## Qwen-Agent tool-coordination environment

Qwen-Agent 0.0.34 is Apache-2.0 (verified from the installed license). Its local API mode requires no hosted subscription, login, or paid feature. `runtime/agent/` contains the dependencies installed from `scripts/native-linux/agent-requirements.txt`; no RAG, GUI, MCP, or execution extras were requested. Some transitive packages support unused capabilities, but remain installation requirements. NumPy, SoundFile, tqdm, and python-dateutil are explicit import-time requirements omitted by upstream's minimal metadata.

The following inventory was checked against installed distribution metadata and license files. The lock pins all versions and hashes. SoundFile includes libsndfile and media libraries under LGPL/BSD terms; its `licensing/license_notes.md` records components and source locations. NumPy's installed license includes OpenBLAS/LAPACK and GCC runtime notices (including the GCC runtime exception). Installing these dependencies does not enable audio, cloud calls, or code execution.

| Package | Version | License |
|---|---|---|
| aiohappyeyeballs | 2.7.1 | PSF-2.0 |
| aiohttp | 3.14.5 | Apache-2.0 AND MIT |
| aiosignal | 1.4.0 | Apache-2.0 |
| annotated-doc | 0.0.5 | MIT |
| annotated-types | 0.8.0 | MIT |
| anyio | 4.16.0 | MIT |
| attrs | 26.1.0 | MIT |
| certifi | 2026.10.23 | MPL-2.0 |
| cffi | 2.1.1 | MIT-0 |
| charset-normalizer | 3.5.2 | MIT |
| click | 8.5.1 | BSD-3-Clause |
| cryptography | 50.0.2 | Apache-2.0 OR BSD-3-Clause |
| dashscope | 2.0.4 | Apache-2.0 |
| dotenv | 0.9.9 | MIT (installed LICENSE) |
| eval_type_backport | 0.4.0 | MIT |
| fastapi | 0.162.2 | MIT |
| frozenlist | 1.8.0 | Apache-2.0 |
| h11 | 0.16.0 | MIT |
| httpcore | 1.0.9 | BSD-3-Clause |
| httpcore2 | 2.16.0 | BSD-3-Clause |
| httpx | 0.28.1 | BSD-3-Clause |
| httpx-sse | 0.4.3 | MIT |
| httpx2 | 2.16.0 | BSD-3-Clause |
| idna | 3.20 | BSD-3-Clause |
| jiter | 0.19.0 | MIT |
| json5 | 0.17.3 | Apache-2.0 |
| jsonlines | 4.0.0 | BSD-3-Clause |
| jsonschema | 4.26.0 | MIT |
| jsonschema-specifications | 2025.9.1 | MIT |
| markdown-it-py | 4.2.0 | MIT |
| mdurl | 0.1.2 | MIT |
| multidict | 7.2.1 | Apache-2.0 |
| numpy | 2.5.4 | BSD-3-Clause AND 0BSD AND MIT AND Zlib AND CC0-1.0; bundled OpenBLAS/LAPACK and GCC runtime notices apply |
| openai | 3.48.0 | Apache-2.0 |
| opentelemetry-api | 1.45.2 | Apache-2.0 |
| opentelemetry-sdk | 1.45.2 | Apache-2.0 |
| opentelemetry-semantic-conventions | 0.66b2 | Apache-2.0 |
| pillow | 13.0.0 | MIT-CMU |
| propcache | 0.5.4 | Apache-2.0 |
| pycparser | 3.12 | BSD-3-Clause |
| pydantic | 2.14.3 | MIT |
| pydantic_core | 2.50.4 | MIT |
| Pygments | 2.21.0 | BSD-2-Clause |
| python-dateutil | 4.0.0 | BSD-3-Clause |
| python-dotenv | 1.2.4 | BSD-3-Clause |
| PyYAML | 6.0.3 | MIT |
| qwen-agent | 0.0.34 | Apache-2.0 (installed LICENSE) |
| referencing | 0.37.0 | MIT |
| regex | 2026.11.9 | Apache-2.0 AND CNRI-Python |
| requests | 2.34.2 | Apache-2.0 |
| rich | 15.0.0 | MIT |
| rpds-py | 2026.9.1 | MIT |
| shellingham | 1.5.4 | ISC |
| sniffio | 1.3.1 | MIT OR Apache-2.0 |
| soundfile | 0.14.0 | BSD-3-Clause; bundled libsndfile/media libraries: LGPL/BSD |
| starlette | 1.10.0 | BSD-3-Clause |
| tenacity | 9.2.1 | Apache-2.0 |
| tiktoken | 0.14.0 | MIT |
| tqdm | 4.70.1 | MPL-2.0 AND MIT |
| truststore | 0.10.5 | MIT |
| typer | 0.29.0 | MIT |
| typing-inspection | 0.4.5 | MIT |
| typing_extensions | 4.16.0 | PSF-2.0 |
| tzdata | 2026.6 | Apache-2.0 |
| urllib3 | 2.8.0 | MIT |
| uvicorn | 0.54.0 | BSD-3-Clause |
| websocket-client | 1.9.2 | Apache-2.0 |
| yarl | 1.25.1 | Apache-2.0 |

## Optional conversation viewer

Obsidian 1.14.4 (installed package 1.14.4-2) is proprietary, not open source. Its [license overview](https://obsidian.md/license) permits free personal and commercial local use without an account. Optional Sync and Publish services are not used or required. It is a replaceable viewer for the [Markdown conversation mirror](conversation-vault.md) and is required while using the optional read-only API connection; core chat does not require it. The exporter uses only the existing Python standard library; any Markdown editor can read its output.

## Optional local Obsidian connector

Cyanheads `obsidian-mcp-server` 3.9.0 is Apache-2.0 (installed LICENSE). Obsidian Local REST API with MCP 5.5.2 is MIT ([license](https://github.com/coddingtonbear/obsidian-local-rest-api/blob/5.5.2/LICENSE)). Node.js 24+ is required; this host uses 26.13.1. Node is MIT with bundled third-party notices in `/usr/share/licenses/nodejs/LICENSE`; npm is Artistic-2.0 with dependency notices in its installed LICENSE. No paid connector features, remote accounts or hosted services are required. Obsidian itself remains proprietary as noted above.

The npm lockfile records exact versions and artifact integrity hashes. Installed package license files were checked; retain these files when redistributing the runtime. Inventory of the installed connector and required dependencies:

| Package | Version | License | Installed evidence |
|---|---|---|---|
| @cyanheads/mcp-ts-core | 0.13.22 | Apache-2.0 | LICENSE |
| @hono/node-server | 2.1.8 | MIT | LICENSE |
| @modelcontextprotocol/core | 2.4.0 | Apache-2.0 | LICENSE |
| @modelcontextprotocol/server | 2.4.0 | Apache-2.0 | LICENSE |
| @opentelemetry/api | 1.10.0 | Apache-2.0 | LICENSE |
| @pinojs/redact | 0.4.0 | MIT | LICENSE |
| argparse | 3.0.4 | PSF-2.0 | LICENSE |
| atomic-sleep | 1.0.0 | MIT | LICENSE |
| colorette | 2.0.20 | MIT | LICENSE.md |
| dateformat | 4.6.3 | MIT | LICENSE |
| end-of-stream | 1.4.5 | MIT | LICENSE |
| fast-copy | 4.3.1 | MIT | LICENSE |
| fast-safe-stringify | 2.1.1 | MIT | LICENSE |
| glob-to-regexp | 0.4.1 | BSD-2-Clause | README.md license section |
| help-me | 5.0.0 | MIT | LICENSE |
| hono | 4.13.18 | MIT | LICENSE |
| jose | 6.2.17 | MIT | LICENSE.md |
| joycon | 3.1.1 | MIT | LICENSE |
| js-yaml | 5.5.0 | MIT | LICENSE |
| json-logic-js | 2.0.5 | MIT | LICENSE |
| marked | 17.0.6 | MIT | LICENSE.md |
| minimist | 1.2.8 | MIT | LICENSE |
| obsidian-mcp-server | 3.9.0 | Apache-2.0 | LICENSE |
| on-exit-leak-free | 2.1.2 | MIT | LICENSE |
| once | 1.4.0 | ISC | LICENSE |
| pino | 10.4.0 | MIT | LICENSE |
| pino-abstract-transport | 3.0.0 | MIT | LICENSE |
| pino-pretty | 13.2.0 | MIT | LICENSE |
| pino-pretty/node_modules/sonic-boom | 5.0.2 | MIT | LICENSE |
| pino-std-serializers | 7.1.0 | MIT | LICENSE |
| process-warning | 5.1.1 | MIT | LICENSE |
| pump | 3.0.4 | MIT | LICENSE |
| quick-format-unescaped | 4.0.4 | MIT | LICENSE |
| real-require | 1.0.0 | MIT | LICENSE.md |
| safe-stable-stringify | 2.5.0 | MIT | LICENSE |
| secure-json-parse | 4.1.1 | BSD-3-Clause | LICENSE |
| sonic-boom | 4.2.1 | MIT | LICENSE |
| split2 | 4.2.0 | ISC | LICENSE |
| strip-json-comments | 5.0.3 | MIT | license |
| thread-stream | 4.2.1 | MIT | LICENSE |
| undici | 8.12.4 | MIT | LICENSE |
| wrappy | 1.0.2 | ISC | LICENSE |
| yaml | 2.9.1 | ISC | LICENSE |
| zod | 4.6.7 | MIT | LICENSE |
