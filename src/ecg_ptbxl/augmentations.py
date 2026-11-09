from __future__ import annotations

from numbers import Integral

import numpy as np
from numpy.typing import ArrayLike, NDArray

AUGMENTATION_PRESETS = {
    "noise_snr_db": (30.0, 20.0, 10.0),
    "gain_factors": (1.05, 1.15, 1.30),
    "wander_relative_amplitude": (0.1, 0.3, 0.6),
    "wander_frequency_hz": 0.3,
    "shift_seconds": (0.1, 0.25, 0.5),
}


def _signal_array(signal: ArrayLike) -> NDArray[np.float64]:
    if np.iscomplexobj(signal):
        raise ValueError("signal must contain real values")
    values = np.asarray(signal, dtype=np.float64)
    if values.ndim != 2 or values.shape[0] < 2 or values.shape[1] < 1:
        raise ValueError("signal must have shape (samples >= 2, leads >= 1)")
    if not np.isfinite(values).all():
        raise ValueError("signal must contain only finite values")
    return values


def _finite_float(value: float, name: str) -> float:
    number = float(value)
    if not np.isfinite(number):
        raise ValueError(f"{name} must be finite")
    return number


def _generator(rng: np.random.Generator) -> np.random.Generator:
    if not isinstance(rng, np.random.Generator):
        raise TypeError("rng must be a numpy.random.Generator")
    return rng


def _finite_result(values: NDArray[np.float64]) -> NDArray[np.float64]:
    if not np.isfinite(values).all():
        raise ValueError("augmentation parameters produce non-finite values")
    return values


def _require_standard_leads(values: NDArray[np.float64], lead_consistent: bool) -> None:
    if lead_consistent and values.shape[1] != 12:
        raise ValueError("lead_consistent=True requires 12 standard leads in canonical order")


def _derive_limb_perturbations(values: NDArray[np.float64]) -> NDArray[np.float64]:
    """Derive III, AVR, AVL, AVF from I/II, keeping V1..V6 independent."""
    result = values.copy()
    lead_i, lead_ii = values[:, 0], values[:, 1]
    result[:, 2] = lead_ii - lead_i
    result[:, 3] = -(lead_i + lead_ii) / 2
    result[:, 4] = lead_i - lead_ii / 2
    result[:, 5] = lead_ii - lead_i / 2
    return result


def robust_reference_scale(signal: ArrayLike) -> float:
    """Return median time-centered RMS across nonconstant leads, in signal units.

    Constant leads are excluded. Return zero for an entirely constant recording.
    The scale is shared across leads.
    """
    values = _signal_array(signal)
    # Normalization avoids overflow when squaring and also supports tiny inputs.
    magnitude = float(np.max(np.abs(values)))
    if magnitude == 0:
        return 0.0
    normalized = values / magnitude
    centered = normalized - normalized.mean(axis=0)
    rms = np.sqrt(np.mean(centered**2, axis=0))
    nonconstant = np.ptp(normalized, axis=0) > 0
    if not nonconstant.any():
        return 0.0
    return float(np.median(rms[nonconstant]) * magnitude)


def add_gaussian_noise(
    signal: ArrayLike,
    snr_db: float,
    rng: np.random.Generator,
    *,
    lead_consistent: bool = False,
) -> NDArray[np.float64]:
    """Add independent Gaussian samples using one recording-level noise scale.

    ``sigma = robust_reference_scale(signal) * 10**(-snr_db / 20)``.
    Thus ``snr_db`` is a nominal SNR relative to the robust reference; it is not
    an exact measured SNR for every lead. Noise may also affect a flat lead when
    other leads provide a nonzero reference. All-constant input is unchanged.

    With ``lead_consistent=True``, require standard lead order
    ``I, II, III, AVR, AVL, AVF, V1, ..., V6``. Derive limb noise from I/II so the
    original recording's limb-relation residuals are unchanged. Derived leads
    have different noise variance, so realized SNR should be measured separately.
    """
    values = _signal_array(signal)
    _require_standard_leads(values, lead_consistent)
    snr_db = _finite_float(snr_db, "snr_db")
    rng = _generator(rng)
    scale = robust_reference_scale(values)
    if scale == 0:
        return values.copy()
    with np.errstate(over="ignore", invalid="ignore"):
        sigma = scale * np.power(10.0, -snr_db / 20.0)
    if not np.isfinite(sigma):
        raise ValueError("snr_db produces non-finite noise amplitude")
    noise = rng.normal(0.0, sigma, size=values.shape)
    if lead_consistent:
        noise = _derive_limb_perturbations(noise)
    return _finite_result(values + noise)


def scale_amplitude(signal: ArrayLike, factor: float) -> NDArray[np.float64]:
    """Multiply every sample and lead by the same strictly positive factor.

    Lead ratios, polarity and timing are preserved. Offsets are scaled too.
    """
    values = _signal_array(signal)
    factor = _finite_float(factor, "factor")
    if factor <= 0:
        raise ValueError("factor must be strictly positive")
    with np.errstate(over="ignore", invalid="ignore"):
        result = values * factor
    return _finite_result(result)


def add_baseline_wander(
    signal: ArrayLike,
    fs: float,
    relative_amplitude: float,
    frequency_hz: float,
    rng: np.random.Generator,
    *,
    lead_consistent: bool = False,
) -> NDArray[np.float64]:
    """Add one sinusoid with a shared random phase and amplitude to all leads.

    Peak amplitude equals ``relative_amplitude * robust_reference_scale(signal)``
    in the default shared-baseline mode. With ``lead_consistent=True``, require
    ``I, II, III, AVR, AVL, AVF, V1, ..., V6`` and use random lead weights whose
    median nonzero absolute value is one. Derive limb weights from I/II so the
    recording's limb-relation residuals are unchanged; the phase stays shared.
    Constant input stays unchanged.
    """
    values = _signal_array(signal)
    _require_standard_leads(values, lead_consistent)
    fs = _finite_float(fs, "fs")
    frequency_hz = _finite_float(frequency_hz, "frequency_hz")
    relative_amplitude = _finite_float(relative_amplitude, "relative_amplitude")
    rng = _generator(rng)
    if fs <= 0:
        raise ValueError("fs must be strictly positive")
    if not 0 < frequency_hz < fs / 2:
        raise ValueError("frequency_hz must lie strictly between zero and Nyquist")
    if relative_amplitude < 0:
        raise ValueError("relative_amplitude must be nonnegative")
    scale = robust_reference_scale(values)
    if scale == 0 or relative_amplitude == 0:
        return values.copy()
    phase = rng.uniform(0.0, 2.0 * np.pi)
    time = np.arange(len(values), dtype=np.float64) / fs
    weights = np.ones(values.shape[1])
    if lead_consistent:
        weights = _derive_limb_perturbations(rng.normal(size=(1, 12)))[0]
        weights /= np.median(np.abs(weights[weights != 0]))
    with np.errstate(over="ignore", invalid="ignore"):
        baseline = relative_amplitude * scale * np.sin(2.0 * np.pi * frequency_hz * time + phase)
        result = values + baseline[:, None] * weights
    return _finite_result(result)


def shift_signal(signal: ArrayLike, shift_samples: int) -> NDArray[np.float64]:
    """Shift every lead together without wrapping, filling with boundary values.

    Positive shifts delay (move right); negative shifts advance (move left).
    ``abs(shift_samples)`` must be smaller than the recording length. The retained
    interior is unchanged. Samples at the opposite boundary are discarded.
    """
    values = _signal_array(signal)
    if isinstance(shift_samples, (bool, np.bool_)) or not isinstance(shift_samples, Integral):
        raise ValueError("shift_samples must be an integer")
    shift_samples = int(shift_samples)
    if abs(shift_samples) >= len(values):
        raise ValueError("absolute shift must be smaller than the recording length")
    result = np.empty_like(values)
    if shift_samples > 0:
        result[:shift_samples] = values[0]
        result[shift_samples:] = values[:-shift_samples]
    elif shift_samples < 0:
        advance = -shift_samples
        result[:-advance] = values[advance:]
        result[-advance:] = values[-1]
    else:
        result[:] = values
    return result
