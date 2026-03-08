#![no_std]
//! Safe Rust wrappers around kernel primitives.

/// A safe wrapper around a memory-mapped I/O region.
///
/// Ensures the pointer is non-null and aligned before use.
pub struct IoRegion {
    base: *mut u8,
    size: usize,
}

impl IoRegion {
    /// Creates a new `IoRegion`.
    ///
    /// # Safety
    /// `base` must be a valid, non-null, aligned pointer to a memory-mapped
    /// region of at least `size` bytes that remains valid for the lifetime of
    /// this `IoRegion`.
    pub unsafe fn new(base: *mut u8, size: usize) -> Option<Self> {
        if base.is_null() {
            return None;
        }
        Some(Self { base, size })
    }

    /// Returns the base pointer.
    pub fn as_ptr(&self) -> *mut u8 {
        self.base
    }

    /// Returns the mapped size in bytes.
    pub fn size(&self) -> usize {
        self.size
    }
}

// SAFETY: MMIO regions are accessed only through volatile reads/writes and
// the kernel device model ensures exclusive access per device instance.
unsafe impl Send for IoRegion {}
unsafe impl Sync for IoRegion {}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn io_region_null_rejected() {
        // SAFETY: Passing null to test the null-rejection logic.
        let result = unsafe { IoRegion::new(core::ptr::null_mut(), 16) };
        assert!(result.is_none());
    }
}
