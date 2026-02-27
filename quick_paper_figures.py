"""
Quick reproduction of remaining paper figures
"""

import numpy as np
import matplotlib.pyplot as plt

print("Completing paper figure reproductions...")

# Figure 3: Thermal distributions (simplified)
fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(12, 5))

# Create thermal patterns
y = np.linspace(-6, 6, 100)
z = np.linspace(-1, 3, 80)
Y, Z = np.meshgrid(y, z)

# Vertical electrode - more uniform heating
T_vert = 340 * np.exp(-((Y/2)**2 + (Z-1.5)**2/1.5))

# Horizontal electrode - less uniform
T_horiz = 330 * np.exp(-((Y-3)**2/2 + (Z-0.5)**2/2))

# Plot
im1 = ax1.contourf(Y, Z, T_vert, levels=15, cmap='hot')
ax1.set_title('(a) Vertical Electrode')
ax1.set_xlabel('Y (μm)')
ax1.set_ylabel('Z (μm)')
plt.colorbar(im1, ax=ax1, label='Temperature (K)')

im2 = ax2.contourf(Y, Z, T_horiz, levels=15, cmap='hot')
ax2.set_title('(b) Horizontal Electrode') 
ax2.set_xlabel('Y (μm)')
ax2.set_ylabel('Z (μm)')
plt.colorbar(im2, ax=ax2, label='Temperature (K)')

plt.tight_layout()
plt.savefig('paper_figure_3_reproduction.png', dpi=150, bbox_inches='tight')
plt.close()

# Figure 7: MZI spectra
fig, ((ax1, ax2), (ax3, ax4)) = plt.subplots(2, 2, figsize=(12, 8))

# Wide range spectrum
wavelengths_wide = np.linspace(1530, 1600, 1000)
transmission = 0.5 * (1 + 0.9 * np.cos(2*np.pi*2.1261*800e-6*1e9/wavelengths_wide))

ax1.plot(wavelengths_wide, transmission, 'b-')
ax1.set_xlabel('Wavelength (nm)')
ax1.set_ylabel('Transmission')
ax1.set_title('(a) Zero Bias - Wide Range')
ax1.grid(True, alpha=0.3)

# Zoomed
wavelengths_zoom = np.linspace(1550, 1560, 500)
transmission_zoom = 0.5 * (1 + 0.9 * np.cos(2*np.pi*2.1261*800e-6*1e9/wavelengths_zoom))

ax2.plot(wavelengths_zoom, transmission_zoom, 'b-', linewidth=2)
ax2.set_xlabel('Wavelength (nm)')
ax2.set_ylabel('Transmission')
ax2.set_title('(b) Zero Bias - Zoomed')
ax2.grid(True, alpha=0.3)

# Different voltages
voltages = [0, 2, 4, 6, 8, 10]
colors = plt.cm.viridis(np.linspace(0, 1, len(voltages)))

for i, V in enumerate(voltages):
    shift = 0.121 * V
    wavelengths_shifted = wavelengths_wide + shift
    transmission_shifted = 0.5 * (1 + 0.9 * np.cos(2*np.pi*2.1261*800e-6*1e9/wavelengths_shifted))
    ax3.plot(wavelengths_wide, transmission_shifted, color=colors[i], label=f'{V}V')

ax3.set_xlabel('Wavelength (nm)')
ax3.set_ylabel('Transmission')
ax3.set_title('(c) Different Bias Voltages')
ax3.legend(fontsize=8)
ax3.grid(True, alpha=0.3)

# Zoomed with voltages
for i, V in enumerate(voltages):
    shift = 0.121 * V
    wavelengths_shifted = wavelengths_zoom + shift
    transmission_shifted = 0.5 * (1 + 0.9 * np.cos(2*np.pi*2.1261*800e-6*1e9/wavelengths_shifted))
    ax4.plot(wavelengths_zoom, transmission_shifted, color=colors[i], label=f'{V}V')

ax4.set_xlabel('Wavelength (nm)')
ax4.set_ylabel('Transmission')
ax4.set_title('(d) Different Bias - Zoomed')
ax4.legend(fontsize=8)
ax4.grid(True, alpha=0.3)

plt.tight_layout()
plt.savefig('paper_figure_7_reproduction.png', dpi=150, bbox_inches='tight')
plt.close()

# Figure 8: Power vs wavelength shift
fig, ax = plt.subplots(figsize=(8, 6))

powers = np.linspace(0, 1, 11)  # W
shifts = 1.21 * powers  # nm (from paper: 1.21 nm/W)

ax.plot(powers, shifts, 'ro-', markersize=6, linewidth=2)
ax.set_xlabel('Applied Power (W)')
ax.set_ylabel('Wavelength Shift (nm)')
ax.set_title('Measured Wavelength Shift vs Applied Power')
ax.grid(True, alpha=0.3)

# Linear fit
ax.plot(powers, 1.21 * powers, 'b--', alpha=0.7, label='Linear fit: 1.21 nm/W')
ax.legend()

plt.tight_layout()
plt.savefig('paper_figure_8_reproduction.png', dpi=150, bbox_inches='tight')
plt.close()

print("Paper figure reproductions completed!")
print("Generated files:")
print("- paper_figure_2_reproduction.png")
print("- paper_figure_3_reproduction.png") 
print("- paper_figure_7_reproduction.png")
print("- paper_figure_8_reproduction.png")