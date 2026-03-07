# Linux C → Rust CI/CD Pipeline

A GitHub Actions pipeline that automatically converts Linux kernel C source files into Rust, evaluates security, checks compatibility with existing kernel code, and validates the result boots as a functioning Linux kernel.

---

## What This Does

The Linux kernel is written almost entirely in C. This pipeline automates the process of:

1. **Converting** C files to Rust using the `c2rust` transpiler
2. **Auditing** the generated Rust for security issues
3. **Verifying** the Rust integrates correctly with the existing C kernel
4. **Building** a real kernel and booting it in a virtual machine to confirm it works

The end goal is a kernel where C modules are progressively replaced by safe, audited Rust equivalents — following the direction of the official [Rust for Linux](https://rust-for-linux.com) project.

---

## Directory Structure

```
linux-c2rust-pipeline/
│
├── .github/
│   ├── workflows/
│   │   ├── 01-convert.yml       # Stage 1: C → Rust transpilation
│   │   ├── 02-security.yml      # Stage 2: Security evaluation
│   │   ├── 03-compat.yml        # Stage 3: Compatibility verification
│   │   └── 04-build-test.yml    # Stage 4: Kernel build and boot test
│   └── PR_TEMPLATE_CONVERT.md   # Auto-filled PR description for conversions
│
├── scripts/
│   ├── gen_compile_commands.sh  # Generate compile_commands.json from kernel build
│   ├── idiomize.sh              # Clean up c2rust output toward idiomatic Rust
│   ├── security_policy.sh       # Enforce kernel-specific coding rules
│   ├── check_safety_docs.py     # Verify unsafe blocks have SAFETY: comments
│   ├── gen_bindings.sh          # Generate Rust FFI bindings from kernel headers
│   ├── abi_diff.py              # Detect ABI-breaking changes between builds
│   ├── inject_modules.sh        # Insert Rust modules into kernel source tree
│   ├── build_initramfs.sh       # Build minimal Linux initramfs for QEMU testing
│   ├── boot_test_payload.sh     # Test script that runs inside the booted VM
│   ├── validate_boot_log.py     # Check QEMU output for success/failure markers
│   ├── parse_geiger.py          # Parse cargo-geiger unsafe code report
│   ├── parse_ktap.py            # Parse KUnit test results into JUnit XML
│   ├── gen_report.py            # Build consolidated Markdown report from all stages
│   └── evaluate_pipeline.py     # Final pass/fail decision for the whole pipeline
│
├── config/
│   ├── clippy.toml              # Clippy lint settings (stack limits, complexity)
│   ├── kunit.kunitconfig        # KUnit test configuration for UML kernel
│   └── expected_rust_symbols.txt # Symbols that must exist in the built kernel
│
├── tests/
│   └── kunit/
│       └── rust_converted_test.rs  # In-kernel unit tests for converted modules
│
└── Cargo.toml                   # Rust workspace (no_std, panic=abort)
```

---

## The Four Stages

### Stage 1 — C to Rust Conversion (`01-convert.yml`)

**Trigger:** Push to `main` or a `convert/` branch touching `src/c/`

**What happens:**

1. Builds the kernel with `bear` to capture a `compile_commands.json` — a database of every compiler invocation. `c2rust` needs this to understand include paths, defines, and flags.
2. Runs `c2rust transpile` on each C file. The output is valid but **unsafe** Rust — every pointer operation, every cast is wrapped in `unsafe {}`.
3. Runs `idiomize.sh` which replaces `libc::c_int` with `core::ffi::c_int`, removes `std::` references, and adds placeholder `// SAFETY:` comments.
4. Formats the result with `rustfmt`.
5. Opens a Pull Request with the generated Rust files for human review.

**Output:** A PR containing generated `.rs` files under `src/rust/generated/`

---

### Stage 2 — Security Evaluation (`02-security.yml`)

**Trigger:** PR touching `src/rust/`

**What happens:**

| Check | Tool | What it catches |
|-------|------|-----------------|
| Static analysis | `cargo clippy` | Unsafe patterns, bad casts, missing safety docs |
| Unsafe code count | `cargo-geiger` | Total unsafe functions/expressions per crate |
| Known CVEs | `cargo-audit` | Vulnerable or yanked dependencies |
| Undefined behaviour | `Miri` | Use-after-free, out-of-bounds, invalid pointer arithmetic |
| Kernel policy | `security_policy.sh` | Banned APIs (`std::`, `panic!`, `unwrap()`, `static mut`) |
| Safety comments | `check_safety_docs.py` | Every `unsafe` block must have `// SAFETY:` above it |

**Gate:** All checks must pass before Stage 3 runs.

---

### Stage 3 — Compatibility Check (`03-compat.yml`)

**Trigger:** After Stage 2 gate passes

**What happens:**

1. **FFI Bindings** — `bindgen` is run against the real kernel headers to generate Rust type definitions that match the C structs exactly. These are compared to a saved snapshot to catch ABI-breaking changes (e.g. a struct field removed, a function signature changed).
2. **Symbol Verification** — Checks that every kernel symbol the Rust code references actually exists in the built kernel's symbol table (`/proc/kallsyms`).
3. **Cross-Language Integration** — Builds a test harness where C code calls Rust functions and Rust code calls C kernel functions. Tests run for three architectures: `x86_64`, `arm64`, `riscv64`.
4. **Kbuild Compilation** — Injects the Rust modules into a real kernel source tree and runs `make LLVM=1` to confirm the kernel actually compiles with them included.

**Gate:** All architectures must compile cleanly, no ABI breaks, no missing symbols.

---

### Stage 4 — Build & Boot Test (`04-build-test.yml`)

**Trigger:** After Stage 3 gate passes

**What happens:**

1. **Full Kernel Build** — Builds a complete bootable kernel image for `x86_64`, `arm64`, and `riscv64` with the Rust modules compiled in.
2. **KUnit Tests** — Runs the in-kernel unit tests (`tests/kunit/`) inside a User Mode Linux (UML) kernel — a special kernel that runs as a normal process, no VM needed.
3. **QEMU Boot Test** — Boots the full kernel image in QEMU with a minimal initramfs. The `boot_test_payload.sh` script runs inside the VM and checks:
   - Rust modules are loaded
   - No kernel panic or oops in dmesg
   - Rust symbols appear in `/proc/kallsyms`
4. **Kernel Selftests** — Runs the kernel's own `tools/testing/selftests/rust` suite.
5. **Final Report** — Aggregates all results from all stages into a single Markdown summary posted as a PR comment.

---

## Key Constraints (Why These Rules Exist)

The Linux kernel is a `no_std` environment — the Rust standard library does not exist. This changes many things:

| What you'd normally write | What the kernel requires | Why |
|---------------------------|--------------------------|-----|
| `Box::new(x)` | `Box::try_new(x)?` (kernel allocator) | Kernel allocation can fail; must handle it |
| `Vec::new()` | `Vec::try_with_capacity(n)?` | Same reason |
| `std::sync::Mutex` | `kernel::sync::Mutex` | Kernel has its own locking with lock ordering rules |
| `panic!("msg")` | Return `Err(EINVAL)` | Kernel cannot panic — it would crash the whole system |
| `unwrap()` | `ok_or(ENOMEM)?` | Same reason |
| `println!()` | `pr_info!()` | No stdout in the kernel; use kernel printk |
| `std::alloc` | `kernel::alloc` | Kernel has its own memory allocator (kmalloc) |

Additionally, `Cargo.toml` sets `panic = "abort"` and the kernel build uses `#![no_std]` in all Rust crates.

---

## How to Use This Pipeline

### Prerequisites

- A GitHub repository
- Your C kernel source files placed under `src/c/`
- GitHub Actions enabled

### Setup

```bash
# Clone or copy this pipeline into your repo
cp -r linux-c2rust-pipeline/ your-repo/

# Push your C files to convert
mkdir -p your-repo/src/c/
cp path/to/your/module.c your-repo/src/c/

# Push to trigger Stage 1
git add . && git commit -m "add C module for conversion"
git push origin main
```

### What triggers each stage

| Event | Stage triggered |
|-------|----------------|
| Push to `main`/`convert/**` touching `src/c/` | Stage 1 (conversion) |
| PR opened touching `src/rust/` | Stage 2 (security) |
| Stage 2 completes successfully | Stage 3 (compatibility) |
| Stage 3 completes successfully | Stage 4 (build + boot) |
| Manual `workflow_dispatch` | Any stage individually |

### Adding symbols to verify

Edit `config/expected_rust_symbols.txt` and add the symbol names that your converted modules must export. These are checked against `nm vmlinux` output after the kernel build.

### Adjusting unsafe thresholds

In `scripts/parse_geiger.py`, the defaults are:
- Max 50 unsafe functions per crate
- Max 200 unsafe expressions per crate

Adjust `--threshold-unsafe-fns` and `--threshold-unsafe-exprs` in `02-security.yml` to match your tolerance.

---

## Tool Reference

| Tool | Version | Purpose |
|------|---------|---------|
| `c2rust` | 0.20.0 | Transpiles C to unsafe Rust |
| `cargo clippy` | nightly | Static analysis, lint enforcement |
| `cargo-geiger` | latest | Count unsafe code blocks |
| `cargo-audit` | latest | Scan dependencies for known CVEs |
| `Miri` | nightly | Detect undefined behaviour at runtime |
| `bindgen` | latest | Generate Rust FFI bindings from C headers |
| `QEMU` | system | Boot test the built kernel |
| `KUnit` | in-kernel | Unit test framework inside the kernel |
| `Bear` | system | Capture compile commands for c2rust |

---

## Limitations and Known Issues

- **c2rust output is not safe Rust.** The transpiler produces working but heavily unsafe code. The `idiomize.sh` script makes surface-level improvements, but human review is required before merging.
- **Not all C patterns translate.** Macros, inline assembly, `goto`, and some function pointer patterns may not transpile correctly. These require manual porting.
- **Architecture coverage.** Build tests cover `x86_64`, `arm64`, and `riscv64`. Other architectures need additional cross-compilation toolchains.
- **KUnit UML only runs on x86_64.** The User Mode Linux target only supports x86_64; other architectures use QEMU instead.
- **Kernel version pinned to 6.12.** The bindgen flags and Rust support options are tuned for kernel 6.12. Other versions may need adjustment.
