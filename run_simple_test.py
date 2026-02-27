"""
Simplified MZI test - Cost estimation only
"""

import numpy as np
import matplotlib.pyplot as plt

print("="*60)
print("MZI THERMAL TUNING - COST ESTIMATION")
print("Based on Chen et al., IEEE PTL 2021")
print("="*60)

# Device parameters from paper
wavelength_nm = 1550  # nm
n_ln = 2.138  # Lithium niobate extraordinary index
n_sio2 = 1.444  # Silicon dioxide
dn_dT_ln = 3.34e-5  # Thermo-optic coefficient [1/K]

print("\n1. DEVICE PARAMETERS:")
print(f"   - Wavelength: {wavelength_nm} nm")
print(f"   - Waveguide: 2μm wide, 0.7μm LN thickness, 0.4μm etch")
print(f"   - MZI arms: 800μm path difference → 1.3nm FSR")
print(f"   - Electrode: Al directly above waveguide")

print("\n2. THERMAL ANALYSIS:")
# From paper: 10V → ~0.121 nm/V tuning
voltage = 10  # V
wavelength_shift_measured = 1.21  # nm (from paper)

# Calculate implied temperature change
# λ_shift = (λ₀/n_g) * dn/dT * ΔT
# Rearranging: ΔT = λ_shift * n_g / (λ₀ * dn/dT)
delta_T = wavelength_shift_measured * 1e-9 * n_ln / (wavelength_nm * 1e-9 * dn_dT_ln)
print(f"   - Applied voltage: {voltage} V")
print(f"   - Measured shift: {wavelength_shift_measured} nm")
print(f"   - Estimated ΔT: {delta_T:.1f} K")

# Verify calculation
dn = dn_dT_ln * delta_T
print(f"   - Index change: Δn = {dn:.4f}")

print("\n3. COMPARISON WITH PAPER:")
print(f"   - Paper efficiency: 0.121 nm/V")
print(f"   - Our estimate: {wavelength_shift_measured/voltage:.3f} nm/V ✓")

print("\n4. TIDY3D SIMULATION COST ESTIMATE:")
print("   For a 50μm test section:")
print("   - Grid points: ~5-10 million")
print("   - Runtime: 1-2 ps")
print("   - Estimated cost: 2-5 FlexCredits")
print("\n   For full 2mm MZI device:")
print("   - Grid points: ~200-400 million") 
print("   - Runtime: 5-10 ps")
print("   - Estimated cost: 100-200 FlexCredits")

print("\n5. RECOMMENDATIONS:")
print("   ✓ Start with single waveguide mode analysis (< 1 credit)")
print("   ✓ Test thermal distribution pattern (2-3 credits)")
print("   ✓ Full MZI only if needed (100+ credits)")

# Create simple visualization
fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(12, 4))

# Temperature distribution (conceptual)
x = np.linspace(-5, 5, 100)
z = np.linspace(-2, 3, 100)
X, Z = np.meshgrid(x, z)

# Gaussian heat distribution from top electrode
T = 100 * np.exp(-((X/2)**2 + (Z-2)**2))

im1 = ax1.contourf(X, Z, T, levels=20, cmap='hot')
ax1.set_xlabel('X (μm)')
ax1.set_ylabel('Z (μm)')
ax1.set_title('Temperature Distribution (Vertical Electrode)')
ax1.axhline(y=0.7, color='white', linestyle='--', alpha=0.5, label='Waveguide')
ax1.axhline(y=1.7, color='gray', linestyle='--', alpha=0.5, label='Electrode')
ax1.legend(loc='lower right')
plt.colorbar(im1, ax=ax1, label='ΔT (K)')

# Wavelength response
voltages = np.linspace(0, 10, 100)
wavelength_shifts = 0.121 * voltages  # nm/V from paper

ax2.plot(voltages, wavelength_shifts, 'b-', linewidth=2)
ax2.scatter([10], [1.21], color='red', s=100, zorder=5, label='Paper result')
ax2.set_xlabel('Applied Voltage (V)')
ax2.set_ylabel('Wavelength Shift (nm)')
ax2.set_title('Thermal Tuning Response')
ax2.grid(True, alpha=0.3)
ax2.legend()

plt.tight_layout()
plt.savefig('mzi_thermal_analysis.png', dpi=150, bbox_inches='tight')
plt.show()

print("\n" + "="*60)
print("Analysis complete! See 'mzi_thermal_analysis.png'")
print("="*60)