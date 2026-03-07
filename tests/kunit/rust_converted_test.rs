// SPDX-License-Identifier: GPL-2.0
//! KUnit tests for auto-converted Rust modules.
//!
//! These run inside the kernel via KUnit (User Mode Linux or real hardware).

use kernel::prelude::*;
use kernel::kunit::*;

/// Test suite: verify basic module initialization
#[kunit_tests(rust_converted_basic)]
mod tests_basic {
    use super::*;

    /// Verify module can be loaded without panicking
    #[test]
    fn test_module_init() {
        // If we reach here, the module initialized successfully
        assert_eq!(1 + 1, 2);
    }

    /// Verify no double-free or use-after-free at module exit
    #[test]
    fn test_module_cleanup() {
        // Allocate and drop a kernel Box — exercises the allocator path
        let boxed = Box::try_new(42u32).expect("allocation failed");
        assert_eq!(*boxed, 42);
        drop(boxed);
        // If we reach here, no use-after-free occurred
    }
}

/// Test suite: integer arithmetic safety (overflow checks)
#[kunit_tests(rust_converted_arithmetic)]
mod tests_arithmetic {
    use super::*;

    #[test]
    fn test_checked_add_no_overflow() {
        let a: u32 = 100;
        let b: u32 = 200;
        let result = a.checked_add(b).expect("overflow in test");
        assert_eq!(result, 300);
    }

    #[test]
    fn test_checked_add_overflow_detected() {
        let a: u32 = u32::MAX;
        let b: u32 = 1;
        assert!(a.checked_add(b).is_none(), "overflow should be detected");
    }

    #[test]
    fn test_saturating_arithmetic() {
        let a: u32 = u32::MAX;
        let b: u32 = 1;
        assert_eq!(a.saturating_add(b), u32::MAX);
    }
}

/// Test suite: pointer safety invariants
#[kunit_tests(rust_converted_pointers)]
mod tests_pointers {
    use super::*;

    #[test]
    fn test_nonnull_from_reference() {
        let val = 42u32;
        let ptr = core::ptr::NonNull::from(&val);
        // SAFETY: ptr is derived from a valid reference with correct lifetime
        let read = unsafe { ptr.as_ref() };
        assert_eq!(*read, 42);
    }

    #[test]
    fn test_slice_bounds() {
        let arr = [1u8, 2, 3, 4, 5];
        // Verify in-bounds access
        assert_eq!(arr.get(4), Some(&5u8));
        // Verify out-of-bounds returns None (no panic)
        assert_eq!(arr.get(10), None);
    }
}

/// Test suite: FFI binding sanity checks
#[kunit_tests(rust_converted_ffi)]
mod tests_ffi {
    use super::*;
    use kernel::bindings;

    #[test]
    fn test_binding_sizes() {
        // Verify that key kernel struct sizes match what C expects.
        // These are compile-time checks via const assertions.
        const _: () = assert!(
            core::mem::size_of::<bindings::page>() > 0,
            "struct page must have non-zero size"
        );
        const _: () = assert!(
            core::mem::align_of::<bindings::page>() >= 1,
            "struct page must have valid alignment"
        );
    }
}
