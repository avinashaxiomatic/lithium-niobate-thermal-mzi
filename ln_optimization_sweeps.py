"""
LN MZI Design Optimization Sweeps
==================================
Explores design improvements to the Chen et al. LN MZI thermo-optic phase shifter
by sweeping three key geometry parameters:

1. Isolation thickness (heater-to-waveguide distance)
2. Electrode width (heat spread pattern)
3. Air trench width (lateral thermal isolation)

All sweeps run at V=10V with R=100Ω for speed.
Imports core solver and material functions from ln_mzi_simulation.py.
"""

import sys
import warnings
import time

import numpy as np
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from collections import OrderedDict

from shapely.geometry import LineString, Polygon

from skfem import Basis, ElementTriP0, ElementTriP1
from skfem.io import from_meshio

sys.path.insert(0, "/home/kumar/femwell/repo")
from femwell.mesh import mesh_from_OrderedDict
from femwell.maxwell.waveguide import compute_modes

# Import from existing simulation
sys.path.insert(0, "/home/kumar/femwell")
from ln_mzi_simulation import (
    T_AMB,
    W_SIM,
    H_LN,
    ETCH_DEPTH,
    H_SLAB,
    W_WG,
    K_SIO2,
    K_AL,
    K_LN_X,
    K_LN_Y,
    N_LN,
    N_SIO2,
    DN_DT_LN,
    DN_DT_SIO2,
    R_TOTAL,
    SIGMA_AL,
    WAVELENGTH,
    DELTA_L,
    N_GROUP,
    solve_thermal_2p5d,
    compute_alpha_eff,
)

warnings.filterwarnings("ignore", category=FutureWarning)
warnings.filterwarnings("ignore", message=".*SparseEfficiencyWarning.*")

# Air thermal/optical properties
K_AIR = 0.026  # W/m/K
N_AIR = 1.0


# =============================================================================
# Parameterized Geometry Builders
# =============================================================================
def build_vertical_geometry_param(h_isolation=1.0, w_al=3.0, h_al=0.3, h_substrate=2.0):
    """Build vertical electrode geometry with parameterized dimensions.

    Args:
        h_isolation: SiO2 isolation thickness between LN top and electrode (um).
        w_al: Electrode width (um).
        h_al: Electrode thickness (um).
        h_substrate: SiO2 BOX thickness (um).

    Returns:
        OrderedDict of polygons for meshing.
    """
    y_base = 0.0
    y_box_top = h_substrate
    y_slab_top = y_box_top + H_SLAB
    y_ln_top = y_box_top + H_LN
    y_iso_top = y_ln_top + h_isolation
    y_al_top = y_iso_top + h_al
    y_clad_top = y_al_top + 1.0

    polygons = OrderedDict(
        bottom=LineString([(-W_SIM / 2, y_base), (W_SIM / 2, y_base)]),
        top=LineString([(-W_SIM / 2, y_clad_top), (W_SIM / 2, y_clad_top)]),
        box=Polygon([
            (-W_SIM / 2, y_base), (-W_SIM / 2, y_box_top),
            (W_SIM / 2, y_box_top), (W_SIM / 2, y_base),
        ]),
        slab=Polygon([
            (-W_SIM / 2, y_box_top), (-W_SIM / 2, y_slab_top),
            (W_SIM / 2, y_slab_top), (W_SIM / 2, y_box_top),
        ]),
        core=Polygon([
            (-W_WG / 2, y_slab_top), (-W_WG / 2, y_ln_top),
            (W_WG / 2, y_ln_top), (W_WG / 2, y_slab_top),
        ]),
        isolation=Polygon([
            (-W_SIM / 2, y_ln_top), (-W_SIM / 2, y_iso_top),
            (W_SIM / 2, y_iso_top), (W_SIM / 2, y_ln_top),
        ]),
        heater=Polygon([
            (-w_al / 2, y_iso_top), (-w_al / 2, y_al_top),
            (w_al / 2, y_al_top), (w_al / 2, y_iso_top),
        ]),
        clad=Polygon([
            (-W_SIM / 2, y_iso_top), (-W_SIM / 2, y_clad_top),
            (W_SIM / 2, y_clad_top), (W_SIM / 2, y_iso_top),
        ]),
    )
    return polygons


def build_trench_geometry(w_trench, d_trench=1.5, h_isolation=1.0, w_al=3.0,
                          h_al=0.3, h_substrate=2.0):
    """Build geometry with symmetric air trenches flanking the waveguide.

    Trenches are etched through the isolation layer into the BOX oxide,
    providing lateral thermal isolation around the waveguide core.

    Args:
        w_trench: Trench width (um). 0 = no trench (baseline).
        d_trench: Trench depth from LN top surface downward (um).
        h_isolation: SiO2 isolation thickness (um).
        w_al: Electrode width (um).
        h_al: Electrode thickness (um).
        h_substrate: SiO2 BOX thickness (um).

    Returns:
        OrderedDict of polygons for meshing. Includes 'trench_left' and
        'trench_right' domains when w_trench > 0.
    """
    y_base = 0.0
    y_box_top = h_substrate
    y_slab_top = y_box_top + H_SLAB
    y_ln_top = y_box_top + H_LN
    y_iso_top = y_ln_top + h_isolation
    y_al_top = y_iso_top + h_al
    y_clad_top = y_al_top + 1.0

    # Trench vertical extent: from y_iso_top down by d_trench
    # but not below y_base
    y_trench_top = y_iso_top
    y_trench_bot = max(y_iso_top - d_trench, y_base + 0.1)

    # Trench horizontal placement: just outside the waveguide ridge
    # Leave a small gap (0.2 um) between core edge and trench
    trench_gap = 0.5
    x_trench_inner_left = -(W_WG / 2 + trench_gap + w_trench)
    x_trench_outer_left = -(W_WG / 2 + trench_gap)
    x_trench_inner_right = W_WG / 2 + trench_gap
    x_trench_outer_right = W_WG / 2 + trench_gap + w_trench

    polygons = OrderedDict()
    polygons["bottom"] = LineString([(-W_SIM / 2, y_base), (W_SIM / 2, y_base)])
    polygons["top"] = LineString([(-W_SIM / 2, y_clad_top), (W_SIM / 2, y_clad_top)])
    polygons["box"] = Polygon([
        (-W_SIM / 2, y_base), (-W_SIM / 2, y_box_top),
        (W_SIM / 2, y_box_top), (W_SIM / 2, y_base),
    ])
    polygons["slab"] = Polygon([
        (-W_SIM / 2, y_box_top), (-W_SIM / 2, y_slab_top),
        (W_SIM / 2, y_slab_top), (W_SIM / 2, y_box_top),
    ])
    polygons["core"] = Polygon([
        (-W_WG / 2, y_slab_top), (-W_WG / 2, y_ln_top),
        (W_WG / 2, y_ln_top), (W_WG / 2, y_slab_top),
    ])

    # Insert trench polygons BEFORE isolation so mesher cuts them out
    if w_trench > 0:
        polygons["trench_left"] = Polygon([
            (x_trench_inner_left, y_trench_bot),
            (x_trench_inner_left, y_trench_top),
            (x_trench_outer_left, y_trench_top),
            (x_trench_outer_left, y_trench_bot),
        ])
        polygons["trench_right"] = Polygon([
            (x_trench_inner_right, y_trench_bot),
            (x_trench_inner_right, y_trench_top),
            (x_trench_outer_right, y_trench_top),
            (x_trench_outer_right, y_trench_bot),
        ])

    polygons["isolation"] = Polygon([
        (-W_SIM / 2, y_ln_top), (-W_SIM / 2, y_iso_top),
        (W_SIM / 2, y_iso_top), (W_SIM / 2, y_ln_top),
    ])
    polygons["heater"] = Polygon([
        (-w_al / 2, y_iso_top), (-w_al / 2, y_al_top),
        (w_al / 2, y_al_top), (w_al / 2, y_iso_top),
    ])
    polygons["clad"] = Polygon([
        (-W_SIM / 2, y_iso_top), (-W_SIM / 2, y_clad_top),
        (W_SIM / 2, y_clad_top), (W_SIM / 2, y_iso_top),
    ])
    return polygons


def build_suspended_geometry(w_undercut, d_undercut=None, h_isolation=0.5,
                              w_al=2.0, h_al=0.3, h_substrate=2.0):
    """Build geometry with air-filled undercut cavity in BOX beneath waveguide.

    Models an HF wet etch through side access trenches that removes SiO2
    laterally under the waveguide, creating a suspended structure.

    Args:
        w_undercut: Width of air cavity in BOX (um), centered under waveguide.
                    0 = no undercut (baseline).
        d_undercut: Depth of undercut from BOX top downward (um).
                    Default (None) = full BOX depth = h_substrate.
        h_isolation: SiO2 isolation thickness (um).
        w_al: Electrode width (um).
        h_al: Electrode thickness (um).
        h_substrate: SiO2 BOX thickness (um).

    Returns:
        OrderedDict of polygons for meshing.
    """
    if d_undercut is None:
        d_undercut = h_substrate

    y_base = 0.0
    y_box_top = h_substrate
    y_slab_top = y_box_top + H_SLAB
    y_ln_top = y_box_top + H_LN
    y_iso_top = y_ln_top + h_isolation
    y_al_top = y_iso_top + h_al
    y_clad_top = y_al_top + 1.0

    # Undercut vertical extent: from y_box_top downward by d_undercut
    y_undercut_top = y_box_top
    y_undercut_bot = max(y_box_top - d_undercut, y_base + 0.05)

    # Access trench placement: 0.5 um wide, at waveguide edge + 0.5 um gap
    trench_w = 0.5
    trench_gap = 0.5
    x_trench_l_inner = -(W_WG / 2 + trench_gap + trench_w)
    x_trench_l_outer = -(W_WG / 2 + trench_gap)
    x_trench_r_inner = W_WG / 2 + trench_gap
    x_trench_r_outer = W_WG / 2 + trench_gap + trench_w

    polygons = OrderedDict()
    polygons["bottom"] = LineString([(-W_SIM / 2, y_base), (W_SIM / 2, y_base)])
    polygons["top"] = LineString([(-W_SIM / 2, y_clad_top), (W_SIM / 2, y_clad_top)])

    # Undercut (air cavity) placed BEFORE box so mesher carves it out
    if w_undercut > 0:
        polygons["undercut"] = Polygon([
            (-w_undercut / 2, y_undercut_bot),
            (-w_undercut / 2, y_undercut_top),
            (w_undercut / 2, y_undercut_top),
            (w_undercut / 2, y_undercut_bot),
        ])

    polygons["box"] = Polygon([
        (-W_SIM / 2, y_base), (-W_SIM / 2, y_box_top),
        (W_SIM / 2, y_box_top), (W_SIM / 2, y_base),
    ])
    polygons["slab"] = Polygon([
        (-W_SIM / 2, y_box_top), (-W_SIM / 2, y_slab_top),
        (W_SIM / 2, y_slab_top), (W_SIM / 2, y_box_top),
    ])
    polygons["core"] = Polygon([
        (-W_WG / 2, y_slab_top), (-W_WG / 2, y_ln_top),
        (W_WG / 2, y_ln_top), (W_WG / 2, y_slab_top),
    ])

    # Access trenches placed BEFORE isolation so mesher carves them out
    if w_undercut > 0:
        polygons["trench_left"] = Polygon([
            (x_trench_l_inner, y_undercut_top),
            (x_trench_l_inner, y_iso_top),
            (x_trench_l_outer, y_iso_top),
            (x_trench_l_outer, y_undercut_top),
        ])
        polygons["trench_right"] = Polygon([
            (x_trench_r_inner, y_undercut_top),
            (x_trench_r_inner, y_iso_top),
            (x_trench_r_outer, y_iso_top),
            (x_trench_r_outer, y_undercut_top),
        ])

    polygons["isolation"] = Polygon([
        (-W_SIM / 2, y_ln_top), (-W_SIM / 2, y_iso_top),
        (W_SIM / 2, y_iso_top), (W_SIM / 2, y_ln_top),
    ])
    polygons["heater"] = Polygon([
        (-w_al / 2, y_iso_top), (-w_al / 2, y_al_top),
        (w_al / 2, y_al_top), (w_al / 2, y_iso_top),
    ])
    polygons["clad"] = Polygon([
        (-W_SIM / 2, y_iso_top), (-W_SIM / 2, y_clad_top),
        (W_SIM / 2, y_clad_top), (W_SIM / 2, y_iso_top),
    ])
    return polygons


def build_mesh_sweep(polygons, label=""):
    """Create mesh from polygon dict with resolution settings."""
    resolutions = dict(
        core={"resolution": 0.02, "distance": 0.5},
        slab={"resolution": 0.05, "distance": 0.5},
        heater={"resolution": 0.03, "distance": 0.5},
        isolation={"resolution": 0.05, "distance": 0.5},
        box={"resolution": 0.3, "distance": 1.0},
        clad={"resolution": 0.3, "distance": 1.0},
    )
    # Add trench resolutions if present
    if "trench_left" in polygons:
        resolutions["trench_left"] = {"resolution": 0.05, "distance": 0.3}
        resolutions["trench_right"] = {"resolution": 0.05, "distance": 0.3}
    # Add undercut resolution if present
    if "undercut" in polygons:
        resolutions["undercut"] = {"resolution": 0.1, "distance": 0.5}

    mesh = from_meshio(
        mesh_from_OrderedDict(polygons, resolutions, default_resolution_max=0.4)
    )
    if label:
        print(f"    {label}: {mesh.nelements} elements")
    return mesh


# =============================================================================
# Extended Material Property Functions
# =============================================================================
def setup_thermal_conductivity_ext(basis0, extra_domains=None):
    """Set up anisotropic thermal conductivity with optional extra domains.

    Args:
        basis0: P0 basis.
        extra_domains: dict mapping domain name -> (kx, ky) in W/m/K.
                       e.g. {"trench_left": (K_AIR, K_AIR)}

    Returns:
        kxx, kyy arrays in W/um/K.
    """
    kxx = basis0.zeros()
    kyy = basis0.zeros()

    domain_k = {
        "core": (K_LN_X, K_LN_Y),
        "slab": (K_LN_X, K_LN_Y),
        "box": (K_SIO2, K_SIO2),
        "isolation": (K_SIO2, K_SIO2),
        "heater": (K_AL, K_AL),
        "clad": (K_SIO2, K_SIO2),
    }
    if extra_domains:
        domain_k.update(extra_domains)

    for domain, (kx, ky) in domain_k.items():
        try:
            dofs = basis0.get_dofs(elements=domain)
            kxx[dofs] = kx
            kyy[dofs] = ky
        except Exception:
            pass  # domain may not exist in this geometry

    kxx *= 1e-12
    kyy *= 1e-12
    return kxx, kyy


def setup_epsilon_ext(basis0, temperature_p0=None, extra_domains=None):
    """Set up permittivity field with optional extra domains.

    Args:
        basis0: P0 basis.
        temperature_p0: Temperature field on P0 basis (optional).
        extra_domains: dict mapping domain name -> (n0, dn_dt).
                       e.g. {"trench_left": (N_AIR, 0.0)}

    Returns:
        epsilon array on P0 basis.
    """
    epsilon = basis0.zeros()

    if temperature_p0 is not None:
        dT = temperature_p0 - T_AMB
    else:
        dT = basis0.zeros()

    domain_eps = {
        "core": (N_LN, DN_DT_LN),
        "slab": (N_LN, DN_DT_LN),
        "box": (N_SIO2, DN_DT_SIO2),
        "isolation": (N_SIO2, DN_DT_SIO2),
        "heater": (N_SIO2, DN_DT_SIO2),
        "clad": (N_SIO2, DN_DT_SIO2),
    }
    if extra_domains:
        domain_eps.update(extra_domains)

    for domain, (n0, dndt) in domain_eps.items():
        try:
            dofs = basis0.get_dofs(elements=domain)
            epsilon[dofs] = (n0 + dndt * dT[dofs]) ** 2
        except Exception:
            pass

    return epsilon


# =============================================================================
# Single-Voltage Solver
# =============================================================================
def run_single_voltage_solve(polygons, mesh, alpha_eff, V=10.0,
                             extra_domains_k=None, extra_domains_eps=None):
    """Run one thermal + optical solve at a single voltage.

    Args:
        polygons: Geometry OrderedDict (must contain 'heater').
        mesh: skfem mesh.
        alpha_eff: Out-of-plane heat loss coefficient (W/um^3/K).
        V: Applied voltage (V).
        extra_domains_k: Extra thermal conductivity domains.
        extra_domains_eps: Extra permittivity domains.

    Returns:
        dict with: T_core, dT_core, T_max, neff_0, neff_hot, delta_neff,
                   delta_lambda_nm, power_W, power_mW, tuning_eff_pm_per_mW.
    """
    basis0 = Basis(mesh, ElementTriP0(), intorder=4)
    kxx, kyy = setup_thermal_conductivity_ext(basis0, extra_domains_k)

    A_heater = polygons["heater"].area
    I = V / R_TOTAL
    J = I / A_heater
    P = V * I  # Watts

    # Baseline neff at ambient
    epsilon_0 = setup_epsilon_ext(basis0, extra_domains=extra_domains_eps)
    modes_0 = compute_modes(basis0, epsilon_0, wavelength=WAVELENGTH, num_modes=1)
    neff_0 = np.real(modes_0[0].n_eff)

    # Thermal solve
    basis_t, temp = solve_thermal_2p5d(
        basis0, kxx, kyy, alpha_eff,
        specific_conductivity={"heater": SIGMA_AL},
        current_densities={"heater": J},
        fixed_boundaries={"bottom": T_AMB},
    )

    # Project temperature to P0
    temp_p0 = basis0.project(basis_t.interpolate(temp))
    T_core = np.mean(temp_p0[basis0.get_dofs(elements="core")])
    T_max = np.max(temp)
    dT_core = T_core - T_AMB

    # Hot neff
    epsilon_hot = setup_epsilon_ext(basis0, temp_p0, extra_domains_eps)
    modes_hot = compute_modes(basis0, epsilon_hot, wavelength=WAVELENGTH, num_modes=1)
    neff_hot = np.real(modes_hot[0].n_eff)

    delta_neff = neff_hot - neff_0
    delta_lambda_nm = (delta_neff / N_GROUP) * WAVELENGTH * 1e3  # nm

    power_mW = P * 1e3
    tuning_eff = delta_lambda_nm * 1e3 / power_mW if power_mW > 0 else 0.0  # pm/mW

    return {
        "T_core": T_core,
        "dT_core": dT_core,
        "T_max": T_max,
        "neff_0": neff_0,
        "neff_hot": neff_hot,
        "delta_neff": delta_neff,
        "delta_lambda_nm": delta_lambda_nm,
        "power_W": P,
        "power_mW": power_mW,
        "tuning_eff_pm_per_mW": tuning_eff,
    }


# =============================================================================
# Sweep Functions
# =============================================================================
def sweep_isolation_thickness(alpha_eff):
    """Sweep 1: Vary isolation layer thickness (heater-to-waveguide distance)."""
    h_iso_values = [0.5, 0.75, 1.0, 1.25, 1.5, 1.75, 2.0]
    results = []

    print("\n" + "=" * 60)
    print("SWEEP 1: Isolation Thickness")
    print("=" * 60)
    print(f"  Values: {h_iso_values} um")
    print(f"  V = 10V, R = {R_TOTAL} Ω, P = {10**2/R_TOTAL*1e3:.0f} mW")
    print()

    for h_iso in h_iso_values:
        t0 = time.time()
        print(f"  h_iso = {h_iso:.2f} um ... ", end="", flush=True)

        polygons = build_vertical_geometry_param(h_isolation=h_iso)
        mesh = build_mesh_sweep(polygons)
        r = run_single_voltage_solve(polygons, mesh, alpha_eff)
        r["h_isolation"] = h_iso

        dt = time.time() - t0
        print(f"dT={r['dT_core']:.1f}K  Δneff={r['delta_neff']:.6f}  "
              f"Δλ={r['delta_lambda_nm']:.3f}nm  η={r['tuning_eff_pm_per_mW']:.2f}pm/mW  "
              f"({dt:.1f}s)")
        results.append(r)

    print_sweep_table("Isolation Thickness", "h_iso (um)",
                      [r["h_isolation"] for r in results], results)
    return h_iso_values, results


def sweep_electrode_width(alpha_eff):
    """Sweep 2: Vary electrode (heater) width."""
    w_al_values = [1.0, 1.5, 2.0, 3.0, 4.0, 5.0, 6.0]
    results = []

    print("\n" + "=" * 60)
    print("SWEEP 2: Electrode Width")
    print("=" * 60)
    print(f"  Values: {w_al_values} um")
    print(f"  V = 10V, R = {R_TOTAL} Ω (external), P = {10**2/R_TOTAL*1e3:.0f} mW")
    print()

    for w_al in w_al_values:
        t0 = time.time()
        print(f"  w_al = {w_al:.1f} um ... ", end="", flush=True)

        polygons = build_vertical_geometry_param(w_al=w_al)
        mesh = build_mesh_sweep(polygons)
        r = run_single_voltage_solve(polygons, mesh, alpha_eff)
        r["w_al"] = w_al

        dt = time.time() - t0
        print(f"dT={r['dT_core']:.1f}K  Δneff={r['delta_neff']:.6f}  "
              f"Δλ={r['delta_lambda_nm']:.3f}nm  η={r['tuning_eff_pm_per_mW']:.2f}pm/mW  "
              f"({dt:.1f}s)")
        results.append(r)

    print_sweep_table("Electrode Width", "w_al (um)",
                      [r["w_al"] for r in results], results)
    return w_al_values, results


def sweep_air_trench(alpha_eff):
    """Sweep 3: Vary air trench width (lateral thermal isolation)."""
    w_trench_values = [0, 0.5, 1.0, 1.5, 2.0, 2.5, 3.0]
    d_trench = 1.5  # fixed depth
    results = []

    # Extra domain properties for trenches
    extra_k = {
        "trench_left": (K_AIR, K_AIR),
        "trench_right": (K_AIR, K_AIR),
    }
    extra_eps = {
        "trench_left": (N_AIR, 0.0),
        "trench_right": (N_AIR, 0.0),
    }

    print("\n" + "=" * 60)
    print("SWEEP 3: Air Trench Width")
    print("=" * 60)
    print(f"  Width values: {w_trench_values} um")
    print(f"  Trench depth: {d_trench} um (fixed)")
    print(f"  V = 10V, R = {R_TOTAL} Ω, P = {10**2/R_TOTAL*1e3:.0f} mW")
    print()

    for w_trench in w_trench_values:
        t0 = time.time()
        print(f"  w_trench = {w_trench:.1f} um ... ", end="", flush=True)

        polygons = build_trench_geometry(w_trench, d_trench=d_trench)
        mesh = build_mesh_sweep(polygons)

        # Only pass extra domains when trenches exist
        ek = extra_k if w_trench > 0 else None
        ee = extra_eps if w_trench > 0 else None

        r = run_single_voltage_solve(polygons, mesh, alpha_eff,
                                     extra_domains_k=ek, extra_domains_eps=ee)
        r["w_trench"] = w_trench

        dt = time.time() - t0
        print(f"dT={r['dT_core']:.1f}K  Δneff={r['delta_neff']:.6f}  "
              f"Δλ={r['delta_lambda_nm']:.3f}nm  η={r['tuning_eff_pm_per_mW']:.2f}pm/mW  "
              f"({dt:.1f}s)")
        results.append(r)

    print_sweep_table("Air Trench Width", "w_trench (um)",
                      [r["w_trench"] for r in results], results)
    return w_trench_values, results


def sweep_box_thickness(alpha_eff, best_w_al=2.0, best_h_iso=0.5):
    """Sweep 4: Vary BOX (SiO2 substrate) thickness.

    Thicker BOX = more thermal resistance between waveguide and substrate
    heat sink -> higher dT at core -> better efficiency.
    """
    h_box_values = [1.0, 1.5, 2.0, 2.5, 3.0, 4.0]
    results = []

    print("\n" + "=" * 60)
    print("SWEEP 4: BOX Thickness")
    print("=" * 60)
    print(f"  Values: {h_box_values} um")
    print(f"  w_al = {best_w_al} um, h_iso = {best_h_iso} um (best from Phase 2)")
    print(f"  V = 10V, R = {R_TOTAL} Ohm, P = {10**2/R_TOTAL*1e3:.0f} mW")
    print()

    for h_box in h_box_values:
        t0 = time.time()
        print(f"  h_box = {h_box:.1f} um ... ", end="", flush=True)

        polygons = build_vertical_geometry_param(
            h_isolation=best_h_iso, w_al=best_w_al, h_substrate=h_box
        )
        mesh = build_mesh_sweep(polygons)
        r = run_single_voltage_solve(polygons, mesh, alpha_eff)
        r["h_box"] = h_box
        r = compute_constrained_metrics(r)

        dt = time.time() - t0
        print(f"dT={r['dT_core']:.1f}K  Δneff={r['delta_neff']:.6f}  "
              f"η={r['tuning_eff_pm_per_mW']:.2f}pm/mW  "
              f"T_max={r['T_max']:.0f}K  ({dt:.1f}s)")
        results.append(r)

    print_sweep_table("BOX Thickness", "h_box (um)",
                      [r["h_box"] for r in results], results)
    return h_box_values, results


def sweep_suspended(alpha_eff, best_w_al=2.0, best_h_iso=0.5):
    """Sweep 5: Vary undercut width (suspended structure).

    Removes SiO2 beneath waveguide, forcing heat to travel laterally
    through remaining BOX to reach substrate — dramatically increases
    thermal resistance in the vertical heat path.
    """
    w_undercut_values = [0, 4, 6, 8, 10, 12, 14]
    results = []

    # Extra domain properties for undercut and access trenches
    extra_k = {
        "undercut": (K_AIR, K_AIR),
        "trench_left": (K_AIR, K_AIR),
        "trench_right": (K_AIR, K_AIR),
    }
    extra_eps = {
        "undercut": (N_AIR, 0.0),
        "trench_left": (N_AIR, 0.0),
        "trench_right": (N_AIR, 0.0),
    }

    print("\n" + "=" * 60)
    print("SWEEP 5: Suspended Structure (Undercut Width)")
    print("=" * 60)
    print(f"  Values: {w_undercut_values} um")
    print(f"  w_al = {best_w_al} um, h_iso = {best_h_iso} um (best from Phase 2)")
    print(f"  V = 10V, R = {R_TOTAL} Ohm, P = {10**2/R_TOTAL*1e3:.0f} mW")
    print()

    for w_uc in w_undercut_values:
        t0 = time.time()
        print(f"  w_undercut = {w_uc:.0f} um ... ", end="", flush=True)

        polygons = build_suspended_geometry(
            w_undercut=w_uc, h_isolation=best_h_iso, w_al=best_w_al
        )
        mesh = build_mesh_sweep(polygons)

        # Only pass extra domains when undercut exists
        ek = extra_k if w_uc > 0 else None
        ee = extra_eps if w_uc > 0 else None

        r = run_single_voltage_solve(polygons, mesh, alpha_eff,
                                     extra_domains_k=ek, extra_domains_eps=ee)
        r["w_undercut"] = w_uc
        r = compute_constrained_metrics(r)

        dt = time.time() - t0
        print(f"dT={r['dT_core']:.1f}K  Δneff={r['delta_neff']:.6f}  "
              f"η={r['tuning_eff_pm_per_mW']:.2f}pm/mW  "
              f"T_max={r['T_max']:.0f}K  V_max={r['V_max']:.1f}V  ({dt:.1f}s)")
        results.append(r)

    print_sweep_table("Suspended (Undercut Width)", "w_uc (um)",
                      [r["w_undercut"] for r in results], results)
    return w_undercut_values, results


# =============================================================================
# Results Table
# =============================================================================
def print_sweep_table(title, param_name, param_values, results):
    """Print formatted results table for a sweep."""
    print(f"\n  {'─' * 78}")
    print(f"  {title} — Results Summary")
    print(f"  {'─' * 78}")
    print(f"  {param_name:>12}  {'dT_core(K)':>10}  {'Δneff':>10}  "
          f"{'Δλ(nm)':>8}  {'η(pm/mW)':>10}  {'neff_0':>10}  {'T_max(K)':>10}")
    print(f"  {'─' * 78}")

    best_idx = np.argmax([r["tuning_eff_pm_per_mW"] for r in results])
    for i, (pv, r) in enumerate(zip(param_values, results)):
        marker = " ← BEST" if i == best_idx else ""
        print(f"  {pv:>12.2f}  {r['dT_core']:>10.1f}  {r['delta_neff']:>10.6f}  "
              f"{r['delta_lambda_nm']:>8.3f}  {r['tuning_eff_pm_per_mW']:>10.2f}  "
              f"{r['neff_0']:>10.6f}  {r['T_max']:>10.1f}{marker}")

    print(f"  {'─' * 78}")
    best = results[best_idx]
    print(f"  Best: {param_name} = {param_values[best_idx]:.2f}  →  "
          f"η = {best['tuning_eff_pm_per_mW']:.2f} pm/mW  "
          f"(Δλ = {best['delta_lambda_nm']:.3f} nm)")
    print()


# =============================================================================
# Plotting
# =============================================================================
def plot_sweep(param_values, results, param_name, param_label, filename):
    """Plot 1x3 subplots: tuning efficiency, core ΔT, Δneff vs parameter."""
    fig, axes = plt.subplots(1, 3, figsize=(15, 4.5))

    eff = [r["tuning_eff_pm_per_mW"] for r in results]
    dT = [r["dT_core"] for r in results]
    dneff = [r["delta_neff"] for r in results]

    # Tuning efficiency
    ax = axes[0]
    ax.plot(param_values, eff, "b-o", markersize=6, linewidth=2)
    ax.set_xlabel(param_label)
    ax.set_ylabel("Tuning Efficiency (pm/mW)")
    ax.set_title("Tuning Efficiency")
    ax.grid(True, alpha=0.3)
    # Mark best point
    best_idx = np.argmax(eff)
    ax.plot(param_values[best_idx], eff[best_idx], "r*", markersize=14, zorder=5)
    ax.annotate(f"{eff[best_idx]:.2f}", (param_values[best_idx], eff[best_idx]),
                textcoords="offset points", xytext=(10, 5), fontsize=9, color="red")

    # Core temperature rise
    ax = axes[1]
    ax.plot(param_values, dT, "r-s", markersize=6, linewidth=2)
    ax.set_xlabel(param_label)
    ax.set_ylabel("Core ΔT (K)")
    ax.set_title("Core Temperature Rise")
    ax.grid(True, alpha=0.3)

    # Delta neff
    ax = axes[2]
    ax.plot(param_values, dneff, "g-^", markersize=6, linewidth=2)
    ax.set_xlabel(param_label)
    ax.set_ylabel("Δn_eff")
    ax.set_title("Effective Index Change")
    ax.grid(True, alpha=0.3)

    fig.suptitle(f"Sweep: {param_name} (V=10V, P=1W)", fontsize=13)
    plt.tight_layout()
    plt.savefig(f"/home/kumar/femwell/images/{filename}", dpi=200, bbox_inches="tight")
    plt.close()
    print(f"  Saved: {filename}")


def plot_comparison(sweep1, sweep2, sweep3):
    """Combined comparison plot of tuning efficiency from all 3 sweeps."""
    fig, ax = plt.subplots(figsize=(10, 6))

    params1, results1 = sweep1
    params2, results2 = sweep2
    params3, results3 = sweep3

    eff1 = [r["tuning_eff_pm_per_mW"] for r in results1]
    eff2 = [r["tuning_eff_pm_per_mW"] for r in results2]
    eff3 = [r["tuning_eff_pm_per_mW"] for r in results3]

    # Normalize x-axes to [0, 1] for comparison
    def normalize(vals):
        vals = np.array(vals, dtype=float)
        vmin, vmax = vals.min(), vals.max()
        if vmax > vmin:
            return (vals - vmin) / (vmax - vmin)
        return vals * 0

    ax.plot(normalize(params1), eff1, "b-o", markersize=6, linewidth=2,
            label=f"Isolation thickness ({params1[0]}–{params1[-1]} μm)")
    ax.plot(normalize(params2), eff2, "r-s", markersize=6, linewidth=2,
            label=f"Electrode width ({params2[0]}–{params2[-1]} μm)")
    ax.plot(normalize(params3), eff3, "g-^", markersize=6, linewidth=2,
            label=f"Air trench width ({params3[0]}–{params3[-1]} μm)")

    ax.set_xlabel("Normalized Parameter (0 = min, 1 = max)")
    ax.set_ylabel("Tuning Efficiency (pm/mW)")
    ax.set_title("Design Optimization: Tuning Efficiency Comparison")
    ax.legend(fontsize=10)
    ax.grid(True, alpha=0.3)

    # Add baseline reference line
    baseline_eff = eff1[params1.index(1.0)] if 1.0 in params1 else eff1[0]
    ax.axhline(baseline_eff, color="gray", linestyle="--", alpha=0.5,
               label=f"Baseline ({baseline_eff:.2f} pm/mW)")
    ax.legend(fontsize=10)

    plt.tight_layout()
    plt.savefig("/home/kumar/femwell/images/ln_sweep_comparison.png", dpi=200, bbox_inches="tight")
    plt.close()
    print("  Saved: ln_sweep_comparison.png")


# =============================================================================
# Thermally-Constrained 2D Optimization
# =============================================================================
T_MAX_LIMIT = 473.0  # K (200°C) — pure Al hillock formation limit (Martin et al. 1995)


def compute_constrained_metrics(r, V_sim=10.0):
    """Given results at V_sim, compute max voltage/power/shift within T_MAX_LIMIT.

    Since ΔT scales linearly with power (∝ V²), we can extrapolate:
        dT_max(V) = dT_max(V_sim) × (V/V_sim)²
        V_max = V_sim × sqrt(dT_limit / dT_max_sim)
    """
    dT_max_sim = r["T_max"] - T_AMB  # heater ΔT at simulation voltage
    dT_limit = T_MAX_LIMIT - T_AMB   # 223 K

    if dT_max_sim <= 0:
        return r

    if r["T_max"] <= T_MAX_LIMIT:
        # Already within limit at V_sim
        scale = 1.0
        V_max = V_sim
    else:
        # Must reduce voltage
        scale = dT_limit / dT_max_sim  # power scale factor < 1
        V_max = V_sim * np.sqrt(scale)

    P_max_W = V_max**2 / R_TOTAL
    P_max_mW = P_max_W * 1e3

    # Wavelength shift scales linearly with power
    delta_lambda_max_nm = r["delta_lambda_nm"] * scale
    dT_core_max = r["dT_core"] * scale

    r["V_max"] = V_max
    r["P_max_mW"] = P_max_mW
    r["delta_lambda_max_nm"] = delta_lambda_max_nm
    r["dT_core_at_limit"] = dT_core_max
    r["T_max_at_limit"] = T_AMB + (r["T_max"] - T_AMB) * scale
    r["power_scale"] = scale

    return r


def sweep_2d_constrained(alpha_eff):
    """2D sweep of (w_al × h_iso) with thermal constraint T_max ≤ 523K.

    For each geometry point:
    1. Solve at 10V to get efficiency (pm/mW) and T_max
    2. Compute max usable power within thermal budget
    3. Compute max achievable wavelength shift = efficiency × P_max
    """
    w_al_values = [1.5, 2.0, 2.5, 3.0, 4.0, 5.0]
    h_iso_values = [0.5, 0.75, 1.0, 1.25, 1.5]
    results_grid = {}

    print("\n" + "=" * 70)
    print("THERMALLY-CONSTRAINED 2D OPTIMIZATION")
    print(f"T_max limit: {T_MAX_LIMIT:.0f} K ({T_MAX_LIMIT - 273.15:.0f}°C)")
    print("=" * 70)
    print(f"  Electrode widths:      {w_al_values} um")
    print(f"  Isolation thicknesses: {h_iso_values} um")
    print(f"  Grid points: {len(w_al_values) * len(h_iso_values)}")
    print()

    for w_al in w_al_values:
        for h_iso in h_iso_values:
            t0 = time.time()
            label = f"w_al={w_al:.1f}, h_iso={h_iso:.2f}"
            print(f"  {label} ... ", end="", flush=True)

            polygons = build_vertical_geometry_param(h_isolation=h_iso, w_al=w_al)
            mesh = build_mesh_sweep(polygons)
            r = run_single_voltage_solve(polygons, mesh, alpha_eff)
            r["w_al"] = w_al
            r["h_isolation"] = h_iso
            r = compute_constrained_metrics(r)

            dt = time.time() - t0
            status = "OK" if r["T_max"] <= T_MAX_LIMIT else f"V_max={r['V_max']:.1f}V"
            print(f"η={r['tuning_eff_pm_per_mW']:.2f}pm/mW  "
                  f"T_max={r['T_max']:.0f}K  {status}  "
                  f"Δλ_max={r['delta_lambda_max_nm']:.3f}nm  ({dt:.1f}s)")

            results_grid[(w_al, h_iso)] = r

    # Print results table
    print(f"\n  {'─' * 95}")
    print(f"  Constrained Results (T_max ≤ {T_MAX_LIMIT:.0f}K)")
    print(f"  {'─' * 95}")
    print(f"  {'w_al':>5} {'h_iso':>6}  {'η(pm/mW)':>9}  {'T_max@10V':>9}  "
          f"{'V_max':>6}  {'P_max(mW)':>9}  {'Δλ_max(nm)':>10}  "
          f"{'dT_core':>7}  {'Feasible':>8}")
    print(f"  {'─' * 95}")

    best_key = None
    best_shift = 0
    for w_al in w_al_values:
        for h_iso in h_iso_values:
            r = results_grid[(w_al, h_iso)]
            feasible = "YES" if r["T_max"] <= T_MAX_LIMIT else "reduced"
            marker = ""
            if r["delta_lambda_max_nm"] > best_shift:
                best_shift = r["delta_lambda_max_nm"]
                best_key = (w_al, h_iso)
            print(f"  {w_al:>5.1f} {h_iso:>6.2f}  "
                  f"{r['tuning_eff_pm_per_mW']:>9.2f}  "
                  f"{r['T_max']:>9.0f}  "
                  f"{r['V_max']:>6.1f}  "
                  f"{r['P_max_mW']:>9.0f}  "
                  f"{r['delta_lambda_max_nm']:>10.3f}  "
                  f"{r['dT_core_at_limit']:>7.1f}  "
                  f"{feasible:>8}")
        print()  # gap between w_al groups

    print(f"  {'─' * 95}")
    best = results_grid[best_key]
    print(f"  BEST: w_al={best_key[0]:.1f}μm, h_iso={best_key[1]:.2f}μm")
    print(f"    Max Δλ = {best['delta_lambda_max_nm']:.3f} nm  "
          f"(at V_max={best['V_max']:.1f}V, P={best['P_max_mW']:.0f}mW)")
    print(f"    Efficiency = {best['tuning_eff_pm_per_mW']:.2f} pm/mW")
    print(f"    T_max at limit = {best['T_max_at_limit']:.0f}K")
    print()

    return w_al_values, h_iso_values, results_grid, best_key


def sweep_trench_on_best(alpha_eff, best_w_al, best_h_iso):
    """Try adding air trenches to the best 2D design to squeeze out more gain."""
    w_trench_values = [0, 0.5, 1.0, 1.5, 2.0, 3.0]
    d_trench = 1.5
    results = []

    extra_k = {"trench_left": (K_AIR, K_AIR), "trench_right": (K_AIR, K_AIR)}
    extra_eps = {"trench_left": (N_AIR, 0.0), "trench_right": (N_AIR, 0.0)}

    print(f"\n{'=' * 70}")
    print(f"AIR TRENCH ENHANCEMENT on best design (w_al={best_w_al}, h_iso={best_h_iso})")
    print(f"{'=' * 70}")

    for w_trench in w_trench_values:
        t0 = time.time()
        print(f"  w_trench = {w_trench:.1f} um ... ", end="", flush=True)

        polygons = build_trench_geometry(
            w_trench, d_trench=d_trench,
            h_isolation=best_h_iso, w_al=best_w_al,
        )
        mesh = build_mesh_sweep(polygons)
        ek = extra_k if w_trench > 0 else None
        ee = extra_eps if w_trench > 0 else None

        r = run_single_voltage_solve(polygons, mesh, alpha_eff,
                                     extra_domains_k=ek, extra_domains_eps=ee)
        r["w_trench"] = w_trench
        r = compute_constrained_metrics(r)

        dt = time.time() - t0
        print(f"η={r['tuning_eff_pm_per_mW']:.2f}pm/mW  "
              f"Δλ_max={r['delta_lambda_max_nm']:.3f}nm  "
              f"V_max={r['V_max']:.1f}V  ({dt:.1f}s)")
        results.append(r)

    # Table
    print(f"\n  {'─' * 80}")
    print(f"  Air Trench Enhancement — Results")
    print(f"  {'─' * 80}")
    print(f"  {'w_trench':>8}  {'η(pm/mW)':>9}  {'T_max@10V':>9}  "
          f"{'V_max':>6}  {'P_max(mW)':>9}  {'Δλ_max(nm)':>10}")
    print(f"  {'─' * 80}")

    best_idx = np.argmax([r["delta_lambda_max_nm"] for r in results])
    for i, r in enumerate(results):
        marker = " ← BEST" if i == best_idx else ""
        print(f"  {r['w_trench']:>8.1f}  "
              f"{r['tuning_eff_pm_per_mW']:>9.2f}  "
              f"{r['T_max']:>9.0f}  "
              f"{r['V_max']:>6.1f}  "
              f"{r['P_max_mW']:>9.0f}  "
              f"{r['delta_lambda_max_nm']:>10.3f}{marker}")
    print(f"  {'─' * 80}")

    return w_trench_values, results


def plot_sweep_constrained(param_values, results, param_name, param_label, filename):
    """Plot 1x3 subplots with thermal constraint annotation."""
    fig, axes = plt.subplots(1, 3, figsize=(15, 4.5))

    eff = [r["tuning_eff_pm_per_mW"] for r in results]
    dT = [r["dT_core"] for r in results]
    dneff = [r["delta_neff"] for r in results]
    t_max = [r["T_max"] for r in results]

    # Tuning efficiency
    ax = axes[0]
    ax.plot(param_values, eff, "b-o", markersize=6, linewidth=2)
    ax.set_xlabel(param_label)
    ax.set_ylabel("Tuning Efficiency (pm/mW)")
    ax.set_title("Tuning Efficiency")
    ax.grid(True, alpha=0.3)
    best_idx = np.argmax(eff)
    ax.plot(param_values[best_idx], eff[best_idx], "r*", markersize=14, zorder=5)
    ax.annotate(f"{eff[best_idx]:.2f}", (param_values[best_idx], eff[best_idx]),
                textcoords="offset points", xytext=(10, 5), fontsize=9, color="red")

    # Core temperature rise
    ax = axes[1]
    ax.plot(param_values, dT, "r-s", markersize=6, linewidth=2)
    ax.set_xlabel(param_label)
    ax.set_ylabel("Core dT (K)")
    ax.set_title("Core Temperature Rise")
    ax.grid(True, alpha=0.3)
    # Annotate T_max constraint
    for i, (pv, tm) in enumerate(zip(param_values, t_max)):
        if tm > T_MAX_LIMIT:
            ax.annotate(f"T_max={tm:.0f}K\n>limit",
                        (pv, dT[i]), textcoords="offset points",
                        xytext=(0, 10), fontsize=7, color="red", ha="center")

    # Delta neff
    ax = axes[2]
    ax.plot(param_values, dneff, "g-^", markersize=6, linewidth=2)
    ax.set_xlabel(param_label)
    ax.set_ylabel("dn_eff")
    ax.set_title("Effective Index Change")
    ax.grid(True, alpha=0.3)

    fig.suptitle(f"Sweep: {param_name} (V=10V, P=1W) — T_max limit={T_MAX_LIMIT:.0f}K",
                 fontsize=13)
    plt.tight_layout()
    plt.savefig(f"/home/kumar/femwell/images/{filename}", dpi=200, bbox_inches="tight")
    plt.close()
    print(f"  Saved: {filename}")


def plot_final_design_comparison(results_dict):
    """Bar chart comparing design stages: baseline -> electrode -> BOX -> suspended.

    Args:
        results_dict: OrderedDict of {label: result_dict} with constrained metrics.
    """
    labels = list(results_dict.keys())
    results_list = list(results_dict.values())

    fig, axes = plt.subplots(1, 3, figsize=(16, 5.5))
    colors = ["#4472C4", "#ED7D31", "#70AD47", "#FFC000"][:len(labels)]
    x = np.arange(len(labels))
    bar_width = 0.6

    # Tuning efficiency
    ax = axes[0]
    vals = [r["tuning_eff_pm_per_mW"] for r in results_list]
    bars = ax.bar(x, vals, bar_width, color=colors, edgecolor="black", linewidth=0.5)
    for bar, v in zip(bars, vals):
        ax.text(bar.get_x() + bar.get_width()/2, bar.get_height() + max(vals)*0.02,
                f"{v:.2f}", ha="center", va="bottom", fontsize=9, fontweight="bold")
    ax.set_xticks(x)
    ax.set_xticklabels(labels, fontsize=8, rotation=15, ha="right")
    ax.set_ylabel("pm/mW")
    ax.set_title("Tuning Efficiency")
    ax.grid(True, alpha=0.2, axis="y")

    # Max wavelength shift (within thermal budget)
    ax = axes[1]
    vals = [r["delta_lambda_max_nm"] for r in results_list]
    bars = ax.bar(x, vals, bar_width, color=colors, edgecolor="black", linewidth=0.5)
    for bar, v in zip(bars, vals):
        ax.text(bar.get_x() + bar.get_width()/2, bar.get_height() + max(vals)*0.02,
                f"{v:.3f}", ha="center", va="bottom", fontsize=9, fontweight="bold")
    ax.set_xticks(x)
    ax.set_xticklabels(labels, fontsize=8, rotation=15, ha="right")
    ax.set_ylabel("nm")
    ax.set_title(f"Max wavelength shift (T_max<={T_MAX_LIMIT:.0f}K)")
    ax.grid(True, alpha=0.2, axis="y")

    # Max voltage
    ax = axes[2]
    vals = [r["V_max"] for r in results_list]
    bars = ax.bar(x, vals, bar_width, color=colors, edgecolor="black", linewidth=0.5)
    for bar, v in zip(bars, vals):
        ax.text(bar.get_x() + bar.get_width()/2, bar.get_height() + max(vals)*0.02,
                f"{v:.1f}V", ha="center", va="bottom", fontsize=9, fontweight="bold")
    ax.set_xticks(x)
    ax.set_xticklabels(labels, fontsize=8, rotation=15, ha="right")
    ax.set_ylabel("V")
    ax.set_title("Max Operating Voltage")
    ax.grid(True, alpha=0.2, axis="y")

    fig.suptitle("Design Progression — Thermally Constrained", fontsize=13)
    plt.tight_layout()
    plt.savefig("/home/kumar/femwell/images/ln_final_design_comparison.png",
                dpi=200, bbox_inches="tight")
    plt.close()
    print("  Saved: ln_final_design_comparison.png")


def plot_2d_constrained(w_al_values, h_iso_values, results_grid, best_key):
    """Plot 2D heatmaps: efficiency, max shift, and max power."""
    nw = len(w_al_values)
    nh = len(h_iso_values)

    eff_map = np.zeros((nw, nh))
    shift_map = np.zeros((nw, nh))
    vmax_map = np.zeros((nw, nh))

    for i, w in enumerate(w_al_values):
        for j, h in enumerate(h_iso_values):
            r = results_grid[(w, h)]
            eff_map[i, j] = r["tuning_eff_pm_per_mW"]
            shift_map[i, j] = r["delta_lambda_max_nm"]
            vmax_map[i, j] = r["V_max"]

    fig, axes = plt.subplots(1, 3, figsize=(18, 5))

    for ax, data, title, cmap, label in [
        (axes[0], eff_map, "Tuning Efficiency", "viridis", "pm/mW"),
        (axes[1], shift_map, f"Max Δλ (T_max≤{T_MAX_LIMIT:.0f}K)", "inferno", "nm"),
        (axes[2], vmax_map, f"Max Voltage (T_max≤{T_MAX_LIMIT:.0f}K)", "coolwarm", "V"),
    ]:
        im = ax.imshow(data, origin="lower", aspect="auto", cmap=cmap,
                       extent=[h_iso_values[0], h_iso_values[-1],
                               w_al_values[0], w_al_values[-1]])
        cb = fig.colorbar(im, ax=ax)
        cb.set_label(label)
        ax.set_xlabel("Isolation Thickness (μm)")
        ax.set_ylabel("Electrode Width (μm)")
        ax.set_title(title)

        # Mark best point
        ax.plot(best_key[1], best_key[0], "r*", markersize=18, markeredgecolor="white",
                markeredgewidth=1.5)

        # Annotate cells
        for i, w in enumerate(w_al_values):
            for j, h in enumerate(h_iso_values):
                val = data[i, j]
                ax.text(h, w, f"{val:.2f}", ha="center", va="center",
                        fontsize=7, color="white" if val < np.median(data) else "black")

    fig.suptitle(f"Thermally-Constrained Design Space (T_max ≤ {T_MAX_LIMIT:.0f}K = "
                 f"{T_MAX_LIMIT-273.15:.0f}°C)", fontsize=13)
    plt.tight_layout()
    plt.savefig("/home/kumar/femwell/images/ln_constrained_2d_optimization.png",
                dpi=200, bbox_inches="tight")
    plt.close()
    print("  Saved: ln_constrained_2d_optimization.png")


def plot_final_comparison(baseline_r, best_2d_r, best_trench_r,
                          best_2d_label, best_trench_label):
    """Bar chart comparing baseline vs best 2D vs best 2D+trench designs."""
    fig, axes = plt.subplots(1, 3, figsize=(15, 5))

    designs = ["Baseline\n(paper)", best_2d_label, best_trench_label]
    colors = ["#4472C4", "#ED7D31", "#70AD47"]

    # Tuning efficiency
    ax = axes[0]
    vals = [baseline_r["tuning_eff_pm_per_mW"],
            best_2d_r["tuning_eff_pm_per_mW"],
            best_trench_r["tuning_eff_pm_per_mW"]]
    bars = ax.bar(designs, vals, color=colors, edgecolor="black", linewidth=0.5)
    for bar, v in zip(bars, vals):
        ax.text(bar.get_x() + bar.get_width()/2, bar.get_height() + 0.02,
                f"{v:.2f}", ha="center", va="bottom", fontsize=10, fontweight="bold")
    ax.set_ylabel("pm/mW")
    ax.set_title("Tuning Efficiency")
    ax.grid(True, alpha=0.2, axis="y")

    # Max achievable shift (within thermal budget)
    ax = axes[1]
    vals = [baseline_r["delta_lambda_max_nm"],
            best_2d_r["delta_lambda_max_nm"],
            best_trench_r["delta_lambda_max_nm"]]
    bars = ax.bar(designs, vals, color=colors, edgecolor="black", linewidth=0.5)
    for bar, v in zip(bars, vals):
        ax.text(bar.get_x() + bar.get_width()/2, bar.get_height() + 0.01,
                f"{v:.3f}", ha="center", va="bottom", fontsize=10, fontweight="bold")
    ax.set_ylabel("nm")
    ax.set_title(f"Max Δλ (T_max ≤ {T_MAX_LIMIT:.0f}K)")
    ax.grid(True, alpha=0.2, axis="y")

    # Max voltage
    ax = axes[2]
    vals = [baseline_r["V_max"], best_2d_r["V_max"], best_trench_r["V_max"]]
    bars = ax.bar(designs, vals, color=colors, edgecolor="black", linewidth=0.5)
    for bar, v in zip(bars, vals):
        ax.text(bar.get_x() + bar.get_width()/2, bar.get_height() + 0.1,
                f"{v:.1f}V", ha="center", va="bottom", fontsize=10, fontweight="bold")
    ax.set_ylabel("V")
    ax.set_title("Max Operating Voltage")
    ax.grid(True, alpha=0.2, axis="y")

    fig.suptitle("Design Comparison — Thermally Constrained", fontsize=13)
    plt.tight_layout()
    plt.savefig("/home/kumar/femwell/images/ln_constrained_comparison.png",
                dpi=200, bbox_inches="tight")
    plt.close()
    print("  Saved: ln_constrained_comparison.png")


# =============================================================================
# Heat Flow Validation
# =============================================================================
def validate_heat_flow_paths(alpha_eff):
    """Visualize temperature fields & heat flux for 3 key designs.

    Validates that the dominant heat loss is downward through BOX, and that
    the suspended structure blocks this path.
    """
    print("\n" + "=" * 70)
    print("HEAT FLOW PATH VALIDATION (FEM)")
    print("=" * 70)

    cases = [
        ("Baseline (paper)\nw_al=3, h_iso=1",
         build_vertical_geometry_param(h_isolation=1.0, w_al=3.0),
         None, 2.0),
        ("Optimized electrode\nw_al=1.5, h_iso=0.5",
         build_vertical_geometry_param(h_isolation=0.5, w_al=1.5),
         None, 2.0),
        ("Suspended (w_uc=14)\nw_al=1.5, h_iso=0.5",
         build_suspended_geometry(w_undercut=14, h_isolation=0.5, w_al=1.5),
         {"undercut": (K_AIR, K_AIR),
          "trench_left": (K_AIR, K_AIR),
          "trench_right": (K_AIR, K_AIR)},
         2.0),
    ]

    V = 10.0

    solved = []
    for label, polygons, extra_k, h_sub in cases:
        t0 = time.time()
        print(f"  Solving: {label.split(chr(10))[0]} ... ", end="", flush=True)

        mesh = build_mesh_sweep(polygons)
        basis0 = Basis(mesh, ElementTriP0(), intorder=4)
        kxx, kyy = setup_thermal_conductivity_ext(basis0, extra_k)

        A_heater = polygons["heater"].area
        J = (V / R_TOTAL) / A_heater

        basis_t, temp = solve_thermal_2p5d(
            basis0, kxx, kyy, alpha_eff,
            specific_conductivity={"heater": SIGMA_AL},
            current_densities={"heater": J},
            fixed_boundaries={"bottom": T_AMB},
        )

        p = mesh.p
        t_conn = mesh.t

        # Per-element temperature gradient (constant per P1 triangle)
        x1, y1 = p[0, t_conn[0]], p[1, t_conn[0]]
        x2, y2 = p[0, t_conn[1]], p[1, t_conn[1]]
        x3, y3 = p[0, t_conn[2]], p[1, t_conn[2]]
        T1, T2, T3 = temp[t_conn[0]], temp[t_conn[1]], temp[t_conn[2]]

        det = (x2 - x1) * (y3 - y1) - (x3 - x1) * (y2 - y1)
        dTdx = ((T2 - T1) * (y3 - y1) - (T3 - T1) * (y2 - y1)) / det
        dTdy = ((x2 - x1) * (T3 - T1) - (x3 - x1) * (T2 - T1)) / det

        # Heat flux q = -k * grad(T)
        qx = -kxx * dTdx
        qy = -kyy * dTdy

        # Element centroids & areas
        cx = (x1 + x2 + x3) / 3
        cy = (y1 + y2 + y3) / 3
        elem_areas = 0.5 * np.abs(det)

        # Out-of-plane loss (proportional to local dT)
        T_elem = (T1 + T2 + T3) / 3.0
        dT_elem = T_elem - T_AMB
        P_oop = float(alpha_eff) * np.sum(dT_elem * elem_areas)

        # Vertical temperature profile at x=0
        x_tol = 0.15
        center_mask = np.abs(p[0]) < x_tol
        y_center = p[1, center_mask]
        T_center = temp[center_mask]
        sort_idx = np.argsort(y_center)
        y_center = y_center[sort_idx]
        T_center = T_center[sort_idx]

        dt_elapsed = time.time() - t0
        print(f"T_max={np.max(temp):.0f}K ({dt_elapsed:.1f}s)")

        solved.append({
            "label": label, "mesh": mesh, "temp": temp,
            "qx": qx, "qy": qy, "cx": cx, "cy": cy,
            "y_center": y_center, "T_center": T_center,
            "P_oop": P_oop, "T_max": np.max(temp),
            "h_sub": h_sub,
        })

    # ── Figure: 2x3 grid ──
    # Top: temperature contour maps with heat flux arrows
    # Bottom: vertical temperature profile at x=0
    fig, axes = plt.subplots(2, 3, figsize=(20, 12))

    dT_max_global = max(d["T_max"] for d in solved) - T_AMB
    levels_fill = np.linspace(0, dT_max_global, 60)
    levels_line = np.linspace(0, dT_max_global, 20)

    for col, data in enumerate(solved):
        mesh = data["mesh"]
        dT = data["temp"] - T_AMB

        # ── Top row: 2D temperature field ──
        ax = axes[0, col]
        tc = ax.tricontourf(
            mesh.p[0], mesh.p[1], mesh.t.T, dT,
            levels=levels_fill, cmap="hot", extend="both",
        )
        ax.tricontour(
            mesh.p[0], mesh.p[1], mesh.t.T, dT,
            levels=levels_line, colors="white", linewidths=0.3, alpha=0.5,
        )

        # Heat flux arrows (subsampled)
        n_arrows = 300
        step = max(1, len(data["cx"]) // n_arrows)
        idx = np.arange(0, len(data["cx"]), step)
        q_mag = np.sqrt(data["qx"]**2 + data["qy"]**2)
        q_scale = np.max(q_mag[idx]) * 12 if len(idx) > 0 else 1
        ax.quiver(
            data["cx"][idx], data["cy"][idx],
            data["qx"][idx], data["qy"][idx],
            color="cyan", alpha=0.5, scale=q_scale,
            width=0.003, headwidth=3,
        )

        # Mark key layer boundaries
        h_sub = data["h_sub"]
        for y_line, lbl in [
            (h_sub, "BOX top"),
            (h_sub + H_LN, "LN top"),
        ]:
            ax.axhline(y_line, color="lime", linewidth=0.8, linestyle="--", alpha=0.6)
            ax.text(W_SIM / 2 - 0.2, y_line + 0.05, lbl,
                    fontsize=7, color="lime", ha="right", va="bottom")

        ax.set_xlabel("x (um)")
        ax.set_ylabel("y (um)")
        ax.set_title(data["label"], fontsize=10)
        ax.set_aspect("equal")
        ax.set_xlim(-W_SIM / 2, W_SIM / 2)

        if col == 2:
            cb = fig.colorbar(tc, ax=axes[0, :].tolist(), shrink=0.85,
                              pad=0.02, aspect=30)
            cb.set_label("dT (K)")

        # ── Bottom row: vertical temperature profile ──
        ax = axes[1, col]
        ax.plot(data["y_center"], data["T_center"] - T_AMB,
                "r-", linewidth=2, label="dT at x=0")
        ax.set_xlabel("y (um)")
        ax.set_ylabel("dT (K)")
        ax.set_title(
            f"Vertical profile at x=0\nT_max = {data['T_max']:.0f}K",
            fontsize=10,
        )
        ax.grid(True, alpha=0.3)
        ax.set_ylim(0, dT_max_global * 1.05)

        # Shade key regions
        ax.axvspan(0, h_sub, alpha=0.08, color="blue", label="BOX (SiO2)")
        ax.axvspan(h_sub, h_sub + H_LN, alpha=0.08, color="orange", label="LN")
        ax.legend(fontsize=7, loc="upper left")

    fig.suptitle(
        "Heat Flow Validation: Temperature Fields & Vertical Profiles (V=10V)",
        fontsize=14,
    )
    plt.tight_layout()
    plt.savefig("/home/kumar/femwell/images/ln_heat_flow_validation.png",
                dpi=200, bbox_inches="tight")
    plt.close()
    print("  Saved: ln_heat_flow_validation.png")

    # ── Energy balance table ──
    print(f"\n  {'─' * 70}")
    print(f"  Heat Flow Analysis")
    print(f"  {'─' * 70}")
    P_oop_baseline = solved[0]["P_oop"]
    print(f"  {'Design':<35} {'T_max(K)':>9} {'P_oop(rel)':>10} {'Interpretation':>20}")
    print(f"  {'─' * 70}")
    for d in solved:
        ratio = d["P_oop"] / P_oop_baseline
        lbl = d["label"].split("\n")[0]
        # Higher P_oop = more heat retained = higher dT = less going to bottom
        pct_retained = (1 - 1 / ratio) * 100 if ratio > 1 else 0
        interp = f"+{pct_retained:.0f}% retained" if ratio > 1 else "reference"
        print(f"  {lbl:<35} {d['T_max']:>9.0f} {ratio:>10.1f}x {interp:>20}")

    print(f"  {'─' * 70}")
    print(f"  P_oop ~ integral(dT) over cross-section: higher = more heat trapped")
    print(f"  Suspended design traps {solved[2]['P_oop']/solved[0]['P_oop']:.1f}x more"
          f" heat than baseline")
    print()


# =============================================================================
# Main
# =============================================================================
def main():
    t_start = time.time()

    print("=" * 70)
    print("LN MZI Design Optimization — Thermally Constrained")
    print(f"T_max limit: {T_MAX_LIMIT:.0f} K ({T_MAX_LIMIT - 273.15:.0f}°C)")
    print("=" * 70)

    print("\n--- Computing alpha_eff ---")
    alpha_eff = compute_alpha_eff()

    # ─── Phase 1: Unconstrained 1D sweeps (for reference) ───
    print("\n" + "=" * 70)
    print("PHASE 1: Unconstrained 1D Sweeps (reference)")
    print("=" * 70)

    params1, results1 = sweep_isolation_thickness(alpha_eff)
    params2, results2 = sweep_electrode_width(alpha_eff)
    params3, results3 = sweep_air_trench(alpha_eff)

    # Add constrained metrics to all 1D results
    for r in results1 + results2 + results3:
        compute_constrained_metrics(r)

    # ─── Phase 2: Constrained 2D optimization ───
    print("\n" + "=" * 70)
    print("PHASE 2: Thermally-Constrained 2D Optimization")
    print("=" * 70)

    w_al_vals, h_iso_vals, grid, best_key = sweep_2d_constrained(alpha_eff)

    # ─── Phase 2b: Air trench enhancement on best 2D point ───
    best_2d = grid[best_key]
    wt_vals, trench_results = sweep_trench_on_best(
        alpha_eff, best_key[0], best_key[1]
    )

    best_trench_idx = np.argmax([r["delta_lambda_max_nm"] for r in trench_results])
    best_trench_r = trench_results[best_trench_idx]
    best_trench_wt = wt_vals[best_trench_idx]

    # ─── Phase 3: Vertical heat path optimization ───
    print("\n" + "=" * 70)
    print("PHASE 3: Vertical Heat Path Optimization")
    print("=" * 70)

    params4, results4 = sweep_box_thickness(
        alpha_eff, best_w_al=best_key[0], best_h_iso=best_key[1]
    )
    params5, results5 = sweep_suspended(
        alpha_eff, best_w_al=best_key[0], best_h_iso=best_key[1]
    )

    # Find best BOX thickness
    best_box_idx = np.argmax([r["tuning_eff_pm_per_mW"] for r in results4])
    best_box_r = results4[best_box_idx]
    best_h_box = params4[best_box_idx]

    # Find best suspended design
    best_susp_idx = np.argmax([r["tuning_eff_pm_per_mW"] for r in results5])
    best_susp_r = results5[best_susp_idx]
    best_w_uc = params5[best_susp_idx]

    # ─── Heat flow validation ───
    validate_heat_flow_paths(alpha_eff)

    # ─── Plots ───
    print("\n" + "=" * 70)
    print("Generating plots")
    print("=" * 70)

    # Phase 1 sweep plots
    plot_sweep(params1, results1, "Isolation Thickness",
               "Isolation Thickness (μm)", "ln_sweep1_isolation_thickness.png")
    plot_sweep(params2, results2, "Electrode Width",
               "Electrode Width (μm)", "ln_sweep2_electrode_width.png")
    plot_sweep(params3, results3, "Air Trench Width",
               "Air Trench Width (μm)", "ln_sweep3_air_trench.png")
    plot_comparison((params1, results1), (params2, results2), (params3, results3))

    # 2D constrained heatmap
    plot_2d_constrained(w_al_vals, h_iso_vals, grid, best_key)

    # Phase 2b comparison (baseline vs best_2d vs best_2d+trench)
    baseline_key = (3.0, 1.0)
    baseline_r = grid.get(baseline_key)
    if baseline_r is None:
        print("  Computing baseline point...")
        polygons = build_vertical_geometry_param(h_isolation=1.0, w_al=3.0)
        mesh = build_mesh_sweep(polygons)
        baseline_r = run_single_voltage_solve(polygons, mesh, alpha_eff)
        baseline_r["w_al"] = 3.0
        baseline_r["h_isolation"] = 1.0
        compute_constrained_metrics(baseline_r)

    best_2d_label = f"Optimized\nw={best_key[0]}um\nh={best_key[1]}um"
    best_trench_label = (f"Optimized+trench\nw={best_key[0]}um, h={best_key[1]}um\n"
                         f"trench={best_trench_wt}um")

    plot_final_comparison(baseline_r, best_2d, best_trench_r,
                          best_2d_label, best_trench_label)

    # Phase 3 sweep plots
    plot_sweep_constrained(params4, results4, "BOX Thickness",
                           "BOX Thickness (um)", "ln_sweep4_box_thickness.png")
    plot_sweep_constrained(params5, results5, "Suspended Structure",
                           "Undercut Width (um)", "ln_sweep5_suspended.png")

    # Final design comparison bar chart (4 stages)
    comparison_designs = OrderedDict()
    comparison_designs["Baseline\n(paper)"] = baseline_r
    comparison_designs[f"Best electrode\nw={best_key[0]},h={best_key[1]}"] = best_2d
    comparison_designs[f"+ thick BOX\nh_box={best_h_box}"] = best_box_r
    comparison_designs[f"Suspended\nw_uc={best_w_uc}"] = best_susp_r
    plot_final_design_comparison(comparison_designs)

    # ─── Final Summary ───
    elapsed = time.time() - t_start
    print(f"\n{'=' * 70}")
    print(f"FINAL SUMMARY")
    print(f"{'=' * 70}")
    print(f"Thermal constraint: T_max <= {T_MAX_LIMIT:.0f}K ({T_MAX_LIMIT-273.15:.0f}C)")
    print()

    print(f"  {'Design':<40} {'eta(pm/mW)':>10} {'V_max':>6} {'P_max':>7} "
          f"{'dL_max':>8} {'T_max@10V':>10} {'Improvement':>11}")
    print(f"  {'─' * 100}")

    bl_shift = baseline_r["delta_lambda_max_nm"]

    summary_rows = [
        ("Baseline (paper: w=3, h=1)", baseline_r),
        (f"Best electrode (w={best_key[0]}, h={best_key[1]})", best_2d),
        (f"Best electrode+trench (t={best_trench_wt})", best_trench_r),
        (f"Thick BOX (h_box={best_h_box})", best_box_r),
        (f"Suspended (w_uc={best_w_uc})", best_susp_r),
    ]

    for label, r in summary_rows:
        improvement = (r["delta_lambda_max_nm"] / bl_shift - 1) * 100 if bl_shift > 0 else 0
        sign = "+" if improvement >= 0 else ""
        eff_improvement = (r["tuning_eff_pm_per_mW"] / baseline_r["tuning_eff_pm_per_mW"] - 1) * 100
        eff_sign = "+" if eff_improvement >= 0 else ""
        print(f"  {label:<40} {r['tuning_eff_pm_per_mW']:>10.2f} "
              f"{r['V_max']:>5.1f}V {r['P_max_mW']:>6.0f}mW "
              f"{r['delta_lambda_max_nm']:>7.3f}nm  "
              f"{r['T_max']:>9.0f}K  "
              f"eta:{eff_sign}{eff_improvement:.0f}%")

    print(f"  {'─' * 100}")
    print(f"\n  Total time: {elapsed:.0f}s ({elapsed/60:.1f} min)")
    print(f"  All plots saved to /home/kumar/femwell/images/")


if __name__ == "__main__":
    main()
