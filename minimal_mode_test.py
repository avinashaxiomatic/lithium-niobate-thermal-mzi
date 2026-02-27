"""
Minimal Mode Solver Test - Very Low Credit Usage
Based on Chen et al. paper - using their FDTD approach
"""

import numpy as np
import matplotlib.pyplot as plt
import tidy3d as td
from tidy3d import web

print("="*60)
print("MINIMAL WAVEGUIDE MODE ANALYSIS")
print("Estimated cost: < 0.5 FlexCredits")
print("="*60)

# Parameters from paper
wavelength = 1.55  # μm
freq0 = td.C_0 / wavelength

# Paper's indices (page 2): LN=2.3, SiO2=1.44
n_ln = 2.3  # Using paper's value for consistency
n_sio2 = 1.44

# Create materials
ln_material = td.Medium(permittivity=n_ln**2)
sio2_material = td.Medium(permittivity=n_sio2**2)

# Paper dimensions (page 2)
wg_width = 2.0      # μm
ln_thickness = 0.7   # μm (700 nm)
etch_depth = 0.4     # μm (400 nm)
ridge_height = ln_thickness - etch_depth  # 0.3 μm

# Very small simulation domain for mode solving
domain_size = (0.5, 8, 3)  # x, y, z in μm - minimal x for mode analysis

# Create structures
structures = [
    # SiO2 substrate
    td.Structure(
        geometry=td.Box(
            center=(0, 0, -1.5),
            size=(td.inf, td.inf, 3)
        ),
        medium=sio2_material
    ),
    # LN slab (bottom part after etching)
    td.Structure(
        geometry=td.Box(
            center=(0, 0, ridge_height/2),
            size=(td.inf, td.inf, ridge_height)
        ),
        medium=ln_material
    ),
    # LN ridge (top part - waveguide core)
    td.Structure(
        geometry=td.Box(
            center=(0, 0, ridge_height + etch_depth/2),
            size=(td.inf, wg_width, etch_depth)
        ),
        medium=ln_material
    )
]

# Create a very minimal simulation for mode analysis
grid_spec = td.GridSpec.uniform(dl=wavelength/25)  # Coarser grid to save credits

# Mode monitor
mode_monitor = td.ModeMonitor(
    center=(0, 0, ln_thickness/2),
    size=(0, 6, 2.5),
    freqs=[freq0],
    mode_spec=td.ModeSpec(num_modes=2),  # Just fundamental and first higher order
    name="modes"
)

# Gaussian source for mode excitation
gaussian_source = td.PointDipole(
    center=(-domain_size[0]/2 + 0.1, 0, ln_thickness/2),
    source_time=td.GaussianPulse(freq0=freq0, fwidth=freq0/20),
    polarization='Ez'  # TM mode (Ez dominant for Z-cut LN)
)

# Create minimal simulation
sim = td.Simulation(
    size=domain_size,
    grid_spec=grid_spec,
    structures=structures,
    sources=[gaussian_source],
    monitors=[mode_monitor],
    run_time=2e-12,  # Very short - 2 ps
    boundary_spec=td.BoundarySpec(
        x=td.Boundary.pml(num_layers=5),
        y=td.Boundary.pml(num_layers=5), 
        z=td.Boundary.pml(num_layers=5)
    )
)

print(f"Simulation setup:")
print(f"  Domain: {domain_size[0]} × {domain_size[1]} × {domain_size[2]} μm³")
print(f"  Grid points: ~{sim.num_cells:,}")
print(f"  Runtime: {sim.run_time*1e12:.1f} ps")

# Estimate cost (very rough)
estimated_cost = sim.num_cells / 1e6 * 0.3  # Conservative estimate
print(f"  Estimated cost: {estimated_cost:.3f} FlexCredits")

if estimated_cost > 1.0:
    print("\n⚠️  WARNING: Cost estimate > 1 credit. Consider reducing domain or grid.")
else:
    print(f"\n✅ Cost estimate OK: {estimated_cost:.3f} credits")

# Visualize the structure
fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(12, 5))

# Cross-section view
sim.plot(x=0, ax=ax1)
ax1.set_title("Waveguide Cross-section")
ax1.set_xlabel("Y (μm)")
ax1.set_ylabel("Z (μm)")

# Top view
sim.plot(z=ln_thickness/2, ax=ax2)
ax2.set_title("Top View (at waveguide center)")
ax2.set_xlabel("X (μm)")
ax2.set_ylabel("Y (μm)")

plt.tight_layout()
plt.savefig("minimal_simulation_setup.png", dpi=150, bbox_inches='tight')
plt.show()

print(f"\n{'='*60}")
print("THEORETICAL ANALYSIS (0 credits):")
print(f"{'='*60}")

# Calculate theoretical effective index using simple slab waveguide model
# For a symmetric slab: n_core > n_eff > n_clad
n_core = n_ln
n_clad = n_sio2

# Numerical aperture
NA = np.sqrt(n_core**2 - n_clad**2)
print(f"Numerical Aperture: {NA:.3f}")

# V-parameter (normalized frequency)
V = (2 * np.pi / wavelength) * (wg_width/2) * NA
print(f"V-parameter: {V:.2f}")

# Estimate effective index (simple approximation)
# For fundamental mode: n_eff ≈ n_clad + (n_core - n_clad) * (mode confinement factor)
confinement_factor = 0.7  # Rough estimate for this geometry
n_eff_est = n_clad + (n_core - n_clad) * confinement_factor
print(f"Estimated n_eff: {n_eff_est:.3f}")

# Compare with paper's simulation
print(f"Expected range: {n_clad:.3f} < n_eff < {n_core:.3f}")

print(f"\n{'='*60}")
print("TO RUN THE ACTUAL SIMULATION:")
print(f"{'='*60}")
print("Uncomment the following lines:")
print()
print("# job = web.Job(simulation=sim, task_name='minimal_LN_mode')")
print("# sim_data = job.run(path='mode_data.hdf5')")
print("# mode_data = sim_data['modes']")
print("# n_eff_sim = mode_data.n_eff.values[0]  # First mode")
print("# print(f'Simulated n_eff: {n_eff_sim:.4f}')")

print(f"\n{'='*60}")
print("NEXT STEPS (if this looks good):")
print("1. Run this minimal simulation (~0.3 credits)")
print("2. Validate effective index matches theory") 
print("3. Create thermal distribution analysis")
print("4. Compare tuning efficiency with paper")
print(f"{'='*60}")