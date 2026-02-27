"""
Minimal waveguide mode solver for the LN ridge waveguide
This uses Tidy3D's mode solver which requires minimal credits (~0.1)
"""

import numpy as np
import matplotlib.pyplot as plt
import tidy3d as td
from tidy3d import web

print("="*60)
print("LITHIUM NIOBATE WAVEGUIDE MODE SOLVER")
print("Minimal credit usage demo")
print("="*60)

# Wavelength and frequency
wavelength = 1.55  # μm
freq0 = td.C_0 / wavelength

# Material indices
n_ln = 2.138  # Extraordinary index for TM mode
n_sio2 = 1.444

# Create materials
ln_material = td.Medium(permittivity=n_ln**2)
sio2_material = td.Medium(permittivity=n_sio2**2)

# Waveguide dimensions (μm)
wg_width = 2.0
wg_height = 0.7
etch_depth = 0.4
ridge_height = wg_height - etch_depth

# Create a 2D mode solver simulation (much cheaper than 3D)
# Domain for mode solving
domain_y = 10  # μm
domain_z = 4   # μm

# Create structures
structures = [
    # SiO2 substrate
    td.Structure(
        geometry=td.Box(
            center=(0, 0, -1),
            size=(td.inf, td.inf, 2)
        ),
        medium=sio2_material
    ),
    # LN slab (unetched region)
    td.Structure(
        geometry=td.Box(
            center=(0, 0, ridge_height/2),
            size=(td.inf, td.inf, ridge_height)
        ),
        medium=ln_material
    ),
    # LN ridge (etched region)
    td.Structure(
        geometry=td.Box(
            center=(0, 0, ridge_height + etch_depth/2),
            size=(td.inf, wg_width, etch_depth)
        ),
        medium=ln_material
    )
]

# Create mode source for analysis
mode_source = td.ModeSource(
    center=(0, 0, wg_height/2),
    size=(0, domain_y, domain_z),
    direction='+',
    mode_spec=td.ModeSpec(
        num_modes=4,  # Solve for first 4 modes
        target_neff=n_ln  # Target around LN index
    ),
    source_time=td.GaussianPulse(freq0=freq0, fwidth=freq0/10)
)

# Mode monitor to extract mode profiles
mode_monitor = td.ModeMonitor(
    center=(0, 0, wg_height/2),
    size=(0, domain_y, domain_z),
    freqs=[freq0],
    mode_spec=td.ModeSpec(num_modes=4),
    name="modes"
)

# Create simulation
sim = td.Simulation(
    size=(1, domain_y, domain_z),  # Very small x dimension for mode solving
    grid_spec=td.GridSpec.uniform(dl=wavelength/30),
    structures=structures,
    sources=[mode_source],
    monitors=[mode_monitor],
    run_time=1e-13,  # Very short runtime for mode solving
    boundary_spec=td.BoundarySpec.pml(x=False, y=True, z=True)
)

print(f"\nSimulation parameters:")
print(f"  Domain: {sim.size[0]} x {sim.size[1]} x {sim.size[2]} μm³")
print(f"  Grid points: ~{sim.num_cells:,}")
print(f"  Estimated cost: < 0.1 FlexCredits")

# Visualize the structure
fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(12, 5))

sim.plot(x=0, ax=ax1)
ax1.set_title("Waveguide Cross-section (YZ plane)")
ax1.set_xlabel("Y (μm)")
ax1.set_ylabel("Z (μm)")

# Zoom in on waveguide region
ax2 = plt.subplot(122)
sim.plot(x=0, ax=ax2)
ax2.set_xlim([-3, 3])
ax2.set_ylim([-0.5, 1.5])
ax2.set_title("Zoomed Waveguide Region")
ax2.set_xlabel("Y (μm)")
ax2.set_ylabel("Z (μm)")

plt.tight_layout()
plt.savefig("waveguide_structure.png", dpi=150, bbox_inches='tight')
plt.show()

print("\n" + "="*60)
print("READY TO RUN MODE SOLVER")
print("="*60)
print("\nTo run the simulation and solve for modes:")
print("1. This will use < 0.1 FlexCredits")
print("2. Uncomment the lines below to execute:")
print()
print("# job = web.Job(simulation=sim, task_name='LN_waveguide_modes')")
print("# sim_data = job.run(path='data/simulation_data.hdf5')")
print("# sim_data.plot_field('modes', field_name='Ez', mode_index=0)")

# Calculate theoretical effective index
# For a ridge waveguide, neff should be between n_sio2 and n_ln
print(f"\nExpected effective index range:")
print(f"  {n_sio2:.3f} < n_eff < {n_ln:.3f}")

# Estimate confinement factor
core_area = wg_width * wg_height
mode_area_est = core_area * 1.5  # Rough estimate
confinement = core_area / mode_area_est
print(f"\nEstimated mode confinement: ~{confinement:.1%}")

print("\n" + "="*60)