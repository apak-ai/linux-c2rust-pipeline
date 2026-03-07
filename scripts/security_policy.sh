#!/usr/bin/env bash
# security_policy.sh <rust_src_dir>
# Enforce kernel-specific security policies on generated Rust code.
set -euo pipefail

SRC="${1:?Usage: security_policy.sh <rust_src_dir>}"
FAIL=0

banner() { echo ""; echo "=== $* ==="; }
fail()   { echo "FAIL: $*" >&2; FAIL=1; }
warn()   { echo "WARN: $*"; }

banner "Checking for banned functions"
BANNED_FNS=(
    "std::process::exit"       # use kernel's own exit mechanisms
    "panic!"                   # kernel must not panic; use Result
    "unwrap()"                 # ditto
    "expect("                  # ditto — use map_err
    "println!"                 # no std I/O in kernel
    "eprintln!"
    "std::alloc"               # use kernel allocator via kernel::alloc
    "Box::new("                # use kernel::alloc::Box
    "Vec::new("                # use kernel::alloc::Vec
    "String::new("             # use kernel::str::CString
    "format!("                 # no format! in kernel without alloc feature
    "thread::spawn"            # no std threads in kernel
    "std::sync::Mutex"         # use kernel::sync::Mutex
    "std::sync::Arc"           # use kernel::sync::Arc
)

for fn in "${BANNED_FNS[@]}"; do
    matches=$(grep -rn --include='*.rs' -F "$fn" "$SRC" 2>/dev/null || true)
    if [ -n "$matches" ]; then
        fail "Banned pattern '$fn' found:"
        echo "$matches"
    fi
done

banner "Checking for global mutable state (static mut)"
STATIC_MUT=$(grep -rn --include='*.rs' 'static mut ' "$SRC" 2>/dev/null || true)
if [ -n "$STATIC_MUT" ]; then
    warn "static mut found — review for race conditions (requires LKMM annotation):"
    echo "$STATIC_MUT"
fi

banner "Checking for integer overflow potential"
# Flag unchecked arithmetic on size/index types
OVERFLOW=$(grep -rn --include='*.rs' -E '(usize|u32|u64|i32|i64)\s*\+\s*[0-9]' "$SRC" \
    | grep -v 'checked_add\|saturating_add\|wrapping_add' || true)
if [ -n "$OVERFLOW" ]; then
    warn "Potential unchecked integer arithmetic:"
    echo "$OVERFLOW"
fi

banner "Checking for raw pointer dereferences without bounds"
RAW_DEREF=$(grep -rn --include='*.rs' '\*[a-z_]*ptr\b\|\.as_ptr()\s*\.' "$SRC" 2>/dev/null || true)
if [ -n "$RAW_DEREF" ]; then
    warn "Raw pointer dereferences found — ensure bounds are validated:"
    echo "$RAW_DEREF"
fi

banner "Checking no #[no_mangle] conflicts with kernel C symbols"
NO_MANGLE=$(grep -rn --include='*.rs' '#\[no_mangle\]' "$SRC" 2>/dev/null || true)
if [ -n "$NO_MANGLE" ]; then
    echo "Exported symbols (verify against kernel symbol table):"
    echo "$NO_MANGLE"
fi

banner "Checking for use of deprecated/removed kernel APIs"
DEPRECATED=(
    "kernel::file_operations"   # replaced by kernel::file::Operations
    "kernel::miscdev"           # use kernel::miscdevice
)
for api in "${DEPRECATED[@]}"; do
    matches=$(grep -rn --include='*.rs' -F "$api" "$SRC" 2>/dev/null || true)
    if [ -n "$matches" ]; then
        fail "Deprecated kernel API '$api' found:"
        echo "$matches"
    fi
done

banner "Checking for missing #[allow(clippy::...)] without justification"
BARE_ALLOW=$(grep -rn --include='*.rs' '#\[allow(' "$SRC" \
    | grep -v '//.*justification\|//.*SAFETY\|// Allow:' || true)
if [ -n "$BARE_ALLOW" ]; then
    warn "#[allow(...)] without justification comment:"
    echo "$BARE_ALLOW"
fi

banner "Summary"
if [ "$FAIL" -ne 0 ]; then
    echo "RESULT: FAILED — security policy violations found."
    exit 1
else
    echo "RESULT: PASSED — no critical policy violations."
fi
