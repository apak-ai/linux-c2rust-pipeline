#!/usr/bin/env bash
# idiomize.sh <rust_dir>
# Post-process c2rust output toward idiomatic, safer Rust.
# Applies a series of sed/awk transforms and then runs rustfix suggestions.
set -euo pipefail

RUST_DIR="${1:?Usage: idiomize.sh <rust_dir>}"
RUST_DIR="$(realpath "$RUST_DIR")"

if [ ! -d "$RUST_DIR" ]; then
    echo "ERROR: $RUST_DIR is not a directory" >&2
    exit 1
fi

echo "[idiomize] Processing $RUST_DIR"

for rs_file in "$RUST_DIR"/*.rs; do
    [ -f "$rs_file" ] || continue
    echo "  → $rs_file"

    # 1. Replace raw pointer casts with safer equivalents where possible
    sed -i 's/as \*mut libc::c_void/as *mut core::ffi::c_void/g' "$rs_file"
    sed -i 's/as \*const libc::c_void/as *const core::ffi::c_void/g/g' "$rs_file"

    # 2. Replace libc types with kernel/core equivalents
    sed -i 's/libc::c_int/core::ffi::c_int/g'       "$rs_file"
    sed -i 's/libc::c_uint/core::ffi::c_uint/g'     "$rs_file"
    sed -i 's/libc::c_ulong/core::ffi::c_ulong/g'   "$rs_file"
    sed -i 's/libc::c_long/core::ffi::c_long/g'     "$rs_file"
    sed -i 's/libc::c_char/core::ffi::c_char/g'     "$rs_file"
    sed -i 's/libc::size_t/usize/g'                 "$rs_file"
    sed -i 's/libc::ssize_t/isize/g'                "$rs_file"
    sed -i 's/libc::uint8_t/u8/g'                   "$rs_file"
    sed -i 's/libc::uint16_t/u16/g'                 "$rs_file"
    sed -i 's/libc::uint32_t/u32/g'                 "$rs_file"
    sed -i 's/libc::uint64_t/u64/g'                 "$rs_file"
    sed -i 's/libc::int8_t/i8/g'                    "$rs_file"
    sed -i 's/libc::int16_t/i16/g'                  "$rs_file"
    sed -i 's/libc::int32_t/i32/g'                  "$rs_file"
    sed -i 's/libc::int64_t/i64/g'                  "$rs_file"

    # 3. Add SAFETY comments to bare unsafe blocks lacking one
    python3 "$(dirname "$0")/add_safety_comments.py" "$rs_file"

    # 4. Replace malloc/free patterns with Box/Vec where the analysis
    #    script identifies single-owner heap allocations
    python3 "$(dirname "$0")/convert_allocs.py" "$rs_file"

    # 5. Collapse trivial transmute(x) → x as T casts
    sed -i 's/core::mem::transmute::<\([^>]*\), \1>(\([^)]*\))/\2/g' "$rs_file"
done

# 6. Run rustfix to apply compiler-suggested fixes
cargo fix \
    --manifest-path "$RUST_DIR/../Cargo.toml" \
    --allow-dirty \
    --allow-staged \
    2>&1 || true

echo "[idiomize] Done"
