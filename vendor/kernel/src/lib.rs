#![no_std]
// Stub kernel crate — replaced by the real in-tree kernel crate at build time.
pub use core::{ptr, mem};

pub mod prelude {
    pub use core::ptr;
}

/// Kernel error codes (errno values).
#[repr(i32)]
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum Error {
    ENOMEM = -12,
    ENODEV = -19,
    EINVAL = -22,
}

pub type Result<T = ()> = core::result::Result<T, Error>;
