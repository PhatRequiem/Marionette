# Active software and model licenses

All selected software is free and open source. Local operation has no paid feature, subscription, vendor account, or license-server requirement. Downloads require internet access only during setup. Model licensing is reviewed separately below.

## Runtime and setup

| Component | Verified version | License / evidence |
|---|---|---|
| llama.cpp, ggml, bundled completion libraries | b12211, commit 7d7f02875 | MIT; bundled `runtime/llama.cpp/b12211/llama-b12211/LICENSE`, [upstream](https://github.com/ggml-org/llama.cpp/blob/b12211/LICENSE) |
| Python (setup and launcher manifest loading, standard library only) | 3.14.8 | PSF-2.0 |
| util-linux (`script` terminal recorder) | 2.42.4 | util-linux package: BSD-2-Clause, BSD-3-Clause, BSD-4-Clause-UC, GPL-2.0-only, GPL-2.0-or-later, GPL-3.0-or-later, ISC, LGPL-2.1-or-later, public domain; installed license texts under `/usr/share/licenses/util-linux/` |
| xdg-terminal-exec (default terminal launcher) | 0.14.3 | GPL-3.0-or-later, verified in `/usr/bin/xdg-terminal-exec` |
| Kitty (configured log terminal) | 0.49.2 | GPL-3.0-only |
| GNU coreutils (tail, mktemp, date, mkdir) | 9.12 | GPL-3.0-or-later; package documentation GFDL-1.3-or-later |
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

System package versions and license identifiers were checked using `pacman -Qi`; installed license texts are under `/usr/share/licenses/` and package/upstream source distributions. Linked completion libraries were inspected with `ldd`. These are the current host versions, not a frozen operating-system image. Mesa also uses system graphics/LLVM support libraries provided by the distribution; their package licenses apply.

## Model weights (separate from software)

[Qwen/Qwen3.5-4B](https://huggingface.co/Qwen/Qwen3.5-4B) uses [Apache-2.0](https://huggingface.co/Qwen/Qwen3.5-4B/blob/main/LICENSE), verified from the actual license text. The [Unsloth GGUF distribution](https://huggingface.co/unsloth/Qwen3.5-4B-GGUF/tree/e87f176479d0855a907a41277aca2f8ee7a09523) identifies that base model and the same Apache-2.0 license. We use Q4_K_M at that pinned revision; see the download manifest for its checksum. Unsloth training software is not installed or required. Preserve license and attribution obligations if redistributing weights. This repository does not redistribute weights or runtime binaries.

## Resolved system library inventory

Transitive shared-library package owners resolved with `ldd` and `pacman` for the completion executable, Vulkan backend, and RADV driver on the verified host:

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
