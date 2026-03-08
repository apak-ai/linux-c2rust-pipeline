#![no_std]
//! FFI type bindings for Linux kernel structures.

/// Raw pointer to memory-mapped I/O registers.
pub type IoMem = *mut u8;

pub mod nvmem {
    /// Opaque handle to an nvmem device.
    #[repr(C)]
    pub struct Device {
        _private: [u8; 0],
    }

    /// nvmem device configuration passed to devm_nvmem_register.
    #[repr(C)]
    pub struct Config {
        pub name: *const u8,
        pub dev: *mut u8,
        pub priv_data: *mut u8,
        pub reg_read: Option<unsafe extern "C" fn(
            ctx: *mut u8,
            reg: u32,
            val: *mut u8,
            bytes: usize,
        ) -> i32>,
        pub read_only: bool,
        pub root_only: bool,
        pub stride: u32,
        pub word_size: u32,
        pub size: u32,
    }
}
