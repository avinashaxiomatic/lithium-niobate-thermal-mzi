"""
Replication of Thermally Tuned Mach-Zehnder Interferometer in Z-Cut LN Thin Film
Based on: Chen et al., IEEE Photonics Technology Letters, 2021
"""

import numpy as np
import matplotlib.pyplot as plt
import tidy3d as td
from tidy3d import web

# Physical constants
c0 = 299792458  # Speed of light in m/s
wavelength_nm = 1550  # Operating wavelength in nm
wavelength = wavelength_nm * 1e-9  # Convert to meters
freq0 = c0 / wavelength  # Frequency in Hz

# Device parameters from the paper
# Dimensions in micrometers
waveguide_width = 2.0  # μm
waveguide_height = 0.7  # μm (LN layer thickness)
etch_depth = 0.4  # μm
ridge_height = waveguide_height - etch_depth  # Remaining LN after etching
sio2_thickness = 2.0  # μm (buried oxide)
sio2_cladding = 1.0  # μm (top cladding before metal)
al_thickness = 0.3  # μm (aluminum electrode)

# MMI parameters
mmi_length = 15.5  # μm
mmi_width = 5.0  # μm

# MZI arm parameters
arm_length_short = 1000  # μm (approximate)
arm_length_long = 1800  # μm (800 μm difference for 1.3 nm FSR)
bend_radius = 150  # μm

# Simulation domain
domain_x = 100  # μm (for initial test, we'll use a shorter section)
domain_y = 20  # μm
domain_z = 5  # μm

# Material properties
# Lithium Niobate (Z-cut, TM mode uses extraordinary index)
n_ln_e = 2.138  # Extraordinary refractive index at 1550nm
n_ln_o = 2.211  # Ordinary refractive index at 1550nm
dn_dT_ln = 3.34e-5  # Thermo-optic coefficient [1/K]

# Silicon dioxide
n_sio2 = 1.444  # Refractive index at 1550nm
dn_dT_sio2 = 0.95e-5  # Thermo-optic coefficient [1/K]

# Aluminum (for electrode) - using simplified model
n_al_real = 1.44
n_al_imag = 15.9  # High imaginary part for metal

# Create material definitions
def create_ln_material(temperature_delta=0):
    """Create LN material with temperature-dependent index"""
    n_eff = n_ln_e + dn_dT_ln * temperature_delta
    return td.Medium(permittivity=n_eff**2)

def create_sio2_material(temperature_delta=0):
    """Create SiO2 material with temperature-dependent index"""
    n_eff = n_sio2 + dn_dT_sio2 * temperature_delta
    return td.Medium(permittivity=n_eff**2)

# Aluminum electrode (using PEC approximation for simplicity)
# For actual lossy metal, would need to use dispersive model
aluminum = td.PEC

# Define basic materials at room temperature
ln_material = create_ln_material()
sio2_material = create_sio2_material()

print("Materials defined successfully")
print(f"LN refractive index (extraordinary): {n_ln_e}")
print(f"SiO2 refractive index: {n_sio2}")
print(f"Wavelength: {wavelength_nm} nm")
print(f"Frequency: {freq0/1e12:.2f} THz")