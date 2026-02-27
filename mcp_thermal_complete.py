# LN Thermal MZI Simulation - MCP Ready
# Our main thermal validation problem

from collections import OrderedDict
from shapely.geometry import Polygon
from femwell.mesh import mesh_from_OrderedDict
from femwell.thermal import solve_thermal
from skfem import Basis, ElementTriP0
from skfem.io import from_meshio
import numpy as np
import matplotlib.pyplot as plt

print("="*80)
print("LN THERMAL MZI - MCP CLOUD EXECUTION")
print("="*80)

print("Starting LN Thermal MZI simulation...")

# LN MZI geometry (based on Chen et al. paper)
polygons = OrderedDict()

# Substrate (SiO2)
polygons["substrate"] = Polygon([
    (-6.0, -2.0),  # 12μm × 2μm substrate
    (-6.0, 0.0),
    (6.0, 0.0),
    (6.0, -2.0),
])

# LN waveguide core 
polygons["ln_core"] = Polygon([
    (-1.0, 0.0),   # 2μm × 0.7μm LN waveguide
    (-1.0, 0.7),
    (1.0, 0.7),
    (1.0, 0.0),
])

# SiO2 isolation layer
polygons["isolation"] = Polygon([
    (-6.0, 0.7),   # Isolation above LN
    (-6.0, 1.7),   # 1μm thick
    (6.0, 1.7),
    (6.0, 0.7),
])

# Al electrode (heat source)
polygons["electrode"] = Polygon([
    (-1.5, 1.7),   # 3μm × 0.3μm electrode
    (-1.5, 2.0),
    (1.5, 2.0),
    (1.5, 1.7),
])

print("LN MZI geometry created:")
for name, poly in polygons.items():
    print(f"  {name}: {poly.area:.2f} μm²")

# Mesh with fine resolution in critical regions
resolutions = {
    "ln_core": {"resolution": 0.1, "distance": 1},      # Fine mesh in waveguide
    "electrode": {"resolution": 0.15, "distance": 1},   # Fine mesh in heater
    "isolation": {"resolution": 0.2, "distance": 1},    # Medium mesh
    "substrate": {"resolution": 0.4, "distance": 1},    # Coarse mesh
}

print("Creating LN MZI mesh...")
mesh = from_meshio(mesh_from_OrderedDict(polygons, resolutions, default_resolution_max=0.5))
print(f"LN MZI mesh: {len(mesh.t[0])} elements")

# Create basis
basis0 = Basis(mesh, ElementTriP0(), intorder=4)
print(f"Basis: {basis0.N} DOFs")

# Set LN thermal conductivities
thermal_conductivity = basis0.zeros()

ln_materials = {
    "substrate": 1.3,    # SiO2 substrate
    "ln_core": 5.6,      # LN waveguide  
    "isolation": 1.3,    # SiO2 isolation
    "electrode": 205,    # Al electrode
}

print("Setting LN material properties...")
for domain, k_value in ln_materials.items():
    dofs = basis0.get_dofs(elements=domain)
    thermal_conductivity[dofs] = k_value
    print(f"  {domain}: {k_value} W/(m·K) ({len(dofs)} elements)")

# Convert units for FEMwell
thermal_conductivity *= 1e-12

# Electrical parameters from Chen et al. paper
voltage = 10.0  # V (from paper)
device_resistance = 100.0  # Ω (from paper)
current = voltage / device_resistance
power = voltage * current

# Current density in electrode
electrode_area = 3e-6 * 0.3e-6  # 3μm × 0.3μm
current_density = current / electrode_area

print(f"LN electrical parameters:")
print(f"  Voltage: {voltage} V")
print(f"  Resistance: {device_resistance} Ω") 
print(f"  Power: {power} W")
print(f"  Current density: {current_density:.2e} A/m²")

# Solve LN thermal equation
print("Solving LN thermal equation...")

try:
    basis, temperature = solve_thermal(
        basis0,
        thermal_conductivity,
        specific_conductivity={"electrode": 3.5e7},  # Al electrical conductivity
        current_densities={"electrode": current_density},
        fixed_boundaries={},  # Try without boundaries first
    )
    
    print("✅ LN THERMAL SOLVE SUCCESS!")
    
    # Extract LN core temperature
    ln_dofs = basis0.get_dofs(elements="ln_core")
    ln_temps = temperature[ln_dofs]
    avg_ln_temp = np.mean(ln_temps)
    
    print(f"LN thermal results:")
    print(f"  Max temperature: {np.max(temperature):.1f} K")
    print(f"  LN core temperature: {avg_ln_temp:.1f} K")
    
    # Calculate thermal-optical coupling
    dn_dT = 3.34e-5  # LN thermo-optic coefficient
    ln_temp_rise = avg_ln_temp - 300  # Assume 300K baseline
    delta_n_eff = dn_dT * ln_temp_rise
    
    # Wavelength shift
    wavelength = 1550e-9  # m
    n_eff = 2.1261       # From our Tidy3D simulation
    path_diff = 800e-6   # m
    
    delta_lambda = wavelength * delta_n_eff / n_eff
    
    print(f"Thermal-optical coupling:")
    print(f"  Temperature rise: {ln_temp_rise:.1f} K")
    print(f"  Index change: {delta_n_eff:.2e}")
    print(f"  Wavelength shift: {delta_lambda*1e9:.3f} nm")
    print(f"  Paper target: 1.21 nm")
    
    # TRUE FEM thermal factor
    fem_thermal_factor = delta_lambda / (1.21e-9)
    print(f"  TRUE FEM thermal factor: {fem_thermal_factor:.3f}")
    
    print(f"\n🎯 ANSWER TO THERMAL SCALING QUESTION:")
    print(f"Your question: Is 0.27 arbitrary or physics?")
    print(f"FEM answer: TRUE factor = {fem_thermal_factor:.3f}")
    
    # Compare with previous estimates
    print(f"\nComparison with estimates:")
    print(f"  Analytical: 0.106")
    print(f"  Literature: 0.886") 
    print(f"  Calibrated: 0.27")
    print(f"  TRUE FEM: {fem_thermal_factor:.3f}")
    
    # Determine closest estimate
    estimates = {"Analytical": 0.106, "Literature": 0.886, "Calibrated": 0.27}
    errors = {name: abs(factor - fem_thermal_factor) for name, factor in estimates.items()}
    closest = min(errors.keys(), key=lambda k: errors[k])
    
    print(f"\nClosest estimate: {closest} (error: {errors[closest]/fem_thermal_factor*100:.0f}%)")
    
    if closest == "Calibrated":
        print("✅ Your calibration was excellent physics!")
    elif closest == "Literature":
        print("✅ Literature estimate was most accurate!")
    else:
        print("🔬 Analytical approach was closest!")
    
    fem_factor = fem_thermal_factor
    temp_rise = ln_temp_rise

except Exception as ln_error:
    print(f"❌ LN thermal solve failed: {ln_error}")
    fem_factor = 0
    temp_rise = 0

print(f"\n🏆 FINAL MCP FEMWELL RESULTS:")
print("="*80)
print(f"FEM thermal factor: {fem_factor:.3f}")
print(f"Temperature rise: {temp_rise:.1f} K")

if fem_factor > 0:
    print("🎉 MCP FEMWELL SUCCESS - TRUE THERMAL PHYSICS!")
else:
    print("🔧 MCP FEMwell needs more investigation")

print("="*80)