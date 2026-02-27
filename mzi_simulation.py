"""
MZI Simulation Setup and Cost Estimation
"""

import numpy as np
import matplotlib.pyplot as plt
import tidy3d as td
from tidy3d import web
import json

# Import device parameters
from mzi_thermal_tuning import *

def create_waveguide_geometry():
    """Create a simple waveguide section for testing"""
    
    # Create structures list
    structures = []
    
    # Substrate (SiO2)
    substrate = td.Structure(
        geometry=td.Box(
            center=(0, 0, -sio2_thickness/2),
            size=(td.inf, td.inf, sio2_thickness)
        ),
        medium=sio2_material
    )
    structures.append(substrate)
    
    # LN ridge waveguide (simplified straight section)
    # Bottom part of ridge (unetched region)
    ln_slab = td.Structure(
        geometry=td.Box(
            center=(0, 0, ridge_height/2),
            size=(td.inf, td.inf, ridge_height)
        ),
        medium=ln_material
    )
    structures.append(ln_slab)
    
    # Top part of ridge (waveguide core)
    waveguide_core = td.Structure(
        geometry=td.Box(
            center=(0, 0, ridge_height + etch_depth/2),
            size=(waveguide_width, td.inf, etch_depth)
        ),
        medium=ln_material
    )
    structures.append(waveguide_core)
    
    # Top SiO2 cladding
    top_cladding = td.Structure(
        geometry=td.Box(
            center=(0, 0, waveguide_height + sio2_cladding/2),
            size=(td.inf, td.inf, sio2_cladding)
        ),
        medium=sio2_material
    )
    structures.append(top_cladding)
    
    # Aluminum electrode (directly above waveguide)
    electrode = td.Structure(
        geometry=td.Box(
            center=(0, 0, waveguide_height + sio2_cladding + al_thickness/2),
            size=(waveguide_width + 1, 20, al_thickness)  # Slightly wider than waveguide
        ),
        medium=aluminum
    )
    structures.append(electrode)
    
    return structures

def create_mode_source(sim_size_x):
    """Create TM-polarized mode source"""
    
    # Mode source for TM polarization (E-field in z-direction for Z-cut LN)
    source = td.ModeSource(
        center=(-sim_size_x/2 + 1, 0, waveguide_height/2),
        size=(0, 4*waveguide_width, 3*waveguide_height),
        direction='+',
        mode_spec=td.ModeSpec(
            num_modes=1,
            target_neff=n_ln_e  # Target the fundamental TM mode
        ),
        source_time=td.GaussianPulse(
            freq0=freq0,
            fwidth=freq0/10
        )
    )
    return source

def create_monitors(sim_size_x, sim_size_y, sim_size_z):
    """Create field monitors"""
    monitors = []
    
    # Field monitor in xy plane (top view)
    field_monitor_xy = td.FieldMonitor(
        center=(0, 0, waveguide_height/2),
        size=(sim_size_x - 2, sim_size_y - 2, 0),
        freqs=[freq0],
        name="field_xy"
    )
    monitors.append(field_monitor_xy)
    
    # Field monitor in xz plane (cross-section)
    field_monitor_xz = td.FieldMonitor(
        center=(0, 0, waveguide_height/2),
        size=(sim_size_x - 2, 0, sim_size_z - 1),
        freqs=[freq0],
        name="field_xz"
    )
    monitors.append(field_monitor_xz)
    
    # Mode monitor at output
    mode_monitor = td.ModeMonitor(
        center=(sim_size_x/2 - 1, 0, waveguide_height/2),
        size=(0, 4*waveguide_width, 3*waveguide_height),
        freqs=np.linspace(freq0*0.95, freq0*1.05, 51),
        mode_spec=td.ModeSpec(num_modes=2),
        name="mode_out"
    )
    monitors.append(mode_monitor)
    
    return monitors

def estimate_simulation_cost():
    """Create simulation and estimate computational cost"""
    
    # Create simulation with smaller domain for cost estimation
    test_domain_x = 50  # μm (shorter for testing)
    
    # Grid specification
    grid_spec = td.GridSpec.auto(
        min_steps_per_wvl=20,
        wavelength=wavelength
    )
    
    # Create structures
    structures = create_waveguide_geometry()
    
    # Create source and monitors
    source = create_mode_source(test_domain_x)
    monitors = create_monitors(test_domain_x, domain_y, domain_z)
    
    # Boundary conditions (PML on all sides)
    boundary_spec = td.BoundarySpec(
        x=td.Boundary.pml(),
        y=td.Boundary.pml(),
        z=td.Boundary.pml()
    )
    
    # Create simulation
    sim = td.Simulation(
        size=(test_domain_x, domain_y, domain_z),
        grid_spec=grid_spec,
        structures=structures,
        sources=[source],
        monitors=monitors,
        run_time=1e-12,  # 1 ps
        boundary_spec=boundary_spec,
        medium=td.Medium(permittivity=1)  # Air background
    )
    
    # Estimate cost
    print("\n=== Simulation Setup ===")
    print(f"Domain size: {test_domain_x} x {domain_y} x {domain_z} μm³")
    print(f"Wavelength: {wavelength_nm} nm")
    print(f"Runtime: 1 ps")
    
    # Get grid information
    print(f"\nEstimated grid points: ~{sim.num_cells:,}")
    
    # Estimate FlexCredit cost (this is approximate)
    # Typically ~0.1-1 FlexCredit per million grid points for 1ps
    estimated_cost = sim.num_cells / 1e6 * 0.5  # Conservative estimate
    
    print(f"\n=== COST ESTIMATE ===")
    print(f"Estimated FlexCredits: {estimated_cost:.2f}")
    print(f"(This is a conservative estimate for a {test_domain_x} μm test section)")
    print(f"\nFull MZI device (~2000 μm) would cost approximately: {estimated_cost * 40:.1f} FlexCredits")
    
    # Save simulation for inspection
    sim.plot(z=waveguide_height/2)
    plt.title("MZI Waveguide Cross-section (XY plane)")
    plt.savefig("mzi_geometry_xy.png", dpi=150, bbox_inches='tight')
    plt.show()
    
    sim.plot(y=0)
    plt.title("MZI Waveguide Cross-section (XZ plane)")
    plt.savefig("mzi_geometry_xz.png", dpi=150, bbox_inches='tight')
    plt.show()
    
    return sim, estimated_cost

def run_thermal_test():
    """Simple thermal distribution test"""
    
    print("\n=== Thermal Distribution Analysis ===")
    
    # Create temperature profile (simplified)
    # Assume 10V applied -> ~100K temperature rise (from paper)
    delta_T = 100  # Kelvin
    
    # Calculate index change
    dn_ln = dn_dT_ln * delta_T
    dn_sio2 = dn_dT_sio2 * delta_T
    
    print(f"Temperature rise: {delta_T} K")
    print(f"LN index change: {dn_ln:.4f}")
    print(f"SiO2 index change: {dn_sio2:.5f}")
    
    # Calculate phase shift for 1mm propagation
    L = 1000e-6  # 1mm in meters
    delta_phi = 2 * np.pi * dn_ln * L / wavelength
    print(f"\nPhase shift over 1mm: {delta_phi:.2f} radians")
    print(f"                      {np.degrees(delta_phi):.1f} degrees")
    
    # Estimate wavelength shift for MZI
    FSR = 1.3e-9  # 1.3 nm from paper
    path_diff = 800e-6  # 800 μm path difference
    
    # Wavelength shift per unit phase change
    wavelength_shift = FSR * delta_phi / (2 * np.pi)
    print(f"\nEstimated wavelength shift: {wavelength_shift*1e9:.3f} nm")
    
    # Compare with paper (1.21 nm for 10V)
    voltage_efficiency = wavelength_shift * 1e9 / 10  # nm/V
    print(f"Voltage efficiency: {voltage_efficiency:.3f} nm/V")
    print(f"Paper reports: 0.121 nm/V")

if __name__ == "__main__":
    print("="*50)
    print("MZI Thermal Tuning Simulation")
    print("="*50)
    
    # Run thermal analysis
    run_thermal_test()
    
    # Estimate simulation cost
    print("\n" + "="*50)
    print("Creating simulation for cost estimation...")
    print("="*50)
    
    sim, cost = estimate_simulation_cost()
    
    print("\n" + "="*50)
    print("RECOMMENDATION:")
    if cost < 5:
        print(f"✓ Low cost ({cost:.2f} FlexCredits) - safe to run")
        print("  This is just a small test section.")
    else:
        print(f"⚠ Moderate cost ({cost:.2f} FlexCredits)")
        print("  Consider optimizing grid or reducing domain size")
    
    print("\nTo run the actual simulation, use:")
    print("  python run_mzi_simulation.py")
    print("="*50)