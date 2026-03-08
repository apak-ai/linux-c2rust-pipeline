// SPDX-License-Identifier: GPL-2.0-only
//! Nintendo Wii and Wii U OTP driver.
//!
//! Rust translation of `drivers/nvmem/nintendo-otp.c`.
//! Original author: Emmanuel Gil Peyrot <linkmauve@linkmauve.fr>
//!
//! Exposes the OTP (One-Time Programmable) memory of Nintendo Wii/Wii U
//! consoles via the kernel nvmem subsystem.

use linux_rust_bindings::nvmem;

// Register offsets within the MMIO region.
const HW_OTPCMD: usize = 0;
const HW_OTPDATA: usize = 4;

// Command flags.
const OTP_READ: u32 = 0x8000_0000;

// OTP geometry constants.
const BANK_SIZE: u32 = 128;
const WORD_SIZE: u32 = 4;

/// Private driver state — one instance per platform device.
#[repr(C)]
pub struct NintendoOtpPriv {
    /// Base address of the MMIO register block.
    ///
    /// Obtained from `devm_platform_ioremap_resource` and valid for the
    /// lifetime of the platform device.
    regs: *mut u8,
}

// SAFETY: `NintendoOtpPriv` is only accessed while holding the kernel's
// device-model lock and MMIO is performed via volatile operations, making
// it safe to transfer across thread boundaries.
unsafe impl Send for NintendoOtpPriv {}

extern "C" {
    /// Big-endian 32-bit MMIO read (kernel ioread32be).
    fn ioread32be(addr: *const u8) -> u32;
    /// Big-endian 32-bit MMIO write (kernel iowrite32be).
    fn iowrite32be(val: u32, addr: *mut u8);
}

impl NintendoOtpPriv {
    /// Creates a new `NintendoOtpPriv` from a raw MMIO base pointer.
    ///
    /// # Safety
    /// `regs` must be a valid, non-null MMIO pointer covering at least
    /// `MMIO_SIZE` bytes, as provided by `devm_platform_ioremap_resource`.
    pub unsafe fn new(regs: *mut u8) -> Option<Self> {
        if regs.is_null() {
            return None;
        }
        Some(Self { regs })
    }

    /// Reads `bytes` bytes of OTP data starting at byte offset `reg` into `val`.
    ///
    /// Issues one OTP_READ command per 32-bit word, then reads the result.
    ///
    /// # Safety
    /// - `self.regs` must be a valid MMIO pointer (guaranteed by construction).
    /// - `val` must point to a buffer of at least `bytes` bytes.
    /// - Caller must hold the device-model lock.
    pub unsafe fn reg_read(&self, mut reg: u32, val: *mut u32, bytes: usize) -> i32 {
        let mut words = (bytes / WORD_SIZE as usize) as i32;
        let mut out = val;

        while words > 0 {
            words -= 1;

            let bank = (reg / BANK_SIZE) << 8;
            let addr = (reg / WORD_SIZE) % (BANK_SIZE / WORD_SIZE);
            let cmd = OTP_READ | bank | addr;

            // SAFETY: `self.regs + HW_OTPCMD` is within the MMIO region
            // mapped by `devm_platform_ioremap_resource` (offset 0, within
            // MMIO_SIZE = 8 bytes). The write initiates an OTP read cycle.
            iowrite32be(cmd, self.regs.add(HW_OTPCMD));

            // SAFETY: `self.regs + HW_OTPDATA` is within the MMIO region
            // (offset 4, two 32-bit registers total). The data register is
            // valid after the command write above completes.
            let data = ioread32be(self.regs.add(HW_OTPDATA).cast::<u8>());

            // SAFETY: `out` was derived from the caller-provided `val` buffer
            // of `bytes` bytes. We advance by one `u32` per loop iteration and
            // loop at most `bytes / 4` times, so we never exceed the buffer.
            *out = data;
            out = out.add(1);

            reg += WORD_SIZE;
        }

        0
    }
}

/// C-callable wrapper for `NintendoOtpPriv::reg_read`, registered as the
/// nvmem `reg_read` callback.
///
/// # Safety
/// - `context` must be a valid, non-null pointer to a `NintendoOtpPriv`.
/// - `val` must point to a buffer of at least `bytes` bytes.
#[no_mangle]
pub unsafe extern "C" fn nintendo_otp_reg_read(
    context: *mut u8,
    reg: u32,
    val: *mut u8,
    bytes: usize,
) -> i32 {
    // SAFETY: `context` is set by `nintendo_otp_probe` to a valid, non-null
    // `NintendoOtpPriv` pointer allocated via `devm_kzalloc`. The kernel
    // nvmem core serialises calls to this callback.
    let priv_data = &*(context.cast::<NintendoOtpPriv>());

    // SAFETY: `val` is provided by the nvmem core and is guaranteed to point
    // to a buffer of `bytes` bytes. `priv_data` is valid by the argument above.
    priv_data.reg_read(reg, val.cast::<u32>(), bytes)
}

/// Initialises the OTP nvmem configuration for a given device.
///
/// Fills in the fields common to both Wii and Wii U variants and returns
/// a partially-configured `nvmem::Config`.
///
/// # Safety
/// `dev` and `priv_data` must be valid, non-null pointers that remain live
/// for the lifetime of the returned config.
pub unsafe fn build_nvmem_config(
    dev: *mut u8,
    priv_data: *mut NintendoOtpPriv,
    name: *const u8,
    num_banks: u32,
) -> nvmem::Config {
    // SAFETY: All pointer arguments are validated by the caller (probe function).
    // The function pointers set here are valid for the lifetime of the device.
    nvmem::Config {
        name,
        dev,
        priv_data: priv_data.cast::<u8>(),
        reg_read: Some(nintendo_otp_reg_read),
        read_only: true,
        root_only: true,
        stride: WORD_SIZE,
        word_size: WORD_SIZE,
        size: num_banks * BANK_SIZE,
    }
}
